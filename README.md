# Vetro AI — KSP Datathon

Vetro AI is the data + conversational intelligence layer for the Karnataka SCRB
crime-data datathon project. It builds a Postgres schema matching the provided
FIR ER diagram, seeds it with realistic dummy data, generates FIR summary text
via Gemini, and embeds that text into ChromaDB for RAG retrieval, sitting behind
a FastAPI backend. See `docs/PRD.md` for current product scope and decisions,
and `docs/ARCHITECTURE.md` for the structural layering.

## Setup

1. **Postgres**: have a running Postgres instance. Update `.env`:
   ```
   DATABASE_URL=postgresql+psycopg2://<user>:<pass>@<host>:5432/ksp_datathon
   GEMINI_API_KEY=your_key_here
   ```
   Create the database first: `createdb ksp_datathon` (or via `psql`).

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the pipeline

Run everything in order (schema → lookups → dummy cases → Gemini briefs → embeddings):
```bash
python pipeline.py
```

Useful flags:
- `python pipeline.py --only-db` — just create schema + seed lookup tables (districts, crime heads, IPC sections, etc.), skip case generation. Good for a first sanity check.
- `python pipeline.py --skip-cases` — re-run brief generation + embedding without regenerating case data (e.g. after tweaking the Gemini prompt in `rag/generate_briefs.py`).

You can also run each stage individually:
```bash
python -m db.init_db
python -m db.seed_lookups
python -m db.seed_cases
python -m rag.generate_briefs   # needs GEMINI_API_KEY
python -m rag.embed             # needs GEMINI_API_KEY
```

## What each piece does

| File | Purpose |
|---|---|
| `db/models.py` | SQLAlchemy schema — all 26 tables from the FIR ER diagram, with indexes on district/date/crime-head columns used by chart & map queries |
| `db/connection.py` | DB engine/session, reads `DATABASE_URL` from `.env` |
| `db/init_db.py` | Creates tables (idempotent) |
| `db/seed_lookups.py` | Seeds real reference data: 30 Karnataka districts, real IPC sections, crime head/sub-head taxonomy, case categories (FIR/UDR/Zero FIR/PAR), etc. Deterministic, not random. |
| `db/seed_cases.py` | Generates ~2,500 `CaseMaster` rows + child records (Victim, Accused, ComplainantDetails, ArrestSurrender, ActSectionAssociation) via Faker. Lat/lng bounded to Karnataka's real geographic extent. |
| `rag/generate_briefs.py` | Batched Gemini calls that write realistic fictional FIR summaries into `CaseMaster.BriefFacts`. Resumable — only processes rows where `BriefFacts IS NULL`. |
| `rag/embed.py` | Embeds each case (structured fields + BriefFacts) into ChromaDB. Idempotent via content hashing — re-running only embeds new/changed rows. |
| `pipeline.py` | Runs all of the above in the correct order. |

## Verifying it worked

```sql
-- district distribution (for hotspot map / charts)
SELECT d."DistrictName", COUNT(*) FROM case_master c
JOIN district d ON c."DistrictID" = d."DistrictID"
GROUP BY d."DistrictName" ORDER BY COUNT(*) DESC;
```

```python
# ChromaDB similarity check
import chromadb
client = chromadb.PersistentClient(path="./chroma_store")
collection = client.get_collection("fir_cases")
results = collection.query(query_texts=["murder cases in Mysuru"], n_results=5)
print(results["documents"])
```

## Repository pattern: Postgres vs Catalyst

All database access goes through the `CaseRepository` interface (`domain/interfaces/case_repository.py`), never directly through SQLAlchemy or the Catalyst SDK in application code. Two implementations exist:

- `infrastructure/persistence/postgres_repository.py` — Postgres/Supabase, via SQLAlchemy. **Fully tested against real seeded data.**
- `infrastructure/persistence/catalyst_repository.py` — Catalyst Data Store, via ZCQL + `zcatalyst_sdk`. **Written against Catalyst's documented SDK interface but NOT yet tested against a real Catalyst project** (no network/credentials access from the environment this was built in). Treat as a strong first draft — run it against your actual Catalyst project and report errors.

