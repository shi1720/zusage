/** Student home: what to do today. A to-do list, not a dashboard -
 * the next real interview, due drills (spaced practice), stalled applications. */

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, CalendarClock, Flame, Mail, Mic, Mountain, Play, Smile, Target } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import { Momentum } from "../components/Momentum";
import { Onboarding } from "../components/Onboarding";
import { PageHeader } from "../components/Shell";
import { useCriterionName, useOccupationName } from "../components/useCatalog";
import { Badge, Button, Card, EmptyState, Eyebrow, Spinner } from "../components/ui";
import { cn, dateTime, daysSince, daysUntil, timeAgo } from "../lib/format";
import { LOCALE, useI18n } from "../lib/i18n";
import type { Drill } from "../types";

function LeitnerDots({ box }: { box: number }) {
  return (
    <span className="flex gap-0.5" aria-label={`Box ${box}/5`}>
      {[1, 2, 3, 4, 5].map((b) => (
        <span key={b} className={cn("h-2 w-2 rounded-full", b <= box ? "bg-fir" : "bg-raised")} />
      ))}
    </span>
  );
}

function DrillRow({ drill }: { drill: Drill }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const criterion = useCriterionName();
  const start = useMutation({ mutationFn: () => api.drills.start(drill.id), onSuccess: (iv) => navigate(`/interview/${iv.id}`) });
  return (
    <li className="flex items-center gap-3 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-[15px] font-bold">{drill.question}</p>
        <p className="mt-0.5 flex items-center gap-2 text-xs text-ink-3">
          {drill.criterion && <span>{t("Focus")}: {criterion(drill.criterion)}</span>}
          <LeitnerDots box={drill.box} />
        </p>
      </div>
      <Button variant="outline" size="sm" onClick={() => start.mutate()} disabled={start.isPending}>
        {start.isPending ? <Spinner /> : <Play size={14} />} {t("2 min")}
      </Button>
    </li>
  );
}

