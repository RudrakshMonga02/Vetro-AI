# KSP Datathon — Project PRD & Working Context

**Status:** Living document. Update this file whenever a decision is made, reversed, or new
constraint appears. Treat it as the single source of truth for what we're building and why —
if chat history and this file disagree, this file wins, so keep it current.

**Owner:** Solo (as of this writing). Originally scoped for a 4-person team; task-split section
kept below for reference in case that changes back.

**Time remaining:** ~1 week from time of writing.

---

## 1. Problem Statement (official, verbatim intent)

Build an **Intelligent Conversational AI and Crime Analytics Platform** for Karnataka's State
Crime Records Bureau (SCRB), covering 1100+ police stations, that lets investigators, analysts,
and policymakers query the crime database in natural language and get analytics beyond simple
retrieval.

Required capability areas (from the problem statement):
1. **Conversational Crime Intelligence Interface** — NL chatbot (English + Kannada), context-aware
   follow-ups, voice interaction, PDF export of conversation history.
2. **Criminal Network & Relationship Analysis** — links between accused/victims/locations/financial
   accounts, network visualization, organized-crime/repeat-offender detection.
3. **Crime Pattern & Trend Analytics** — trends by time/geography/crime type/MO, hotspots, seasonal
   patterns.
4. **Sociological Crime Insights** — demographic/socio-economic correlation with crime.
5. **Criminology-Based Offender Profiling** — repeat offenders, behavioral MO analysis, risk scoring.
6. **Investigator Decision Support** — case summaries, timelines, similar-case retrieval, leads.
7. **Financial Crime & Transaction Link Analysis** — money trail / suspicious transaction networks.
8. **Crime Forecasting & Early Warning** — predictive hotspot/pattern alerts.
9. **Explainable AI & Transparent Analytics** — every AI answer must show its evidence trail.
10. **Secure Role-Based Access & Governance** — RBAC for investigator/analyst/supervisor/policymaker
    roles, audit logs, data protection compliance.

## 2. Dataset

**No real KSP data has been provided.** What we have instead:
- An official **ER diagram / DB design doc** (`Police_FIR_ER_Diagram.pdf`) — 26+ tables, this is
  the ground truth schema to build against.
- Our own **synthetic dummy data**: ~1,000 `CaseMaster` rows + child records generated via Faker
  (`db/seed_cases.py`), with fictional case narratives (`BriefFacts`) written by Gemini.
- Real reference data seeded deterministically (not random): 30 Karnataka districts (31 once
  Vijayanagara is included — carved out of Ballari in 2021), real IPC sections, crime
  head/sub-head taxonomy, case categories (FIR/UDR/Zero FIR/PAR).

**Implication:** the pipeline is explicitly designed as a data-source swap, not a rewrite — schema
and lookup seeding stay fixed; only `seed_cases.py`'s Faker generation gets replaced by a real-data
loader if/when real data arrives. Do not assume real data will show up before submission; build and
demo against the synthetic set, but don't let anything be hardcoded in a way that blocks a swap.

## 3. Schema — status vs. official ER diagram

Cross-checked our `db/models.py` (26 tables) against the official ER diagram. Result: ~95% aligned.
Two real mismatches found and fixed so far (see Decision Log):

- ✅ **Fixed:** `ActSectionAssociation.SectionID` was an unenforced bare string. `Section`'s PK is
  composite (`SectionCode`, `ActCode`) since the same section number exists under multiple acts.
  Added a proper `ForeignKeyConstraint` on `(SectionID, ActID)`.
- ✅ **Fixed:** `ArrestSurrender` ↔ `Accused` was modeled as many-to-one (one arrest row per accused).
  Official diagram requires many-to-many via a junction table (`inv_arrestsurrenderaccused`, one
  arrest *event* can cover multiple accused e.g. a joint raid). Added `InvArrestSurrenderAccused`
  junction table with `IsAccused`/`IsComplainantAccused` flags per link. Updated `seed_cases.py` to
  actually generate ~25% joint-arrest events (2+ accused per event) so this shape gets exercised,
  not just declared. Updated both `repository_postgres.py` and `catalyst/repository_catalyst.py`'s
  `get_case_network()` to walk the junction table.
- ⏳ **Open / not yet addressed:** `Inv_OccuranceTime` — official diagram has this as a separate 1:1
  table off `CaseMaster`. We currently fold its fields (`IncidentFromDate`, `IncidentToDate`,
  `InfoReceivedPSDate`, `latitude`, `longitude`) directly into `CaseMaster`. No action needed unless
  real data ships this as a genuinely separate table — then the loader needs a join, not a schema
  change (columns already exist under the right names).

## 4. Mandatory Platform Constraint: Catalyst by Zoho

**This changes the architecture significantly and was not accounted for in the original build.**
Per the datathon rules:
- **Deployment via Catalyst is mandatory, without exception.**
- Using a third-party alternative when a matching Catalyst service exists **may invalidate the
  submission**. This is not a soft suggestion — treat it as a hard requirement per capability.
- Catalyst credits already claimed; a Catalyst project already exists.

### 4.1 Capability → Required Catalyst Service mapping (from official resource doc)

