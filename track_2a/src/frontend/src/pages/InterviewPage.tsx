/** The interview room - focus mode, no app chrome.
 *
 * Learning-science moments built into the flow:
 * - predict-then-reveal: the student rates their own answer BEFORE the coach's
 *   feedback appears (metacognitive calibration);
 * - immediate retry: answer the same question again and see the delta
 *   (deliberate practice);
 * - scaffolds on demand: a structure hint per phase (STAR etc.) plus the
 *   student's own story bank - help that fades because it's opt-in.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CornerDownLeft,
  Lightbulb,
  Mic,
  MicOff,
  RotateCcw,
  Square,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../api";
import { CriterionRows } from "../components/charts";
import { CONFIDENCE_FACES } from "../components/OccIcon";
import { useToast } from "../components/Toast";
import { usePhaseName } from "../components/useCatalog";
import { Badge, Button, Modal, Spinner, Typing } from "../components/ui";
import { cn } from "../lib/format";
import { LANG_LABEL, useI18n } from "../lib/i18n";
import { useDictation, useTts } from "../lib/speech";
import type { Assessment, Interview, Phase, Turn } from "../types";

// ---------------------------------------------------------------------------
// progress: Swiss trail signposts
// ---------------------------------------------------------------------------

function TrailProgress({ iv }: { iv: Interview }) {
  const phaseName = usePhaseName();
  const phases = useMemo(() => [...new Set(iv.phases)] as Phase[], [iv.phases]);
  const answeredPhases = new Set(iv.turns.map((t) => t.phase));
  const current = iv.done ? null : iv.current.phase;
  return (
    <ol className="flex min-w-0 items-center gap-1.5 overflow-x-auto" aria-label="Progress">
      {phases.map((phase) => {
        const isCurrent = phase === current;
        const done = !isCurrent && answeredPhases.has(phase);
        return (
          <li key={phase} className="flex shrink-0 items-center gap-1.5" aria-current={isCurrent ? "step" : undefined}>
            {isCurrent ? (
              <span className="signpost font-sign py-1 pl-2.5 text-[11.5px]">{phaseName(phase)}</span>
            ) : (
              <span className={cn("flex items-center gap-1.5 text-[12.5px]", done ? "text-ink-2" : "text-ink-3")}>
                <span className={cn("h-3.5 w-2 rounded-[2px]", done ? "blaze" : "border border-line bg-card")} />
                <span className="hidden lg:inline">{phaseName(phase)}</span>
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

// ---------------------------------------------------------------------------
// coach panel
// ---------------------------------------------------------------------------

const RATING = [
  { value: 1, face: "😕", label: "Not great" },
  { value: 2, face: "🙂", label: "Okay" },
  { value: 3, face: "💪", label: "Strong" },
];

function highlight(answer: string, evidence?: string) {
  if (!evidence) return answer;
  const idx = answer.toLowerCase().indexOf(evidence.toLowerCase());
  if (idx < 0) return answer;
  return (
    <>
      {answer.slice(0, idx)}
      <mark className="rounded bg-sign px-0.5 text-ink">{answer.slice(idx, idx + evidence.length)}</mark>
      {answer.slice(idx + evidence.length)}
    </>
  );
}

function FeedbackCard({
  turn,
  feedback,
  canRetry,
  onRetry,
  onRate,
}: {
  turn: Turn;
  feedback: Assessment;
  canRetry: boolean;
  onRetry: () => void;
  onRate: (rating: number) => void;
}) {
  const { t } = useI18n();
  const [revealed, setRevealed] = useState(turn.self_rating != null);
  const [showBetter, setShowBetter] = useState(false);
  useEffect(() => {
    setRevealed(turn.self_rating != null);
    setShowBetter(false);
  }, [turn.idx, turn.self_rating]);

  if (!revealed) {
    return (
      <div className="animate-rise">
        <p className="font-display text-lg font-bold">{t("How did that answer go?")}</p>
        <p className="mt-1 text-sm text-ink-2">{t("Guess first - then compare with your coach. This trains your inner judge.")}</p>
        <div className="mt-4 grid grid-cols-3 gap-2">
          {RATING.map((r) => (
            <button
              key={r.value}
              onClick={() => {
                onRate(r.value);
                setRevealed(true);
              }}
              className="flex cursor-pointer flex-col items-center gap-1 rounded-2xl border border-line bg-card py-3 transition-all hover:border-ink hover:bg-sign/30"
            >
              <span className="text-2xl">{r.face}</span>
              <span className="text-xs font-bold">{t(r.label)}</span>
            </button>
          ))}
        </div>
        <button onClick={() => setRevealed(true)} className="mt-3 cursor-pointer text-xs text-ink-3 underline">
          {t("Skip and show feedback")}
        </button>
      </div>
    );
  }

  const scores = feedback.scores ?? {};
  const values = Object.values(scores) as number[];
  const mean = values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  const coachBand = mean == null ? null : mean < 2.25 ? 1 : mean < 3.25 ? 2 : 3;
  const own = turn.self_rating;

  return (
    <div className="animate-rise space-y-4">
      <div className="flex items-center justify-between gap-2">
        <p className="font-sign text-[12px] text-dusk">{t("Your coach")}</p>
        {feedback.degraded && <Badge tone="sign">{t("backup coach")}</Badge>}
      </div>

      {own != null && coachBand != null && (
        <p className="rounded-xl bg-raised px-3 py-2 text-[13px] text-ink-2">
          {own === coachBand
            ? t("Your guess matched the coach - good self-assessment!")
            : own > coachBand
              ? t("You rated yourself a bit higher than the coach did.")
              : t("You were stricter with yourself than the coach - it went better than you thought!")}
        </p>
      )}

      {feedback.strength && (
        <div>
          <p className="text-[13px] font-bold text-fir">✓ {t("What worked")}</p>
          <p className="mt-0.5 text-[15px] leading-snug">{feedback.strength}</p>
        </div>
      )}
      {feedback.tip && (
        <div className="rounded-xl border-l-4 border-sign bg-sign/12 px-3 py-2.5">
          <p className="text-[13px] font-bold">→ {t("Try next")}</p>
          <p className="mt-0.5 text-[15px] leading-snug">{feedback.tip}</p>
        </div>
      )}
      {feedback.evidence && (
        <p className="text-[13px] text-ink-2">
          <span className="font-bold">{t("Based on your words:")}</span> «{feedback.evidence}»
        </p>
      )}
      {feedback.privacy_note && <p className="rounded-xl bg-lake/10 px-3 py-2 text-[13px] text-lake">{feedback.privacy_note}</p>}

      {values.length > 0 && <CriterionRows scores={scores} previous={turn.previous?.scores} compact />}

      {feedback.better_answer && (
        <div>
          <button onClick={() => setShowBetter((v) => !v)} className="cursor-pointer text-sm font-bold text-lake hover:underline">
            {showBetter ? t("Hide example") : t("How it could sound")}
          </button>
          {showBetter && (
            <p className="mt-2 rounded-xl bg-raised p-3 text-[14.5px] leading-relaxed italic">{feedback.better_answer}</p>
          )}
        </div>
      )}

      {canRetry && (
        <Button variant="outline" className="w-full" onClick={onRetry}>
          <RotateCcw size={16} /> {t("Try this answer again")}
        </Button>
      )}
    </div>
  );
}

function HintPanel({ phase, stories }: { phase: Phase | null; stories: string[] }) {
  const { t } = useI18n();
  const frames: Record<string, string[]> = {
    intro: [t("Who are you?"), t("What do you enjoy doing?"), t("What connects you to this job?")],
    motivation: [t("Your reason"), t("A real experience (e.g. trial apprenticeship)"), t("Why this company")],
    strengths: [t("Name the strength"), t("Give an example"), t("How it helps in the job")],
    situational: [t("Situation"), t("What YOU did"), t("Result / what you learned")],
    candidate_questions: [t("What does a typical day look like?"), t("Can I do the vocational baccalaureate (BM)?"), t("When will you decide?")],
  };
  const steps = frames[phase ?? ""] ?? frames.situational;
  return (
    <div className="animate-rise space-y-3">
      <p className="font-sign text-[12px] text-dusk">{t("Hint")}</p>
      <p className="text-sm text-ink-2">
        {phase === "candidate_questions" ? t("Good questions to ask:") : t("A structure that works:")}
      </p>
      <ol className="space-y-1.5">
        {steps.map((step, i) => (
          <li key={step} className="flex items-start gap-2 text-[15px]">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sign font-mono text-[11px] font-bold">
              {i + 1}
            </span>
            {step}
          </li>
        ))}
      </ol>
      {stories.length > 0 && (
        <div className="rounded-xl bg-raised p-3">
          <p className="text-[13px] font-bold">{t("From your story bank")}</p>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-[13.5px] text-ink-2">
            {stories.slice(0, 3).map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// page
// ---------------------------------------------------------------------------

export default function InterviewPage() {
  const { id = "" } = useParams();
  const { t } = useI18n();
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: iv, isLoading, error, refetch } = useQuery({ queryKey: ["interview", id], queryFn: () => api.interviews.get(id) });
  const { data: profile } = useQuery({ queryKey: ["profile"], queryFn: api.me.profile });

  const [draft, setDraft] = useState("");
  const [retrying, setRetrying] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [voiceOn, setVoiceOn] = useState(() => {
    try {
      return localStorage.getItem("zusage.voice") === "1";
    } catch {
      return false;
    }
  });
  const [finishing, setFinishing] = useState(false);
  const [confAfter, setConfAfter] = useState<number | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const lastSpoken = useRef<string>("");

  const lang = iv?.language ?? "de";
  const tts = useTts(lang);
  const appendDictation = useCallback((text: string) => setDraft((d) => (d ? `${d} ${text}` : text)), []);
  const dictation = useDictation(lang, appendDictation);

  const setData = (next: Interview) => queryClient.setQueryData(["interview", id], next);

  const send = useMutation({
    mutationFn: (answer: string) => (retrying ? api.interviews.retry(id, answer) : api.interviews.answer(id, answer)),
    onSuccess: (next) => {
      setData(next);
      setDraft("");
      setRetrying(false);
      setShowHint(false);
      if (next.done && !next.safety_pause) setFinishing(true);
    },
    onError: (exc) => toast(exc instanceof ApiError ? exc.message : t("The coach did not answer - try again."), "err"),
  });

  const rate = useMutation({
    mutationFn: ({ idx, rating }: { idx: number; rating: number }) => api.interviews.rate(id, idx, rating),
    onSuccess: setData,
    onError: (exc) => toast(exc instanceof Error ? exc.message : t("Something went wrong - try again."), "err"),
  });

  const resume = useMutation({ mutationFn: () => api.interviews.resume(id), onSuccess: setData,
    onError: (exc) => toast(exc instanceof Error ? exc.message : t("Something went wrong - try again."), "err") });

  const finish = useMutation({
    mutationFn: () => api.interviews.finish(id, confAfter),
    onSuccess: (done) => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["progress"] });
      void queryClient.invalidateQueries({ queryKey: ["drills"] });
      navigate(done.status === "completed" ? `/report/${done.id}` : "/");
    },
    onError: (exc) => toast(exc instanceof Error ? exc.message : t("Something went wrong - try again."), "err"),
  });

  // speak new interviewer messages when voice is on
  useEffect(() => {
    if (!iv || !voiceOn || iv.safety_pause) return;
    if (iv.interviewer_message && iv.interviewer_message !== lastSpoken.current) {
      lastSpoken.current = iv.interviewer_message;
      tts.speak(iv.interviewer_message);
    }
  }, [iv, voiceOn, tts]);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [iv?.turns.length, send.isPending]);

  // Opening an already-finished interview goes straight to its summit log
  // (only on first load - a just-finished one first asks for confidence).
  const checkedInitial = useRef(false);
  useEffect(() => {
    if (!iv || checkedInitial.current) return;
    checkedInitial.current = true;
    if (iv.status === "completed") navigate(`/report/${iv.id}`, { replace: true });
  }, [iv, navigate]);

  if (error) {
    return <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-5 text-center" role="alert">
      <p>{error.message}</p><Button variant="primary" onClick={() => void refetch()}>{t("Try again")}</Button>
      <Link to="/">{t("Back to today")}</Link></div>;
  }
  if (isLoading || !iv) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const lastTurn = iv.turns[iv.turns.length - 1];
  const training = iv.mode !== "real";
  const stories = [...new Set([
    ...(profile?.data.stories ?? []).map((s) => s.text),
    ...(profile?.data.experience ? [profile.data.experience] : []),
  ].filter(Boolean))];
  const retryQuestion = retrying && lastTurn ? lastTurn.question : null;

  const submit = () => {
    const answer = draft.trim();
    if (!answer || send.isPending) return;
    if (dictation.listening) dictation.stop();
    send.mutate(answer);
  };

  const toggleVoice = () => {
    const next = !voiceOn;
    setVoiceOn(next);
    try {
      localStorage.setItem("zusage.voice", next ? "1" : "0");
    } catch {
      /* ignore */
    }
    if (next) {
      lastSpoken.current = iv.interviewer_message;
      tts.speak(iv.interviewer_message);
    } else tts.stop();
  };

  return (
    <div className="flex h-dvh flex-col bg-page">
      {/* top bar */}
      <header className="flex items-center gap-3 border-b border-line-soft bg-panel px-3 py-2.5 sm:px-5">
        <Link to="/" className="rounded-lg p-2 text-ink-2 hover:bg-raised" aria-label={t("Leave interview")} title={t("Leave - you can continue later")}>
          <ArrowLeft size={20} />
        </Link>
        <div className="min-w-0 flex-1">
          <TrailProgress iv={iv} />
        </div>
        <Badge tone={training ? "lake" : "neutral"} className="hidden sm:inline-flex">
          {iv.mode === "drill" ? t("Drill") : training ? t("Training") : t("Dress rehearsal")}
        </Badge>
        {tts.available && (
          <button
            onClick={toggleVoice}
            className={cn("cursor-pointer rounded-lg p-2", voiceOn ? "bg-sign text-ink" : "text-ink-3 hover:bg-raised")}
            aria-pressed={voiceOn}
            title={voiceOn ? t("Voice on - the interviewer speaks") : t("Turn on the interviewer's voice")}
          >
            {voiceOn ? <Volume2 size={18} /> : <VolumeX size={18} />}
          </button>
        )}
        <Button variant="outline" size="sm" onClick={() => setFinishing(true)} disabled={iv.turns.length === 0 || send.isPending}>
          <Square size={14} /> {t("Finish")}
        </Button>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* conversation */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-8">
            <div className="mx-auto max-w-2xl space-y-5">
              <div className="flex items-center gap-3 pb-2">
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-card text-2xl ring-card">
                  {iv.persona?.avatar}
                </span>
                <div>
                  <p className="font-bold">{iv.persona?.name}</p>
                  <p className="text-sm text-ink-3">
                    {iv.persona?.role} · {iv.company.name}, {iv.company.town}
                  </p>
                  <p className="text-xs text-ink-3">
                    {iv.occupation?.label} · {LANG_LABEL[iv.language]}
                  </p>
                </div>
              </div>

              {iv.turns.map((turn) => (
                <div key={turn.idx} className="space-y-3">
                  <InterviewerBubble text={turn.question} faded />
                  <div className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-ink px-4 py-3 text-[15.5px] leading-relaxed text-white">
                    {training && turn.assessment ? highlight(turn.answer, turn.assessment.evidence) : turn.answer}
                    {turn.retry_of != null && (
                      <span className="mt-1 block text-[11px] text-white/60">↻ {t("second attempt")}</span>
                    )}
                  </div>
                </div>
              ))}

              {send.isPending ? (
                <div className="flex items-center gap-3 text-sm text-ink-3">
                  <Typing /> {t("{name} is listening…", { name: iv.persona?.name ?? "" })}
                </div>
              ) : (
                !iv.safety_pause && (
                  <InterviewerBubble
                    text={retryQuestion ?? iv.interviewer_message}
                    current
                    onSpeak={tts.available ? () => tts.speak(retryQuestion ?? iv.interviewer_message) : undefined}
                  />
                )
              )}
            </div>
          </div>

          {/* composer */}
          {!iv.done && !iv.safety_pause && (
            <div className="border-t border-line-soft bg-panel px-4 py-3 sm:px-8">
              <div className="mx-auto max-w-2xl">
                {retrying && (
                  <div className="mb-2 flex items-center justify-between rounded-lg bg-sign/25 px-3 py-1.5 text-sm">
                    <span>↻ {t("New attempt - use the coach's tip.")}</span>
                    <button className="cursor-pointer text-xs underline" onClick={() => setRetrying(false)}>
                      {t("Cancel")}
                    </button>
                  </div>
                )}
                <div className="flex items-end gap-2">
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
                    }}
                    rows={3}
                    maxLength={1500}
                    placeholder={iv.language === "gsw" ? t("Answer in dialect or standard German…") : t("Your answer…")}
                    aria-label={t("Your answer")}
                    className="min-h-[84px] flex-1 resize-none rounded-2xl border border-line bg-card px-4 py-3 text-[16px] leading-relaxed focus:border-ink focus:outline-none"
                    disabled={send.isPending}
                    autoFocus
                  />
                  <div className="flex flex-col gap-2">
                    {dictation.available && (
                      <button
                        onClick={dictation.listening ? dictation.stop : dictation.start}
                        className={cn(
                          "flex h-11 w-11 cursor-pointer items-center justify-center rounded-xl border",
                          dictation.listening ? "recording border-blaze bg-blaze text-white" : "border-line bg-card text-ink-2 hover:border-ink",
                        )}
                        aria-pressed={dictation.listening}
                        title={t("Dictate (uses your browser's speech recognition)")}
                      >
                        {dictation.listening ? <MicOff size={18} /> : <Mic size={18} />}
                      </button>
                    )}
                    <button
                      onClick={submit}
                      disabled={!draft.trim() || send.isPending}
                      className="flex h-11 w-11 cursor-pointer items-center justify-center rounded-xl bg-ink text-white disabled:opacity-40"
                      aria-label={t("Send answer")}
                      title={t("Send (Ctrl+Enter)")}
                    >
                      {send.isPending ? <Spinner className="border-t-white" /> : <CornerDownLeft size={18} />}
                    </button>
                  </div>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs text-ink-3">
                  <button onClick={() => setShowHint((v) => !v)} className="flex cursor-pointer items-center gap-1 font-bold text-lake hover:underline">
                    <Lightbulb size={14} /> {showHint ? t("Hide hint") : t("I'm stuck - give me a hint")}
                  </button>
                  <span className="font-mono">{draft.length}/1500</span>
                </div>
                {showHint && (
                  <div className="mt-3 rounded-2xl bg-card p-4 ring-card lg:hidden">
                    <HintPanel phase={iv.current.phase} stories={stories} />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* coach panel */}
        <aside className="hidden w-[380px] shrink-0 overflow-y-auto border-l border-line-soft bg-panel p-5 lg:block">
          {training && iv.last_feedback && lastTurn && !showHint ? (
            <FeedbackCard
              turn={lastTurn}
              feedback={iv.last_feedback}
              canRetry={iv.can_retry && !retrying && iv.mode === "training"}
              onRetry={() => setRetrying(true)}
              onRate={(rating) => rate.mutate({ idx: lastTurn.idx, rating })}
            />
          ) : showHint || training ? (
            <HintPanel phase={iv.current.phase} stories={stories} />
          ) : (
            <div className="space-y-3">
              <p className="font-sign text-[12px] text-dusk">{t("Dress rehearsal")}</p>
              <p className="text-[15px] leading-relaxed text-ink-2">
                {t("Like the real interview: no tips in between. Your full feedback waits in your summit log at the end.")}
              </p>
              <div className="rounded-xl bg-raised p-3 text-sm text-ink-2">
                <p className="font-bold text-ink">{t("Nervous? Try this:")}</p>
                <p className="mt-1">{t("Breathe in for 4 seconds, out for 6. Then answer the first sentence slowly.")}</p>
              </div>
            </div>
          )}
          <p className="mt-8 border-t border-line-soft pt-3 font-mono text-[11px] text-ink-3">
            {iv.usage.model} · {iv.usage.llm_calls} {t("model calls")} · {iv.usage.calls_per_answer} / {t("answer")}
          </p>
        </aside>
      </div>

      {/* mobile feedback drawer */}
      {training && iv.last_feedback && lastTurn && !send.isPending && (
        <MobileFeedback key={lastTurn.idx}>
          <FeedbackCard
            turn={lastTurn}
            feedback={iv.last_feedback}
            canRetry={iv.can_retry && !retrying && iv.mode === "training"}
            onRetry={() => setRetrying(true)}
            onRate={(rating) => rate.mutate({ idx: lastTurn.idx, rating })}
          />
        </MobileFeedback>
      )}

      {iv.safety_pause && iv.safety_message && (
        <Modal title={t("Let's pause for a moment")} onClose={() => resume.mutate()}>
          <p className="text-[15.5px] leading-relaxed">{iv.safety_message}</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <a href="https://www.147.ch" target="_blank" rel="noreferrer">
              <Button variant="sign">147.ch</Button>
            </a>
            <Button variant="outline" onClick={() => resume.mutate()}>
              {t("Continue practising")}
            </Button>
            <Button variant="ghost" onClick={() => navigate("/")}>
              {t("Stop for today")}
            </Button>
          </div>
        </Modal>
      )}

      {finishing && (
        <Modal title={iv.done ? t("Interview finished!") : t("Finish the interview?")} onClose={() => !iv.done && setFinishing(false)}>
          <p className="text-[15px] text-ink-2">{t("How confident do you feel about job interviews now?")}</p>
          <div className="mt-3 flex flex-wrap gap-2" role="radiogroup">
            {CONFIDENCE_FACES.map((face, i) => (
              <button
                key={face}
                role="radio"
                aria-checked={confAfter === i + 1}
                onClick={() => setConfAfter(i + 1)}
                className={cn(
                  "flex h-12 w-12 cursor-pointer items-center justify-center rounded-xl border text-xl",
                  confAfter === i + 1 ? "border-ink bg-sign" : "border-line bg-card",
                )}
              >
                {face}
              </button>
            ))}
          </div>
          <Button variant="primary" size="lg" className="mt-5 w-full" onClick={() => finish.mutate()} disabled={finish.isPending}>
            {finish.isPending ? <Spinner className="border-t-white" /> : null}
            {t("Open my summit log")}
          </Button>
          {finish.isPending && <p className="mt-2 text-center text-xs text-ink-3">{t("Your coach is writing your feedback…")}</p>}
        </Modal>
      )}
    </div>
  );
}

