"""
Offender profiling routes: repeat-offender scoring, cross-case links
for a given accused name, and on-demand MO (modus operandi) extraction
per case.

Name-matching caveat (repeated from domain/interfaces/case_repository.py,
worth repeating here since it's exactly the kind of thing a route
consumer needs to know without reading the interface docstring): there
is no stable person-identity key across cases in the ER diagram, so
"repeat offender" here means "same accused name recurs across cases" --
fuzzy by construction, not verified identity linkage. Every response
below carries match_basis: "name" for this reason.

MO extraction hits a real, billed Gemini call per request (see
api/services/mo_extraction.py) -- rate-limited the same way /chat is,
reusing the one shared Limiter instance (api/rate_limiter.py) rather
than constructing a second one. Extracted MO is persisted permanently
in the case_mo_extraction table (domain/interfaces/case_repository.py's
get_mo_extraction()/save_mo_extraction()) rather than the ephemeral
response cache used elsewhere -- a case's BriefFacts never change once
seeded, so an extraction is effectively permanent, and /similar-mo below
needs to compare across many cases' keywords, which an exact-key cache
backend can't support.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.rate_limiter import limiter as _limiter
from api.services.mo_extraction import extract_mo, suggest_leads, synthesize_profile
from api.services.response_cache import cached_or_compute
from infrastructure.llm.llm_factory import get_llm_provider
from infrastructure.persistence.repository_factory import get_case_repository

router = APIRouter()


class SynthesizeProfileRequest(BaseModel):
    # Already-extracted per-case MO summaries, sent by the frontend --
    # this route never re-fetches or re-extracts anything, it only
    # combines what's already in the caller's hands into one profile.
    mo_summaries: list[str] = Field(max_length=50)


@router.get("/repeat")
def repeat_offenders(min_case_count: int = 2):
    repo = get_case_repository()
    key = f"offenders:repeat:{min_case_count}"
    return cached_or_compute(key, lambda: repo.get_repeat_offender_network(min_case_count=min_case_count))


@router.get("/{accused_name}/cases")
def offender_cases(accused_name: str):
    repo = get_case_repository()
    result = repo.get_cross_case_links(accused_name)
    if result["match_count"] == 0:
        raise HTTPException(status_code=404, detail="No matching accused found")
    return result


@router.get("/case/{case_id}/mo")
@_limiter.limit("10/minute")
async def case_mo(request: Request, case_id: int):
    # DB-persisted (case_mo_extraction), not the ephemeral response
    # cache -- see module docstring. A repeat view of the same case
    # never spends a second LLM call.
    repo = get_case_repository()
    existing = repo.get_mo_extraction(case_id)
    if existing is not None:
        return {"case_id": case_id, **existing}

    case = repo.get_case_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    result = await extract_mo(case.get("brief"), get_llm_provider())
    if not result.get("error"):
        repo.save_mo_extraction(case_id, result.get("mo_summary"), result.get("keywords", []))
    return {"case_id": case_id, **result}


@router.get("/case/{case_id}/similar-mo")
@_limiter.limit("10/minute")
async def similar_mo_cases(request: Request, case_id: int, min_shared: int = 2, limit: int = 10):
    # The only LLM call this route makes is for case_id itself, if it
    # doesn't already have a persisted MO -- comparison only runs
    # against OTHER cases that already have one (someone ran "Extract
    # MO" on them before), never bulk-extracts a whole crime-type's
    # worth of cases just to answer one similarity query. See
    # get_similar_mo_cases()'s docstring for the full reasoning.
    repo = get_case_repository()
    existing = repo.get_mo_extraction(case_id)
    if existing is None:
        case = repo.get_case_by_id(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Case not found")
        result = await extract_mo(case.get("brief"), get_llm_provider())
        if result.get("error") or not result.get("keywords"):
            raise HTTPException(
                status_code=400, detail="MO extraction unavailable for this case"
            )
        repo.save_mo_extraction(case_id, result.get("mo_summary"), result["keywords"])
        existing = {"mo_summary": result.get("mo_summary"), "keywords": result["keywords"]}

    similar = repo.get_similar_mo_cases(
        case_id, existing["keywords"], min_shared=min_shared, limit=limit
    )
    return {"case_id": case_id, "keywords": existing["keywords"], "similar_cases": similar}


@router.post("/synthesize-profile")
@_limiter.limit("10/minute")
async def synthesize_offender_profile(request: Request, body: SynthesizeProfileRequest):
    result = await synthesize_profile(body.mo_summaries, get_llm_provider())
    if result.get("error") == "insufficient_summaries":
        raise HTTPException(
            status_code=400, detail="Need at least 2 extracted MO summaries to synthesize a profile"
        )
    return result


@router.get("/case/{case_id}/leads")
def case_leads(case_id: int):
    repo = get_case_repository()
    key = f"offenders:leads:{case_id}"
    return cached_or_compute(key, lambda: repo.get_investigative_leads(case_id))


@router.post("/case/{case_id}/leads/summarize")
@_limiter.limit("10/minute")
async def summarize_leads(request: Request, case_id: int):
    # Separate, explicit, button-triggered LLM step -- same "don't spend
    # LLM quota automatically" discipline as MO extraction/profile
    # synthesis. Re-fetches the already-cheap structural leads rather
    # than trusting client-supplied data for the prompt.
    repo = get_case_repository()
    case = repo.get_case_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    leads = repo.get_investigative_leads(case_id)
    result = await suggest_leads(
        case.get("brief"), leads["cross_case_links"], leads["similar_open_cases"], get_llm_provider()
    )
    if result.get("error") in ("no_brief_facts", "insufficient_findings"):
        raise HTTPException(status_code=400, detail=f"Cannot generate leads summary: {result['error']}")
    return result
