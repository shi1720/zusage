/** First-run onboarding for students: three short steps that give the
 * interviewer something personal to work with (and the coach a story bank). */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useState } from "react";

import { api } from "../api";
import { useAuth } from "../auth";
import { cn } from "../lib/format";
import { LANG_LABEL, loc, useI18n } from "../lib/i18n";
import type { InterviewLang } from "../types";
import { useToast } from "./Toast";
import { OccIcon } from "./OccIcon";
import { Button, Field, inputClass, Modal, Segmented } from "./ui";
import { useCatalog } from "./useCatalog";

export function Onboarding() {
  const toast = useToast();
  const { t, lang } = useI18n();
  const { user, setUser } = useAuth();
  const { data: catalog } = useCatalog();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const [age, setAge] = useState("15");
  const [school, setSchool] = useState("");
  const [hobbies, setHobbies] = useState("");
  const [occupation, setOccupation] = useState("");
  const [language, setLanguage] = useState<InterviewLang>(lang);
  const [experience, setExperience] = useState("");
  const [story, setStory] = useState("");

  const finish = useMutation({
    mutationFn: async () => {
      await api.me.saveProfile({
        age: Number(age) || undefined,
        school,
        hobbies: hobbies.split(",").map((h) => h.trim()).filter(Boolean).slice(0, 8),
        target_occupation_id: occupation || undefined,
        interview_language: language,
        experience,
        stories: story.trim() ? [{ title: "", text: story.trim() }] : [],
      });
      return api.me.update({ onboarded: true });
    },
    onError: (e) => toast(e.message, "err"),
    onSuccess: (u) => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      setUser(u);
    },
  });
  const skip = useMutation({ mutationFn: () => api.me.update({ onboarded: true }), onSuccess: setUser });

  if (!user || user.role !== "student" || user.onboarded) return null;

  return (
    <Modal title={t("Welcome to Zusage, {name}!", { name: user.display_name })} onClose={() => skip.mutate()} wide>
      <div className="mb-5 flex gap-1.5" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span key={i} className={cn("h-1.5 flex-1 rounded-full", i <= step ? "bg-sign" : "bg-raised")} />
        ))}
      </div>

      {step === 0 && (
        <div className="space-y-4">
          <p className="text-[15px] text-ink-2">{t("Three quick questions so your interviewer can ask about YOU. No addresses or phone numbers needed.")}</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t("Age")}>
              <input type="number" min={13} max={25} className={inputClass} value={age} onChange={(e) => setAge(e.target.value)} />
            </Field>
            <Field label={t("School / class")} hint={t("e.g. Sek A, 3rd year")}>
              <input className={inputClass} value={school} onChange={(e) => setSchool(e.target.value)} />
            </Field>
          </div>
          <Field label={t("Hobbies")} hint={t("Separate with commas")}>
            <input className={inputClass} value={hobbies} onChange={(e) => setHobbies(e.target.value)} />
          </Field>
        </div>
      )}

      {step === 1 && (
        <div className="space-y-4">
          <Field label={t("Dream apprenticeship")}>
            <div className="grid max-h-72 grid-cols-1 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
              {catalog?.occupations.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  onClick={() => setOccupation(o.id)}
                  className={cn(
                    "flex cursor-pointer items-center gap-2.5 rounded-xl border p-2.5 text-left text-sm",
                    occupation === o.id ? "border-ink bg-sign/30" : "border-line hover:border-ink-3",
                  )}
                >
                  <OccIcon name={o.icon} size={18} className="shrink-0 text-ink-2" />
                  <span className="font-bold leading-snug">{loc(o.name, lang)}</span>
                </button>
              ))}
            </div>
          </Field>
          <Field label={t("Preferred interview language")}>
            <Segmented
              value={language}
              onChange={setLanguage}
              options={(["de", "fr", "it", "en", "gsw"] as InterviewLang[]).map((l) => ({ value: l, label: LANG_LABEL[l] }))}
            />
          </Field>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <Field label={t("Trial apprenticeships & experience")} hint={t("Where did you do a Schnupperlehre? What did you do there?")}>
            <textarea className={cn(inputClass, "min-h-20")} value={experience} onChange={(e) => setExperience(e.target.value)} />
          </Field>
          <Field label={t("One moment you're proud of")} hint={t("A problem you solved or a time you helped someone - great material for answers.")}>
            <textarea className={cn(inputClass, "min-h-20")} value={story} onChange={(e) => setStory(e.target.value)} maxLength={400} />
          </Field>
        </div>
      )}

      <div className="mt-6 flex items-center justify-between">
        <button onClick={() => skip.mutate()} className="cursor-pointer text-sm text-ink-3 underline">
          {t("Skip for now")}
        </button>
        {step < 2 ? (
          <Button variant="primary" onClick={() => setStep(step + 1)}>
            {t("Next")} <ArrowRight size={16} />
          </Button>
        ) : (
          <Button variant="sign" onClick={() => finish.mutate()} disabled={finish.isPending}>
            {t("Let's go")} <ArrowRight size={16} />
          </Button>
        )}
      </div>
    </Modal>
  );
}