function InterviewerBubble({ text, current, faded, onSpeak }: { text: string; current?: boolean; faded?: boolean; onSpeak?: () => void }) {
  return (
    <div
      className={cn(
        "max-w-[92%] rounded-2xl rounded-bl-md bg-card px-4 py-3 ring-card",
        current && "animate-rise",
        faded && "opacity-75",
      )}
    >
      <p className={cn("leading-relaxed", current ? "font-display text-[19px] font-semibold" : "text-[15px]")}>{text}</p>
      {current && onSpeak && (
        <button onClick={onSpeak} className="mt-1.5 flex cursor-pointer items-center gap-1 text-xs text-ink-3 hover:text-ink" aria-label="Play">
          <Volume2 size={13} /> ▶
        </button>
      )}
    </div>
  );
}

function MobileFeedback({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  const { t } = useI18n();
  if (!open)
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed right-4 bottom-36 z-40 cursor-pointer rounded-full bg-dusk px-4 py-2 text-sm font-bold text-white shadow-lg lg:hidden"
      >
        {t("Coach feedback")}
      </button>
    );
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 max-h-[70vh] overflow-y-auto rounded-t-2xl bg-card p-5 shadow-[0_-12px_40px_-12px_rgb(22_35_46/0.4)] lg:hidden">
      <button onClick={() => setOpen(false)} className="mb-2 w-full cursor-pointer text-center text-xs text-ink-3">
        ▾ {t("Hide")}
      </button>
      {children}
    </div>
  );
}
