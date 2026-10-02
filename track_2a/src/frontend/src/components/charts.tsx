/** Hand-rolled SVG charts - no chart library, so the bundle stays small and
 * the app runs air-gapped. Colours come from validated tokens in index.css. */

import { useState } from "react";

import { useI18n } from "../lib/i18n";
import { cn, scoreColor, shortDate } from "../lib/format";
import { CRITERIA, type Criterion } from "../types";
import { useCriterionName } from "./useCatalog";

/** Four-segment meter for one rubric criterion (1-4). */
export function ScoreMeter({ value, className }: { value: number | null | undefined; className?: string }) {
  return (
    <div className={cn("flex gap-[2px]", className)} aria-hidden>
      {[1, 2, 3, 4].map((step) => (
        <span
          key={step}
          className="h-2 flex-1 rounded-[3px]"
          style={{ background: value != null && value >= step - 0.25 ? scoreColor(value) : "var(--color-raised)" }}
        />
      ))}
    </div>
  );
}

export function CriterionRows({
  scores,
  previous,
  compact,
}: {
  scores: Partial<Record<Criterion, number>>;
  previous?: Partial<Record<Criterion, number>>;
  compact?: boolean;
}) {
  const name = useCriterionName();
  const entries = CRITERIA.filter((c) => scores[c] != null);
  return (
    <ul className={cn("space-y-2.5", compact && "space-y-1.5")}>
      {entries.map((crit) => {
        const value = scores[crit]!;
        const before = previous?.[crit];
        const delta = before != null ? value - before : null;
        return (
          <li key={crit} className="grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-3">
            <span className="truncate text-sm text-ink-2">{name(crit)}</span>
            <ScoreMeter value={value} />
            <span className="w-14 text-right font-mono text-sm text-ink">
              {value.toFixed(1)}
              {delta != null && delta !== 0 && (
                <span className={cn("ml-1 text-xs", delta > 0 ? "text-fir" : "text-ink-3")}>
                  {delta > 0 ? "+" : ""}
                  {delta.toFixed(1)}
                </span>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** Six-axis radar: "now" (solid blue) vs optional "before" (dashed orange). */
export function Radar({
  now,
  before,
  size = 280,
  labels = true,
}: {
  now: Partial<Record<Criterion, number>>;
  before?: Partial<Record<Criterion, number>> | null;
  size?: number;
  labels?: boolean;
}) {
  const { t } = useI18n();
  const name = useCriterionName();
  const [hover, setHover] = useState<Criterion | null>(null);
  const pad = labels ? 44 : 12;
  const r = size / 2 - pad;
  const cx = size / 2;
  const cy = size / 2;
  const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / CRITERIA.length;
  const point = (i: number, v: number) => [cx + Math.cos(angle(i)) * (r * v) / 4, cy + Math.sin(angle(i)) * (r * v) / 4];
  const poly = (scores: Partial<Record<Criterion, number>>) =>
    CRITERIA.map((c, i) => point(i, scores[c] ?? 1).join(",")).join(" ");

  return (
    <figure className="relative">
      <svg
        viewBox={labels ? `-84 0 ${size + 168} ${size}` : `0 0 ${size} ${size}`}
        className="w-full max-w-[440px]"
        role="img"
        aria-label={t("Score profile")}
      >
        {[1, 2, 3, 4].map((level) => (
          <polygon
            key={level}
            points={CRITERIA.map((_, i) => point(i, level).join(",")).join(" ")}
            fill="none"
            stroke="var(--color-line)"
            strokeWidth={level === 4 ? 1.2 : 0.8}
          />
        ))}
        {CRITERIA.map((c, i) => {
          const [x, y] = point(i, 4);
          return <line key={c} x1={cx} y1={cy} x2={x} y2={y} stroke="var(--color-line-soft)" strokeWidth={0.8} />;
        })}
        {before && (
          <polygon
            points={poly(before)}
            fill="none"
            stroke="var(--color-series-before)"
            strokeWidth={2}
            strokeDasharray="5 4"
            strokeLinejoin="round"
          />
        )}
        <polygon
          points={poly(now)}
          fill="color-mix(in oklab, var(--color-series-now) 14%, transparent)"
          stroke="var(--color-series-now)"
          strokeWidth={2}
          strokeLinejoin="round"
        />
        {CRITERIA.map((c, i) => {
          const value = now[c];
          if (value == null) return null;
          const [x, y] = point(i, value);
          return (
            <g key={c} onMouseEnter={() => setHover(c)} onMouseLeave={() => setHover(null)}>
              <circle cx={x} cy={y} r={12} fill="transparent" />
              <circle cx={x} cy={y} r={hover === c ? 5.5 : 4} fill="var(--color-series-now)" stroke="#fff" strokeWidth={2} />
            </g>
          );
        })}
        {labels &&
          CRITERIA.map((c, i) => {
            const [x, y] = point(i, 5.05);
            const anchor = Math.abs(x - cx) < 4 ? "middle" : x > cx ? "start" : "end";
            return (
              <text
                key={c}
                x={x}
                y={y}
                textAnchor={anchor}
                dominantBaseline="middle"
                className="fill-ink-2"
                style={{ fontSize: 11.5, fontWeight: hover === c ? 700 : 400 }}
              >
                {name(c)}
              </text>
            );
          })}
      </svg>
      {hover && now[hover] != null && (
        <div className="pointer-events-none absolute top-2 left-2 rounded-lg bg-ink px-2.5 py-1.5 text-xs text-white shadow-lg">
          {name(hover)}: <span className="font-mono">{now[hover]!.toFixed(1)}</span>
          {before?.[hover] != null && (
            <span className="text-white/70">
              {" "}
              ({t("before")} {before[hover]!.toFixed(1)})
            </span>
          )}
        </div>
      )}
      {before && (
        <figcaption className="mt-2 flex flex-wrap gap-4 text-xs text-ink-2">
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-5 bg-series-now" /> {t("This session")}
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-0 w-5 border-t-2 border-dashed border-series-before" /> {t("Previous session")}
          </span>
        </figcaption>
      )}
    </figure>
  );
}

/** Overall score (0-100) over time, with a crosshair tooltip. */
export function TrendChart({
  points,
  locale,
  height = 180,
}: {
  points: { date: string; value: number; label?: string }[];
  locale: string;
  height?: number;
}) {
  const { t } = useI18n();
  const [hover, setHover] = useState<number | null>(null);
  const width = 560;
  const padL = 34;
  const padR = 14;
  const padT = 14;
  const padB = 26;
  if (points.length === 0) return null;
  const x = (i: number) => (points.length === 1 ? (width + padL - padR) / 2 : padL + (i * (width - padL - padR)) / (points.length - 1));
  const y = (v: number) => padT + (1 - v / 100) * (height - padT - padB);
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.value)}`).join(" ");

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label={t("Overall score over time")}
        onMouseLeave={() => setHover(null)}
      >
        {[0, 25, 50, 75, 100].map((v) => (
          <g key={v}>
            <line x1={padL} x2={width - padR} y1={y(v)} y2={y(v)} stroke="var(--color-line-soft)" strokeWidth={1} />
            <text x={padL - 8} y={y(v)} textAnchor="end" dominantBaseline="middle" className="fill-ink-3 font-mono" style={{ fontSize: 10 }}>
              {v}
            </text>
          </g>
        ))}
        <path d={path} fill="none" stroke="var(--color-series-now)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {hover != null && (
          <line x1={x(hover)} x2={x(hover)} y1={padT} y2={height - padB} stroke="var(--color-ink-3)" strokeDasharray="3 3" />
        )}
        {points.map((p, i) => (
          <g key={i} onMouseEnter={() => setHover(i)}>
            <rect x={x(i) - 18} y={padT} width={36} height={height - padT - padB} fill="transparent" />
            <circle cx={x(i)} cy={y(p.value)} r={hover === i ? 6 : 4.5} fill="var(--color-series-now)" stroke="#fff" strokeWidth={2} />
          </g>
        ))}
        {points.map((p, i) =>
          i === 0 || i === points.length - 1 || points.length <= 6 ? (
            <text key={`d${i}`} x={x(i)} y={height - 8} textAnchor="middle" className="fill-ink-3" style={{ fontSize: 10.5 }}>
              {shortDate(p.date, locale)}
            </text>
          ) : null,
        )}
      </svg>
      {hover != null && (
        <div
          className="pointer-events-none absolute -translate-x-1/2 rounded-lg bg-ink px-2.5 py-1.5 text-xs whitespace-nowrap text-white shadow-lg"
          style={{ left: `${(x(hover) / width) * 100}%`, top: 0 }}
        >
          {shortDate(points[hover].date, locale)} · <span className="font-mono">{points[hover].value}</span>
          {points[hover].label && <span className="text-white/70"> · {points[hover].label}</span>}
        </div>
      )}
    </div>
  );
}

/** Confidence before → after per session (dumbbell rows, 1-5 scale). */
export function ConfidenceDumbbell({
  rows,
  locale,
}: {
  rows: { date: string; before: number; after: number }[];
  locale: string;
}) {
  const { t } = useI18n();
  const pct = (v: number) => `${((v - 1) / 4) * 100}%`;
  return (
    <div className="space-y-3">
      <div className="flex justify-between pl-20 text-[11px] text-ink-3">
        <span>{t("very nervous")}</span>
        <span>{t("very confident")}</span>
      </div>
      {rows.map((row, i) => {
        const lo = Math.min(row.before, row.after);
        const hi = Math.max(row.before, row.after);
        return (
          <div key={i} className="grid grid-cols-[4.5rem_1fr] items-center gap-2">
            <span className="text-xs text-ink-3">{shortDate(row.date, locale)}</span>
            <div className="relative h-5" title={`${row.before} → ${row.after}`}>
              <div className="absolute top-1/2 h-px w-full bg-line" />
              <div
                className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded bg-fir/50"
                style={{ left: pct(lo), width: `calc(${pct(hi)} - ${pct(lo)})` }}
              />
              <span
                className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-series-before"
                style={{ left: pct(row.before) }}
              />
              <span
                className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-series-now"
                style={{ left: pct(row.after) }}
              />
            </div>
          </div>
        );
      })}
      <div className="flex gap-4 pl-20 text-xs text-ink-2">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-series-before" /> {t("before")}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-series-now" /> {t("after")}
        </span>
      </div>
    </div>
  );
}
