/** Neural interviewer speech on the hosted app, optional device speech locally.
 * Dictation remains a separate opt-in browser feature. */
import { useCallback, useEffect, useRef, useState } from "react";
import { LOCALE } from "./i18n";
import type { InterviewLang } from "../types";

export function pickVoice(voices: SpeechSynthesisVoice[], locale: string): SpeechSynthesisVoice | undefined {
  const base = locale.slice(0, 2).toLowerCase();
  return voices.filter(v => v.lang.slice(0, 2).toLowerCase() === base).sort((a, b) => {
    const score = (v: SpeechSynthesisVoice) =>
      (/natural|neural|premium|enhanced|google|siri/i.test(v.name) ? 40 : 0) +
      (v.lang.toLowerCase() === locale.toLowerCase() ? 20 : 0) + (v.default ? 1 : 0);
    return score(b) - score(a);
  })[0];
}

let deviceGeneration = 0;
export const browserTts = {
  available: () => typeof window !== "undefined" && "speechSynthesis" in window,
  speak(text: string, lang: InterviewLang, onEnd?: () => void, rate = 0.95) {
    if (!this.available()) { onEnd?.(); return; }
    this.stop();
    const generation = deviceGeneration;
    const start = () => {
      if (generation !== deviceGeneration) return;
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = LOCALE[lang];
      const voice = pickVoice(window.speechSynthesis.getVoices(), LOCALE[lang]);
      if (voice) utterance.voice = voice;
      utterance.rate = rate;
      utterance.onend = utterance.onerror = () => { if (generation === deviceGeneration) onEnd?.(); };
      window.speechSynthesis.speak(utterance);
    };
    if (window.speechSynthesis.getVoices().length) start();
    else {
      let started = false;
      const ready = () => { if (started) return; started = true; window.speechSynthesis.removeEventListener("voiceschanged", ready); start(); };
      window.speechSynthesis.addEventListener("voiceschanged", ready, { once: true });
      window.setTimeout(ready, 500);
    }
  },
  stop() { deviceGeneration++; if (this.available()) window.speechSynthesis.cancel(); },
};

export function useTts(lang: InterviewLang, interviewId: string, natural: boolean, rate = 0.95) {
  const [speaking, setSpeaking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [fallback, setFallback] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const abort = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const urls = useRef(new Map<string, string>());
  const stop = useCallback(() => {
    generation.current++;
    abort.current?.abort();
    abort.current = null;
    if (audio.current) { audio.current.onended = null; audio.current.onerror = null; audio.current.pause(); audio.current.removeAttribute("src"); audio.current.load(); }
    browserTts.stop();
    setLoading(false); setSpeaking(false);
  }, []);
  const speak = useCallback((text: string) => {
    if (!text) return;
    stop();
    const current = generation.current;
    setBlocked(false); setFallback(false); setSpeaking(true);
    const finished = () => { if (current === generation.current) { setSpeaking(false); setLoading(false); } };
    const device = () => { setFallback(natural); browserTts.speak(text, lang, finished, rate); };
    if (!natural) { device(); return; }
    const player = audio.current ?? new Audio();
    audio.current = player;
    player.onended = finished;
    const key = `${lang}:${rate}:${text}`;
    const play = async (url: string) => {
      if (current !== generation.current) return;
      setLoading(false);
      player.src = url;
      player.onerror = () => { if (current === generation.current) { setBlocked(true); finished(); } };
      try { await player.play(); }
      catch { if (current === generation.current) { setBlocked(true); finished(); } }
    };
    const cached = urls.current.get(key);
    if (cached) { void play(cached); return; }
    const controller = new AbortController(); abort.current = controller;
    setLoading(true);
    const deadline = window.setTimeout(() => {
      if (current !== generation.current || controller.signal.aborted) return;
      controller.abort(); setLoading(false); device();
    }, 20000);
    void (async () => {
      try {
        const response = await fetch(`/api/interviews/${encodeURIComponent(interviewId)}/speech`, {
          method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, rate }), signal: controller.signal,
        });
        if (!response.ok) {
          if (current !== generation.current) return;
          setLoading(false);
          if (response.status === 503 || response.status === 429) device();
          else { setBlocked(true); finished(); }
          return;
        }
        const blob = await response.blob();
        if (current !== generation.current) return;
        const url = URL.createObjectURL(blob);
        urls.current.set(key, url);
        while (urls.current.size > 4) { const first = urls.current.keys().next().value!; URL.revokeObjectURL(urls.current.get(first)!); urls.current.delete(first); }
        await play(url);
      } catch { if (current === generation.current && !controller.signal.aborted) { setLoading(false); device(); } }
      finally { window.clearTimeout(deadline); }
    })();
  }, [lang, interviewId, natural, rate, stop]);
  useEffect(() => { stop(); return stop; }, [lang, interviewId, natural, rate, stop]);
  useEffect(() => () => { for (const url of urls.current.values()) URL.revokeObjectURL(url); urls.current.clear(); }, []);
  return { speak, stop, speaking, loading, fallback, blocked, available: natural || browserTts.available() };
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
