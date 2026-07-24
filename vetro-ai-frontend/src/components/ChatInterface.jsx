import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Send, Loader2, FileDown, Mic, MicOff, Volume2, VolumeX } from "lucide-react";
import { getOwnerHeaders } from "../lib/ownerToken";
import { useAuth } from "../context/AuthContext";
import { API_BASE, getOfficerHeaders } from "../lib/apiClient";
import { exportConversationToPdf } from "../lib/exportPdf";
import MarkdownMessage from "./MarkdownMessage";
import {
  isSpeechRecognitionSupported,
  createRecognizer,
} from "../lib/speechRecognition";

/**
 * ChatInterface -- the message thread for ONE conversation.
 *
 * Controlled by conversationId (from ChatApp.jsx / Sidebar selection),
 * not self-managed session storage -- multi-session chat means each
 * "Investigation" thread has its own persisted history in Postgres
 * (see api/routes/conversations.py), and this component just renders
 * whichever conversation is currently active, reloading history
 * whenever conversationId changes.
 *
 * Design direction: "incident log" rather than generic chat bubbles --
 * this is an analyst tool for crime data, not a consumer messaging app.
 */

// Markers separating streamed answer text from trailing JSON payloads --
// must match api/services/chat_service.py's CITATION_SENTINEL /
// FOLLOWUP_SENTINEL exactly. Only ever present on answers that produced
// them (citations: SemanticSearchStrategy only; followups: whenever the
// suggestion call succeeds) -- SQL/entity-list answers never contain
// either, so this split is a no-op for those.
const CITATION_SENTINEL = "\n\n<<<VETRO_CITATIONS>>>\n";
const FOLLOWUP_SENTINEL = "\n\n<<<VETRO_FOLLOWUPS>>>\n";

const VOICE_LANGS = { en: "en-IN", kn: "kn-IN" };

/** Convert a rendered AI answer into natural speech. Keep Kannada letters and
 * ordinary punctuation intact while removing visual/UI-only artifacts. */
