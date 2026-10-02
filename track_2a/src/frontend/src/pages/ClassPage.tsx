/** Teacher cockpit: the whole class on one screen - who practised, where the
 * class struggles (with a lesson idea for each weak criterion), who needs a
 * nudge, and how the application pipeline stands. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, Copy, PartyPopper, Plus, RefreshCw, Users } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import { CriterionRows } from "../components/charts";
import { PageHeader } from "../components/Shell";
import { useToast } from "../components/Toast";
import { useCriterionName } from "../components/useCatalog";
import { Badge, Button, Card, EmptyState, Eyebrow, Field, inputClass, Spinner } from "../components/ui";
import { cn, scoreColor, timeAgo } from "../lib/format";
import { LOCALE, useI18n } from "../lib/i18n";
import { CRITERIA, type ClassOverview, type Criterion } from "../types";

const LESSON_IDEAS: Record<Criterion, string> = {
  examples: "Pair work: each student tells a 60-second story using Situation → what I did → result. Partner asks 'and what did YOU do?'.",
  self_awareness: "Strength bingo: students collect three strengths from classmates, each with a moment they observed it.",
  motivation: "Trial-day debrief: each student writes 3 sentences 'What surprised me in my Schnupperlehre and why I want this job'.",
  clarity: "Headline first: answer any question in one sentence, then add one reason. Practise with a timer (30 s).",
  communication: "Role play greetings and closings: handshake, 'Grüezi Frau…', full sentences, thanking at the end.",
  relevance: "Company research sprint: 10 minutes on the company website, note 2 facts to mention in the interview.",
};

function CreateClass() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [school, setSchool] = useState("");
  const create = useMutation({
    mutationFn: () => api.classes.create(name, school),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["classes"] }),
  });
  return (
    <Card className="max-w-lg p-6">
      <p className="font-display text-lg font-bold">{t("Create your first class")}</p>
      <p className="mt-1 text-sm text-ink-2">{t("Students join with a 6-letter code - no e-mail addresses needed.")}</p>
      <form
        className="mt-4 space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate();
        }}
      >
        <Field label={t("Class name")}>
          <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} placeholder="3. Sek A" required />
        </Field>
        <Field label={t("School")}>
          <input className={inputClass} value={school} onChange={(e) => setSchool(e.target.value)} />
        </Field>
        <Button variant="primary" disabled={create.isPending}>
          <Plus size={16} /> {t("Create class")}
        </Button>
      </form>
    </Card>
  );
}

function Heatmap({ data, classId }: { data: ClassOverview; classId: string }) {
  const { t, lang } = useI18n();
  const name = useCriterionName();
  const locale = LOCALE[lang];
  const FLAG: Record<string, { label: string; tone: "blaze" | "sign" | "fir" | "lake" }> = {
    inactive: { label: t("not practising"), tone: "blaze" },
    low_confidence: { label: t("low confidence"), tone: "sign" },
    interview_soon: { label: t("interview soon"), tone: "lake" },
    has_offer: { label: t("has an offer"), tone: "fir" },
  };
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] border-separate border-spacing-0 text-left">
        <thead>
          <tr className="text-[12px] text-ink-3">
            <th className="sticky left-0 bg-card py-2 pr-3 font-normal">{t("Student")}</th>
            {CRITERIA.map((c) => (
              <th key={c} className="w-[74px] px-1 py-2 text-center font-normal">
                {name(c)}
              </th>
            ))}
            <th className="px-2 py-2 font-normal">{t("Sessions")}</th>
            <th className="px-2 py-2 font-normal">{t("Last practice")}</th>
            <th className="px-2 py-2 font-normal">{t("Notes")}</th>
          </tr>
        </thead>
        <tbody>
          {data.students.map((s) => (
            <tr key={s.id} className="group">
              <td className="sticky left-0 border-t border-line-soft bg-card py-2 pr-3">
                <Link to={`/classes/${classId}/students/${s.id}`} className="font-bold hover:underline">
                  {s.name}
                </Link>
                {s.latest_overall != null && (
                  <span className="ml-2 font-mono text-xs text-ink-3">
                    {s.latest_overall}
                    {s.first_overall != null && s.first_overall !== s.latest_overall && (
                      <span className={s.latest_overall > s.first_overall ? "text-fir" : ""}>
                        {" "}
                        ({s.latest_overall > s.first_overall ? "+" : ""}
                        {s.latest_overall - s.first_overall})
                      </span>
                    )}
                  </span>
                )}
              </td>
              {CRITERIA.map((c) => {
                const v = s.averages[c];
                return (
                  <td key={c} className="border-t border-line-soft px-1 py-1.5">
                    <div
                      className="flex h-8 items-center justify-center rounded-md font-mono text-[12.5px]"
                      style={{
                        background: v != null ? scoreColor(v) : "var(--color-panel)",
                        color: v != null && v >= 2.5 ? "#fff" : "var(--color-ink)",
                      }}
                      title={v != null ? `${name(c)}: ${v.toFixed(1)}` : t("no data")}
                    >
                      {v != null ? v.toFixed(1) : "·"}
                    </div>
                  </td>
                );
              })}
              <td className="border-t border-line-soft px-2 font-mono text-sm">
                {s.sessions}
                {s.drills_done > 0 && <span className="text-ink-3"> +{s.drills_done}</span>}
              </td>
              <td className="border-t border-line-soft px-2 text-sm text-ink-2">
                {s.last_practice ? timeAgo(s.last_practice, locale) : "–"}
              </td>
              <td className="border-t border-line-soft px-2">
                <div className="flex flex-wrap gap-1">
                  {s.flags.map((f) => (
                    <Badge key={f} tone={FLAG[f].tone}>
                      {FLAG[f].label}
                    </Badge>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ClassPage() {
  const { t } = useI18n();
  const toast = useToast();
  const name = useCriterionName();
  const params = useParams();
  const queryClient = useQueryClient();
  const { data: classes, isLoading } = useQuery({ queryKey: ["classes"], queryFn: api.classes.list });
  const classId = params.classId ?? classes?.[0]?.id;
  const { data } = useQuery({ queryKey: ["class", classId], queryFn: () => api.classes.get(classId!), enabled: !!classId });
  const newCode = useMutation({
    mutationFn: () => api.classes.newCode(classId!),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["class", classId] }),
  });

  if (isLoading) return <Spinner />;
  if (!classes?.length)
    return (
      <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
        <PageHeader eyebrow={t("My class")} title={t("Welcome!")} />
        <CreateClass />
      </div>
    );
  if (!data)
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );

  const n = data.students.length;
  const needAttention = data.students.filter((s) => s.flags.includes("inactive") || s.flags.includes("low_confidence"));
  const maxWeek = Math.max(1, ...data.weekly_sessions.map((w) => w.sessions));

  return (
    <div className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
      <PageHeader
        eyebrow={`${t("My class")} · ${data.class.school}`}
        title={data.class.name}
        sub={t("Scores and activity of your students. Answer texts are only visible if a student agrees.")}
        actions={
          <div className="flex items-center gap-2 rounded-2xl bg-card px-4 py-2.5 ring-card">
            <span className="text-xs text-ink-3">{t("Class code")}</span>
            <span className="font-mono text-xl font-bold tracking-widest">{data.class.code}</span>
            <button
              className="cursor-pointer rounded p-1 text-ink-3 hover:text-ink"
              aria-label={t("Copy")}
              onClick={() => {
                void navigator.clipboard?.writeText(data.class.code);
                toast(t("Code copied"));
              }}
            >
              <Copy size={15} />
            </button>
            <button
              className="cursor-pointer rounded p-1 text-ink-3 hover:text-ink"
              aria-label={t("New code")}
              title={t("New code")}
              onClick={() => newCode.mutate()}
            >
              <RefreshCw size={15} />
            </button>
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { icon: <Users size={16} />, value: n, label: t("students") },
          { icon: <CalendarClock size={16} />, value: `${data.active_last_7d}/${n}`, label: t("practised this week") },
          { icon: <PartyPopper size={16} />, value: data.students_with_offer, label: t("have an offer") },
          { icon: <AlertTriangle size={16} />, value: needAttention.length, label: t("need a nudge") },
        ].map((tile) => (
          <Card key={tile.label} className="p-4">
            <span className="text-ink-3">{tile.icon}</span>
            <p className="font-hero mt-1 text-[32px] leading-none">{tile.value}</p>
            <p className="mt-1 text-xs text-ink-3">{tile.label}</p>
          </Card>
        ))}
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1.1fr]">
        <Card className="p-6">
          <Eyebrow className="mb-3">{t("Class profile")}</Eyebrow>
          {Object.keys(data.class_averages).length ? (
            <CriterionRows scores={data.class_averages} />
          ) : (
            <p className="text-sm text-ink-3">{t("No interviews yet.")}</p>
          )}
          {data.weekly_sessions.length > 0 && (
            <div className="mt-6">
              <p className="mb-2 text-xs text-ink-3">{t("Practice sessions per week")}</p>
              <div className="flex h-20 items-end gap-1.5">
                {data.weekly_sessions.map((w) => (
                  <div key={w.week} className="flex flex-1 flex-col items-center gap-1" title={`${w.week}: ${w.sessions}`}>
                    <span className="font-mono text-[10px] text-ink-3">{w.sessions}</span>
                    <div className="w-full rounded-t-[4px] bg-series-now" style={{ height: `${(w.sessions / maxWeek) * 56}px` }} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card className="border-t-4 border-sign p-6">
          <Eyebrow className="mb-3">{t("Where the class struggles - and a lesson idea")}</Eyebrow>
          {data.weak_spots.length ? (
            <ul className="space-y-4">
              {data.weak_spots.map((c) => (
                <li key={c}>
                  <p className="flex items-center gap-2 font-bold">
                    {name(c)} <span className="font-mono text-sm text-ink-3">Ø {data.class_averages[c]?.toFixed(1)}</span>
                  </p>
                  <p className="mt-1 text-[15px] leading-snug text-ink-2">{t(LESSON_IDEAS[c])}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-3">–</p>
          )}
          {needAttention.length > 0 && (
            <div className="mt-5 rounded-xl bg-raised p-3 text-[14px]">
              <span className="font-bold">{t("Check in with:")}</span>{" "}
              {needAttention.map((s) => s.name).join(", ")}
            </div>
          )}
        </Card>
      </div>

      <Card className="mt-5 p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <Eyebrow>{t("Students × criteria (last 3 interviews)")}</Eyebrow>
          <div className="flex items-center gap-1.5 text-[11px] text-ink-3">
            {[1, 2, 3, 4].map((v) => (
              <span key={v} className="flex items-center gap-1">
                <span className="h-3 w-3 rounded-sm" style={{ background: scoreColor(v) }} /> {v}
              </span>
            ))}
          </div>
        </div>
        {n ? (
          <Heatmap data={data} classId={classId!} />
        ) : (
          <EmptyState icon={<Users size={26} />} title={t("No students yet")} hint={t("Share the class code {code} with your students.", { code: data.class.code })} />
        )}
      </Card>

      <Card className="mt-5 p-6">
        <Eyebrow className="mb-3">{t("Applications in the class")}</Eyebrow>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-6">
          {(
            [
              ["interested", t("Interested")],
              ["schnupper", t("Trial apprenticeship")],
              ["applied", t("Applied")],
              ["interview", t("Interview")],
              ["offer", t("Offer")],
              ["rejected", t("Rejected")],
            ] as const
          ).map(([key, label]) => (
            <div key={key} className={cn("rounded-xl p-3", key === "offer" ? "bg-fir/10" : "bg-panel")}>
              <p className="font-hero text-2xl">{data.pipeline[key]}</p>
              <p className="text-[11px] text-ink-3">{label}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
