"""
Embeds each CaseMaster row into ChromaDB for RAG retrieval.

Idempotent: computes a content hash per case and skips re-embedding if
unchanged (same pattern used in CodeNavigator). This means re-running
this script after generate_briefs.py adds more rows, or after the real
dataset replaces dummy data, only embeds what's new/changed -- not
everything from scratch.
"""
import hashlib
import os
import time

import chromadb
from dotenv import load_dotenv
from google import genai

from db.connection import get_session
from db.models import CaseMaster, District, CrimeSubHead, CaseCategory, GravityOffence, CaseStatusMaster

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
EMBED_MODEL = "gemini-embedding-001"

chroma_client = chromadb.PersistentClient(path="./chroma_store")
collection = chroma_client.get_or_create_collection(name="fir_cases")

BATCH_SIZE = 20


def build_case_text(row) -> str:
    (cm_id, district, crime_type, category, gravity, status, reg_date, brief) = row
    brief_part = brief or "No detailed summary available."
    return (
        f"FIR case {cm_id}: {category} registered on {reg_date} in {district} district. "
        f"Crime type: {crime_type}. Gravity: {gravity}. Status: {status}. "
        f"Details: {brief_part}"
    )


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_existing_hashes(ids: list[str]) -> dict:
    """Fetch existing stored hashes (in metadata) for a batch of ids, if present."""
    if not ids:
        return {}
    result = collection.get(ids=ids, include=["metadatas"])
    hashes = {}
    for id_, meta in zip(result["ids"], result["metadatas"]):
        if meta and "content_hash" in meta:
            hashes[id_] = meta["content_hash"]
    return hashes


def embed_cases():
    session = get_session()
    try:
        rows = (
            session.query(
                CaseMaster.CaseMasterID,
                District.DistrictName,
                CrimeSubHead.CrimeHeadName,
                CaseCategory.LookupValue,
                GravityOffence.LookupValue,
                CaseStatusMaster.CaseStatusName,
                CaseMaster.CrimeRegisteredDate,
                CaseMaster.BriefFacts,
            )
            .join(District, CaseMaster.DistrictID == District.DistrictID)
            .join(CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
            .join(CaseCategory, CaseMaster.CaseCategoryID == CaseCategory.CaseCategoryID)
            .join(GravityOffence, CaseMaster.GravityOffenceID == GravityOffence.GravityOffenceID)
            .join(CaseStatusMaster, CaseMaster.CaseStatusID == CaseStatusMaster.CaseStatusID)
            .all()
        )

        total = len(rows)
        print(f"{total} cases in DB. Checking which need (re-)embedding...")

        to_embed_ids, to_embed_texts, to_embed_metas = [], [], []

        for start in range(0, total, BATCH_SIZE):
            batch = rows[start:start + BATCH_SIZE]
            batch_ids = [str(r[0]) for r in batch]
            batch_texts = [build_case_text(r) for r in batch]
            batch_hashes = [content_hash(t) for t in batch_texts]

            existing = get_existing_hashes(batch_ids)

            for id_, text, h, row in zip(batch_ids, batch_texts, batch_hashes, batch):
                if existing.get(id_) == h:
                    continue  # unchanged, skip
                to_embed_ids.append(id_)
                to_embed_texts.append(text)
                to_embed_metas.append({
                    "content_hash": h,
                    "district": row[1],
                    "crime_type": row[2],
                    "category": row[3],
                    "gravity": row[4],
                    "status": row[5],
                    "date": str(row[6]),
                })

        print(f"{len(to_embed_ids)} cases need embedding (new or changed).")
        if not to_embed_ids:
            print("Nothing to do.")
            return

        for start in range(0, len(to_embed_ids), BATCH_SIZE):
            ids_batch = to_embed_ids[start:start + BATCH_SIZE]
            texts_batch = to_embed_texts[start:start + BATCH_SIZE]
            metas_batch = to_embed_metas[start:start + BATCH_SIZE]

            # Retry with backoff on rate-limit (429) errors -- free tier caps
            # requests/minute, so short bursts will hit this. Retries a few
            # times with increasing waits before giving up on this batch.
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    result = client.models.embed_content(model=EMBED_MODEL, contents=texts_batch)
                    embeddings = [e.values for e in result.embeddings]
                    break
                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        wait = 60 * (attempt + 1)  # 60s, 120s, 180s...
                        print(f"  rate limited, waiting {wait}s before retry "
                              f"(attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait)
                    else:
                        raise
            else:
                print(f"  batch at {start} failed after {max_retries} retries, skipping "
                      f"-- re-run this script later to pick up remaining cases")
                continue

            collection.upsert(
                ids=ids_batch,
                embeddings=embeddings,
                documents=texts_batch,
                metadatas=metas_batch,
            )
            print(f"  embedded {min(start + BATCH_SIZE, len(to_embed_ids))}/{len(to_embed_ids)}")
            time.sleep(2)  # small pause between batches to stay under rate limits

        print("Done embedding.")
    finally:
        session.close()


if __name__ == "__main__":
    embed_cases()
