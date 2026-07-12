// Browser-native voice I/O (Web Speech API) -- not Catalyst Zia. Zia is
// the "mapped" service for STT/TTS per the resource doc, but the
// installed zcatalyst_sdk has no speech method at all, and Catalyst
// service integration is deferred anyway. This needs zero backend
// dependency and works today; a CatalystZiaProvider could replace the
// synthesis/recognition calls later without touching the UI that uses
// this module, if that's ever worth doing.
//
// Support is patchy per-browser (notably Firefox) -- every export here
// is feature-detected by the caller before use, never assumed present.

export function isSpeechRecognitionSupported() {
  return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function isSpeechSynthesisSupported() {
  return "speechSynthesis" in window;
}

/**
 * Creates a one-shot recognizer. onResult fires once with the final
 * transcript; it does NOT auto-submit anything -- the caller decides
 * what to do with the transcribed text (this app fills the query box
 * and lets the investigator review/edit before sending, since silently
 * auto-submitting a mis-transcription is worse than one extra click on
 * an evidence-adjacent tool).
 */
export function createRecognizer({ onResult, onEnd, onError, lang = "en-IN" }) {
  const SpeechRecognitionImpl = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognizer = new SpeechRecognitionImpl();
  recognizer.lang = lang;
  recognizer.interimResults = false;
  recognizer.maxAlternatives = 1;

  recognizer.onresult = (event) => {
    const transcript = event.results[0]?.[0]?.transcript;
    if (transcript) onResult(transcript);
  };
  recognizer.onerror = (event) => {
    if (onError) onError(event.error);
  };
  recognizer.onend = () => {
    if (onEnd) onEnd();
  };

  return recognizer;
}

/** Strips common Markdown syntax so read-aloud doesn't speak literal
 * "**", "##", "-", etc. Not a full parser -- just the constructs
 * MarkdownMessage.jsx actually renders. */
export function stripMarkdownForSpeech(text) {
  return text
    .replace(/```[\s\S]*?```/g, " code block ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/^>\s?/gm, "")
    .replace(/^[-*]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .trim();
}

export function speak(text, lang = "en-IN") {
  if (!isSpeechSynthesisSupported()) return;
  window.speechSynthesis.cancel(); // don't queue/overlap with a prior utterance
  const utterance = new SpeechSynthesisUtterance(stripMarkdownForSpeech(text));
  utterance.lang = lang;
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking() {
  if (isSpeechSynthesisSupported()) window.speechSynthesis.cancel();
}