function sanitizeSpeechText(text) {
  return text
    .replace(/<<<VETRO_[A-Z_]+>>>/g, "")
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!?(?:\[([^\]]*)\]\([^)]*\))/g, "$1")
    .replace(/https?:\/\/[^\s)\]]+/gi, "")
    .replace(/\[(?:\d+|source|citation|case\s*#?\d+)[^\]]*\]/gi, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*(?:[-*+] |\d+[.)] )/gm, "")
    .replace(/[~*_>#|]/g, " ")
    .replace(/\b[A-Za-z0-9_-]{20,}\b/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function useAutoScroll(dep) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [dep]);
  return ref;
}

function formatTime() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** Strips both trailing metadata blocks off a raw accumulated stream,
 * in whichever combination is present. Followups (if any) always come
 * last, so peel from the end first. */
function splitMetadata(accumulated) {
  let displayText = accumulated;
  let citations = null;
  let followups = null;

  const followupIdx = displayText.indexOf(FOLLOWUP_SENTINEL);
  if (followupIdx !== -1) {
    try {
      followups = JSON.parse(displayText.slice(followupIdx + FOLLOWUP_SENTINEL.length));
    } catch {
      followups = null;
    }
    displayText = displayText.slice(0, followupIdx);
  }

  const citationIdx = displayText.indexOf(CITATION_SENTINEL);
  if (citationIdx !== -1) {
    try {
      citations = JSON.parse(displayText.slice(citationIdx + CITATION_SENTINEL.length));
    } catch {
      citations = null;
    }
    displayText = displayText.slice(0, citationIdx);
  }

  return { displayText, citations, followups };
}

export default function ChatInterface({ conversationId, conversationTitle, onMessageSent }) {
  const navigate = useNavigate();
  const { officer } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [speakingIndex, setSpeakingIndex] = useState(null);
  // Controls investigator-facing response language and browser speech tools.
  const [language, setLanguage] = useState("en");
  const scrollRef = useAutoScroll(messages);
  const recognizerRef = useRef(null);
  const audioRef = useRef(null);
  const audioRequestIdRef = useRef(0);
  const finalTranscriptRef = useRef("");
  const recognitionFailedRef = useRef(false);

  const micSupported = isSpeechRecognitionSupported();

  // Reload this conversation's persisted history whenever the active
  // conversation changes (sidebar switch) -- this is what makes each
  // investigation's memory genuinely independent in the UI, not just
  // on the backend.
  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }

    let cancelled = false;
    setIsLoadingHistory(true);

    fetch(`${API_BASE}/conversations/${conversationId}/messages`, { headers: { ...getOwnerHeaders(), ...getOfficerHeaders() } })
      .then((res) => {
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        return res.json();
      })
      .then((history) => {
        if (cancelled) return;
        setMessages(
          history.map((m) => ({
            role: m.role === "user" ? "query" : "response",
            text: m.text,
            citations: m.citations ?? null,
            time: formatTime(),
          }))
        );
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("Failed to load conversation history:", err);
          setMessages([]);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoadingHistory(false);
      });

    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  useEffect(() => {
    // Never render a prior officer's client-side transcript during account switching.
    setMessages([]);
    setInput("");
    stopAudio();
  }, [officer?.user_id]);

  // Stop any in-flight recognition/speech when switching conversations,
  // so a lingering mic session or read-aloud doesn't bleed across
  // "Investigation" threads.
  useEffect(() => {
    return () => {
      recognizerRef.current?.stop();
      stopAudio();
    };
  }, [conversationId]);

  async function handleSend(overrideQuery) {
    const query = (overrideQuery ?? input).trim();
    if (!query || isStreaming || !conversationId) return;

    const userMsg = { role: "query", text: query, time: formatTime() };
    const assistantMsg = { role: "response", text: "", citations: null, followups: null, time: formatTime() };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setIsStreaming(true);

    try {
      const res = await fetch(`${API_BASE}/chat/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getOwnerHeaders(),
          ...getOfficerHeaders(),
        },
        body: JSON.stringify({
          query,
          conversation_id: conversationId,
          language,
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`Server returned ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        accumulated += decoder.decode(value, { stream: true });
        // Live-typing update during the stream -- both metadata
        // sentinels (if any) only ever appear after the real answer
        // text, so showing the raw accumulated string mid-stream looks
        // identical to today until the very last chunks arrive. The
        // final split happens once, after done, below.
        setMessages((prev) => {
          const next = [...prev];
          next[next.length - 1] = { ...next[next.length - 1], text: accumulated };
          return next;
        });
      }

      const { displayText, citations, followups } = splitMetadata(accumulated);
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = { ...next[next.length - 1], text: displayText, citations, followups };
        return next;
      });
      // -1 denotes the automatically narrated latest response; it keeps
      // the global Stop audio control visible without tying playback to a
      // stale message-array index.
      void playBackendAudio(displayText, -1);

      // Let the parent know a message completed -- this is what
      // triggers the sidebar to refresh (picks up auto-generated
      // title from the first message, and re-sorts by updated_at).
      if (onMessageSent) onMessageSent();
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          ...next[next.length - 1],
          text: `Query failed: ${err.message}. Confirm the backend is running at ${API_BASE}.`,
          error: true,
        };
        return next;
      });
    } finally {
      setIsStreaming(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function handleExportPdf() {
    if (isExporting || messages.length === 0) return;
    setIsExporting(true);
    try {
      await exportConversationToPdf(messages, conversationTitle);
    } catch (err) {
      console.error("PDF export failed:", err);
    } finally {
      setIsExporting(false);
    }
  }

  function toggleListening() {
    if (!micSupported) return;
    if (isListening) {
      recognizerRef.current?.stop();
      return;
    }

    stopAudio();
    finalTranscriptRef.current = "";
    recognitionFailedRef.current = false;
    const recognizer = createRecognizer({
      lang: VOICE_LANGS[language],
      onResult: (transcript) => {
        finalTranscriptRef.current = transcript.trim();
        setInput(finalTranscriptRef.current);
      },
      onEnd: () => {
        setIsListening(false);
        const transcript = finalTranscriptRef.current;
        finalTranscriptRef.current = "";
        if (!recognitionFailedRef.current && transcript && !isStreaming) {
          handleSend(transcript);
        }
      },
      onError: () => {
        recognitionFailedRef.current = true;
        setIsListening(false);
      },
    });
    recognizerRef.current = recognizer;
    setIsListening(true);
    recognizer.start();
  }

  function stopAudio() {
    // Invalidates an in-flight TTS fetch so a cancelled response cannot
    // begin playing after the officer has pressed Stop audio.
    audioRequestIdRef.current += 1;

    const activeAudio = audioRef.current;
    if (activeAudio) {
      activeAudio.audio.pause();
      activeAudio.audio.src = "";
      URL.revokeObjectURL(activeAudio.url);
      audioRef.current = null;
    }
    setSpeakingIndex(null);
  }

  async function playBackendAudio(text, messageIndex = -1) {
    const speechText = sanitizeSpeechText(text);
    if (!speechText) return;

    stopAudio();
    const requestId = audioRequestIdRef.current;

    try {
      const response = await fetch(`${API_BASE}/audio/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getOwnerHeaders(), ...getOfficerHeaders() },
        body: JSON.stringify({ text: speechText, language }),
      });

      if (!response.ok) {
        throw new Error(`TTS server returned ${response.status}`);
      }

      const blob = await response.blob();
      if (requestId !== audioRequestIdRef.current) return;

      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = { audio, url };
      setSpeakingIndex(messageIndex);

      const cleanup = () => {
        if (audioRef.current?.audio === audio) {
          URL.revokeObjectURL(url);
          audioRef.current = null;
          setSpeakingIndex(null);
        }
      };

      audio.onended = cleanup;
      audio.onerror = cleanup;
      await audio.play();
    } catch (error) {
      if (requestId === audioRequestIdRef.current) {
        console.error("Backend TTS failed:", error);
        setSpeakingIndex(null);
      }
    }
  }

  function toggleSpeak(index, text) {
    if (speakingIndex === index) {
      stopAudio();
      return;
    }
    void playBackendAudio(text, index);
  }

  return (
    <div className="flex flex-col h-full bg-[#0B1120] text-[#E4E7EC] flex-1 min-w-0">
      {/* Header */}
      <div className="border-b border-[#2A3348] px-6 py-4 flex items-center justify-between shrink-0">
        <div>
          <h1 className="font-mono text-sm tracking-widest text-[#D4A24C] uppercase">
            KSP Crime Data Terminal
          </h1>
          <p className="text-xs text-[#6B7488] mt-0.5">Karnataka SCRB &middot; Query Interface</p>
        </div>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => setLanguage((current) => (current === "en" ? "kn" : "en"))}
            aria-label="Change chat language"
            title="Change response and voice language"
            className="text-xs font-mono tracking-wider text-[#6B7488] hover:text-[#D4A24C]
                       border border-[#2A3348] rounded px-2 py-1 transition-colors"
          >
            {language === "en" ? "English" : "ಕನ್ನಡ"}
          </button>
          {speakingIndex !== null && (
            <button
              type="button"
              onClick={stopAudio}
              title="Stop audio"
              className="flex items-center gap-1 text-xs font-mono uppercase tracking-wider text-[#B0503C]
                         hover:text-[#E06950] transition-colors"
            >
              <VolumeX className="w-3.5 h-3.5" /> Stop audio
            </button>
          )}
          <button
            onClick={handleExportPdf}
            disabled={isExporting || isStreaming || messages.length === 0}
            title="Export conversation as PDF"
            className="flex items-center gap-1.5 text-xs font-mono uppercase tracking-wider
                       text-[#6B7488] hover:text-[#D4A24C] disabled:opacity-30
                       disabled:cursor-not-allowed disabled:hover:text-[#6B7488] transition-colors"
          >
            {isExporting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <FileDown className="w-3.5 h-3.5" />
            )}
            Export PDF
          </button>
          <div className="flex items-center gap-2 text-xs text-[#6B7488] font-mono">
            <span className={`w-1.5 h-1.5 rounded-full ${isStreaming ? "bg-[#D4A24C] animate-pulse" : "bg-[#3A6B4C]"}`} />
            {isStreaming ? "RETRIEVING" : "READY"}
          </div>
        </div>
      </div>

      {/* Message log */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {isLoadingHistory && (
          <div className="h-full flex items-center justify-center">
            <Loader2 className="w-5 h-5 animate-spin text-[#4A5268]" />
          </div>
        )}

        {!isLoadingHistory && messages.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center text-center px-4">
            <p className="font-mono text-xs text-[#6B7488] tracking-wide uppercase mb-2">
              No active query
            </p>
            <p className="text-sm text-[#4A5268] max-w-sm">
              Ask about case trends, district statistics, or specific incident details.
              Example: <span className="text-[#8B93A8]">"Which district has the most cybercrime cases?"</span>
            </p>
          </div>
        )}

        {!isLoadingHistory && messages.map((msg, i) => {
          const isLastMessage = i === messages.length - 1;
          return (
          <div key={i} className="max-w-3xl mx-auto">
            {msg.role === "query" ? (
              <div className="flex items-start gap-3">
                <span className="font-mono text-[10px] text-[#6B7488] mt-1.5 shrink-0 w-14">{msg.time}</span>
                <div className="flex-1 border-l-2 border-[#2A3348] pl-3">
                  <span className="font-mono text-[10px] text-[#D4A24C] uppercase tracking-wider">Query</span>
                  <p className="text-[#E4E7EC] mt-1">{msg.text}</p>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-3 mt-2">
                <span className="font-mono text-[10px] text-[#6B7488] mt-1.5 shrink-0 w-14">{msg.time}</span>
                <div className={`flex-1 border-l-2 pl-3 ${msg.error ? "border-[#B0503C]" : "border-[#3A6B4C]"}`}>
                  <div className="flex items-center justify-between">
                    <span className={`font-mono text-[10px] uppercase tracking-wider ${msg.error ? "text-[#B0503C]" : "text-[#3A6B4C]"}`}>
                      {msg.error ? "Error" : "Result"}
                    </span>
                    {msg.text && !isStreaming && (
                      <button
                        onClick={() => toggleSpeak(i, msg.text)}
                        title="Read answer aloud"
                        className="text-[#4A5268] hover:text-[#D4A24C] transition-colors"
                      >
                        {speakingIndex === i ? (
                          <VolumeX className="w-3.5 h-3.5" />
                        ) : (
                          <Volume2 className="w-3.5 h-3.5" />
                        )}
                      </button>
                    )}
                  </div>
                  {msg.text ? (
                    <>
                      <MarkdownMessage text={msg.text} />
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-2">
                          {msg.citations.map((c) => (
                            <button
                              key={c.case_id}
                              onClick={() => navigate(`/network?case=${c.case_id}`)}
                              title={`${c.district ?? "?"} · ${c.crime_type ?? "?"} · ${c.date ?? "?"} · ${c.status ?? "?"} — open in Network Graph`}
                              className="text-[10px] font-mono uppercase tracking-wide text-[#8B93A8]
                                         border border-[#2A3348] rounded px-1.5 py-0.5
                                         hover:border-[#D4A24C] hover:text-[#D4A24C] transition-colors"
                            >
                              Case #{c.case_id}
                            </button>
                          ))}
                        </div>
                      )}
                      {isLastMessage && msg.followups && msg.followups.length > 0 && !isStreaming && (
                        <div className="flex flex-wrap gap-1.5 mt-3">
                          {msg.followups.map((q, fi) => (
                            <button
                              key={fi}
                              onClick={() => handleSend(q)}
                              className="text-xs text-left text-[#A8AEC0] border border-[#2A3348] rounded-full
                                         px-3 py-1.5 hover:border-[#D4A24C] hover:text-[#D4A24C] transition-colors"
                            >
                              {q}
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="text-[#C8CCD8] mt-1 leading-relaxed">
                      <span className="inline-flex items-center gap-1.5 text-[#6B7488]">
                        <Loader2 className="w-3 h-3 animate-spin" /> processing
                      </span>
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        );})}
      </div>

      {/* Input */}
      <div className="border-t border-[#2A3348] px-6 py-4 shrink-0">
        <div className="max-w-3xl mx-auto flex items-end gap-3">
          {micSupported && (
            <button
              onClick={toggleListening}
              disabled={!conversationId || isStreaming}
              title={isListening ? "Stop listening" : "Speak your query"}
              className={`rounded px-3 py-3 border transition-colors shrink-0 disabled:opacity-30
                ${isListening
                  ? "bg-[#B0503C] border-[#B0503C] text-[#0B1120] animate-pulse"
                  : "bg-[#151B2E] border-[#2A3348] text-[#6B7488] hover:text-[#D4A24C] hover:border-[#D4A24C]"}`}
            >
              {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>
          )}
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={language === "kn" ? "ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ನಮೂದಿಸಿ..." : "Enter query..."}
            rows={1}
            disabled={!conversationId}
            className="flex-1 bg-[#151B2E] border border-[#2A3348] rounded px-4 py-3 text-sm
                       text-[#E4E7EC] placeholder-[#4A5268] focus:outline-none focus:border-[#D4A24C]
                       resize-none font-mono disabled:opacity-50"
          />
          <button
            onClick={() => handleSend()}
            disabled={isStreaming || !input.trim() || !conversationId}
            className="bg-[#D4A24C] text-[#0B1120] rounded px-4 py-3 disabled:opacity-30
                       disabled:cursor-not-allowed hover:bg-[#E0B15F] transition-colors shrink-0"
          >
            {isStreaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}
