# Vetro AI — KSP Datathon

Vetro AI is a Karnataka SCRB crime-data platform built for the KSP Datathon (team
TraceTitans): a Postgres-backed FIR schema matching the provided ER diagram, seeded with
realistic dummy data, sitting behind a FastAPI backend and a React (Vite) frontend with six
investigator-facing feature areas — conversational chat, network graphs, a hotspot map,
trend analytics, offender profiling, and per-case decision support (timelines + leads).

See `docs/PRD.md` for the full product decision log (what was built, why, and what was
verified live) and `docs/ARCHITECTURE.md` for the structural/layering rationale.

## Quick start

**Backend:**
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
```
Copy `.env.example` → `.env` and fill in at minimum `DATABASE_URL` (a real Postgres/Supabase
connection string) and either a Catalyst QuickML setup or `GEMINI_API_KEY` (see "LLM backend"
below). Then:
```bash
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```
Visit `http://localhost:8000/docs` for the interactive API tester.

**Frontend:**
```bash
cd vetro-ai-frontend
npm install
npm run dev
```
Open `http://localhost:5173`. Copy `vetro-ai-frontend/.env.example` → `.env` if the backend
isn't on `localhost:8000`.

Start the backend first — the frontend will load fine without it, but every tab will show
fetch errors until the API is reachable.

## Data pipeline (Stage 1)

Run everything in order (schema → lookups → dummy cases → Gemini briefs → embeddings):
```bash
python pipeline.py
```
Useful flags:
- `python pipeline.py --only-db` — just create schema + seed lookup tables (districts, crime
  heads, IPC sections, etc.), skip case generation. Good for a first sanity check.
- `python pipeline.py --skip-cases` — re-run brief generation + embedding without
  regenerating case data (e.g. after tweaking the Gemini prompt in `rag/generate_briefs.py`).

Or run each stage individually:
```bash
python -m db.init_db
python -m db.seed_lookups
python -m db.seed_cases
python -m rag.generate_briefs   # needs GEMINI_API_KEY
python -m rag.embed             # needs GEMINI_API_KEY
```

| File | Purpose |
|---|---|
| `db/models.py` | SQLAlchemy schema — all tables from the FIR ER diagram, plus app-level `Conversation`/`Message` tables for chat history, with indexes on district/date/crime-head columns used by chart & map queries |
| `db/connection.py` | DB engine/session, reads `DATABASE_URL` from `.env` |
| `db/init_db.py` | Creates tables (idempotent) |
| `db/seed_lookups.py` | Seeds real reference data: 31 Karnataka districts, real IPC sections, crime head/sub-head taxonomy, case categories (FIR/UDR/Zero FIR/PAR), etc. Deterministic, not random. |
| `db/seed_cases.py` | Generates dummy `CaseMaster` rows + child records (Victim, Accused, ComplainantDetails, ArrestSurrender, ActSectionAssociation) via Faker. Lat/lng bounded to Karnataka's real geographic extent. |
| `rag/generate_briefs.py` | Batched Gemini calls that write realistic fictional FIR summaries into `CaseMaster.BriefFacts`. Resumable — only processes rows where `BriefFacts IS NULL`. |
| `rag/embed.py` | Embeds each case (structured fields + BriefFacts) into ChromaDB. Idempotent via content hashing — re-running only embeds new/changed rows. |
| `pipeline.py` | Runs all of the above in the correct order. |

### Known limitations of this dummy-data pass
- `Employee`/`PolicePersonID`/IO fields are left `NULL` — not needed for any current feature.
- `ChargesheetDetails` table exists in schema but isn't seeded — code that reads it (the
  investigation timeline) handles zero rows as the normal case, not an error.
- Sociological breakdown is complainant-side demographics only (caste/religion/occupation) —
  the schema has no equivalent lookups on Accused or Victim, so this must never be presented
  as "offender demographics."
