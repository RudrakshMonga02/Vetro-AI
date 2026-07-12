# Vetro AI — Architecture Document

**Status:** Living document, companion to `docs/PRD.md`. PRD tracks product decisions and the
running Decision Log; this file tracks *structural* architecture decisions. Update both when a
change touches both product scope and code structure.

This document was originally written as a **target design** proposing a
`domain/application/infrastructure/presentation` four-layer split. That specific folder split
was **not adopted** — see "What actually shipped" below for why, and for the structure this
codebase actually uses today.

---

## Core principle: Clean Architecture, dependencies point inward only

This part of the original design held and is genuinely how the codebase is built:

```
Routes (api/)  →  Domain (interfaces)
                        ↑
         Infrastructure (adapters) implements these
```

`domain/interfaces/` defines interfaces (`CaseRepository`, `ConversationRepository`,
`LLMProvider`, `CacheProvider`) and imports nothing external. Route/service code in `api/`
only depends on those interfaces, never on a concrete Postgres/Gemini/Catalyst class
directly — concrete classes are constructed by a factory function and injected at the call
site.

**This is what actually enables everything else in this doc**: swapping LLM providers, DB
backends, or Catalyst services is "write a new adapter + flip an env var," not "rewrite the
app." This has already paid off twice in practice — the LLM backend was switched from Gemini
to Catalyst QuickML, and the response cache backend was switched from an in-memory dict to
real Catalyst Cache, both as adapter-swap + config changes with zero changes to any route or
service code.

## What actually shipped (the real folder structure)

```
vetro-ai/
├── domain/
│   ├── interfaces/          # CaseRepository, ConversationRepository, LLMProvider,
│   │                        # CacheProvider — the only 4 interfaces actually in use
│   └── entities/            # scaffolded, empty — no entity classes were needed in
│                             # practice; repository methods return plain dicts instead
├── infrastructure/
│   ├── llm/                 # gemini_provider, catalyst_quickml_provider, llm_factory
│   ├── persistence/         # postgres_repository, catalyst_repository (partial stub),
│   │                        # repository_factory, postgres_conversation_repository,
│   │                        # conversation_repository_factory
│   ├── cache/                # in_memory_cache_provider, catalyst_cache_provider,
│   │                          # cache_provider_factory
│   ├── catalyst_oauth.py      # shared OAuth session for direct Catalyst REST calls
│   │                          # (QuickML + Cache both bypass the zcatalyst_sdk's HTTP
│   │                          #  layer this way — see docs/PRD.md decision log)
│   ├── auth/, storage/, vectorstore/   # scaffolded, empty — not built yet (see below)
├── api/
│   ├── main.py                # FastAPI app, CORS, rate limiter, router mounts
│   ├── rate_limiter.py        # shared slowapi Limiter instance
│   ├── routes/                 # chat, conversations, analytics, map_routes, graph,
│   │                            # offenders, sociology — THIN, call services/repos only
│   ├── services/                # chat_service (orchestration), mo_extraction (LLM
│   │                             # prompts), response_cache (cached_or_compute helper),
│   │                             # forecasting (linear trend projection)
│   └── strategies/              # query_strategy.py — SQL vs semantic-search routing
│                                 # for the chatbot; ChromaDB is called directly here,
│                                 # not behind a VectorStore interface
├── db/                          # SQLAlchemy models, connection, seed scripts
├── rag/                         # one-time Gemini brief generation + ChromaDB embedding
├── pipeline.py                  # runs db + rag steps in order
├── vetro-ai-frontend/            # single React (Vite) app
└── docs/ (PRD.md, ARCHITECTURE.md)
```

**Not present, and don't recreate them:** `application/`, `presentation/`, `config/` were
scaffolded early as an attempt at the original four-layer split, but ended up as empty
`__init__.py` stubs with zero real code and zero imports anywhere — the project settled on
the flatter `domain → infrastructure → api` structure above instead, which gets the same
dependency-inversion benefit (routes depend on interfaces, never concrete adapters) with one
fewer layer to navigate. If you find those three folders still present in the repo, they're
dead weight, not a return to some deprecated old structure — they were never load-bearing.

