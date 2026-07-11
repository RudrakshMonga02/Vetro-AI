"""
Language-agnostic query classification: replaces classify_query()'s
English-keyword heuristic (query_strategy.py) as the primary path when
the incoming query isn't (confidently) English.

WHY THIS EXISTS: classify_query() matches literal English phrases like
"how many", "list all", "most" against the query text. That's fine for
English, but silently wrong for Kannada script or Kannalish (romanized/
code-mixed Kannada+English) -- none of those phrases exist in the query
text, so every non-English aggregate/entity-list question falls through
to SemanticSearchStrategy regardless of what's actually being asked,
with no error or signal that classification failed. An LLM naturally
understands intent across languages, so this replaces the heuristic
with one small classification+translation call, tried first.

Also returns an English gloss of the query. This matters specifically
for SemanticSearchStrategy: the `fir_cases` ChromaDB collection was
embedded from English `BriefFacts` text (rag/embed.py) -- embedding a
Kannada or Kannalish query directly and hoping cross-lingual embedding
alignment is good enough is a real gamble. Translating first is the
safer, verifiable choice. SQLQueryStrategy/EntityListStrategy don't
actually use the query text at all (they pull structured aggregates/
rows regardless of phrasing), so the gloss is harmless for those.
"""
from api.strategies.query_strategy import (
    EntityListStrategy,
    QueryStrategy,
    SQLQueryStrategy,
    SemanticSearchStrategy,
    classify_query as classify_query_keywords,
)
from domain.interfaces.llm_provider import LLMProvider

_CLASSIFY_PROMPT_TEMPLATE = """Classify this crime-database chatbot question into exactly \
one category, and provide an English translation of it (if it's already in English, \
repeat it unchanged). The question may be in English, Kannada, or a Kannada/English mix \
(Kannalish) -- classify by meaning, not by matching English words.

Categories:
- AGGREGATE: asking for counts, statistics, trends, comparisons, totals, breakdowns \
(e.g. "how many cases", "which district has the most theft", "monthly trend")
- ENTITY_LIST: asking to list/enumerate specific people -- accused, criminals, \
offenders, suspects (e.g. "list all criminals", "who are the accused")
- SEMANTIC: asking about the details/circumstances of specific case(s), or anything \
that isn't a statistic or a list of people

Respond in EXACTLY this format, nothing else:
CATEGORY: <AGGREGATE|ENTITY_LIST|SEMANTIC>
ENGLISH: <english translation of the question>

Question: {query}"""


def _build_strategy(category: str) -> QueryStrategy:
    category = category.strip().upper()
    if category == "AGGREGATE":
        return SQLQueryStrategy()
    if category == "ENTITY_LIST":
        return EntityListStrategy()
    return SemanticSearchStrategy()


def _parse_response(raw: str, fallback_query: str) -> tuple[QueryStrategy, str]:
    category = "SEMANTIC"
    english_query = fallback_query
    for line in raw.splitlines():
        line = line.strip()
        if line.upper().startswith("CATEGORY:"):
            category = line.split(":", 1)[1].strip()
        elif line.upper().startswith("ENGLISH:"):
            value = line.split(":", 1)[1].strip()
            if value:
                english_query = value
    return _build_strategy(category), english_query


async def classify_query_llm(query: str, llm: LLMProvider) -> tuple[QueryStrategy, str]:
    """Returns (strategy, english_query). Degrades to the keyword
    heuristic (query itself as the "english_query") if the LLM call
    fails or returns something unparseable -- a classification hiccup
    shouldn't break the chat turn, it should fall back to best-effort
    English-keyword matching same as before this module existed."""
    try:
        raw = await llm.generate(_CLASSIFY_PROMPT_TEMPLATE.format(query=query))
        if not raw or not raw.strip():
            return classify_query_keywords(query), query
        return _parse_response(raw, query)
    except Exception:
        return classify_query_keywords(query), query
