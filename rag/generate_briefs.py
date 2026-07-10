"""
Fills CaseMaster.BriefFacts with realistic (fictional) FIR summaries
using Gemini, so RAG retrieval later has meaningful text to embed
instead of lorem-ipsum filler.

Batched + resumable: only processes rows where BriefFacts IS NULL,
so a crash/rate-limit-stop halfway through just needs a re-run.
"""
import os
import time

from dotenv import load_dotenv
from google import genai
from sqlalchemy import select

from db.connection import get_session
from db.models import CaseMaster, District, CrimeSubHead, CaseCategory

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"

BATCH_SIZE = 20
SLEEP_BETWEEN_BATCHES_SEC = 2  # be polite to free-tier rate limits


def build_prompt(rows):
    """rows: list of (CaseMasterID, district_name, crime_subhead, category, reg_date)"""
    lines = []
    for cm_id, district, crime_type, category, reg_date in rows:
        lines.append(
            f"- id={cm_id}: A {category} for {crime_type} registered in "
            f"{district} district on {reg_date}."
        )
    joined = "\n".join(lines)
    return f"""You are generating short, realistic (fictional) FIR case summaries for a
police-data demo application. For each case below, write a 2-3 sentence factual-sounding
summary of what might have happened, consistent with the given crime type, district, and date.
Do not include real names. Keep each summary generic enough to be clearly fictional but
specific enough to sound like a real case brief (e.g. mention plausible circumstances,
time of day, general location like "near the bus stand" or "at the victim's residence").

Cases:
{joined}

Respond with ONLY a JSON array of objects, no markdown, no preamble, in this exact form:
[{{"id": <id>, "brief": "<summary text>"}}, ...]
"""


def parse_response(text: str):
    import json
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return json.loads(cleaned)


def generate_briefs():
    session = get_session()
    try:
        pending = (
            session.query(
                CaseMaster.CaseMasterID,
                District.DistrictName,
                CrimeSubHead.CrimeHeadName,
                CaseCategory.LookupValue,
                CaseMaster.CrimeRegisteredDate,
            )
            .join(District, CaseMaster.DistrictID == District.DistrictID)
            .join(CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
            .join(CaseCategory, CaseMaster.CaseCategoryID == CaseCategory.CaseCategoryID)
            .filter(CaseMaster.BriefFacts.is_(None))
            .all()
        )
    finally:
        session.close()

    total = len(pending)
    print(f"{total} cases need BriefFacts generated.")
    if total == 0:
        return

    succeeded = 0
    failed_batches = 0

    for start in range(0, total, BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]
        prompt = build_prompt(batch)

        try:
            response = client.models.generate_content(model=MODEL, contents=prompt)
            results = parse_response(response.text)
        except Exception as e:
            failed_batches += 1
            print(f"  batch at {start} failed ({e}), skipping -- will retry on next run")
            time.sleep(SLEEP_BETWEEN_BATCHES_SEC)
            continue

        result_map = {r["id"]: r["brief"] for r in results}

        # Fresh session per batch -- avoids holding one connection open across
        # the whole run, which Supabase's pooler can drop mid-way on slow/flaky runs.
        batch_session = get_session()
        try:
            for cm_id, *_ in batch:
                brief = result_map.get(cm_id)
                if brief:
                    batch_session.query(CaseMaster).filter_by(CaseMasterID=cm_id).update(
                        {"BriefFacts": brief}
                    )
            batch_session.commit()
            succeeded += len(batch)
            print(f"  {succeeded}/{total} briefs written")
        except Exception as e:
            batch_session.rollback()
            failed_batches += 1
            print(f"  batch at {start} DB write failed ({e}), skipping -- will retry on next run")
        finally:
            batch_session.close()

        time.sleep(SLEEP_BETWEEN_BATCHES_SEC)

    print(f"Done. {succeeded}/{total} briefs written successfully, {failed_batches} batches failed.")
    if failed_batches > 0:
        print("Re-run this script to retry the failed/remaining cases (BriefFacts IS NULL filter picks them up automatically).")


if __name__ == "__main__":
    generate_briefs()
