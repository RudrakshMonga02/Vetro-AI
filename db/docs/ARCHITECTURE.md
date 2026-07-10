# Vetro AI — Architecture Document

**Status:** Living document, companion to `docs/PRD.md`. PRD tracks product decisions and the
running Decision Log; this file tracks *structural* architecture decisions. Update both when a
change touches both product scope and code structure.

**Project rename:** the assistant is now branded **Vetro AI** ("Vetro" = the assistant persona).
Repo/folder renames to `vetro-ai` are a housekeeping task, not urgent — don't block feature work on it.

---

## Why this document exists

The MVP (KSP Crime Data Platform) works, but was built feature-by-feature without a layering
discipline. Before adding more features (analytics, maps, graphs, reports, agent workflows), we're
locking in an architecture so that adding one feature doesn't silently break three others, and so
four developers can work in parallel without constant merge conflicts.

## Core principle: Clean Architecture, dependencies point inward only

```
Presentation  →  Application (use-cases)  →  Domain (entities + interfaces)
                                                       ↑
                                          Infrastructure (adapters) implements these
```

Domain layer defines interfaces (`LLMProvider`, `CaseRepository`, `VectorStore`, `CacheProvider`,
`AuthProvider`, `FileStorage`, `TranslationService`) and imports nothing external. Application layer
(use-cases) only depends on those interfaces, never on a concrete Gemini/Postgres/Catalyst class
directly — concrete classes are injected in at the presentation layer via FastAPI `Depends()`.

**This single rule is what enables every other goal in this doc**: swapping LLM providers, DB
backends, or Catalyst services becomes "write a new adapter + flip a factory/config," not "rewrite
the app."

## Folder Structure

```
vetro-ai/
├── domain/
│   ├── entities/            # Case, Accused, Victim, Investigation, Message
│   ├── interfaces/          # LLMProvider, CaseRepository, VectorStore, CacheProvider,
│   │                        # AuthProvider, FileStorage, TranslationService, SpeechService
│   └── exceptions.py
├── application/
│   ├── chat/                # AnswerQueryUseCase, ConversationMemory, QueryRouter/Strategies,
│   │                        # InvestigationAgent (LangGraph lives ONLY here)
│   ├── analytics/           # crime trends, offender risk scoring
│   ├── network/             # case network, cross-case link detection
│   ├── reports/             # PDF/report generation use-cases
│   └── auth/                # RBAC policy (provider-agnostic rules)
├── infrastructure/
│   ├── llm/                 # gemini_provider, openai_provider, catalyst_quickml_provider, factory
│   ├── persistence/         # postgres_repository, catalyst_datastore_repository, factory
│   ├── vectorstore/         # chroma_store, quickml_rag_store
│   ├── cache/                # in_memory_cache, catalyst_cache
│   ├── auth/                 # catalyst_auth_adapter
│   └── storage/              # catalyst_stratus_adapter
├── presentation/
│   ├── api/routes/           # chat, analytics, map, graph, reports, auth — THIN, no business logic
│   ├── api/dependencies.py   # all DI wiring lives here
│   └── schemas/               # Pydantic request/response models
├── config/settings.py         # env-driven; factories read this to pick adapters
├── frontend/                  # single React app
├── docs/ (PRD.md, ARCHITECTURE.md)
└── tests/ (unit/ against fake adapters, integration/)
```

## Design Patterns in Use

- **Repository** — `CaseRepository` interface, Postgres/Catalyst implementations (already exists,
  extending it).
- **Strategy** — query routing (`SQLQueryStrategy`, `SemanticSearchStrategy`, `EntityListStrategy`
  already exist; add more as needed, e.g. `TimelineStrategy`).
- **Adapter** — every class in `infrastructure/` wraps a 3rd-party SDK behind our own interface.
- **Factory** — `llm_factory.py`, `repository_factory.py` — one place decides which concrete adapter
  to build, driven by `config/settings.py`.
- **Dependency Injection** — via FastAPI `Depends()`, wired in `presentation/api/dependencies.py`.
  Use-cases receive interfaces as constructor args, never construct concrete adapters themselves.
- **Facade** — use-cases like `AnswerQueryUseCase` hide multi-step orchestration behind one call.
- **Chain of Responsibility** (as-needed) — if query classification grows beyond keyword heuristics
  into multiple fallback classifiers.
- **Observer** (as-needed) — audit logging without hardcoding log calls inside every use-case.

## SOLID, applied here
- **S**: use-cases orchestrate; adapters handle provider-specific mechanics. Never mixed.
- **O**: new provider = new adapter file. Never edit an existing adapter to add another provider's logic.
- **L**: any `LLMProvider` implementation must be swappable without the use-case caring — enforce by
  keeping interface method signatures provider-agnostic.
- **I**: split interfaces narrowly (`LLMProvider` vs `EmbeddingProvider` vs `VectorStore`) so a
  provider isn't forced to implement methods it can't support.
- **D**: application layer depends on `domain.interfaces.X`, never on `infrastructure.x.ConcreteX`.

## AI Layer — Provider Independence

