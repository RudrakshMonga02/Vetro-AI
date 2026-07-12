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
than constructing a second one.
"""
import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.rate_limiter import limiter as _limiter
from api.services.mo_extraction import extract_mo, suggest_leads, synthesize_profile
from api.services.response_cache import cached_or_compute
from infrastructure.cache.cache_provider_factory import get_cache_provider
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
    # Inlined rather than routed through cached_or_compute -- extract_mo()
    # is async (a real LLM call), and that helper is sync-only. Worth
    # caching regardless of the rate limit above: a case's BriefFacts
    # never change once seeded, so a repeat view of the same case
    # shouldn't spend a second LLM call reaching the same answer. Longer
    # TTL than the analytics routes for the same reason -- this is
    # closer to "permanent" than "changes when new cases land."
    cache = get_cache_provider()
    cache_key = f"offenders:mo:{case_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        try:
            return json.loads(cached)
        except ValueError:
            pass

    repo = get_case_repository()
    case = repo.get_case_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    result = await extract_mo(case.get("brief"), get_llm_provider())
    response = {"case_id": case_id, **result}
    cache.set(cache_key, json.dumps(response, default=str), expiry_hours=24)
    return response


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