Switch between them via `.env`:
```
DATA_BACKEND=postgres   # local/Supabase dev
DATA_BACKEND=catalyst   # once Catalyst Data Store tables exist
```
Routes/services call `infrastructure.persistence.repository_factory.get_case_repository()` and never need to know which backend is active.

### Before using the Catalyst backend

1. **Create matching tables in the Catalyst console** (or via SDK) with these exact names: `CaseMaster`, `District`, `CrimeSubHead`, `CrimeHead`, `CaseCategory`, `GravityOffence`, `CaseStatusMaster`, `Victim`, `Accused`, `ArrestSurrender` — same columns as `db/models.py`.
2. **Check the dev-environment row limits.** Catalyst's dev environment caps at 5,000 rows/table and 25,000 rows/project total. Since production environment usage costs credits, the default dummy dataset is now sized at **1,000 cases** (~7,400 rows total across all tables) specifically to stay well under these limits for free/cheap testing. Only scale back up to 2,500+ cases once you're confident the Catalyst integration works and are ready to spend credits on it.
3. **Verify ZCQL date functions.** `get_monthly_trend()` currently collapses dates to `YYYY-MM` in Python rather than in ZCQL, since ZCQL's exact date-truncation function wasn't confirmed. If ZCQL has a native equivalent to Postgres' `to_char()`, moving that logic into the query would be more efficient at scale.
4. **Known dependency conflict:** `zcatalyst-sdk` wants `typing_extensions~=4.12.1`; `google-genai`/`pydantic` want `>=4.14.1`. Both currently install with a pip warning but no hard failure — test this combination early in your actual FastAPI app rather than assuming it's fine.

### Karnataka districts

Fixed to the correct 31 districts (previously missing Vijayanagara, carved out of Ballari in 2021).


The pipeline is built so this is a data-source swap, not a rewrite:
- Steps 1-2 (schema, lookups) almost certainly don't change.
- Replace `seed_cases.py`'s Faker generation with a loader for the real
  SQL dump / CSVs, inserting into the same tables with the same shape.
- Steps 4-5 (briefs, embed) are already resumable/idempotent — they'll
  just process whatever new rows show up.
- All chart/analytics queries should aggregate in SQL (not pull full
  tables into pandas), and the embedding step is already batched — so
  this scales to a much larger real dataset without code changes.

## Known limitations of this dummy-data pass

- `Employee`/`PolicePersonID`/IO fields are left `NULL` — not needed for
  chatbot/charts/map/forecasting/graph features, can be seeded later if
  a feature ends up needing officer-level data.
- `ChargesheetDetails` table exists in schema but isn't seeded yet.
- Local dev uses plain Postgres; deployment must move to Catalyst Data
  Store per datathon rules — confirm Catalyst's SQL dialect compatibility
  before that migration.

---

# Stage 2: FastAPI Backend

Sits on top of Stage 1 -- imports `infrastructure.persistence.repository_factory.get_case_repository()`
and nothing from Stage 1 was modified to build this. Run it with:

```bash
uvicorn api.main:app --reload
```

Visit `http://localhost:8000/docs` for the interactive API tester (auto-generated by FastAPI).

## Architecture / design patterns used

- **Repository pattern** (`domain/interfaces/case_repository.py` + `infrastructure/persistence/{postgres_repository,catalyst_repository}.py`) --
  routes never touch SQLAlchemy or ZCQL directly.
- **Factory pattern** (`infrastructure/persistence/repository_factory.py`, `infrastructure/llm/llm_factory.py`) --
  picks Postgres vs Catalyst, and Gemini vs (future) Catalyst QuickML, based on env vars.