```python
# domain/interfaces/llm_provider.py
class LLMProvider(ABC):
    async def generate(self, messages: list[Message], **kwargs) -> str: ...
    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[str]: ...

# infrastructure/llm/llm_factory.py
def get_llm_provider() -> LLMProvider:
    return {
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
        "catalyst_quickml": CatalystQuickMLProvider,
    }[settings.LLM_PROVIDER]()
```

Switching providers = one env var change. Same pattern as the existing Postgres/Catalyst repository swap.

### LangChain / LangGraph decision: **use LangGraph, scoped narrowly**

**Use it for:** multi-step reasoning, agent/tool-calling workflows, investigation memory,
suggested-follow-up generation — all inside `application/chat/investigation_agent.py` and nothing
else. This is exactly the class of problem (conditional multi-step graphs with state) LangGraph is
built for; hand-rolling it gets unmaintainable past 2-3 steps.

**Do NOT use it for:**
- The `LLMProvider` abstraction itself — keep this hand-rolled so Catalyst QuickML (which doesn't
  look like a typical chat-completions API) doesn't have to fight LangChain's model assumptions.
- Simple single-shot queries (aggregate SQL, entity lists) — no graph needed, keep as direct
  use-case calls.
- Repository/vector store access — our own `CaseRepository`/`VectorStore` interfaces map better onto
  Catalyst's real constraints (e.g. QuickML RAG's document-upload model breaks typical LangChain
  retriever assumptions anyway) than adopting LangChain's retriever abstractions would.

**Blast radius rule:** only `application/chat/` may import `langgraph`/`langchain`. If it doesn't
work out, the damage is contained to one module.

## Catalyst Integration — service by service

| Service | Use it? | Integration point |
|---|---|---|
| Data Store | Yes (mandatory) | `infrastructure/persistence/catalyst_datastore_repository.py` |
| Authentication | Yes | `infrastructure/auth/catalyst_auth_adapter.py`; RBAC *rules* stay provider-agnostic in `application/auth/rbac_policy.py` |
| QuickML LLM Serving | Yes | New `LLMProvider` impl, via factory |
| QuickML RAG | Yes, if early-access clears (see PRD §4.3 risk) | New `VectorStore` impl, abstracted so document-upload model doesn't leak into use-cases |
| Cache | Yes | `infrastructure/cache/catalyst_cache.py`; used for analytics results that don't change often |
| Stratus (blob storage) | Yes | Generated PDF reports, via `FileStorage` interface |
| SmartBrowz | Yes | PDF export of conversation history, via a `ReportGenerator` interface |
| Zia Services (voice/translation) | Yes | Kannada translation + voice I/O, via `TranslationService`/`SpeechService` interfaces |
| Cron | Yes, later | Scheduled forecasting job as its own `application/forecasting/` use-case |
| AppSail | Mandatory deployment target | Deployment only, no architecture impact |
| API Gateway | Useful, not urgent | Infra-level auth/throttling in front of Functions |
| Signals / Circuits / Push Notifications / Mail | **Skip for now** | Solve event-driven/orchestration problems this project doesn't have yet — adding them now is complexity without payoff |

Every Catalyst service is wrapped the same way Postgres/Gemini are: adapter implements a domain
interface. If a Catalyst service is blocked (e.g. QuickML RAG access), the existing Gemini+ChromaDB
path fits the same interfaces — falling back is a factory config change, not an architecture change.

## Data Flow (frontend → DB → back)

```
Frontend query
  → POST /chat  (presentation/api/routes/chat.py — thin)
    → AnswerQueryUseCase.execute(query, session_id)
      → ConversationMemory.get_history(session_id)         [interface]
      → QueryRouter.classify(query) → Strategy
        → Strategy.build_context(query, repo: CaseRepository)  [interface]
      → LLMProvider.stream(messages + context)              [interface]
    → StreamingResponse → frontend
```

Every layer-crossing arrow passes through an interface, never a concrete class.

## Team Collaboration — parallel work, answered directly

**Yes, 4 developers can work in parallel with minimal collision**, given this structure:
- Analytics dev → only touches `application/analytics/` + its route
- Maps/network dev → only touches `application/network/` (or new `application/maps/`) + its route
- AI/LLM dev → only touches `infrastructure/llm/` + `application/chat/`
- Frontend dev → only touches `frontend/`

**Shared surface, and the only real collision risk:** `domain/interfaces/`. Team norm: nobody
changes an existing interface method's signature without flagging it to the group first — adding a
new method is low-risk, changing an existing one is the actual danger zone.

## Pitfalls to avoid
- Business logic creeping into `presentation/` routes "just this once" — it always spreads.
- LangGraph creeping beyond `application/chat/` — keep the blast radius contained.
- Skipping the interface/adapter step for a Catalyst service because it seems quick — those are
  exactly the ones that hurt when a fallback is needed later (see QuickML RAG risk in PRD).
- No unit tests against fake adapters — this is what actually lets 4 people merge without needing a
  shared live DB/API for every test run.

## Status of migration from current MVP structure
Not yet executed — this document is the target design. The existing `db/`, `api/`, `rag/`,
`catalyst/` folders from the MVP need to be reorganized into this structure. Track this migration as
its own task in the PRD Decision Log once started, rather than doing it silently alongside unrelated
feature work.
