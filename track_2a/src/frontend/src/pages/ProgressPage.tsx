/** Progress: mastery over time on the six criteria, confidence, calibration,
 * and the spaced-practice queue (Leitner boxes). */

import { useQuery } from "@tanstack/react-query";
import { Brain, Mountain } from "lucide-react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { ConfidenceDumbbell, CriterionRows, Radar, TrendChart } from "../components/charts";
import { PageHeader } from "../components/Shell";
import { useCriterionName } from "../components/useCatalog";
import { Badge, Card, EmptyState, Eyebrow, Spinner } from "../components/ui";
import { cn, shortDate } from "../lib/format";
import { LANG_LABEL, LOCALE, useI18n } from "../lib/i18n";

const BOX_DAYS = [1, 3, 7, 14, 30];

export default function ProgressPage() {
  const { t, lang } = useI18n();
  const criterion = useCriterionName();
  const locale = LOCALE[lang];
  const { data, isLoading } = useQuery({ queryKey: ["progress"], queryFn: api.progress });
  const { data: history } = useQuery({ queryKey: ["interviews"], queryFn: api.interviews.list });

  if (isLoading || !data) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }
  const full = data.timeline.filter((p) => p.mode !== "drill" && p.overall != null);
  const first = full[0];
  const conf = data.timeline
    .filter((p) => p.confidence_before != null && p.confidence_after != null)
    .map((p) => ({ date: p.date, before: p.confidence_before!, after: p.confidence_after! }));
  const boxes = [1, 2, 3, 4, 5].map((b) => data.drills.filter((d) => d.box === b).length);

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
      <PageHeader eyebrow={t("Progress")} title={t("How far you've come")} sub={t("Every practice interview, drill and retry - measured on the same six criteria.")} />

      {full.length === 0 ? (
        <EmptyState
          icon={<Mountain size={28} />}
          title={t("Your trail starts with the first interview")}
          hint={t("Finish a practice interview to see your profile here.")}
          action={
            <Link to="/practice" className="font-bold text-lake hover:underline">
              {t("Start practice interview")} →
            </Link>
          }
        />
      ) : (
        <div className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
            <Card className="p-6">
              <Eyebrow className="mb-3">{t("Summit points per interview")}</Eyebrow>
              <TrendChart
                points={full.map((p) => ({ date: p.date, value: p.overall! }))}
                locale={locale}
              />
            </Card>
            <Card className="p-6">
              <Eyebrow className="mb-3">{t("Now vs. your first interview")}</Eyebrow>
              <div className="flex justify-center">
                <Radar now={data.criteria_now} before={full.length > 1 ? first.averages : null} size={260} />
              </div>
            </Card>
          </div>

          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="p-6 lg:col-span-1">
              <Eyebrow className="mb-3">{t("Criteria (last 3 interviews)")}</Eyebrow>
              <CriterionRows scores={data.criteria_now} previous={full.length > 1 ? first.averages : undefined} />
            </Card>
            <Card className="p-6">
              <Eyebrow className="mb-3">{t("Confidence before → after")}</Eyebrow>
              {conf.length ? <ConfidenceDumbbell rows={conf.slice(-6)} locale={locale} /> : <p className="text-sm text-ink-3">–</p>}
            </Card>
            <Card className="p-6">
              <Eyebrow className="mb-3">{t("Self-assessment")}</Eyebrow>
              {data.calibration ? (
                <>
                  <p className="font-hero text-[44px] leading-none">{Math.round(data.calibration.accuracy * 100)}%</p>
                  <p className="mt-1 text-sm text-ink-2">
                    {t("of your guesses matched the coach ({n} answers).", { n: data.calibration.n })}
                  </p>
                  <p className="mt-3 flex items-start gap-2 rounded-xl bg-raised p-3 text-[13.5px] text-ink-2">
                    <Brain size={16} className="mt-0.5 shrink-0" />
                    {data.calibration.bias > 0.3
                      ? t("You tend to rate yourself higher than the coach. Check: did you give a concrete example?")
                      : data.calibration.bias < -0.3
                        ? t("You're stricter with yourself than the coach. You're better than you think!")
                        : t("You judge yourself realistically - a real skill for interviews.")}
                  </p>
                </>
              ) : (
                <p className="text-sm text-ink-3">{t("Rate your answers before the feedback appears - after 3 ratings you'll see how well you judge yourself.")}</p>
              )}
            </Card>
          </div>

          <Card className="p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Eyebrow>{t("Spaced practice · drill boxes")}</Eyebrow>
              <span className="text-xs text-ink-3">{t("A drill moves up a box when you answer it well, and back to box 1 when not.")}</span>
            </div>
            <div className="mt-4 grid grid-cols-5 gap-2">
              {boxes.map((count, i) => (
                <div key={i} className={cn("rounded-xl p-3 text-center", count ? "bg-raised" : "bg-panel")}>
                  <p className="font-hero text-2xl">{count}</p>
                  <p className="text-[11px] text-ink-3">
                    {t("Box {n}", { n: i + 1 })} · {BOX_DAYS[i]}d
                  </p>
                </div>
              ))}
            </div>
            {data.drills.length > 0 && (
              <ul className="mt-4 divide-y divide-line-soft">
                {data.drills.map((d) => (
                  <li key={d.id} className="flex items-center gap-3 py-2.5 text-[14.5px]">
                    <span className="min-w-0 flex-1 truncate">{d.question}</span>
                    {d.criterion && <Badge>{criterion(d.criterion)}</Badge>}
                    <span className={cn("text-xs", d.due ? "font-bold text-blaze" : "text-ink-3")}>
                      {d.due ? t("due") : shortDate(d.due_at, locale)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="p-6">
            <Eyebrow className="mb-3">{t("All interviews")}</Eyebrow>
            <ul className="divide-y divide-line-soft">
              {(history ?? [])
                .filter((h) => h.status === "completed")
                .map((h) => (
                  <li key={h.id}>
                    <Link to={`/report/${h.id}`} className="flex items-center gap-3 py-3 hover:bg-panel">
                      <span className="w-16 text-sm text-ink-3">{shortDate(h.created_at, locale)}</span>
                      <span className="min-w-0 flex-1 truncate">
                        <span className="font-bold">{h.mode === "drill" ? t("Drill") : h.occupation}</span>
                        <span className="text-sm text-ink-3"> · {h.company} · {LANG_LABEL[h.language]}</span>
                      </span>
                      <span className="font-mono font-bold">{h.overall ?? "–"}</span>
                    </Link>
                  </li>
                ))}
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}