export default function TodayPage() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const criterion = useCriterionName();
  const occName = useOccupationName();
  const { data, isLoading } = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const locale = LOCALE[lang];
  const firstName = user?.display_name.split(" ")[0] ?? "";

  if (isLoading || !data) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }
  const next = data.upcoming_interviews[0];
  const s = data.stats;

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
      <Onboarding />
      <PageHeader
        eyebrow={new Date().toLocaleDateString(locale, { weekday: "long", day: "numeric", month: "long" })}
        title={t("Hello {name}!", { name: firstName })}
        sub={
          data.due_drills.length
            ? t("{n} short drills are waiting - about {m} minutes.", { n: data.due_drills.length, m: data.due_drills.length * 2 })
            : t("Nothing due. A good day for a full practice interview.")
        }
      />

      <div className="grid gap-5 lg:grid-cols-[1.35fr_1fr]">
        <div className="min-w-0 space-y-5">
          {data.active_interview && (
            <Card className="flex items-center gap-4 border-l-4 border-lake p-5">
              <Mic className="shrink-0 text-lake" />
              <div className="min-w-0 flex-1">
                <p className="font-bold">{t("Interview in progress")}</p>
                <p className="truncate text-sm text-ink-3">
                  {data.active_interview.occupation?.label} · {data.active_interview.progress.answered}/
                  {data.active_interview.progress.planned} {t("questions")}
                </p>
              </div>
              <Link to={`/interview/${data.active_interview.id}`}>
                <Button variant="primary" size="sm">
                  {t("Continue")} <ArrowRight size={14} />
                </Button>
              </Link>
            </Card>
          )}

          {next ? (
            <Card className="contours overflow-hidden p-6">
              <p className="signpost font-sign inline-block py-1 pl-2.5 text-[12px]">
                {daysUntil(next.interview_at!) <= 0
                  ? t("Today")
                  : t("In {n} days", { n: daysUntil(next.interview_at!) })}
              </p>
              <h2 className="font-display mt-3 text-2xl font-extrabold">{t("Interview at {company}", { company: next.company })}</h2>
              <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-2">
                <CalendarClock size={15} /> {dateTime(next.interview_at!, locale)}
                {next.contact_name && <> · {next.contact_name}</>}
              </p>
              <p className="mt-3 text-[15px] text-ink-2">
                {next.practice_sessions
                  ? t("You've rehearsed this one {n}× - best score {s}.", { n: next.practice_sessions, s: next.best_score ?? "–" })
                  : t("Rehearse exactly this interview - with questions about this company and its job ad.")}
              </p>
              <Button
                variant="sign"
                size="lg"
                className="mt-5"
                onClick={() => navigate(`/practice?application=${next.id}&occupation=${next.occupation_id}`)}
              >
                <Mic size={18} /> {t("Rehearse this interview")}
              </Button>
            </Card>
          ) : (
            <Card className="contours p-6">
              <h2 className="font-display text-2xl font-extrabold">{t("Ready for a practice round?")}</h2>
              <p className="mt-2 text-[15px] text-ink-2">{t("Five questions, about six minutes. Your coach shows you what already works.")}</p>
              <Link to="/practice">
                <Button variant="sign" size="lg" className="mt-5">
                  <Mic size={18} /> {t("Start practice interview")}
                </Button>
              </Link>
            </Card>
          )}

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <Eyebrow>{t("Due today · spaced practice")}</Eyebrow>
              {data.next_drill_at && !data.due_drills.length && (
                <span className="text-xs text-ink-3">
                  {t("Next drill")} {timeAgo(data.next_drill_at, locale)}
                </span>
              )}
            </div>
            {data.due_drills.length ? (
              <ul className="mt-1 divide-y divide-line-soft">
                {data.due_drills.slice(0, 5).map((d) => (
                  <DrillRow key={d.id} drill={d} />
                ))}
              </ul>
            ) : (
              <div className="mt-4">
                <EmptyState
                  icon={<Mountain size={26} />}
                  title={t("No drills due")}
                  hint={t("After each interview, your weakest answers come back here after 1, 3 and 7 days.")}
                />
              </div>
            )}
          </Card>

          {data.follow_ups.length > 0 && (
            <Card className="p-6">
              <Eyebrow className="mb-3">{t("Waiting for an answer")}</Eyebrow>
              <ul className="space-y-3">
                {data.follow_ups.map((a) => (
                  <li key={a.id} className="flex items-start gap-3">
                    <Mail size={18} className="mt-0.5 shrink-0 text-ink-3" />
                    <div className="text-[15px]">
                      <p>
                        {t("No reply from {company} for {n} days.", { company: a.company, n: daysSince(a.updated_at) })}
                      </p>
                      <p className="text-sm text-ink-3">
                        {t("It's okay to call politely and ask about the status of your application.")}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <div className="min-w-0 space-y-5">
          <Momentum/>
          <Card className="grid grid-cols-2 gap-px overflow-hidden bg-line-soft p-0">
            {[
              { icon: <Mic size={16} />, value: s.sessions, label: t("interviews") },
              { icon: <Flame size={16} />, value: s.streak, label: t("day streak") },
              { icon: <Target size={16} />, value: s.last_overall ?? "–", label: t("last score") },
              {
                icon: <Smile size={16} />,
                value: s.confidence_gain != null ? `${s.confidence_gain > 0 ? "+" : ""}${s.confidence_gain}` : "–",
                label: t("confidence per session"),
              },
            ].map((tile) => (
              <div key={tile.label} className="bg-card p-4">
                <span className="text-ink-3">{tile.icon}</span>
                <p className="font-hero mt-1 text-[30px] leading-none">{tile.value}</p>
                <p className="mt-1 text-xs text-ink-3">{tile.label}</p>
              </div>
            ))}
          </Card>

          {data.focus.length > 0 && (
            <Card className="p-5">
              <Eyebrow className="mb-2">{t("Your focus")}</Eyebrow>
              <p className="text-[15px] text-ink-2">{t("The next interviews will train these on purpose:")}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {data.focus.map((c) => (
                  <Badge key={c} tone="sign" className="px-3 py-1 text-sm">
                    {criterion(c)}
                  </Badge>
                ))}
              </div>
            </Card>
          )}

          <Card className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <Eyebrow>{t("My apprenticeships")}</Eyebrow>
              <Link to="/applications" className="text-sm font-bold text-lake hover:underline">
                {t("Open")}
              </Link>
            </div>
            <ul className="space-y-1.5 text-[15px]">
              {(
                [
                  ["schnupper", t("Trial apprenticeship")],
                  ["applied", t("Applied")],
                  ["interview", t("Interview")],
                  ["offer", t("Offer")],
                ] as const
              ).map(([key, label]) => (
                <li key={key} className="flex justify-between">
                  <span className="text-ink-2">{label}</span>
                  <span className="font-mono font-bold">{s.applications[key]}</span>
                </li>
              ))}
            </ul>
            {data.upcoming_interviews.length > 1 && (
              <p className="mt-3 text-xs text-ink-3">
                + {data.upcoming_interviews.length - 1} {t("more interviews coming up")} ({occName(data.upcoming_interviews[1].occupation_id)})
              </p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