- **Strategy pattern** (`api/strategies/query_strategy.py`) -- routes chatbot
  questions to either SQL aggregation or ChromaDB semantic search, based on
  a keyword classifier. Tested against 6 representative queries, all routed correctly.
- **Service layer** (`api/services/chat_service.py`) -- orchestrates
  classification -> context retrieval -> LLM call. Routes stay thin.

## Endpoints

| Route | Method | Status | Description |
|---|---|---|---|
| `/` | GET | Tested, working | Health check |
| `/chat/` | POST | Built + tested up to the LLM call (needs real `GEMINI_API_KEY` to fully verify) | RAG chatbot. Body: `{"query": "..."}`. Streams plain text back (`transfer-encoding: chunked` confirmed). |
| `/analytics/districts` | GET | Tested, working | District-wise case counts |
| `/analytics/crime-types` | GET | Tested, working | Crime-type breakdown, optional `?district=` filter |
| `/analytics/trend` | GET | Tested, working | Monthly case volume, optional `?district=` filter |
| `/map/hotspots` | GET | Tested, working | Lat/lng + crime type for all cases, optional `?limit=` |
| `/graph/case/{case_id}` | GET | Tested, working | Victim/Accused/Arrest network for one case, Cytoscape-ready `{nodes, edges}` shape |

Analytics/map/graph are currently thin routes calling already-tested
repository methods directly -- functional, not yet feature-complete
(e.g. no pagination, no caching, no clustering on the map for scale).
Chat is the one fully built out with the Strategy/Service layers.

## What's tested vs. not

**Fully tested end-to-end, live, against real seeded Postgres data:**
- All 5 non-chat routes -- confirmed `200 OK` with correct real data through the full stack (route -> service -> repository -> Postgres)
- `/chat/`'s entire pipeline up to (not including) the actual Gemini API response -- confirmed the query classifier, SQL-strategy context builder (real district/crime-type/trend data), and prompt construction all work correctly. The only untested part is the live Gemini call itself, which failed in this build environment purely due to network restrictions (`generativelanguage.googleapis.com` not in this sandbox's allowlist) -- not a code bug. Test this yourself locally with a real `GEMINI_API_KEY` to confirm the final mile.
- Streaming mechanics confirmed via `curl -i`: response headers show `transfer-encoding: chunked`, meaning the frontend's chunk-reading loop will work as designed.

**Not yet tested:**
- Semantic search strategy's live Gemini-embedding + ChromaDB query path (same network restriction as above; the *mechanism* was verified against a local test collection using precomputed embeddings, which is the correct pattern -- but not against your real `fir_cases` collection with real Gemini embeddings)
- The full chatbot response quality/tone (depends on real Gemini output)

## Frontend

`vetro-ai-frontend/` is the real React (Vite) chat UI -- multi-session "Investigation" sidebar, streaming Markdown-rendered responses, and client-side PDF export of a conversation. Run it with:

```bash
cd vetro-ai-frontend
npm install
npm run dev
```

Then open `http://localhost:5173` with the backend (`uvicorn api.main:app --reload`) running.

## Known bug found and fixed during testing

`SemanticSearchStrategy` originally called `collection.query(query_texts=...)`,
which would have silently tried to use ChromaDB's default auto-embedder
instead of Gemini -- wrong, since the `fir_cases` collection was populated
with precomputed Gemini embeddings (see `rag/embed.py`). Fixed to embed
the query via Gemini first, then query by vector
(`collection.query(query_embeddings=...)`). Caught this by actually running
the code against a test ChromaDB collection, not just reading it.

## Next steps

1. Test `/chat/` with a real `GEMINI_API_KEY` locally, confirm both strategies produce sensible answers.
2. Build out `/analytics`, `/map`, `/graph` further if the demo needs pagination, caching (Catalyst Cache is a good fit here), or map clustering.
3. Resolve the Catalyst QuickML question -- `infrastructure/llm/catalyst_quickml_provider.py` already has a `CatalystQuickMLProvider` placeholder ready to implement once that's answered.
