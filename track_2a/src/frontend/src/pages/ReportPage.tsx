/** The "Gipfelbuch" (summit log) - the end-of-interview report.
 *
 * Signature visual: the interview drawn as a Swiss trail elevation profile.
 * Each answer is a waypoint whose height is its rubric score; the summit
 * carries a red-white-red blaze. Structure follows Hattie & Timperley:
 * where am I going (goal), how am I going (profile), where to next (2 goals).
 */

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Mountain, Printer, Repeat } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import { CriterionRows, Radar } from "../components/charts";
import { CONFIDENCE_FACES } from "../components/OccIcon";
import { usePhaseName } from "../components/useCatalog";
import { Badge, Button, Card, Eyebrow, Spinner } from "../components/ui";
import { cn, longDate, scoreColor } from "../lib/format";
import { LANG_LABEL, LOCALE, useI18n } from "../lib/i18n";
import type { Turn } from "../types";

function turnMean(turn: Turn): number | null {
  const values = Object.values(turn.assessment?.scores ?? {}) as number[];
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

function ElevationProfile({ turns }: { turns: Turn[] }) {
  const { t } = useI18n();
  const phaseName = usePhaseName();
  const [hover, setHover] = useState<number | null>(null);
  const points = turns.map((turn) => ({ turn, value: turnMean(turn) })).filter((p) => p.value != null) as {
    turn: Turn;
    value: number;
  }[];
  if (points.length < 2) return null;
  const W = 640;
  const H = 170;
  const padX = 18;
  const top = 26;
  const base = H - 24;
  const x = (i: number) => padX + (i * (W - 2 * padX)) / (points.length - 1);
  const y = (v: number) => base - ((v - 1) / 3) * (base - top);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.value)}`).join(" ");
  const area = `${line} L${x(points.length - 1)},${base} L${x(0)},${base} Z`;
  const peak = points.reduce((best, p, i) => (p.value > points[best].value ? i : best), 0);

  return (
    <figure className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={t("Your interview as a trail: height = score per answer")}>
        <defs>
          <linearGradient id="hill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--color-score-3)" stopOpacity="0.35" />
            <stop offset="100%" stopColor="var(--color-score-1)" stopOpacity="0.15" />
          </linearGradient>
        </defs>
        {[1, 2, 3, 4].map((lvl) => (
          <g key={lvl}>
            <line x1={padX} x2={W - padX} y1={y(lvl)} y2={y(lvl)} stroke="var(--color-line-soft)" strokeDasharray={lvl === 4 ? "" : "2 4"} />
            <text x={W - padX} y={y(lvl) - 4} textAnchor="end" className="fill-ink-3 font-mono" style={{ fontSize: 10 }}>
              {lvl}
            </text>
          </g>
        ))}
        <path d={area} fill="url(#hill)" />
        <path d={line} fill="none" stroke="var(--color-ink)" strokeWidth={2} strokeLinejoin="round" strokeDasharray="7 4" />
        {/* summit blaze */}
        <g transform={`translate(${x(peak) - 6}, ${y(points[peak].value) - 26})`}>
          <rect width="12" height="5" fill="var(--color-blaze)" />
          <rect y="5" width="12" height="5" fill="#fff" stroke="var(--color-line)" strokeWidth="0.5" />
          <rect y="10" width="12" height="5" fill="var(--color-blaze)" />
        </g>
        {points.map((p, i) => (
          <g key={p.turn.idx} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <rect x={x(i) - 16} y={top - 10} width={32} height={base - top + 20} fill="transparent" />
            <circle cx={x(i)} cy={y(p.value)} r={hover === i ? 7 : 5.5} fill={scoreColor(p.value)} stroke="var(--color-ink)" strokeWidth={1.5} />
          </g>
        ))}
        <line x1={padX} x2={W - padX} y1={base} y2={base} stroke="var(--color-ink-3)" />
      </svg>
      {hover != null && (
        <div
          className="pointer-events-none absolute max-w-[260px] -translate-x-1/2 rounded-lg bg-ink px-3 py-2 text-xs text-white shadow-lg"
          style={{ left: `${(x(hover) / W) * 100}%`, top: -8 }}
        >
          <span className="font-bold">{phaseName(points[hover].turn.phase)}</span> ·{" "}
          <span className="font-mono">{points[hover].value.toFixed(1)}</span>
          <span className="mt-0.5 block text-white/75">{points[hover].turn.question.slice(0, 90)}</span>
        </div>
      )}
    </figure>
  );
}

export default function ReportPage() {
  const { id = "" } = useParams();
  const { t, lang } = useI18n();
  const phaseName = usePhaseName();
  const { data: iv, error, refetch } = useQuery({ queryKey: ["interview", id], queryFn: () => api.interviews.get(id) });
  const { data: history } = useQuery({ queryKey: ["interviews"], queryFn: api.interviews.list });
  const [openTurn, setOpenTurn] = useState<number | null>(null);

  const previous = useMemo(() => {
    if (!iv || !history) return null;
    return (
      history.find((h) => h.id !== iv.id && h.status === "completed" && h.mode !== "drill" && h.created_at < iv.created_at && h.averages) ??
      null
    );
  }, [iv, history]);

  if (error) {
    return <div className="flex flex-col items-center gap-4 p-10 text-center" role="alert"><p>{error.message}</p>
      <Button variant="primary" onClick={() => void refetch()}>{t("Try again")}</Button><Link to="/">{t("Back to today")}</Link></div>;
  }
  if (!iv) {
    return (
      <div className="flex h-full items-center justify-center p-10">
        <Spinner />
      </div>
    );
  }
  const report = iv.report;
  const narrative = report?.narrative ?? {};
  const locale = LOCALE[lang];
  const scoredTurns = iv.turns.filter((turn) => turn.assessment && Object.keys(turn.assessment.scores ?? {}).length);

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
      <div className="no-print mb-6 flex flex-wrap items-center justify-between gap-3">
        <Link to="/" className="text-sm text-ink-3 hover:text-ink">
          ← {t("Back to today")}
        </Link>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => window.print()}>
            <Printer size={15} /> {t("Print / PDF")}
          </Button>
          <Link to={`/practice?occupation=${iv.occupation?.id ?? ""}`}>
            <Button variant="primary" size="sm">
              <Repeat size={15} /> {t("Practise again")}
            </Button>
          </Link>
        </div>
      </div>

      {/* summit header */}
      <Card className="contours overflow-hidden p-6 sm:p-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-xl">
            <Eyebrow>
              {t("Summit log")} · {longDate(iv.created_at, locale)}
            </Eyebrow>
            <h1 className="font-display mt-2 text-[30px] leading-tight font-extrabold sm:text-[36px]">
              {narrative.headline || t("Interview completed")}
            </h1>
            <p className="mt-1 text-sm text-ink-3">
              {iv.occupation?.label} · {iv.company.name} · {iv.persona?.name} · {LANG_LABEL[iv.language]}
            </p>
            {narrative.summary && <p className="mt-4 text-[16px] leading-relaxed text-ink-2">{narrative.summary}</p>}
          </div>
          <div className="shrink-0 text-left sm:text-right">
            <p className="font-hero text-[64px] leading-none">{report?.overall ?? "–"}</p>
            <p className="text-sm text-ink-3">{t("of 100 summit points")}</p>
            {previous?.overall != null && report && (
              <Badge tone={report.overall >= previous.overall ? "fir" : "neutral"} className="mt-2">
                {report.overall >= previous.overall ? "▲" : "▼"} {Math.abs(report.overall - previous.overall)} {t("vs. last time")}
              </Badge>
            )}
          </div>
        </div>
        <div className="mt-6">
          <ElevationProfile turns={scoredTurns} />
        </div>
      </Card>

      {narrative.wise_feedback && (
        <p className="font-display mx-auto my-8 max-w-3xl text-center text-[19px] leading-snug font-semibold text-ink">
          «{narrative.wise_feedback}»
        </p>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-6">
          <Eyebrow className="mb-3">{t("Your profile")}</Eyebrow>
          {report && Object.keys(report.averages).length > 0 ? (
            <>
              <div className="flex justify-center">
                <Radar now={report.averages} before={previous?.averages ?? null} />
              </div>
              <div className="mt-4">
                <CriterionRows scores={report.averages} previous={previous?.averages ?? undefined} />
              </div>
            </>
          ) : (
            <p className="text-sm text-ink-3">{t("Not enough answers for a profile yet.")}</p>
          )}
        </Card>

        <div className="min-w-0 space-y-5">
          <Card className="p-6">
            <Eyebrow className="mb-3">{t("What already works")}</Eyebrow>
            <ul className="space-y-2.5">
              {(narrative.strengths ?? []).map((s) => (
                <li key={s} className="flex gap-2.5 text-[15.5px] leading-snug">
                  <span className="mt-1 h-3.5 w-2 shrink-0 rounded-[2px] blaze" aria-hidden />
                  {s}
                </li>
              ))}
            </ul>
            {narrative.best_moment && (
              <p className="mt-4 rounded-xl bg-raised p-3 text-[14px] text-ink-2">
                <span className="font-bold text-ink">{t("Best moment:")}</span> {narrative.best_moment}
              </p>
            )}
          </Card>

          <Card className="border-t-4 border-sign p-6">
            <Eyebrow className="mb-3">{t("Your next stage")}</Eyebrow>
            <ol className="space-y-4">
              {(narrative.goals ?? []).map((goal, i) => (
                <li key={goal.title} className="flex gap-3">
                  <span className="signpost font-sign h-fit py-1 pl-2 text-[11px]">{i + 1}</span>
                  <div>
                    <p className="font-bold">{goal.title}</p>
                    <p className="text-[15px] leading-snug text-ink-2">{goal.how}</p>
                  </div>
                </li>
              ))}
            </ol>
            <Link to="/" className="no-print mt-5 inline-flex items-center gap-1.5 text-sm font-bold text-lake hover:underline">
              <Mountain size={15} /> {t("Your weakest answers are now 2-minute drills")} <ArrowRight size={14} />
            </Link>
          </Card>

          {iv.confidence_before != null && iv.confidence_after != null && (
            <Card className="flex items-center gap-4 p-5">
              <span className="text-3xl">{CONFIDENCE_FACES[iv.confidence_before - 1]}</span>
              <ArrowRight className="text-ink-3" />
              <span className="text-3xl">{CONFIDENCE_FACES[iv.confidence_after - 1]}</span>
              <p className="text-[15px] text-ink-2">
                {iv.confidence_after > iv.confidence_before
                  ? t("You feel more confident than before. That's what practice does.")
                  : iv.confidence_after === iv.confidence_before
                    ? t("Your confidence is stable - keep going, it grows with repetition.")
                    : t("Tough round? That's normal. The next one usually feels easier.")}
              </p>
            </Card>
          )}
        </div>
      </div>

      <section className="mt-10">
        <h2 className="font-display mb-4 text-xl font-bold">{t("Answer by answer")}</h2>
        <div className="space-y-3">
          {iv.turns.map((turn) => {
            const mean = turnMean(turn);
            const open = openTurn === turn.idx;
            return (
              <Card key={turn.idx} className="overflow-hidden">
                <button
                  className="flex w-full cursor-pointer items-center gap-4 p-4 text-left"
                  onClick={() => setOpenTurn(open ? null : turn.idx)}
                  aria-expanded={open}
                >
                  <span
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl font-mono text-sm font-bold"
                    style={{ background: scoreColor(mean), color: mean != null && mean >= 2.5 ? "#fff" : "var(--color-ink)" }}
                  >
                    {mean != null ? mean.toFixed(1) : "–"}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs text-ink-3">
                      {phaseName(turn.phase)}
                      {turn.is_followup ? ` · ${t("follow-up")}` : ""}
                      {turn.retry_of != null ? ` · ↻ ${t("second attempt")}` : ""}
                    </span>
                    <span className="block truncate font-bold">{turn.question}</span>
                  </span>
                  <span className="text-ink-3">{open ? "−" : "+"}</span>
                </button>
                {open && (
                  <div className="grid gap-5 border-t border-line-soft p-4 sm:grid-cols-2">
                    <div>
                      <p className="text-xs font-bold text-ink-3">{t("Your answer")}</p>
                      <p className="mt-1 text-[15px] leading-relaxed">{turn.answer || <em className="text-ink-3">{t("(deleted after the retention period)")}</em>}</p>
                      {turn.previous && (
                        <p className="mt-2 text-[13px] text-ink-3">
                          {t("First attempt:")} «{turn.previous.answer}»
                        </p>
                      )}
                      {turn.assessment?.better_answer && (
                        <>
                          <p className="mt-4 text-xs font-bold text-ink-3">{t("How it could sound")}</p>
                          <p className="mt-1 rounded-xl bg-raised p-3 text-[14.5px] leading-relaxed italic">{turn.assessment.better_answer}</p>
                        </>
                      )}
                    </div>
                    <div className="space-y-3">
                      {turn.assessment?.strength && (
                        <p className="text-[15px]">
                          <span className="font-bold text-fir">✓ </span>
                          {turn.assessment.strength}
                        </p>
                      )}
                      {turn.assessment?.tip && (
                        <p className={cn("rounded-xl border-l-4 border-sign bg-sign/12 px-3 py-2 text-[15px]")}>→ {turn.assessment.tip}</p>
                      )}
                      {turn.assessment?.scores && <CriterionRows scores={turn.assessment.scores} previous={turn.previous?.scores} compact />}
                    </div>
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      </section>

      <p className="mt-10 text-center font-mono text-[11px] text-ink-3">
        {t("Coach model")}: {iv.usage.model} · {iv.usage.llm_calls} {t("model calls")} · {iv.usage.calls_per_answer} {t("per answer")} ·{" "}
        {iv.usage.tokens_in + iv.usage.tokens_out} tokens
      </p>
    </div>
  );
}