| Capability | Required Catalyst Service |
|---|---|
| Serverless functions/backend logic | Catalyst Serverless (Functions) |
| Docker image deployment | Catalyst AppSail (custom OCI runtime) |
| Full web app in managed runtime | Catalyst AppSail (managed runtime) |
| Frontend / SPA / static site | Catalyst Slate or Web Client Hosting |
| Custom domain + SSL | Catalyst Domain Mappings |
| Relational database | **Catalyst Data Store** |
| Unstructured/semi-structured data | Catalyst NoSQL |
| Object/blob storage | Catalyst Stratus |
| Cache | Catalyst Cache |
| Full-text search (in Data Store) | Catalyst Data Store |
| Text LLMs / RAG / knowledge bases | **Catalyst QuickML** (LLM Serving, RAG) |
| No-code ML pipelines | Catalyst QuickML |
| Automated tabular model training | Catalyst Zia AutoML |
| OCR/Face/Text Analytics/Image Mod/Object Recognition/Barcode/ID Scanner | Catalyst Zia Services |
| Voice (STT/TTS/translation) | Catalyst Zia Services |
| PDF/image report generation, screenshots, headless browser, scraping | Catalyst SmartBrowz |
| User auth / login/signup | **Catalyst Authentication** |
| API routing/throttling/auth in front of Functions | Catalyst API Gateway |
| OAuth tokens for Zoho/3rd-party | Catalyst Connections |
| Scheduled jobs/cron | Catalyst Cron (Cloud Scale) / Job Scheduling |
| Reacting to in-project events | Catalyst Signals + Event Functions |
| Cross-app event bus | Catalyst Signals |
| Multi-step workflow orchestration | Catalyst Circuits |
| Transactional email | Catalyst Mail |
| Push notifications | Catalyst Push Notifications |
| CI/CD | Catalyst Pipelines |

### 4.2 What this means for our existing build

| Current | Must become |
|---|---|
| Postgres (`repository_postgres.py`) as primary | **Catalyst Data Store** primary; Postgres becomes dev/local-only fallback. Repository pattern already supports this swap — `catalyst/repository_catalyst.py` needs to go from "untested draft" to "primary, tested." |
| FastAPI app hosted anywhere | Fine to keep FastAPI, but must deploy on **Catalyst AppSail** |
| Planned custom JWT auth | Scrap it — use **Catalyst Authentication** instead. Role comes from Catalyst user attributes, not a hand-rolled `users` table. |
| Gemini direct calls (`llm_provider.py`, `rag/embed.py`, `rag/generate_briefs.py`) | Route through **Catalyst QuickML** (LLM Serving for plain chat, RAG for knowledge-base Q&A). `llm_provider.py` already has an unfinished `CatalystQuickMLProvider` placeholder for this. |
| ChromaDB vector store | **Not compatible with QuickML's model at all** — see §4.3. Needs architectural change, not a swap. |
| No caching yet | **Catalyst Cache**, not Redis/in-memory as previously planned |
| No voice/PDF/Kannada yet | Voice → **Zia Services**; PDF export → **SmartBrowz**; translation → **Zia Services** |
| No blob storage yet | **Catalyst Stratus** for exported PDFs / any file artifacts |
| No scheduled jobs yet | **Catalyst Cron** for forecasting/early-warning batch jobs |
| No API gateway yet | **Catalyst API Gateway** in front of Functions |

### 4.3 QuickML RAG — critical findings (research done, confirmed via Catalyst docs)

- QuickML RAG is **no-code, document-upload based** — not a programmable embeddings/vector-DB
  pipeline. You upload documents (PDF/Word/text), Catalyst does chunking + embeddings + retrieval
  internally. **No vector database, no manual chunking, no embeddings setup on our end.**
- Powered by **Qwen 2.5 14B Instruct** (not Gemini).
- Comes with a **response breakdown panel** showing exactly which uploaded content was referenced
  — this is a gift for requirement #9 (Explainable AI), effectively free if we use it.
- Separately, **QuickML LLM Serving** lets you call hosted models (Qwen 2.5-14B-Instruct,
  Qwen 2.5-7B-Coder, Qwen 2.5-7B-Vision) via OAuth REST API for non-RAG chat completions. This is
  the direct Gemini-call replacement and appears to be generally available, not gated.
- **⚠️ RAG specifically is in EARLY ACCESS** — requires requesting access
  (`support@zohocatalyst.com`), not self-serve. This is the single biggest schedule risk in the
  whole project right now. **Unresolved as of this writing — must check Catalyst console for our
  project's access status immediately, and email support if not already enabled.**

**Architectural consequence:** our current RAG design (embed structured case rows + Gemini-written
`BriefFacts` into ChromaDB, query via our own vector similarity code) does not map onto QuickML's
model. The QuickML-native pattern is: generate one text/PDF document per case (or per batch) →
upload to QuickML Knowledge Base → query via their hosted RAG API. Our existing `chat_service.py` /
`query_strategy.py` split (classify query → SQL aggregation vs. semantic search) still holds as a
design — only the semantic branch's implementation changes.

**Fallback plan (must keep alive in parallel, do not let RAG block the whole project):** keep the
Gemini+ChromaDB pipeline working as Plan B. If QuickML RAG access doesn't come through in time,
present the architecture as "designed for Catalyst QuickML RAG" with the Gemini version as the
working demo fallback, stated honestly. A documented, honest fallback beats a broken live demo.

### 4.4 Still to verify (open research items)
- Catalyst Data Store: real capabilities/limits for our schema size (dev-tier row caps were
  mentioned in original README: 5,000 rows/table, 25,000 rows/project total in dev environment).
- Catalyst Authentication: exact role/attribute model, whether it natively supports custom roles
  (Investigator/Analyst/Supervisor/Policymaker) or needs a custom claims layer on top.
- Catalyst Cache: API shape, TTL support.
- AppSail: whether FastAPI (Python) is a supported managed runtime, or if this pushes us toward
  Catalyst Functions (which may mean restructuring the FastAPI app into discrete serverless
  functions rather than one deployed app).

## 5. Feature Priority (given synthetic data + 1 week solo)

