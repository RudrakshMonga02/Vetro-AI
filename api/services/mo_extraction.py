"""
MO (modus operandi) / keyword extraction from a case's BriefFacts text,
via an LLMProvider prompt -- NOT Catalyst Zia NER/keyword-extraction.

Zia is the "mapped" Catalyst service for this capability per the
resource doc, but Catalyst-service integration is deferred (see
docs/PRD.md); the existing LLMProvider abstraction (already used for
chat) does the same job today without any new dependency. If/when a
CatalystZiaProvider is wired up manually, this module's function
signature (brief_facts, llm) -> dict stays the same regardless of
which LLMProvider implementation is passed in -- swapping the
extraction mechanism is a caller-side choice, not a rewrite here.
"""
from domain.interfaces.llm_provider import LLMProvider

_MO_PROMPT_TEMPLATE = """Extract the modus operandi (MO) and key behavioral/circumstantial \
details from this FIR case brief. Respond in EXACTLY this format, nothing else:

MO_SUMMARY: <one-sentence summary of the method/approach used>
KEYWORDS: <comma-separated list of 5-10 short tags -- e.g. weapon type, time of day, \
location type, target profile, entry method>

Case brief: {brief_facts}"""

_SYNTHESIS_PROMPT_TEMPLATE = """You are given per-case modus operandi summaries for the same \
repeat offender, one per line. Write a short combined behavioral profile paragraph (3-5 \
sentences) identifying patterns across their cases -- recurring methods, escalation or \
consistency over time, common target/location types. Do not invent details not implied by \
the summaries below. If the summaries don't share any clear pattern, say so plainly rather \
than forcing one.

Per-case MO summaries:
{summaries_block}"""

_LEADS_PROMPT_TEMPLATE = """You are helping an investigator on an open FIR case. Below is the \
case's brief facts, followed by structural findings already pulled from the database: other \
cases linked through the same accused name(s), and other open cases nearby (same district and \
crime type). Write a short "recommended next steps" paragraph (3-5 sentences) grounded ONLY in \
what is given below -- do not invent facts, names, or leads not implied by this data. If the \
structural findings are thin or show no clear connection, say so plainly rather than forcing a lead.

Case brief: {brief_facts}

Cross-case links (same accused name in other cases): {cross_case_block}

Other open cases in the same district and crime type: {similar_cases_block}"""


async def synthesize_profile(mo_summaries: list[str], llm: LLMProvider) -> dict[str, str | None]:
    """Combines already-extracted per-case MO summaries (sent by the
    caller, no re-fetching/re-extraction here) into one behavioral
    profile paragraph -- a SECOND LLM call, so only invoke this when a
    user explicitly asks for it, not automatically per offender. Same
    graceful-degradation pattern as extract_mo()."""
    usable = [s.strip() for s in mo_summaries if s and s.strip()]
    if len(usable) < 2:
        return {"profile_summary": None, "error": "insufficient_summaries"}

    try:
        summaries_block = "\n".join(f"- {s}" for s in usable)
        raw = await llm.generate(_SYNTHESIS_PROMPT_TEMPLATE.format(summaries_block=summaries_block))
        return {"profile_summary": raw.strip() or None}
    except Exception:
        return {"profile_summary": None, "error": "synthesis_unavailable"}


async def suggest_leads(
    brief_facts: str | None,
    cross_case_links: list[dict],
    similar_open_cases: list[dict],
    llm: LLMProvider,
) -> dict[str, str | None]:
    """Combines a case's brief facts with already-fetched structural findings
    (cross_case_links, similar_open_cases -- both computed by
    get_investigative_leads(), never re-fetched here) into one "recommended
    next steps" paragraph -- a real LLM call, so only invoke when a user
    explicitly asks, not automatically on page load. Same graceful-degradation
    pattern as extract_mo()/synthesize_profile()."""
    if not brief_facts or not brief_facts.strip():
        return {"leads_summary": None, "error": "no_brief_facts"}
    if not cross_case_links and not similar_open_cases:
        return {"leads_summary": None, "error": "insufficient_findings"}

    try:
        cross_case_block = "\n".join(
            f"- {c['accused_name']} also appears in Case {c['case_id']} "
            f"({c['crime_type']}, {c['district']}, {c['date']})"
            for c in cross_case_links
        ) or "None found."
        similar_cases_block = "\n".join(
            f"- Case {c['case_id']} ({c['crime_type']}, {c['district']}, {c['date']}, status: {c['status']})"
            for c in similar_open_cases
        ) or "None found."
        prompt = _LEADS_PROMPT_TEMPLATE.format(
            brief_facts=brief_facts,
            cross_case_block=cross_case_block,
            similar_cases_block=similar_cases_block,
        )
        raw = await llm.generate(prompt)
        return {"leads_summary": raw.strip() or None}
    except Exception:
        return {"leads_summary": None, "error": "synthesis_unavailable"}


async def extract_mo(brief_facts: str | None, llm: LLMProvider) -> dict[str, object]:
    """Returns {'mo_summary': str|None, 'keywords': list[str]}, plus an
    'error' key if extraction failed. Degrades gracefully on any LLM
    failure (same pattern as query_rewriter.py/query_classifier.py) --
    an extraction hiccup shows as "unavailable" in the profiling view,
    it doesn't break the page."""
    if not brief_facts or not brief_facts.strip():
        return {"mo_summary": None, "keywords": []}

    try:
        raw = await llm.generate(_MO_PROMPT_TEMPLATE.format(brief_facts=brief_facts))
        summary: str | None = None
        keywords: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if line.upper().startswith("MO_SUMMARY:"):
                summary = line.split(":", 1)[1].strip()
            elif line.upper().startswith("KEYWORDS:"):
                keywords = [k.strip() for k in line.split(":", 1)[1].split(",") if k.strip()]
        return {"mo_summary": summary, "keywords": keywords}
    except Exception:
        return {"mo_summary": None, "keywords": [], "error": "extraction_unavailable"}
