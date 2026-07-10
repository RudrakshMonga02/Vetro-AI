"""
Runs the full Stage 1 data pipeline in order:
  1. init_db        - create tables (safe to re-run)
  2. seed_lookups    - populate reference tables (safe to re-run)
  3. seed_cases      - generate dummy CaseMaster + child rows
  4. generate_briefs - fill BriefFacts via Gemini (needs GEMINI_API_KEY)
  5. embed_cases     - embed into ChromaDB (idempotent, needs GEMINI_API_KEY)

Usage:
    python pipeline.py                # run everything
    python pipeline.py --skip-cases   # re-run briefs/embed only (e.g. after
                                       # editing generate_briefs prompt)
    python pipeline.py --only-db      # just schema + lookups, no case data

When the REAL dataset replaces the dummy data: swap out seed_cases.py's
data source (or write a new `load_real_dataset.py` with the same shape --
insert CaseMaster + child rows) and re-run from step 4 onward. Steps 1-2
don't change; steps 4-5 are already resumable/idempotent by design.
"""
import argparse

from db.init_db import init_db
from db.seed_lookups import seed_lookups
from db.seed_cases import seed_cases
from rag.generate_briefs import generate_briefs
from rag.embed import embed_cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-cases", action="store_true",
                         help="Skip case generation (use existing case_master data)")
    parser.add_argument("--only-db", action="store_true",
                         help="Only run schema + lookup seeding, skip cases/briefs/embed")
    args = parser.parse_args()

    print("=== Step 1: init_db ===")
    init_db()

    print("=== Step 2: seed_lookups ===")
    seed_lookups()

    if args.only_db:
        print("--only-db set, stopping here.")
        return

    if not args.skip_cases:
        print("=== Step 3: seed_cases ===")
        seed_cases()
    else:
        print("=== Step 3: seed_cases (skipped) ===")

    print("=== Step 4: generate_briefs ===")
    generate_briefs()

    print("=== Step 5: embed_cases ===")
    embed_cases()

    print("=== Pipeline complete ===")


if __name__ == "__main__":
    main()
