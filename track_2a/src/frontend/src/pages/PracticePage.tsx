/** Set up a practice interview: which apprenticeship, which language, who
 * interviews, how realistic - and a one-tap confidence check (self-efficacy
 * baseline for the "before → after" measure). */

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, ChevronDown, ClipboardPaste, Timer } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, ApiError } from "../api";
import { CONFIDENCE_FACES, OccIcon } from "../components/OccIcon";
import { PageHeader } from "../components/Shell";
import { useToast } from "../components/Toast";
import { useCatalog } from "../components/useCatalog";
import { Button, Card, Eyebrow, inputClass, Segmented, Spinner } from "../components/ui";
import { cn } from "../lib/format";
import { LANG_LABEL, loc, useI18n } from "../lib/i18n";
import type { InterviewLang } from "../types";

export default function PracticePage() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { data: catalog } = useCatalog();
  const { data: profile } = useQuery({ queryKey: ["profile"], queryFn: api.me.profile });
  const { data: apps } = useQuery({ queryKey: ["applications"], queryFn: api.applications.list });

  const [occupation, setOccupation] = useState<string>(params.get("occupation") ?? "");
  const [applicationId, setApplicationId] = useState<string | null>(params.get("application"));
  const [language, setLanguage] = useState<InterviewLang>(lang);
  const [persona, setPersona] = useState("warm");
  const [mode, setMode] = useState<"training" | "real">("training");
  const [length, setLength] = useState<"quick" | "full">("quick");
  const [confidence, setConfidence] = useState<number | null>(null);
  const [posting, setPosting] = useState("");
  const [showPosting, setShowPosting] = useState(false);

  // sensible defaults from the student's profile / chosen application
  useEffect(() => {
    if (!profile) return;
    if (!occupation && profile.data.target_occupation_id) setOccupation(profile.data.target_occupation_id);
    if (profile.data.interview_language) setLanguage(profile.data.interview_language);
  }, [profile]); // eslint-disable-line react-hooks/exhaustive-deps

  const application = useMemo(() => apps?.find((a) => a.id === applicationId) ?? null, [apps, applicationId]);
  useEffect(() => {
    if (application?.occupation_id) setOccupation(application.occupation_id);
  }, [application]);

  const start = useMutation({
    mutationFn: () =>
      api.interviews.start({
        occupation_id: occupation,
        language,
        persona_id: persona,
        mode,
        length,
        application_id: applicationId,
        posting: posting.trim() || undefined,
        confidence_before: confidence,
      }),
    onSuccess: (iv) => navigate(`/interview/${iv.id}`),
    onError: (exc) => toast(exc instanceof ApiError ? exc.message : t("Could not start the interview."), "err"),
  });

  const interviewable = (apps ?? []).filter((a) => !["offer", "rejected"].includes(a.status));

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
      <PageHeader
        eyebrow={t("Practice interview")}
        title={t("Set up your interview")}
        sub={t("Choose what feels right today. You can always pause, retry an answer or stop early.")}
      />

      <div className="space-y-8">
        {interviewable.length > 0 && (
          <section>
            <Eyebrow className="mb-3">{t("For a real application? (optional)")}</Eyebrow>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setApplicationId(null)}
                className={cn(
                  "cursor-pointer rounded-xl border px-3.5 py-2 text-sm",
                  !applicationId ? "border-ink bg-ink text-white" : "border-line bg-card hover:border-ink-3",
                )}
              >
                {t("General practice")}
              </button>
              {interviewable.map((a) => (
                <button
                  key={a.id}
                  onClick={() => setApplicationId(a.id)}
                  className={cn(
                    "cursor-pointer rounded-xl border px-3.5 py-2 text-left text-sm",
                    applicationId === a.id ? "border-ink bg-ink text-white" : "border-line bg-card hover:border-ink-3",
                  )}
                >
                  <span className="block font-bold">{a.company}</span>
                  <span className={cn("block text-xs", applicationId === a.id ? "text-white/70" : "text-ink-3")}>
                    {a.town}
                    {a.posting ? ` · ${t("with job ad")}` : ""}
                  </span>
                </button>
              ))}
            </div>
          </section>
        )}

        <section>
          <Eyebrow className="mb-3">{t("Apprenticeship")}</Eyebrow>
          {!catalog ? (
            <Spinner />
          ) : (
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
              {catalog.occupations.map((occ) => {
                const active = occupation === occ.id;
                return (
                  <button
                    key={occ.id}
                    onClick={() => setOccupation(occ.id)}
                    aria-pressed={active}
                    className={cn(
                      "flex cursor-pointer items-center gap-3 rounded-2xl border p-3 text-left transition-all",
                      active ? "border-ink bg-card shadow-[0_0_0_2px_var(--color-ink)]" : "border-line bg-card hover:border-ink-3",
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                        active ? "bg-sign text-sign-ink" : "bg-raised text-ink-2",
                      )}
                    >
                      <OccIcon name={occ.icon} />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-[14.5px] leading-snug font-bold">{loc(occ.name, lang)}</span>
                      <span className="text-xs text-ink-3">{occ.level === "EBA" ? t("2 years · Federal VET Certificate") : t("3–4 years · Federal VET Diploma")}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <div className="grid gap-8 lg:grid-cols-2">
          <section>
            <Eyebrow className="mb-3">{t("Interview language")}</Eyebrow>
            <Segmented
              value={language}
              onChange={setLanguage}
              options={(["de", "fr", "it", "en", "gsw"] as InterviewLang[]).map((code) => ({
                value: code,
                label: LANG_LABEL[code],
                hint: code === "gsw" ? t("Beta · type in dialect") : undefined,
              }))}
            />
          </section>

          <section>
            <Eyebrow className="mb-3">{t("Interviewer")}</Eyebrow>
            <div className="grid gap-2 sm:grid-cols-3">
              {catalog?.personas.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setPersona(p.id)}
                  aria-pressed={persona === p.id}
                  className={cn(
                    "cursor-pointer rounded-2xl border p-3 text-left transition-all",
                    persona === p.id ? "border-ink bg-card shadow-[0_0_0_2px_var(--color-ink)]" : "border-line bg-card hover:border-ink-3",
                  )}
                >
                  <span className="text-xl">{p.avatar}</span>
                  <span className="mt-1 block text-sm font-bold">{loc(p.name, language)}</span>
                  <span className="block text-xs text-ink-3">{loc(p.role, lang)}</span>
                  <span className="mt-2 flex gap-1" aria-label={t("Difficulty {n} of 3", { n: p.difficulty })}>
                    {[1, 2, 3].map((d) => (
                      <span key={d} className={cn("h-1.5 w-4 rounded-sm", d <= p.difficulty ? "bg-ink" : "bg-raised")} />
                    ))}
                  </span>
                </button>
              ))}
            </div>
          </section>
        </div>

        <div className="grid gap-8 lg:grid-cols-2">
          <section>
            <Eyebrow className="mb-3">{t("Mode")}</Eyebrow>
            <Segmented
              value={mode}
              onChange={setMode}
              options={[
                { value: "training", label: t("Training"), hint: t("Coach tips after every answer, retry allowed") },
                { value: "real", label: t("Dress rehearsal"), hint: t("Like the real thing - feedback at the end") },
              ]}
            />
          </section>
          <section>
            <Eyebrow className="mb-3">{t("Length")}</Eyebrow>
            <Segmented
              value={length}
              onChange={setLength}
              options={[
                { value: "quick", label: t("Short"), hint: t("5 questions · about 6 min") },
                { value: "full", label: t("Complete"), hint: t("10 questions · about 15 min") },
              ]}
            />
          </section>
        </div>

        <section>
          <button
            onClick={() => setShowPosting((v) => !v)}
            className="flex cursor-pointer items-center gap-2 text-sm font-bold text-lake hover:underline"
          >
            <ClipboardPaste size={16} /> {t("Paste a job ad to tailor the questions (optional)")}
            <ChevronDown size={16} className={cn("transition-transform", showPosting && "rotate-180")} />
          </button>
          {showPosting && (
            <textarea
              className={cn(inputClass, "mt-3 min-h-32")}
              placeholder={t("Paste the text of the apprenticeship ad here…")}
              value={posting}
              onChange={(e) => setPosting(e.target.value)}
              maxLength={6000}
            />
          )}
        </section>

        <Card className="contours p-6">
          <p className="font-display text-lg font-bold">{t("How confident do you feel about job interviews right now?")}</p>
          <p className="text-sm text-ink-2">{t("Just for you - we'll ask again afterwards so you can see the difference.")}</p>
          <div className="mt-4 flex flex-wrap gap-2" role="radiogroup">
            {CONFIDENCE_FACES.map((face, i) => (
              <button
                key={face}
                role="radio"
                aria-checked={confidence === i + 1}
                aria-label={t("Confidence {n} of 5", { n: i + 1 })}
                onClick={() => setConfidence(i + 1)}
                className={cn(
                  "flex h-14 w-14 cursor-pointer items-center justify-center rounded-2xl border text-2xl transition-all",
                  confidence === i + 1 ? "scale-110 border-ink bg-sign" : "border-line bg-card hover:border-ink-3",
                )}
              >
                {face}
              </button>
            ))}
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <Button variant="primary" size="lg" disabled={!occupation || start.isPending} onClick={() => start.mutate()}>
              {start.isPending ? <Spinner className="border-t-white" /> : <ArrowRight size={18} />}
              {t("Start interview")}
            </Button>
            <span className="flex items-center gap-1.5 text-sm text-ink-3">
              <Timer size={15} /> {length === "quick" ? t("about 6 min") : t("about 15 min")}
            </span>
            {!occupation && <span className="text-sm text-ink-3">{t("Choose an apprenticeship first.")}</span>}
          </div>
        </Card>
      </div>
    </div>
  );
}
