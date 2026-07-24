"""
Query routing strategy: decides whether a chatbot question needs
SQL-style aggregation (via CaseRepository) or semantic/RAG search
(via ChromaDB) -- the exact fork flagged when we first planned the
chatbot. Two questions like "which district has the most thefts" vs
"tell me about cases involving a stolen motorbike near a bus stand"
need fundamentally different retrieval, not just different phrasing.

This is intentionally a simple keyword-heuristic classifier for the
MVP, not an LLM-based classifier -- cheaper, faster, and good enough
for a datathon demo. Swap for an LLM-based classifier later if the
heuristic misses too often.
"""
import re
from abc import ABC, abstractmethod
from typing import Any

from api.services.response_cache import cached_or_compute
from domain.interfaces.case_repository import CaseRepository
from api.middleware.auth import OfficerContext

AGGREGATE_KEYWORDS = [
    "how many", "count", "most", "least", "highest", "lowest", "trend",
    "compare", "average", "total", "which district", "over time",
    "increase", "decrease", "rate", "statistics", "stats", "breakdown",
]

# Questions asking to enumerate specific people, not aggregate stats.
# Checked BEFORE the aggregate keywords below, since phrases like
# "list all" or "how many criminals are there" could otherwise get
# mis-routed to the district/crime-type SQL summary, which has no
# person-level data in it at all.
ENTITY_LIST_KEYWORDS = [
    "list all", "list the", "criminals", "accused", "offenders",
    "suspects", "who are the", "show me all",
]


class QueryStrategy(ABC):
    @abstractmethod
    def build_context(self, query: str, repo: CaseRepository, officer: OfficerContext | None = None) -> tuple[str, list[dict] | None]:
        """Return (context_text, citations). context_text feeds into the
        LLM prompt as before. citations is None for strategies with no
        discrete, document-level sources -- SQL aggregates and entity
        lists aren't "citable documents" in the same sense a specific
        case record is. Only SemanticSearchStrategy returns a real
        citations list, built from ChromaDB's ids/metadatas."""
        ...


class SQLQueryStrategy(QueryStrategy):
    """For aggregate/statistical questions -- pulls structured summaries
    from the repository rather than individual case text.

    Routed through the same response cache the /analytics/* routes use
    (api/services/response_cache.py), and deliberately with the SAME
    cache keys those routes use for the equivalent unfiltered query --
    so a chat question and a Trends-tab page load share one cache entry
    instead of each maintaining a redundant copy of the same data. This
    was previously the slowest part of an aggregate chat answer: these
    four calls hit Postgres/Supabase directly, uncached, every single
    turn -- a "how many cases" question was paying the same ~9-10s
    round-trip the districts query was measured at before caching."""

    def build_context(self, query: str, repo: CaseRepository, officer: OfficerContext | None = None) -> tuple[str, list[dict] | None]:
        scope = officer.cache_key if officer else "unscoped"
        total = cached_or_compute(f"analytics:total_count:{scope}", lambda: repo.get_total_case_count(officer=officer))
        district_counts = cached_or_compute(f"analytics:districts:{scope}", lambda: repo.get_district_counts(officer=officer))
        crime_counts = cached_or_compute(f"analytics:crime_types:all:{scope}", lambda: repo.get_crime_type_counts(officer=officer))
        trend = cached_or_compute(f"analytics:trend:all:all:{scope}", lambda: repo.get_monthly_trend(officer=officer))

        # Exact total, from a real COUNT query -- NOT derived by having
        # the LLM sum the (possibly truncated) breakdown below. This was
        # a real bug: "how many cases do we have" was previously being
        # answered by the model summing a district list capped at 15
        # rows, silently wrong once there are more districts than that.
        lines = [f"Total case count (exact): {total}"]

        lines.append("\nDistrict-wise case counts:")
        for row in district_counts[:15]:
            lines.append(f"  {row['district']}: {row['count']}")
        if len(district_counts) > 15:
            lines.append(f"  ...and {len(district_counts) - 15} more districts not shown.")

        lines.append("\nCrime-type counts:")
        for row in crime_counts[:15]:
            lines.append(f"  {row['crime_type']}: {row['count']}")
        if len(crime_counts) > 15:
            lines.append(f"  ...and {len(crime_counts) - 15} more crime types not shown.")

        lines.append("\nMonthly case volume (most recent first):")
        for row in trend[-12:]:
            lines.append(f"  {row['month']}: {row['count']}")

        return "\n".join(lines), None


