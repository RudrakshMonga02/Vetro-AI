import { useState, useEffect, useCallback } from "react";
import Sidebar from "./Sidebar";
import ChatInterface from "./ChatInterface";
import { apiGet, apiPost, apiDelete } from "../lib/apiClient";

/**
 * ChatApp -- top-level container owning conversation list state.
 * Sidebar and ChatInterface are both controlled by this component;
 * neither talks to the other directly (standard lift-state-up pattern,
 * same as ChatInterface already used internally for its own messages).
 */

export default function ChatApp() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadConversations = useCallback(async () => {
    try {
      const data = await apiGet("/conversations");
      setConversations(data);
      return data;
    } catch (err) {
      console.error("Failed to load conversations:", err);
      return [];
    }
  }, []);

  // On first mount: load existing conversations. If none exist yet,
  // auto-create one -- matches ChatGPT's behavior of always having an
  // active thread rather than showing a blank "create one" prompt on
  // first visit.
  useEffect(() => {
    (async () => {
      setIsLoading(true);
      const existing = await loadConversations();
      if (existing.length > 0) {
        setActiveConversationId(existing[0].id);
      } else {
        await handleCreate();
      }
      setIsLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate() {
    try {
      const conv = await apiPost("/conversations", {});
      setConversations((prev) => [
        { id: conv.id, title: conv.title, updated_at: conv.updated_at },
        ...prev,
      ]);
      setActiveConversationId(conv.id);
    } catch (err) {
      console.error("Failed to create conversation:", err);
    }
  }

  function handleSelect(id) {
    setActiveConversationId(id);
  }

  async function handleDelete(id) {
    try {
      await apiDelete(`/conversations/${id}`);

      const remaining = conversations.filter((c) => c.id !== id);
      setConversations(remaining);

      // If the deleted conversation was the active one, fall back to
      // the next most recent, or create a fresh one if that was the
      // last conversation -- never leave the UI with no active thread
      // and a stale message list still showing.
      if (activeConversationId === id) {
        if (remaining.length > 0) {
          setActiveConversationId(remaining[0].id);
        } else {
          await handleCreate();
        }
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-full bg-[#0B1120] items-center justify-center">
        <p className="text-xs text-[#4A5268] font-mono uppercase tracking-wider">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelect={handleSelect}
        onCreate={handleCreate}
        onDelete={handleDelete}
      />
      <ChatInterface
        conversationId={activeConversationId}
        conversationTitle={conversations.find((c) => c.id === activeConversationId)?.title}
        onMessageSent={loadConversations}
      />
    </div>
  );
}