**Demo-critical (map directly to problem statement's 10 numbered asks):**
- NL chatbot with follow-up context
- Criminal network graph (case-level, and ideally cross-case repeat-offender links)
- Crime hotspot map
- Trend/pattern analytics dashboard
- Explainability surfaced in UI (which SQL query ran / which documents were retrieved — QuickML RAG
  gives us document-level explainability for free if access comes through)
- Some RBAC + audit logging, even partial, to visibly hit requirement #10

**High-value if time allows:**
- Repeat-offender risk scoring (simple aggregation: count prior `Accused` rows per person across
  cases — no ML needed for a defensible v1)
- Cross-case link detection (same accused name/ID across multiple `CaseMaster` rows)
- PDF export of chat history (via SmartBrowz now, not a Python PDF lib)

**Explicitly required but not yet built at all:**
- Kannada language support
- Voice interaction

**Can be simplified/faked for demo purposes:**
- True crime forecasting/ML — a naive trend extrapolation is enough to demonstrate "predictive
  insight" without building real ML infra, given time constraints.

## 6. Decision Log

Chronological. Add a new entry every time a real decision is made — this is what keeps this
document trustworthy as the source of truth.

- **[Schema]** Added `InvArrestSurrenderAccused` junction table; removed direct
  `AccusedMasterID` FK from `ArrestSurrender`. Updated `seed_cases.py`, `repository_postgres.py`,
  `catalyst/repository_catalyst.py` accordingly.
- **[Schema]** Fixed `ActSectionAssociation.SectionID` to be a real composite FK against `Section`.
- **[Platform]** Confirmed Catalyst deployment is mandatory; began mapping existing architecture
  onto required Catalyst services (see §4).
- **[Platform/Risk]** Discovered QuickML RAG is early-access gated; flagged as top schedule risk;
  decided to keep Gemini+ChromaDB pipeline alive as fallback rather than block on Catalyst access.
- **[Team]** Team size changed from 4 to solo. Task-split plan in §7 is now historical reference,
  not an active assignment.
- **[Bug fix]** Frontend white screen: `lucide-react@0.383.0` doesn't support React 19 as a peer
  dependency, so `npm install` was failing with `ERESOLVE` and a stale/partial `node_modules` was
  being used by `vite` anyway. Bumped `lucide-react` to `^0.487.0` in `ksp-frontend/package.json`.
- **[Architecture — Stage 0 executed]** Scaffolded the Clean Architecture folder structure from
  `docs/ARCHITECTURE.md` (`domain/`, `application/`, `infrastructure/`, `presentation/`, `config/`,
  each with the sub-folders per module). Moved (not copied) the repository layer into it:
  `db/repository_base.py` → `domain/interfaces/case_repository.py`;
  `db/repository_postgres.py` → `infrastructure/persistence/postgres_repository.py`;
  `catalyst/repository_catalyst.py` → `infrastructure/persistence/catalyst_repository.py`;
  `db/repository_factory.py` → `infrastructure/persistence/repository_factory.py`. Updated all 5
  consumer files (`chat_service.py`, `query_strategy.py`, `map_routes.py`, `graph.py`,
  `analytics.py`) to import from the new paths. Old files deleted, empty `catalyst/` folder removed.
  All touched files verified to compile. `db/models.py`, `db/connection.py`, `db/seed_*.py` stay put
  for now (not part of Stage 0's scope — models/connection are a later migration step).
  Also deleted the dead `frontend/` (incomplete, no build config) and `frontend_test/` (throwaway
  test page) folders per earlier cleanup discussion, since this was a natural moment for it.
  **Not yet moved:** `api/main.py` and `api/routes/*` still live under `api/`, not yet under
  `presentation/` — next step of the migration, not done in this pass to keep the change reviewable
  in one sitting.
- **[Architecture — Stage 1 executed]** Split the existing (already well-designed)
  `api/strategies/llm_provider.py` into proper layers: `LLMProvider` interface →
  `domain/interfaces/llm_provider.py`; `GeminiProvider` → `infrastructure/llm/gemini_provider.py`;
  `CatalystQuickMLProvider` placeholder → `infrastructure/llm/catalyst_quickml_provider.py`;
  factory → `infrastructure/llm/llm_factory.py`. Updated `chat_service.py`'s import, deleted the old
  single-file version. No behavior change — this file was already correctly designed (interface +
  adapter + factory), it just needed to move into the right layer folders. Verified via `py_compile`
  on all touched files.

- **[Feature — Stage 2, solo re-sequenced]** Built conversation memory (context-aware follow-up
  questions) — an explicit, previously-unbuilt problem-statement requirement (§1 item 1). Followed
  the Catalyst-first policy explicitly requested: interface (`domain/interfaces/conversation_memory.py`)
  + `InMemoryConversationMemory` (works today, single-instance only — documented limitation, not
  fit for multi-instance AppSail deployment) + `CatalystConversationMemory` placeholder (Catalyst
  Cache is the mapped service per §4.1; NotImplementedError until Cache credentials are confirmed
  working) + factory (`CACHE_BACKEND` env var, singleton pattern — required here unlike the other
  factories, since `ChatService` is constructed per-request and a non-singleton in-memory store
  would silently lose all history every request). `ChatService.stream_answer()` now takes a
  `session_id`, feeds the last 6 turns into the prompt, and stores the turn only after the full
  answer streams successfully (avoids poisoning future context with a partial/failed response).
  `/chat` route generates a `session_id` if none provided and returns it via `X-Session-Id` header;
  had to add `expose_headers=["X-Session-Id"]` to CORS config since browsers hide custom response
  headers from JS by default even with `allow_headers=["*"]` (that only covers request headers).
  Frontend persists the session id in `sessionStorage` (per-tab, not per-browser — a fresh tab
  starts a new conversation, a refreshed tab continues the old one). Added `LLM_BACKEND` and
  `CACHE_BACKEND` to `.env` template. All touched files verified via `py_compile`.
  **Pre-deployment blocker to remember:** `InMemoryConversationMemory` will break under multiple
  AppSail instances — must swap to `CatalystConversationMemory` (or confirm AppSail will only ever
  run a single instance for this app) before relying on this in production.

- **[Bug fix — real logic bug, not just plumbing]** First live chatbot test surfaced two gaps:
  1. `"how many cases do we have"` was answered by having the LLM sum a district-count breakdown
     that was silently truncated to 15 rows (Karnataka has 31 districts) — an unverified guess
     dressed up as a number. Fixed by adding `get_total_case_count()` (a real `COUNT(*)`-equivalent)
     to `CaseRepository` (both Postgres and Catalyst implementations) and using it directly in
     `SQLQueryStrategy` instead of relying on LLM arithmetic over partial data.
  2. `"list all criminals with FIRs"` correctly said it had no data — because the RAG embeddings
     only ever contained `CaseMaster`/`BriefFacts` text, never `Accused` table data, so semantic
     search had nothing to find. Added `get_accused_list()` to the repository interface + both
     implementations, plus a new `EntityListStrategy` in `query_strategy.py` triggered by
     "list all", "criminals", "accused", "offenders", "suspects" etc., checked *before* the
     aggregate-keyword check so these don't get misrouted to the district/crime-type SQL summary
     (which has no person-level data in it).

- **[Platform — Docker+AppSail path confirmed, request-scoped SDK constraint found]** Researched
  AppSail's actual container/networking model. Confirmed: AppSail accepts arbitrary OCI containers
  (FastAPI+Uvicorn included) — this is a first-class, compliance-safe path per §4.1's own mapping
  ("Docker image deployment | Catalyst AppSail (custom OCI runtime)"), not a workaround. Key
  constraints found: (1) must bind `0.0.0.0` and read the port from
  `X_ZOHO_CATALYST_LISTEN_PORT`, injected at runtime, not build time; (2) no TCP/SQLAlchemy access
  to Catalyst Data Store — must go through `zcatalyst_sdk`; (3) the SDK is request-scoped
  (`zcatalyst_sdk.initialize(req=request)`), meaning it cannot be used in standalone scripts
  (`db/seed_cases.py`, `db/init_db.py`) or in `on_event("startup")` hooks without a workaround —
  **the workaround itself (ZCQL / API-key-based auth for background/non-request contexts) is
  still unresolved and is the next open research item, not yet safe to assume away.**
  **Downstream impact, not yet resolved:** `catalyst_repository.py` is a bigger build than "test
  the untested draft" — it likely needs a partial rewrite around SDK calls instead of ORM queries.
  `CatalystConversationMemory` (Catalyst Cache) has the same request-scope question to answer.
  Seed/init scripts may need a documented workaround or a one-time manual/console-based path.

- **[Infra — Phase 0 closeout + Docker walking-skeleton scaffolding]** Closed the one open Phase 0
  item: CORS was still `allow_origins=["*"]` despite `CORS_ALLOWED_ORIGINS` already existing in
  `.env.example` — the var was defined but never actually read in `api/main.py`. Fixed: `main.py`
  now reads `CORS_ALLOWED_ORIGINS` (comma-separated) from env and **fails loudly at startup** if
  it's unset, rather than silently falling back to a wildcard — verified both the happy path (env
  set → correct origins loaded) and the failure path (env unset → `RuntimeError` at import time,
  not a silent security hole) with direct tests. Added the missing var to `.env` itself (was only
  in `.env.example`). Pinned all of `requirements.txt` (was previously unpinned, a Phase 5 item
  pulled forward since we were already in these files) — **this surfaced a real dependency
  conflict**, not just a formality: `zcatalyst-sdk==1.4.0` hard-pins `typing-extensions~=4.12.1`,
  which is incompatible with `google-genai>=2.0.0` (needs `>=4.14.0`) and `pydantic>=2.12` (needs
  `>=4.14.1`). Resolved by pinning `google-genai==1.65.0` (last 1.x line still on the looser
  `>=4.11.0` constraint) and `pydantic==2.11.0` (last line on `>=4.12.2`) — verified the full
  `pip install -r requirements.txt` resolves cleanly and the app boots and registers all routes
  under these pinned versions. **Worth knowing:** this caps how far `google-genai`/`pydantic` can
  be bumped later without either an update to `zcatalyst-sdk` upstream or dropping the exact-pin
  constraint on `typing-extensions` — revisit if a future feature needs a newer `google-genai` API.
  Added `Dockerfile` (`python:3.13-slim`, matching `app-config.json`'s `python_3_13` stack for
  consistency) and `.dockerignore`. Dockerfile reads `X_ZOHO_CATALYST_LISTEN_PORT` at container
  start via shell-form `CMD` (not exec-array form, since the var must be shell-expanded at
  runtime, not baked in at build time), falls back to `9000` for local `docker run`. **Not yet
  verified: an actual `docker build`/`docker run` and a real AppSail deploy** — no Docker daemon
  available in the environment this was built in, so only the underlying Python app (pinned deps,
  CORS logic, route registration) was verified directly via `uvicorn`; the container build itself
  and the live AppSail push are still open verification steps, run them next.

- **[Branding]** Completed the folder-rename housekeeping item flagged in `ARCHITECTURE.md`
  ("Repo/folder renames to `vetro-ai` are a housekeeping task, not urgent"). Renamed project root
  to `Vetro-AI/`, `ksp-frontend/` to `vetro-ai-frontend/`, updated `ksp-frontend/package.json`'s
  `name` field, `index.html`'s `<title>`, and `README.md`'s title/intro. Updated root `.gitignore`
  frontend-path entries to match the renamed folder. Left `docs/PRD.md`'s existing historical
  entries referencing the old `ksp-frontend/` path untouched (this file's own stated principle is
  to be a trustworthy chronological log — rewriting past entries to match current naming would
  undermine that). Did not rename the local Postgres database name (`ksp_datathon`, referenced in
  `README.md`'s setup instructions) — that's a local dev identifier, not project branding, and
  renaming it would require anyone with an existing local DB to also rename theirs; flagging here
  rather than changing it silently.

- **[Bug fix — conversation memory existed but follow-ups still didn't actually work]** Diagnosed
  precisely: `ConversationMemory` (in-memory + Catalyst Cache implementations, factory, interface)
  was already fully built and wired into `ChatService`, and history was already being fed into the
  final LLM prompt as text. But `classify_query()` and every `QueryStrategy.build_context()` in
  `query_strategy.py` only ever received the *current* message — never history. So a follow-up like
  "only from 2022" after "show murders in Bangalore" would get embedded/classified as the literal
  string "only from 2022" alone, retrieving irrelevant context; the LLM seeing prior turns as text
  in the final prompt can't undo already-wrong retrieval upstream of it. Fixed with a new
  `api/strategies/query_rewriter.py`: before `classify_query()`/`build_context()` run, an LLM call
  rewrites the current message into a standalone query using history (e.g. "only from 2022" →
  "murders in Bangalore in 2022"), and that rewritten query — not the original — flows through the
  existing, unchanged strategy pipeline. The user's original phrasing is still what's shown in the
  final prompt and stored back into memory, so history stays in the user's own words for future
  rewrite calls, not a chain of progressively-rewritten text. Skips the rewrite LLM call entirely
  on the first turn of a conversation (no history to resolve against). Degrades gracefully to the
  original query, not an exception, if the rewrite call itself fails. Added `generate()` (plain,
  non-streaming) to the `LLMProvider` interface for this — `stream_generate()` alone doesn't fit a
  short utility call where the caller needs the whole result before doing anything with it;
  implemented in both `GeminiProvider` and the `CatalystQuickMLProvider` placeholder, so the
  interface stays satisfiable by both. Verified in isolation with a fake `LLMProvider`: follow-up
  correctly resolved using 2-turn history, first-turn (no history) correctly skips the LLM call and
  returns the query unchanged, and a simulated rewrite failure correctly degrades to the original
  query rather than raising. Full app re-verified to boot cleanly with all of the above wired in.

- **[Feature — multi-conversation chat, persisted, replacing the ephemeral session model]** Built
  "Investigation A/B/C..." style multi-session chat (like ChatGPT's conversation list), each with
  genuinely independent, persisted history — not a UI-level filter over one shared history. This
  is a bigger architectural change than it sounds: the old `ConversationMemory` abstraction
  (in-memory / Catalyst Cache, `infrastructure/cache/`) was built as an ephemeral prompt-building
  cache keyed by an auto-generated `session_id` — fine for "does the bot remember the last
  message," not fit for a persisted, listable, switchable conversation history that survives a
  server restart. Replaced it with a new `ConversationRepository` (mirrors the `CaseRepository`
  interface/factory pattern) backed by two new Postgres tables, `Conversation`
  (`id, title, created_at, updated_at`) and `Message` (`id, conversation_id, role, content,
  timestamp`) — `db/models.py`. `ChatService` now reads/writes through this repository instead of
  the cache; `query_rewriter.py` needed zero changes since both abstractions share the same
  history shape (`[{'role', 'text'}, ...]`) on purpose. New `api/routes/conversations.py`: create,
  list (ordered by `updated_at` desc — directly drives sidebar order, no client-side re-sorting),
  get messages, rename, delete (cascades to messages via the SQLAlchemy relationship). `chat.py`'s
  `ChatRequest` now takes a required `conversation_id` (int) instead of an optional `session_id`
  (str/uuid) — conversations are created explicitly via `POST /conversations` before the first
  message is ever sent, not auto-generated on first chat call; `/chat/` 404s cleanly on an unknown
  `conversation_id` rather than silently creating orphaned messages. Titles auto-generate from the
  first user message (truncated to 60 chars, ChatGPT-style), only while the conversation still has
  its "New Investigation" placeholder title — never overwrites a title a rename endpoint has
  already set. Frontend: new `Sidebar.jsx` (list, create, delete, relative-timestamp display,
  matches the existing "incident log" dark/amber aesthetic) and `ChatApp.jsx` (owns conversation
  list state, auto-creates a first conversation on empty first-run rather than showing a blank
  "create one" prompt) sit above the existing `ChatInterface.jsx`, which is now a controlled
  component keyed by a `conversationId` prop — reloads message history via
  `GET /conversations/{id}/messages` on every conversation switch, sends `conversation_id` instead
  of managing its own `sessionStorage` session id. Old `X-Session-Id` response header and its
  CORS `expose_headers` entry removed (no longer meaningful). Verified: full repository test
  (independent memory across two conversations, correct auto-title, correct sidebar ordering,
  rename, cascade delete on removal) all passed against a real SQLite-backed run; full API test
  (create/list/get-messages/rename/delete, plus 404 guards on `/chat/` and `/conversations/{id}
  /messages` for unknown ids) all passed against a live server; all four new/changed frontend
  files (`Sidebar.jsx`, `ChatInterface.jsx`, `ChatApp.jsx`, `App.jsx`) syntax-checked cleanly via
  `esbuild`. **Not yet verified: a real browser run** — no way to launch an actual browser/Vite
  dev server in the environment this was built in, so the visual result and click-through behavior
  (does the sidebar actually look right, does switching conversations feel instant, does the
  "New Investigation" auto-create-on-empty flow work in practice) still need a real local
  `npm run dev` check before being called done. The old `ConversationMemory` cache classes
  (`infrastructure/cache/`) are now dead code, not deleted — left in place in case a fast
  in-process cache is useful again later (e.g. as a read-through cache in front of the repository),
  but nothing calls them anymore; worth removing outright if they're still unused by submission
  time, dead code left in a codebase invites confusion about which system is authoritative.

- **[Security — vulnerability review + fixes]** Reviewed the conversations/chat feature built in
  the prior session against standard web-app security concerns, given this handles (eventually
  real) crime case data. Found and fixed:
  1. **Critical — no authorization on conversations.** `Conversation`/`Message` had no ownership
     field at all; any `conversation_id` was globally readable/renameable/deletable by anyone who
     could guess/enumerate the sequential integer id. Fixed with a stopgap `owner_token` column on
     `Conversation` (NOT real multi-user auth — see `db/models.py`'s docstring on this) — every
     read/mutate route now requires an `X-Owner-Token` header, and a wrong/missing token gets the
     SAME 404 as a nonexistent id (never a distinct 403), so ownership can't be probed. Token is
     **client-generated once per device/browser** (`vetro-ai-frontend/src/lib/ownerToken.js`,
     `crypto.randomUUID()` in `localStorage`) and shared across all of that device's conversations
     — first implementation attempt wrongly had the server mint a new token per conversation,
     which would have broken `list_conversations()` (each token would only ever match one
     conversation) — caught and fixed before shipping.
  2. **Critical — no rate limiting on `/chat`.** Direct cost/DoS exposure (unauthenticated,
     unlimited, billed Gemini calls per request). Added `slowapi`, keyed by remote IP
     (`api/rate_limiter.py`, one shared `Limiter` instance — an earlier draft accidentally
     created two separate `Limiter()` objects, which would have silently broken slowapi's
     expectations; fixed before shipping), `10/minute` on `/chat` specifically.
  3. **High — non-parameterized ZCQL queries** in `catalyst_repository.py` (f-string
     interpolation of `case_id`/`arrest_id`/`limit`). Route-level `int` type hints were the only
     actual protection; added explicit `int()` casts inside the repository methods themselves as
     defense-in-depth, so this isn't solely dependent on every future caller going through a
     type-coerced route.
  4. **Medium — stale `.dockerignore` path** (`ksp-frontend/` instead of `vetro-ai-frontend/`,
     leftover from the project rename) — fixed, was silently not excluding anything.
  5. **Medium — no input length caps.** Added `max_length` to `ChatRequest.query` (2000 chars),
     conversation title fields (200 chars), and the owner-token header itself.
  Also updated all three frontend components (`ChatApp.jsx`, `ChatInterface.jsx`) to send the new
  `X-Owner-Token` header on every request — without this the app would have been completely
  broken by the ownership fix (every call 401ing), since the frontend from the prior session
  predates this security pass entirely.
  **Still open, not fixed in this pass:** sequential integer ids remain guessable in principle
  (mitigated but not eliminated by the ownership check); real per-user accounts (Catalyst
  Authentication + RBAC) still needed before this is genuinely production-appropriate — the
  owner_token scheme is explicitly a stopgap, not a destination.


## 7. Original 4-Person Task Split (kept for reference — not current)

- **Data/Backend core:** schema fixes, real LLM calls working, repository layer
- **Auth/Security/System design:** auth, RBAC, audit logging, caching, rate limiting
- **Frontend:** single consolidated React UI (chat + network graph + hotspot map + analytics)
- **Features:** Kannada, voice, PDF export, offender risk scoring, cross-case link detection

Now solo — re-sequence as a single-person priority list, not parallel tracks. Revisit §5 for
current priority order.

## 8. Known Repo Cleanup Items
- ✅ Done: dead `frontend/` and `frontend_test/` scaffolds deleted (Stage 0 pass).
- ⏳ Open: `api/main.py` + `api/routes/*` still need to move into `presentation/api/` per
  `ARCHITECTURE.md` — deferred to keep the Stage 0 change reviewable in one sitting.

## 9. How We Work Together (process note, not product spec)

- This file is updated by Claude whenever a decision is made in conversation, and should be
  re-read at the start of any new session to restore context cheaply.
- When in doubt about priority, defer to §5 and the problem statement in §1 — not to what feels
  technically interesting to build.
- Given solo + 1 week, bias toward: (1) whatever unblocks the live demo, (2) whatever maps
  directly to a numbered problem-statement requirement, (3) polish, in that order.

- **[Feature] Better response rendering (Markdown).** Two parts: (1) `chat_service.py`'s prompt
  now explicitly instructs the LLM to format answers in Markdown (headings for distinct topics,
  **bold** for key figures, bullet/numbered lists, blockquotes for standout observations) while
  telling it not to force structure on genuinely simple one-line answers. (2) Frontend: added
  `react-markdown` + `remark-gfm`, new `MarkdownMessage.jsx` component with custom renderers for
  every element (headings, bold, lists, blockquotes, inline/block code, tables, links) styled to
  match the existing "incident log" dark/amber palette rather than react-markdown's default
  browser styles -- so this reads as designed-in, not bolted-on. Replaced the old flat
  `whitespace-pre-wrap` `<p>` in `ChatInterface.jsx` with this component for assistant responses
  only (user queries stay plain text, no need for markdown there). Streaming note, documented in
  the component itself: re-parses the full accumulated text on every streamed chunk; react-markdown
  tolerates incomplete/unclosed markdown without throwing, worst case a `**` renders literally for
  the handful of milliseconds before its closing marker streams in.
  **Not yet verified in a real browser** -- no way to run `npm install`/`npm run dev` or esbuild in
  this sandbox (no network access); needs a real local check that `react-markdown`/`remark-gfm`
  install cleanly and the rendered output actually looks right before considering this done.

- **[Feature — client-side PDF export of a conversation, first item off the chat feature list]**
  Per the fuller problem-statement context provided this session (multilingual/Kannalish, voice
  I/O, local PDF export, XAI citation badges, admin CRUD -- see chat requirements discussion), PDF
  export was picked to build first: self-contained, no Catalyst-service dependency, no priority
  ordering blocked on unresolved Catalyst QuickML/Zia access status. New
  `vetro-ai-frontend/src/lib/exportPdf.js`, wired into `ChatInterface.jsx` as an "Export PDF" button
  in the chat header (disabled with no messages or mid-stream). Uses `html2pdf.js` (html2canvas +
  jsPDF) so it renders whatever is actually on screen -- markdown, tables, and any future embedded
  images/diagrams (e.g. a network graph) -- rather than re-deriving formatting from raw message
  text, so it stays correct automatically as `MarkdownMessage` evolves. Filename/heading come from
  the conversation's title, threaded down from `ChatApp.jsx`.
  **Two real bugs found and fixed by actually running this in a real (Playwright-driven) browser,
  not just reading the code:**
  1. The initial implementation cloned the message-log node and moved the clone off-screen (`left:
     -99999px`) to capture the full conversation instead of just the scrolled-into-view portion.
     This produced a near-empty 3KB PDF every time -- html2canvas re-clones the whole document into
     its own iframe to measure/render the target, and an element parked thousands of pixels outside
     the viewport gets measured with **height 0** in that internal clone (confirmed directly:  my
     own clone measured a correct non-zero `offsetHeight` right up until the moment html2canvas
     touched it). Fixed by capturing the **live element in place** instead (temporarily setting
     `height: auto; overflow: visible` on the actual node, capturing, then restoring), accepting a
     brief in-place layout expansion during capture rather than fighting html2canvas's off-screen
     clone-measurement behavior.
  2. Even after that fix, the exported PDF rendered on a **plain white background** -- illegible,
     since the UI's light-gray/amber text colors are designed for the dark "incident log" theme.
     Root cause: the message-log element itself has no explicit background (it only looks dark by
     inheriting from an ancestor), and html2canvas only renders the captured element's own subtree,
     not its ancestors. The `html2canvas: { backgroundColor: ... }` config option alone didn't take
     effect reliably; fixed by setting the background color directly on the element being captured
     (temporarily, restored afterward) as the deciding fix rather than only relying on that option.
  Verified end-to-end with a real Playwright-driven Chromium session against a live `uvicorn` +
  Postgres + real Gemini backend: sent a live chat query, waited for the real streamed response,
  clicked Export PDF, confirmed a real download event fired, then extracted the embedded image from
  the resulting PDF (via `pypdf`) and visually confirmed correct dark-theme background, correct
  text/heading/label colors, and correct content (query + response + export heading) -- not just
  "the button doesn't crash."

- **[Bug fix — Gemini model deprecated, found while testing PDF export]** Live chat testing (needed
  to get a real streamed response to export) surfaced `google.genai.errors.ClientError: 404
  NOT_FOUND` on every `/chat/` call: `models/gemini-2.5-flash` -- the hardcoded default in
  `infrastructure/llm/gemini_provider.py` -- is no longer available to this API key even though it
  still appears in `client.models.list()`. Root-caused by listing models actually available for
  `generateContent` and testing directly against the live API (not guessing a replacement name).
  Fixed by switching the default to `gemini-flash-latest`, Google's floating alias to the current
  recommended flash model -- deliberately chosen over pinning another specific dated model name
  again, since pinning is exactly what caused this breakage once Google deprecated the old one for
  new keys.

- **[Cleanup — dead code and a stale duplicate project snapshot removed]** Found while reading the
  repo end-to-end this session, unrelated to any single feature: `db/config/`, `db/domain/`,
  `db/infrastructure/`, `db/docs/`, `db/ksp-frontend/` were an entire stale, pre-rename copy of the
  domain/infrastructure layers, this PRD, and the frontend, accidentally nested inside `db/` and
  tracked in git since the very first commit -- diverging from their real top-level counterparts
  (e.g. `db/docs/PRD.md` was missing this file's last ~160 lines of history; `db/ksp-frontend/
  package.json` still said `"name": "ksp-frontend"`). Nothing imported from them; confirmed via
  grep before deleting. Also removed three more dead files nothing imports anymore, left behind by
  earlier migration stages that claimed (incorrectly) to have deleted them: `db/repository_base.py`,
  `db/repository_factory.py`, `db/repository_postgres.py` (superseded by `domain/interfaces/
  case_repository.py` + `infrastructure/persistence/*`), and `api/strategies/llm_provider.py`
  (superseded by `domain/interfaces/llm_provider.py` + `infrastructure/llm/*`). Updated `README.md`'s
  stale references to all of the above (old file paths in the Repository/Factory pattern sections,
  a "Test frontend" section describing the long-deleted `frontend_test/index.html`) to reflect
  current reality. Did not touch this file's (`docs/PRD.md`) own historical decision-log entries
  that reference the old paths -- those describe what was true *at the time*, and rewriting history
  here would undermine the "trustworthy chronological log" principle stated at the top of this file.

- **[Config] `.env.example` brought in sync with what the code actually reads.** It only listed
  `GEMINI_API_KEY`, `SUPABASE_*`, and `CORS_ALLOWED_ORIGINS` -- missing `DATABASE_URL`,
  `DATA_BACKEND`, `LLM_BACKEND`, and `CACHE_BACKEND`, all of which are real `os.getenv()` reads
  (`db/connection.py`, `infrastructure/persistence/repository_factory.py`, `infrastructure/llm/
  llm_factory.py`, `infrastructure/cache/conversation_memory_factory.py`) that were previously
  undocumented anywhere a new clone of this repo would see them. Added with comments noting their
  defaults, so a fresh `.env` built from the example still boots correctly without them explicitly
  set.

- **[Feature — PDF export rebuilt as real text, not a screenshot]** User tested the html2canvas
  version from the previous entry and asked directly: "is this a picture?" -- yes, and on
  reflection a genuine defect for this use case, not just a style question: an investigator
  exporting a conversation as an evidence/reference record wants selectable, searchable, copyable
  text, not a raster image, and any future clickable citation badge (`[Source: FIR #412/2025]`)
  needs to stay a *real* link, which a screenshot can never provide. Rebuilt
  `exportPdf.js` around `jsPDF` directly (dropped `html2pdf.js`/`html2canvas` as dependencies
  entirely) plus `unified`/`remark-parse`/`remark-gfm` to parse each assistant message's markdown
  into an AST and walk it into properly laid-out PDF text -- headings, bold/italic, ordered/
  unordered lists, blockquotes (with a rendered accent bar), fenced code blocks (monospace +
  background), GFM tables, and real clickable links, all via a hand-rolled word-wrap-with-mixed-
  styles renderer (jsPDF has no native rich-text wrapping). Reads straight from the `messages`
  array already held in `ChatInterface` state rather than the rendered DOM at all -- this also
  fully sidesteps the html2canvas off-screen-measurement bug from the previous entry, since there's
  no DOM capture step anymore. Switched the color palette from the on-screen dark theme to a
  printable white-background/dark-text one (screen colors were tuned for a dark background and
  would be low-contrast on white paper). jsPDF and the markdown-parsing libs are dynamically
  imported inside `exportConversationToPdf()` (not static top-level imports) so they stay out of
  the initial page bundle, matching the lazy-loading discipline the original html2canvas version
  already had -- confirmed via a production build that only `jspdf`'s chunk is pulled in on click,
  `unified`/`remark-parse`/`remark-gfm` are already eagerly bundled anyway via `MarkdownMessage.jsx`
  so those specific dynamic imports don't achieve further splitting (harmless, not a regression).
  **Two more real bugs found by directly testing the actual rendering primitives, not just reading
  the code:** (1) the unordered-list bullet character (`•`, U+2022) came out as a mangled
  replacement glyph under text extraction -- jsPDF's default core fonts only support WinAnsi
  encoding; switched to a plain `-`. (2) the document title (built from the conversation's
  auto-generated title, which can be long) was being drawn unwrapped and ran off the page edge;
  fixed with `doc.splitTextToSize()`. Verified directly and independently of any PDF-rendering
  tool's own quirks: (a) called `jsPDF.splitTextToSize()` with the exact title string in isolation
  and confirmed it now returns two full, correctly-broken lines, not one truncated line; (b)
  extracted the real text layer of a freshly re-generated export via `pypdf` and confirmed the
  body content -- headings, a numbered top-5 list, district names and counts -- came back exactly
  right and in order. (One caveat surfaced and deliberately not chased further: `pypdf`'s own
  text-extraction heuristic still garbles the *wrapped title line specifically* in its reconstructed
  output, despite the line being provably correct at the rendering-call level per (a) above -- a
  known limitation of that extraction heuristic around line-wrap boundaries, not a defect in the
  generated PDF; real PDF viewers render it correctly.) Full round-trip (live chat query -> live
  Gemini response -> Export PDF -> real download -> text extraction) re-verified end-to-end via a
  Playwright-driven Chromium session against the running app, same as the previous entry.

- **[Bug fix — Critical, `.gitignore` was silently untracking `vetro-ai-frontend/src/lib/` entirely]**
  Found while double-checking that this session's new `exportPdf.js` would actually get committed:
  `git status` showed it as untracked, expected for a new file -- but so was the *existing*
  `ownerToken.js`, which should never have shown up as untracked at all. Root cause: `.gitignore`'s
  standard Python boilerplate section uses unanchored patterns (`build/`, `dist/`, `lib/`, `lib64/`
  -- no leading `/`), which git matches at *any* depth, not just the repo root. `lib/` was silently
  matching `vetro-ai-frontend/src/lib/` too. Practical impact: **`ownerToken.js` -- the file
  implementing the owner-token conversation-auth stopgap from the earlier security review entry --
  was never actually tracked in git**, on any commit since it was written; anyone cloning this repo
  fresh would get a build that imports a file that doesn't exist. Fixed by anchoring the four
  colliding patterns to the repo root (`/build/`, `/dist/`, `/lib/`, `/lib64/`), preserving their
  original intent (ignore Python packaging artifacts at the root) without catching same-named
  directories elsewhere in the tree. `vetro-ai-frontend/src/lib/ownerToken.js` and the new
  `exportPdf.js` both now show up correctly as addable. **Worth a repo-wide double check next time
  there's a "why is this file missing after clone" surprise** -- this class of bug (silently-ignored
  file, no error, no warning) is exactly the kind that survives unnoticed across many commits.