class EntityListStrategy(QueryStrategy):
    """For 'list all accused/criminals/offenders/suspects' style
    questions -- pulls real rows from the Accused table. Semantic
    search over case briefs cannot answer these at all, since the
    embedded case text never includes accused names."""

    def __init__(self, limit: int = 50):
        self.limit = limit

    def build_context(self, query: str, repo: CaseRepository, officer: OfficerContext | None = None) -> tuple[str, list[dict] | None]:
        accused = repo.get_accused_list(limit=self.limit, officer=officer)
        if not accused:
            return "No accused records found.", None

        lines = [f"Accused persons on record (showing up to {self.limit}):"]
        for a in accused:
            lines.append(
                f"  {a['accused_name']} (age {a['age']}, gender {a['gender']}) — "
                f"FIR {a['crime_no']}, {a['crime_type']}, status: {a['case_status']}"
            )
        return "\n".join(lines), None


class SemanticSearchStrategy(QueryStrategy):
    """For questions about specific case details/circumstances -- pulls
    relevant case text via ChromaDB similarity search.

    IMPORTANT: the fir_cases collection was populated with precomputed
    Gemini embeddings (see rag/embed.py), NOT ChromaDB's default
    auto-embedder. So the query text must also be embedded via Gemini
    before searching -- querying with raw query_texts= would silently
    try to use ChromaDB's default embedder instead, which is wrong and
    also requires downloading a model ChromaDB doesn't ship with."""

    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def build_context(self, query: str, repo: CaseRepository, officer: OfficerContext | None = None) -> tuple[str, list[dict] | None]:
        import os
        import chromadb
        from google import genai

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        embed_result = client.models.embed_content(
            model="gemini-embedding-001", contents=[query]
        )
        query_embedding = embed_result.embeddings[0].values

        chroma_client = chromadb.PersistentClient(path="./chroma_store")
        collection = chroma_client.get_or_create_collection(name="fir_cases")

        where = {"district": officer.jurisdiction_id} if officer and officer.role == "DISTRICT_SP" else None
        results = collection.query(
            query_embeddings=[query_embedding], n_results=self.top_k,
            include=["documents", "metadatas"], where=where,
        )
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        if not docs:
            return "No matching case records found.", None

        # Citations are for explainability -- surfacing which specific
        # case records the answer is grounded in, per the "explainable
        # AI / transparent analytics" requirement. rag/embed.py's
        # metadata has no crime_no (only district/crime_type/date/
        # status), so case_id (== CaseMasterID) is the identifier the
        # frontend links against, not a human FIR number.
        authorized = [(id_, doc, m) for id_, doc, m in zip(ids, docs, metas) if officer is None or repo.get_case_by_id(int(id_), officer=officer)]
        if not authorized:
            return "No matching case records within your jurisdiction.", None
        citations = [
            {
                "case_id": id_, "district": m.get("district"),
                "crime_type": m.get("crime_type"), "date": m.get("date"),
                "status": m.get("status"),
            }
            for id_, _, m in authorized
        ]

        return "Relevant case records:\n" + "\n---\n".join(doc for _, doc, _ in authorized), citations


def classify_query(query: str) -> QueryStrategy:
    """Simple keyword heuristic. Checks entity-list keywords first (e.g.
    'list all accused'), since those questions want person-level rows,
    not the district/crime-type aggregate summary -- checking aggregate
    keywords first would misroute 'list all criminals' style questions
    just because they contain no aggregate word, or worse, silently
    answer from an aggregate table with no person data in it."""
    q_lower = query.lower()
    if any(kw in q_lower for kw in ENTITY_LIST_KEYWORDS):
        return EntityListStrategy()
    if any(re.search(rf"\b{re.escape(kw)}\b", q_lower) for kw in AGGREGATE_KEYWORDS):
        return SQLQueryStrategy()
    return SemanticSearchStrategy()
