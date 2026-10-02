/** Minimal i18n: English source strings are the keys; DE / FR / IT live in
 * strings.ts. Missing translations fall back to English, never to a key. */

import { createContext, useCallback, useContext, useMemo, useState } from "react";

import type { InterviewLang, Lang, Localized } from "../types";
import { WORKSPACE_STRINGS } from "./workspaceStrings";
import { STRINGS } from "./strings";

type Vars = Record<string, string | number>;

interface I18n {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (source: string, vars?: Vars) => string;
}

const I18nContext = createContext<I18n>({ lang: "en", setLang: () => {}, t: (s) => s });

export function detectLang(): Lang {
  try {
    const saved = localStorage.getItem("zusage.lang");
    if (saved === "de" || saved === "fr" || saved === "it" || saved === "en") return saved;
  } catch {
    /* storage unavailable */
  }
  return "en";
}

export function translate(lang: Lang, source: string, vars?: Vars): string {
  let text = lang === "en" ? source : (WORKSPACE_STRINGS[lang] as Record<string, string>)?.[source] ?? (WORKSPACE_STRINGS[lang] as Record<string,string>)?.[source] ?? (WORKSPACE_STRINGS[lang] as Record<string,string>)?.[source] ?? STRINGS[lang]?.[source] ?? source;
  if (vars) for (const [key, value] of Object.entries(vars)) text = text.replaceAll(`{${key}}`, String(value));
  return text;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detectLang);
  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    document.documentElement.lang = next;
    try {
      localStorage.setItem("zusage.lang", next);
    } catch {
      /* ignore */
    }
  }, []);
  const t = useCallback((source: string, vars?: Vars) => translate(lang, source, vars), [lang]);
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}

/** Pick a localized catalog value (occupation names, persona roles...). */
export function loc(value: Localized | undefined, lang: InterviewLang): string {
  if (!value) return "";
  return value[lang] ?? value[lang === "gsw" ? "de" : lang] ?? value.de ?? value.en ?? "";
}

export const LANG_LABEL: Record<InterviewLang, string> = {
  de: "Deutsch",
  fr: "Français",
  it: "Italiano",
  en: "English",
  gsw: "Schwiizerdütsch",
};

export const LOCALE: Record<InterviewLang, string> = {
  de: "de-CH",
  fr: "fr-CH",
  it: "it-CH",
  en: "en-GB",
  gsw: "de-CH",
};
