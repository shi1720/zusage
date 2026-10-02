import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";

import { api } from "../api";
import { loc, useI18n } from "../lib/i18n";
import type { Criterion, InterviewLang, Phase } from "../types";

export function useCatalog() {
  return useQuery({ queryKey: ["catalog"], queryFn: api.catalog, staleTime: Infinity });
}

const CRITERION_EN: Record<Criterion, string> = {
  clarity: "Clarity",
  relevance: "Relevance",
  motivation: "Motivation",
  self_awareness: "Self-awareness",
  communication: "Communication",
  examples: "Concrete examples",
};

export function useCriterionName() {
  const { t } = useI18n();
  return useCallback((crit: Criterion | string) => t(CRITERION_EN[crit as Criterion] ?? crit), [t]);
}

const PHASE_EN: Record<Phase, string> = {
  intro: "Introduction",
  motivation: "Motivation",
  strengths: "Strengths",
  situational: "Situations",
  candidate_questions: "Your questions",
  closing: "Goodbye",
};

export function usePhaseName() {
  const { t } = useI18n();
  return useCallback((phase: Phase | string | null) => (phase ? t(PHASE_EN[phase as Phase] ?? phase) : ""), [t]);
}

export function useOccupationName() {
  const { data } = useCatalog();
  const { lang } = useI18n();
  return useCallback(
    (id: string, as?: InterviewLang) => loc(data?.occupations.find((o) => o.id === id)?.name, as ?? lang) || id,
    [data, lang],
  );
}
