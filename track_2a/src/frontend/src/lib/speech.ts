/** Voice layer - TTS for the interviewer, optional dictation for the student.
 *
 * Text-to-speech uses the browser's speechSynthesis, which runs on-device on
 * all major OSes (no audio leaves the machine). The engine is behind a tiny
 * interface so an on-premise neural TTS (e.g. Piper) can be plugged in later
 * without touching the interview UI - the FHGR "TTS-ready" requirement.
 *
 * Dictation uses the Web Speech API. In Chrome that API streams audio to the
 * browser vendor, so it is OFF by default and the UI says so explicitly.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { LOCALE } from "./i18n";
import type { InterviewLang } from "../types";

export interface TtsEngine {
  speak(text: string, lang: InterviewLang, onEnd?: () => void): void;
  stop(): void;
  available(): boolean;
}

function pickVoice(locale: string): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis?.getVoices() ?? [];
  const exact = voices.find((v) => v.lang === locale);
  const base = voices.find((v) => v.lang.startsWith(locale.slice(0, 2)));
  return exact ?? base;
}

export const browserTts: TtsEngine = {
  available: () => typeof window !== "undefined" && "speechSynthesis" in window,
  speak(text, lang, onEnd) {
    if (!this.available()) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = LOCALE[lang];
    const voice = pickVoice(LOCALE[lang]);
    if (voice) utterance.voice = voice;
    utterance.rate = 0.96;
    utterance.onend = () => onEnd?.();
    utterance.onerror = () => onEnd?.();
    window.speechSynthesis.speak(utterance);
  },
  stop() {
    if (this.available()) window.speechSynthesis.cancel();
  },
};

export function useTts(lang: InterviewLang) {
  const [speaking, setSpeaking] = useState(false);
  const speak = useCallback(
    (text: string) => {
      if (!browserTts.available() || !text) return;
      setSpeaking(true);
      browserTts.speak(text, lang, () => setSpeaking(false));
    },
    [lang],
  );
  const stop = useCallback(() => {
    browserTts.stop();
    setSpeaking(false);
  }, []);
  useEffect(() => () => browserTts.stop(), []);
  return { speak, stop, speaking, available: browserTts.available() };
}

// --- dictation ------------------------------------------------------------

type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  onresult: ((event: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};

function recognitionCtor(): (new () => Recognition) | null {
  const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function useDictation(lang: InterviewLang, onText: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const rec = useRef<Recognition | null>(null);
  const available = typeof window !== "undefined" && recognitionCtor() !== null;

  const start = useCallback(() => {
    const Ctor = recognitionCtor();
    if (!Ctor) return;
    const recognition = new Ctor();
    recognition.lang = LOCALE[lang];
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      let text = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) text += event.results[i][0].transcript;
      }
      if (text) onText(text.trim());
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);
    rec.current = recognition;
    recognition.start();
    setListening(true);
  }, [lang, onText]);

  const stop = useCallback(() => {
    rec.current?.stop();
    setListening(false);
  }, []);

  useEffect(() => () => rec.current?.stop(), []);
  return { start, stop, listening, available };
}
