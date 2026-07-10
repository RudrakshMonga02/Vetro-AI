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