- Local dev uses plain Postgres/Supabase; Karnataka SCRB datathon rules require the final
  deployment target to be Catalyst Data Store — that migration is deferred (see
  `docs/PRD.md`'s decision log for why), the repository interface is already built to make
  that swap a config change, not a rewrite (see "Repository pattern" below).

## Feature tour (frontend)

| Tab | Purpose |
|---|---|
| **Chat** | Multi-session "Investigation A/B/C…" threads, each with independently persisted history (Postgres-backed, not in-memory). Answers route to either a real SQL aggregate query or semantic search over case briefs (ChromaDB + Gemini embeddings) depending on the question, with citations back to real case IDs that persist across reopened conversations. Supports English, Kannada, and "Kannalish" (Latin-script Kannada), streamed responses, and client-side PDF export of a conversation. |
| **Network Graph** | Single-case mode: a case's Victim/Accused/ArrestSurrender relationships as a Cytoscape graph, with repeat offenders flagged directly on the node (dashed amber border + case count). Alongside the graph: an investigation timeline (chronological view of registration/incident/arrest/chargesheet dates) and suggested leads (structural cross-case links + similar open cases nearby, plus an optional one-click LLM-generated "recommended next steps" summary). Aggregate mode: every repeat offender and the cases connecting them, with co-accused edges. |
| **Hotspot Map** | Every case plotted by lat/lng, real marker clustering (`react-leaflet-cluster`) that merges/splits naturally on zoom, optional crime-type filter, click-through into the Network Graph. |
| **Trends & Forecasting** | District/crime-type breakdowns, monthly trend charts, a simple linear forecast (deliberately returns no projection rather than a fabricated one when there's under 2 months of history), and the sociological (complainant-demographic) breakdown. |
| **Offender Profiling** | Repeat-offender list with a simple count-based risk tier, per-case MO (modus operandi) extraction via one grounded LLM call, and an on-demand combined behavioral profile synthesized across an offender's extracted MOs. |

**Standing caveat that shows up across Network Graph and Offender Profiling:** there is no
stable person-identity key across cases anywhere in the ER diagram, so "repeat offender" /
"cross-case link" means "same accused name recurs" — fuzzy by construction, not verified
identity linkage. Every relevant API response carries `match_basis: "name"` for this reason.

## Backend architecture

- **Repository pattern** (`domain/interfaces/case_repository.py` +
  `infrastructure/persistence/{postgres_repository,catalyst_repository}.py`) — routes never
  touch SQLAlchemy or ZCQL directly.
- **Factory pattern** (`infrastructure/persistence/repository_factory.py`,
  `infrastructure/llm/llm_factory.py`, `infrastructure/cache/cache_provider_factory.py`) —
  picks the DB backend, LLM backend, and cache backend based on env vars.
- **Strategy pattern** (`api/strategies/query_strategy.py`) — routes chatbot questions to
  either SQL aggregation or ChromaDB semantic search, based on a keyword classifier.
- **Service layer** (`api/services/`) — `chat_service.py` orchestrates classification →
  context retrieval → LLM call; `mo_extraction.py` and `response_cache.py` are the other two
  service-layer pieces. Routes stay thin.

See `docs/ARCHITECTURE.md` for the full rationale and folder-by-folder breakdown.

## Repository pattern: Postgres vs Catalyst

All database access goes through the `CaseRepository` interface
(`domain/interfaces/case_repository.py`), never directly through SQLAlchemy or the Catalyst
SDK in application code. Two implementations exist:

- `infrastructure/persistence/postgres_repository.py` — Postgres/Supabase, via SQLAlchemy.
  **This is the live backend** — fully implemented and tested against real seeded data.
- `infrastructure/persistence/catalyst_repository.py` — Catalyst Data Store, via ZCQL +
  `zcatalyst_sdk`. **A first draft, not yet implemented for the newer repository methods**
  (`get_cross_case_links`, `get_repeat_offender_network`, `get_sociological_breakdown`,
  `get_case_timeline`, `get_investigative_leads` all currently raise `NotImplementedError`
  here) and not tested against a real Catalyst project. `DATA_BACKEND=catalyst` should not be
  selected until this is filled in.

Switch between them via `.env`:
```
DATA_BACKEND=postgres   # local/Supabase dev (current default)
DATA_BACKEND=catalyst   # once Catalyst Data Store tables + the stub methods above exist
```
Routes/services call `infrastructure.persistence.repository_factory.get_case_repository()`
and never need to know which backend is active.

### Before using the Catalyst Data Store backend
1. Create matching tables in the Catalyst console (or via SDK) with the same names/columns as
   `db/models.py`.
2. Check the dev-environment row limits (5,000 rows/table, 25,000 rows/project on Catalyst's
   free dev tier) before seeding at full scale.
3. Fill in the `NotImplementedError` stub methods listed above.
4. `zcatalyst-sdk` pins `typing_extensions~=4.12.1`; other deps want newer — currently
   installs with a pip warning, not a hard failure, but worth testing early.

## LLM backend: Catalyst QuickML vs Gemini

Set via `LLM_BACKEND` in `.env`:
- `catalyst_quickml` (**current default**) — Catalyst's QuickML LLM Serving, called directly
  via OAuth + REST (see `infrastructure/catalyst_oauth.py` and
  `infrastructure/llm/catalyst_quickml_provider.py`), bypassing the `zcatalyst_sdk`'s HTTP
  layer entirely since it requires a deployed-Function request context this app doesn't run
  in. Needs `CATALYST_AUTH`, `QUICKML_ENDPOINT_URL`, `QUICKML_MODEL`,
  `X_ZOHO_CATALYST_ORG_ID` all set — see `.env.example` for exactly what each one is and
  where to find it. Streaming is fake (word-chunked) — the real endpoint was tested directly
  and confirmed not to support `stream: true` (see `docs/PRD.md` decision log).
- `gemini` — direct Gemini calls via `google-genai`, needs only `GEMINI_API_KEY`. The
  practical fallback for local dev if you haven't done the Catalyst OAuth setup yet.

Picked via `infrastructure/llm/llm_factory.py`; every caller depends on the `LLMProvider`
interface (`domain/interfaces/llm_provider.py`), never a concrete provider class.

## Response caching

`RESPONSE_CACHE_BACKEND` in `.env` — `in_memory` (dev default, single-process only) or
`catalyst` (real Catalyst Cache REST calls, degrades silently to "no cache" on any error
rather than breaking a request). Used for analytics/sociology/offender-profiling/leads
results, since none of that changes until new case data is seeded — see
`api/services/response_cache.py`'s `cached_or_compute()` helper and
`infrastructure/cache/cache_provider_factory.py`. Not the same thing as the unrelated,
currently-dead `CACHE_BACKEND` var (leftover from an earlier, unused conversation-memory
approach — conversation history is Postgres-backed, not cache-backed).

## API reference

All routes below are mounted with their listed prefix in `api/main.py`. Interactive docs at
`/docs` are the authoritative source; this table is a map of what exists and why.

### Chat & conversations
| Route | Method | Description |
|---|---|---|
| `/chat/` | POST | Streams a chat answer for `{"query", "conversation_id"}`. Requires `X-Owner-Token`, rate-limited (10/min), triggers a real LLM call. |
| `/conversations` | POST | Create a new conversation thread. |
| `/conversations` | GET | List all conversations for the calling `X-Owner-Token`. |
| `/conversations/{id}/messages` | GET | Full message history for one conversation, citations included. |
| `/conversations/{id}` | PATCH | Rename a conversation. |
| `/conversations/{id}` | DELETE | Delete a conversation and its messages. |

### Analytics & map
| Route | Method | Description |
|---|---|---|
| `/analytics/districts` | GET | District-wise case counts. Cached. |
| `/analytics/crime-types` | GET | Crime-type breakdown, optional `?district=`. Cached. |
| `/analytics/trend` | GET | Monthly case volume, optional `?district=&crime_type=`. Cached. |
| `/analytics/forecast` | GET | `{"history", "forecast"}` — linear trend projection, optional `?district=&crime_type=&horizon=&lookback_months=`. Empty forecast when there's under 2 months of history. Cached. |
| `/map/hotspots` | GET | Lat/lng + crime type for all cases, optional `?limit=&crime_type=`, for the clustered hotspot map. |
| `/sociology/breakdown` | GET | Complainant-side demographic breakdown by caste/religion/occupation × crime type, optional `?crime_type=`. Cached. |

### Network graph & decision support
| Route | Method | Description |
|---|---|---|
| `/graph/case/{id}` | GET | Victim/Accused/ArrestSurrender network for one case, Cytoscape-ready `{nodes, edges}`; accused nodes flagged `cross_case`/`case_count` if a repeat offender. |
| `/graph/case/{id}/timeline` | GET | Chronologically sorted case events (registered, incident, info received, arrests, chargesheet if present). |
| `/offenders/case/{id}/leads` | GET | Structural investigative leads: cross-case accused links + similar open cases nearby (same district + crime type). Cached. |
| `/offenders/case/{id}/leads/summarize` | POST | One button-triggered, grounded LLM call producing a short "recommended next steps" paragraph over the leads above. Rate-limited. |

### Offender profiling
| Route | Method | Description |
|---|---|---|
| `/offenders/repeat` | GET | Every accused name appearing in 2+ distinct cases, with a risk tier, optional `?min_case_count=`. Cached. |
| `/offenders/{accused_name}/cases` | GET | Every case a given accused name appears in (name-matched). |
| `/offenders/case/{id}/mo` | GET | On-demand MO extraction for one case via a grounded LLM call. Cached (24h), rate-limited. |
| `/offenders/synthesize-profile` | POST | Combines already-extracted per-case MO summaries into one behavioral profile paragraph. Rate-limited. |

## What's verified vs. not

**Verified live**, end-to-end against real seeded Postgres data, this session: all routes
above, citation persistence across a reopened conversation, the cross-case flag against a
real repeat offender, the investigation timeline's chronological ordering, and both the
positive and negative branches of suggested leads (a real cross-case link found; a real
"nothing found" case correctly returning empty rather than a forced result).

**Not yet verified:** a real browser click-through of the frontend. Every check above was
done at the API/backend level (`curl`/`Invoke-RestMethod` against the running app) — the
frontend builds clean and the same session's automated browser tooling wasn't available to
drive it, so things like the map's cluster-then-decluster-on-zoom behavior, and the general
look of the new timeline/leads panels, still need a human to actually click through
`localhost:5173`.

## Known bug found and fixed during earlier development

`SemanticSearchStrategy` originally called `collection.query(query_texts=...)`, which would
have silently tried to use ChromaDB's default auto-embedder instead of Gemini — wrong, since
the `fir_cases` collection was populated with precomputed Gemini embeddings (see
`rag/embed.py`). Fixed to embed the query via Gemini first, then query by vector
(`collection.query(query_embeddings=...)`). Caught by actually running the code against a
test ChromaDB collection, not just reading it.
