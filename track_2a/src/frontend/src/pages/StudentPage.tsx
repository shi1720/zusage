/** Teacher view of one student: trend, goals, applications - and the
 * transcripts only if the student opted in. */

import { useQuery } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../api";
import { CriterionRows, TrendChart } from "../components/charts";
import { PageHeader } from "../components/Shell";
import { Badge, Card, Eyebrow, Spinner } from "../components/ui";
import { longDate } from "../lib/format";
import { LANG_LABEL, LOCALE, useI18n } from "../lib/i18n";
import { STATUS_LABEL } from "./ApplicationsPage";

export default function StudentPage() {
  const { classId = "", studentId = "" } = useParams();
  const { t, lang } = useI18n();
  const locale = LOCALE[lang];
  const [open, setOpen] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: ["student", classId, studentId],
    queryFn: () => api.classes.student(classId, studentId),
  });
  if (!data)
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  const full = data.timeline.filter((p) => p.mode !== "drill" && p.overall != null);

  return (
    <div className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
      <Link to={`/classes/${classId}`} className="text-sm text-ink-3 hover:text-ink">
        ← {t("Back to class")}
      </Link>
      <PageHeader
        title={data.student.name}
        sub={
          data.student.consent_share ? (
            <Badge tone="fir">{t("shares answers with you")}</Badge>
          ) : (
            <span className="flex items-center gap-1.5">
              <Lock size={14} /> {t("Answers private - you see scores and goals only.")}
            </span>
          )
        }
      />
      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <Card className="p-6">
          <Eyebrow className="mb-3">{t("Summit points per interview")}</Eyebrow>
          {full.length ? (
            <TrendChart points={full.map((p) => ({ date: p.date, value: p.overall! }))} locale={locale} />
          ) : (
            <p className="text-sm text-ink-3">{t("No interviews yet.")}</p>
          )}
        </Card>
        <Card className="p-6">
          <Eyebrow className="mb-3">{t("Applications")}</Eyebrow>
          <ul className="space-y-2 text-[15px]">
            {data.applications.map((a) => (
              <li key={a.company} className="flex justify-between gap-2">
                <span>{a.company}</span>
                <Badge tone={a.status === "offer" ? "fir" : a.status === "interview" ? "sign" : "neutral"}>{t(STATUS_LABEL[a.status])}</Badge>
              </li>
            ))}
            {!data.applications.length && <li className="text-sm text-ink-3">–</li>}
          </ul>
        </Card>
      </div>

      <h2 className="font-display mt-8 mb-3 text-xl font-bold">{t("Sessions")}</h2>
      <div className="space-y-3">
        {data.sessions.map((s) => (
          <Card key={s.id} className="p-5">
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-mono text-2xl font-bold">{s.overall ?? "–"}</span>
              <div className="min-w-0 flex-1">
                <p className="font-bold">{s.mode === "drill" ? t("Drill") : s.occupation}</p>
                <p className="text-sm text-ink-3">
                  {longDate(s.date, locale)} · {LANG_LABEL[s.language]}
                </p>
              </div>
              {s.detail && (
                <button onClick={() => setOpen(open === s.id ? null : s.id)} className="cursor-pointer text-sm font-bold text-lake hover:underline">
                  {open === s.id ? t("Hide answers") : t("Show answers")}
                </button>
              )}
            </div>
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              {s.averages && <CriterionRows scores={s.averages} compact />}
              {s.goals && (
                <ul className="space-y-1.5 text-[14px]">
                  {s.goals.map((g) => (
                    <li key={g.title}>
                      <span className="font-bold">{g.title}:</span> <span className="text-ink-2">{g.how}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {open === s.id && s.detail && (
              <div className="mt-4 space-y-3 border-t border-line-soft pt-4">
                {s.detail.turns.map((turn) => (
                  <div key={turn.idx} className="text-[14.5px]">
                    <p className="text-ink-3">{turn.question}</p>
                    <p className="mt-0.5">{turn.answer}</p>
                    {turn.assessment?.tip && <p className="mt-0.5 text-sm text-dusk">→ {turn.assessment.tip}</p>}
                  </div>
                ))}
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