`domain/entities/`, `infrastructure/auth/`, `infrastructure/storage/`,
`infrastructure/vectorstore/` are also currently just empty scaffolding — real candidates for
future work (see "Catalyst Integration" table below), not dead in the same sense, but nothing
depends on them today.

## Design Patterns actually in use

- **Repository** — `CaseRepository` / `ConversationRepository` interfaces, with Postgres
  implementations live and a partial Catalyst Data Store stub (several methods still raise
  `NotImplementedError` — see `README.md`'s "Repository pattern" section for exactly which).
- **Factory** — `llm_factory.py`, `repository_factory.py`, `cache_provider_factory.py`,
  `conversation_repository_factory.py` — each picks a concrete adapter based on one env var,
  read once and cached (singleton-style) rather than re-read per request.
- **Strategy** — `api/strategies/query_strategy.py`: `SQLQueryStrategy` vs
  `SemanticSearchStrategy`, chosen by a keyword classifier per incoming chat query.
- **Service layer** — `api/services/*.py` sits between thin routes and the
  repository/LLM-provider interfaces, so routes never contain orchestration logic directly.

**Patterns the original draft of this document proposed but that were not adopted in
practice**, worth naming explicitly so nobody goes looking for them: a formal Dependency
Injection framework (FastAPI's plain function calls turned out to be enough), a Facade layer
distinct from the service layer, Chain of Responsibility for query classification (the
keyword classifier never grew past a single pass), and an Observer-based audit log (no
cross-cutting logging concern has come up yet that a service-layer function call doesn't
already handle directly).

## SOLID, as actually applied
- **S**: routes stay thin; services orchestrate; adapters (`infrastructure/`) handle
  provider-specific mechanics. This held up well in practice.
- **O**: a new LLM/DB/cache provider is a new adapter file behind the existing interface
  (proven twice — QuickML and Catalyst Cache were both added this way without touching an
  existing adapter).
- **L**: any `LLMProvider`/`CacheProvider`/`CaseRepository` implementation is swappable
  without caller changes — enforced by keeping interface method signatures provider-agnostic.
- **I**: interfaces are split narrowly (`LLMProvider` vs `CacheProvider` vs
  `CaseRepository`/`ConversationRepository`, rather than one god-interface).
- **D**: `api/` depends on `domain.interfaces.X`, never on `infrastructure.x.ConcreteX`
  directly — every route/service gets its concrete adapter via a factory call.

## AI Layer — Provider Independence

```python
# domain/interfaces/llm_provider.py
class LLMProvider(ABC):
    async def generate(self, prompt: str) -> str: ...
    async def stream_generate(self, prompt: str) -> AsyncIterator[str]: ...

# infrastructure/llm/llm_factory.py
def get_llm_provider() -> LLMProvider:
    backend = os.getenv("LLM_BACKEND", "gemini")
    return {"gemini": GeminiProvider, "catalyst_quickml": CatalystQuickMLProvider}[backend]()
```
Switching providers is one env var change (`LLM_BACKEND`) — this is the actual mechanism
behind the Gemini → Catalyst QuickML switch documented in `docs/PRD.md`.

### On LangGraph / LangChain: not used, and not currently needed

The original draft of this document proposed adopting LangGraph for multi-step
reasoning/agent workflows. In practice, the chatbot's needs turned out to be well served by
the simpler Strategy pattern above (a keyword classifier choosing between two query-handling
paths) plus one or two sequential, explicitly-orchestrated LLM calls where synthesis is
genuinely needed (MO extraction → profile synthesis, structural leads → optional LLM
summary — see `api/services/mo_extraction.py`). Neither `langgraph` nor `langchain` appears
in `requirements.txt`. Revisit this only if a real feature needs genuine conditional
multi-step agent state that a hand-orchestrated service function can't express cleanly —
don't adopt it speculatively.

## Catalyst Integration — actual status, service by service

| Service | Status | Integration point |
|---|---|---|
| QuickML LLM Serving | **Live, default** (`LLM_BACKEND=catalyst_quickml`) | `infrastructure/llm/catalyst_quickml_provider.py`, direct OAuth+REST via `infrastructure/catalyst_oauth.py` |
| Cache | **Live, default** (`RESPONSE_CACHE_BACKEND=catalyst`) | `infrastructure/cache/catalyst_cache_provider.py`, same OAuth session pattern |
| Data Store | **Deferred, mandatory eventually** | `infrastructure/persistence/catalyst_repository.py` — partial stub, several methods `NotImplementedError`. Deliberately paused (see PRD decision log's "strategic pivot" entry) in favor of product-depth work; Postgres/Supabase remains the live backend |
| Authentication | Not started | Would back real multi-user auth, replacing the current per-device `X-Owner-Token` stopgap (see `api/routes/conversations.py`) |
| Stratus (blob storage) | Not started | Would back server-side generated report storage, if that's ever built (PDF export today is client-side, no storage needed) |
| Zia (translation/voice) | Not used for translation — multilingual chat (English/Kannada/Kannalish) is handled via LLM prompting instead, not a dedicated Zia call | n/a |
| Cron | Not started | Discussed (see PRD decision log's cron explanation entry) but no scheduled job exists yet — nothing in the current feature set needs one |
| AppSail | Not started | Deployment target once ready to deploy; `app-config.json`/`catalyst.json` already exist in the repo root for this |

Every live Catalyst integration bypasses `zcatalyst_sdk`'s HTTP layer (`initialize()`/
`initialize_app()` both assume either a deployed-Function request context or a costly-to-obtain
ZAID) in favor of hand-rolled OAuth + direct REST calls — confirmed via live testing that the
real Catalyst APIs don't require what the SDK's local validation demands. See
`infrastructure/catalyst_oauth.py` and the PRD decision log for the full story.

## Data Flow (frontend → DB → back), as it actually runs

```
Frontend query
  → POST /chat/  (api/routes/chat.py — thin: owner-token check, then delegates)
    → ChatService.stream_answer(query, conversation_id, owner_token)
      → ConversationRepository.get_messages(...)              [interface]
      → QueryRouter/Strategy.build_context(query, repo)         [interface: CaseRepository]
      → LLMProvider.stream_generate(prompt)                     [interface]
    → StreamingResponse → frontend
    → ConversationRepository.append_message(..., citations=...) [interface]
```
Every layer-crossing arrow passes through an interface, never a concrete class — this part of
the original design is intact even though the folder names around it changed.

## Team Collaboration — realistic ownership boundaries given the actual structure

- Analytics/sociology dev → `api/routes/analytics.py`, `api/routes/sociology.py`,
  `api/services/forecasting.py`, the corresponding repository methods
- Network/map/offender-profiling dev → `api/routes/graph.py`, `api/routes/map_routes.py`,
  `api/routes/offenders.py`, the corresponding repository methods
- AI/LLM dev → `infrastructure/llm/`, `api/services/chat_service.py`,
  `api/services/mo_extraction.py`, `api/strategies/`
- Frontend dev → `vetro-ai-frontend/`

**Shared surface, and the real collision risk:** `domain/interfaces/`. Team norm: nobody
changes an existing interface method's signature without flagging it to the group first —
adding a new method (as happened repeatedly this project — `get_case_timeline`,
`get_investigative_leads`, etc. were all added to `CaseRepository` over time) is low-risk;
changing an existing method's signature is the actual danger zone since both `postgres_repository.py`
and `catalyst_repository.py` must stay in sync with it.

## Pitfalls actually encountered (and how they were handled)

- **Reusing a scoped credential across unrelated services** — attempted once (reusing a
  QuickML-scoped OAuth token to test Cache endpoints), correctly flagged as a problem; fixed
  by requesting one combined-scope credential covering both services. Lesson generalized: get
  the right scope up front rather than probing with what you already have.
- **Silent gaps between the two repository backends** — `catalyst_repository.py` not
  implementing a method that `postgres_repository.py` has is currently handled by a loud
  `NotImplementedError` plus an explicit "KNOWN GAP" code comment, not a silent fallback. Keep
  doing this — a repository method that quietly returns wrong/empty data on one backend is far
  worse than one that fails loudly.
- **No unit tests against fake adapters yet** — the verification approach this project has
  actually used instead is hitting the real running app's endpoints directly (`curl`/
  `Invoke-RestMethod`) after every change, documented in `docs/PRD.md`'s decision log. This
  has worked so far at this project's size, but doesn't scale as well to multiple parallel
  contributors as real unit tests against fake adapters would — worth revisiting if the team
  grows.
