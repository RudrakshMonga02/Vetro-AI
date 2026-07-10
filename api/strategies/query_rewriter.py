"""
Query rewriting: resolves a follow-up question ("only from 2022") into a
standalone query ("murders in Bangalore in 2022") using conversation
history, BEFORE it hits classify_query()/build_context().

WHY THIS EXISTS, precisely: conversation memory (infrastructure/cache/)
already stores and retrieves history correctly, and ChatService already
feeds that history into the final LLM prompt as text. But that alone
does NOT make follow-ups work end to end -- classify_query() and every
QueryStrategy.build_context() in query_strategy.py only ever see the
CURRENT message. A follow-up like "only from 2022" carries no signal on
its own: classify_query() can't tell it's a filter refinement, and
SemanticSearchStrategy would embed the literal string "only from 2022"
and retrieve unrelated cases. The LLM seeing history as text in the
final prompt can't undo already-wrong retrieval.

This module closes that specific gap: rewrite the query into a
self-contained one FIRST, using history, then let the existing
classify_query()/build_context() pipeline run completely unchanged on
the rewritten query. Nothing about query_strategy.py needs to know
this step exists.
"""

from domain.interfaces.llm_provider import LLMProvider

# Skip the rewrite LLM call entirely when there's no history yet (first
# turn in a conversation) -- nothing to resolve against, and it would
# just be a wasted round-trip.
_REWRITE_PROMPT_TEMPLATE = """You rewrite follow-up questions into standalone questions using \
conversation history. Output ONLY the rewritten question, nothing else -- no \
explanation, no quotes, no preamble.

If the current question is already standalone (doesn't reference anything from \
earlier in the conversation), output it completely unchanged.

Conversation history:
{history_block}

Current question: {current_query}

Rewritten standalone question:"""


async def rewrite_query(
    current_query: str,
    history: list[dict[str, str]],
    llm: LLMProvider,
) -> str:
    """Returns current_query unchanged if there's no history to resolve
    against, or if the rewrite call fails for any reason -- a failed
    rewrite should degrade to "treat it as a fresh question" (today's
    behavior), not break the whole chat turn."""
    if not history:
        return current_query

    history_block = "\n".join(
        f"{'User' if turn['role'] == 'user' else 'Assistant'}: {turn['text']}"
        for turn in history
    )
    prompt = _REWRITE_PROMPT_TEMPLATE.format(
        history_block=history_block, current_query=current_query
    )

    try:
        rewritten = await llm.generate(prompt)
        rewritten = rewritten.strip()
        return rewritten if rewritten else current_query
    except Exception:
        # Degrade gracefully -- a rewrite failure shouldn't take down
        # the whole chat turn, it should just fall back to pre-rewrite
        # behavior (current_query used as-is, same as before this
        # module existed).
        return current_query
