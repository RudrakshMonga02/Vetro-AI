import { useState, useEffect, useCallback } from "react";
import Sidebar from "./Sidebar";
import ChatInterface from "./ChatInterface";
import { AUTH_HEADERS } from "../lib/ownerToken";

/**
 * ChatApp -- top-level container owning conversation list state.
 * Sidebar and ChatInterface are both controlled by this component;
 * neither talks to the other directly (standard lift-state-up pattern,
 * same as ChatInterface already used internally for its own messages).
 */

const API_BASE = "http://localhost:8000";

export default function ChatApp() {
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadConversations = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/conversations`, { headers: AUTH_HEADERS });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();
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
      const res = await fetch(`${API_BASE}/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...AUTH_HEADERS },
        body: JSON.stringify({}),
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const conv = await res.json();
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
      const res = await fetch(`${API_BASE}/conversations/${id}`, {
        method: "DELETE",
        headers: AUTH_HEADERS,
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);

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
      <div className="flex h-screen bg-[#0B1120] items-center justify-center">
        <p className="text-xs text-[#4A5268] font-mono uppercase tracking-wider">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen">
      <Sidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelect={handleSelect}
        onCreate={handleCreate}
        onDelete={handleDelete}
      />
      <ChatInterface
        conversationId={activeConversationId}
        onMessageSent={loadConversations}
      />
    </div>
  );
}
