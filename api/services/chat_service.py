"""
ChatService: the orchestration layer for the RAG chatbot. Ties together:
  - query_strategy.classify_query()                -> decides SQL vs semantic context
  - infrastructure.persistence.repository_factory   -> Postgres or Catalyst, whichever is active
  - infrastructure.llm.llm_factory                  -> Gemini or (future) Catalyst QuickML
  - infrastructure.persistence.conversation_repository_factory -> persisted chat history

Routes should only ever call ChatService.stream_answer() -- they never
touch strategies, repositories, or LLM providers directly.

CONVERSATION HISTORY, why it's here: "context-aware conversations
allowing follow-up queries without repeating context" is an explicit
problem-statement requirement (see docs/PRD.md section 1, item 1).

HISTORY SOURCE, note on a design change: this used to read from
ConversationMemory (infrastructure/cache/ -- in-memory or Catalyst
Cache), an ephemeral per-process cache keyed by an auto-generated
session_id. That's been replaced with ConversationRepository
(Postgres-backed, keyed by a real conversation_id the frontend creates
explicitly via POST /conversations) -- see docs/PRD.md decision log
for why multi-session chat needed persisted storage, not a cache, as
its source of truth. The two abstractions happen to share the same
history shape ([{'role', 'text'}, ...]) on purpose, so query_rewriter.py
needed zero changes despite the swap underneath it.
"""
from typing import AsyncIterator

from api.strategies.query_rewriter import rewrite_query
from api.strategies.query_strategy import classify_query
from infrastructure.llm.llm_factory import get_llm_provider
from infrastructure.persistence.conversation_repository_factory import (
    get_conversation_repository,
)
from infrastructure.persistence.repository_factory import get_case_repository

# How many prior turns to actually feed back into the prompt. Postgres
# can hold the full history indefinitely; this just caps how much of
# it gets spent on prompt tokens for any single turn.
TURNS_FED_TO_PROMPT = 6


class ChatService:
    def __init__(self):
        self.repo = get_case_repository()
        self.llm = get_llm_provider()
        self.conversations = get_conversation_repository()

    async def stream_answer(
        self, user_query: str, conversation_id: int, owner_token: str
    ) -> AsyncIterator[str]:
        # owner_token is re-checked here (not just at the route layer)
        # as defense-in-depth -- see domain/interfaces/conversation_repository.py
        # and the vulnerability review in docs/PRD.md. If this doesn't
        # match, get_messages() returns [] rather than raising, so this
        # degrades to "empty history" rather than a crash; the route
        # layer's own get_conversation() check is what actually returns
        # the 404 to the caller.
        history = self.conversations.get_messages(conversation_id, owner_token)[-TURNS_FED_TO_PROMPT:]

        retrieval_query = await rewrite_query(user_query, history, self.llm)

        strategy = classify_query(retrieval_query)
        context = strategy.build_context(retrieval_query, self.repo)

        history_block = self._format_history(history)

        prompt = f"""You are a helpful assistant answering questions about Karnataka crime
data (FIR records) for a police-data analytics platform. Use ONLY the context below to
answer -- if the context doesn't contain enough information, say so honestly rather than
guessing. Keep answers concise and factual.

Format your answer in Markdown so it renders cleanly in the UI:
- Use a heading (## or ###) for a title if the answer covers a distinct topic
- Use **bold** for key numbers/findings (e.g. totals, percentages, district names being highlighted)
- Use bullet lists for multiple items (districts, crime types, case details)
- Use a blockquote (>) for a single standout observation or caveat
- Use a numbered list for sequential/ranked information (e.g. top 5 districts by count)
- Don't force formatting where plain prose reads better -- a one-line factual answer
  ("We have 256 cases.") doesn't need a heading or bullets, just say it plainly.

If the question refers back to something discussed earlier in the conversation (e.g. "that
case", "the second one", "what about the other district"), use the conversation history
below to resolve what it's referring to.

Conversation history so far:
{history_block}

Context:
{context}

Question: {user_query}

Answer:"""

        answer_chunks: list[str] = []
        async for chunk in self.llm.stream_generate(prompt):
            answer_chunks.append(chunk)
            yield chunk

        # Persist this turn AFTER the full answer has streamed, so a
        # request that errors partway through doesn't leave a
        # half-written assistant turn poisoning future context.
        # Store the user's ORIGINAL phrasing (not retrieval_query) --
        # the rewrite is an internal retrieval aid, not what the user
        # actually said, and future rewrite calls should work from
        # what was really typed, not a previously-rewritten version.
        # append_message() for the "user" role also auto-titles the
        # conversation from this text if it's still untitled -- see
        # postgres_conversation_repository.py.
        full_answer = "".join(answer_chunks)
        self.conversations.append_message(conversation_id, "user", user_query)
        self.conversations.append_message(conversation_id, "assistant", full_answer)

    @staticmethod
    def _format_history(history: list[dict[str, str]]) -> str:
        if not history:
            return "(no prior messages in this conversation)"
        lines = []
        for turn in history:
            speaker = "User" if turn["role"] == "user" else "Assistant"
            lines.append(f"{speaker}: {turn['text']}")
        return "\n".join(lines)
