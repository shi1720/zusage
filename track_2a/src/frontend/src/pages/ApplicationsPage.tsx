/** Lehrstellen tracker - the OfferLoop pipeline, re-cut for Swiss apprenticeships:
 * interested → trial apprenticeship → applied → interview → offer | rejected.
 * Every card can launch a rehearsal tailored to that company and job ad. */

import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Mic, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api";
import { PageHeader } from "../components/Shell";
import { useToast } from "../components/Toast";
import { useCatalog, useOccupationName } from "../components/useCatalog";
import { Button, Field, inputClass, Modal, Spinner } from "../components/ui";
import { cn, dateTime } from "../lib/format";
import { loc, LOCALE, useI18n } from "../lib/i18n";
import { APP_STATUSES, type Application, type AppStatus } from "../types";

export const STATUS_LABEL: Record<AppStatus, string> = {
  interested: "Interested",
  schnupper: "Trial apprenticeship",
  applied: "Applied",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
};

const STATUS_TONE: Record<AppStatus, string> = {
  interested: "bg-raised",
  schnupper: "bg-lake/15",
  applied: "bg-dusk/15",
  interview: "bg-sign",
  offer: "blaze",
  rejected: "bg-line",
};

function AppCard({ app, onOpen, overlay }: { app: Application; onOpen?: () => void; overlay?: boolean }) {
  const { t, lang } = useI18n();
  const occName = useOccupationName();
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: app.id });
  return (
    <div
      ref={overlay ? undefined : setNodeRef}
      {...(overlay ? {} : listeners)}
      {...(overlay ? {} : attributes)}
      onClick={onOpen}
      className={cn(
        "cursor-grab rounded-xl bg-card p-3.5 ring-card transition-shadow hover:shadow-md active:cursor-grabbing",
        isDragging && !overlay && "opacity-30",
        overlay && "rotate-2 shadow-xl",
      )}
    >
      <p className="font-bold leading-snug">{app.company}</p>
      <p className="mt-0.5 text-[13px] text-ink-3">
        {app.occupation_id ? occName(app.occupation_id) : app.title}
        {app.town && ` · ${app.town}`}
      </p>
      {app.interview_at && (
        <p className="mt-2 flex items-center gap-1 text-xs font-bold text-ink">
          <CalendarClock size={13} /> {dateTime(app.interview_at, LOCALE[lang])}
        </p>
      )}
      {app.practice_sessions > 0 && (
        <p className="mt-1.5 text-xs text-fir">
          {t("Rehearsed {n}×", { n: app.practice_sessions })} · {t("best")} {app.best_score ?? "–"}
        </p>
      )}
    </div>
  );
}

function Column({ status, apps, onOpen }: { status: AppStatus; apps: Application[]; onOpen: (id: string) => void }) {
  const { t } = useI18n();
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <section
      ref={setNodeRef}
      className={cn("flex w-full shrink-0 snap-start sm:w-64 flex-col rounded-2xl bg-panel p-2.5 transition-colors", isOver && "bg-sign/20")}
    >
      <header className="flex items-center gap-2 px-1.5 pt-1 pb-2.5">
        <span className={cn("h-3 w-3 rounded-[3px]", STATUS_TONE[status])} />
        <h2 className="text-sm font-bold">{t(STATUS_LABEL[status])}</h2>
        <span className="ml-auto font-mono text-xs text-ink-3">{apps.length}</span>
      </header>
      <div className="flex min-h-24 flex-col gap-2">
        {apps.map((app) => (
          <AppCard key={app.id} app={app} onOpen={() => onOpen(app.id)} />
        ))}
      </div>
    </section>
  );
}

function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function AppEditor({ app, initial, onClose }: { app: Application | null; initial?: Partial<Application>; onClose: () => void }) {
  const { t, lang } = useI18n();
  const toast = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: catalog } = useCatalog();
  const [form, setForm] = useState({
    company: app?.company ?? initial?.company ?? "",
    occupation_id: app?.occupation_id ?? initial?.occupation_id ?? "",
    town: app?.town ?? initial?.town ?? "",
    status: app?.status ?? ("interested" as AppStatus),
    interview_at: toLocalInput(app?.interview_at ?? null),
    contact_name: app?.contact_name ?? "",
    posting: app?.posting ?? initial?.posting ?? "",
    notes: app?.notes ?? "",
    title: app?.title ?? initial?.title ?? "",
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["applications"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const save = useMutation({
    mutationFn: () => {
      const body = { ...form, interview_at: form.interview_at ? new Date(form.interview_at).toISOString() : null };
      return app ? api.applications.update(app.id, body) : api.applications.create(body);
    },
    onSuccess: () => {
      refresh();
      toast(app ? t("Saved") : t("Apprenticeship added"));
      onClose();
    },
    onError: () => toast(t("Could not save - check the fields."), "err"),
  });
  const remove = useMutation({
    mutationFn: () => api.applications.remove(app!.id),
    onSuccess: () => {
      refresh();
      onClose();
      toast(t("Removed"), "info", {
        label: t("Undo"),
        onClick: () => void api.applications.restore(app!.id).then(refresh),
      });
    },
  });
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  return (
    <Modal title={app ? app.company : t("Add an apprenticeship")} onClose={onClose} wide>
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Field label={t("Company")}>
          <input className={inputClass} value={form.company} onChange={set("company")} required maxLength={120} />
        </Field>
        <Field label={t("Role / title")}><input className={inputClass} value={form.title} onChange={set("title")} maxLength={160}/></Field>
        <Field label={t("Town")}>
          <input className={inputClass} value={form.town} onChange={set("town")} maxLength={80} />
        </Field>
        <Field label={t("Apprenticeship")}>
          <select className={inputClass} value={form.occupation_id} onChange={set("occupation_id")}>
            <option value="">-</option>
            {catalog?.occupations.map((o) => (
              <option key={o.id} value={o.id}>
                {loc(o.name, lang)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("Status")}>
          <select className={inputClass} value={form.status} onChange={set("status")}>
            {APP_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(STATUS_LABEL[s])}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("Interview date")}>
          <input type="datetime-local" className={inputClass} value={form.interview_at} onChange={set("interview_at")} />
        </Field>
        <Field label={t("Contact person")}>
          <input className={inputClass} value={form.contact_name} onChange={set("contact_name")} maxLength={120} />
        </Field>
        <div className="sm:col-span-2">
          <Field label={t("Job ad text")} hint={t("Paste it here - your rehearsal will ask about it.")}>
            <textarea className={cn(inputClass, "min-h-28")} value={form.posting} onChange={set("posting")} maxLength={6000} />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <Field label={t("Notes")}>
            <textarea className={cn(inputClass, "min-h-16")} value={form.notes} onChange={set("notes")} maxLength={4000} />
          </Field>
        </div>
        {app && <div className="sm:col-span-2"><p className="mb-2 text-sm font-bold">{t("Stage history")}</p><ol className="space-y-2 text-xs text-ink-3">{app.history.map((h,i)=><li key={i}>{t(STATUS_LABEL[h.to as AppStatus]??h.to)} · {dateTime(h.at,LOCALE[lang])}</li>)}</ol></div>}
        <div className="flex flex-wrap items-center gap-2 sm:col-span-2">
          <Button variant="primary" disabled={save.isPending}>
            {save.isPending && <Spinner className="border-t-white" />} {t("Save")}
          </Button>
          {app && form.occupation_id && (
            <Button
              type="button"
              variant="sign"
              onClick={() => navigate(`/practice?application=${app.id}&occupation=${form.occupation_id}`)}
            >
              <Mic size={16} /> {t("Rehearse interview")}
            </Button>
          )}
          {app && (
            <Button type="button" variant="danger" className="ml-auto" onClick={() => remove.mutate()}>
              <Trash2 size={15} /> {t("Remove")}
            </Button>
          )}
        </div>
      </form>
    </Modal>
  );
}

export default function ApplicationsPage() {
  const { t } = useI18n();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data: apps, isLoading } = useQuery({ queryKey: ["applications"], queryFn: api.applications.list });
  const [captureText,setCaptureText]=useState("");
  const [initial,setInitial]=useState<Partial<Application>>({});
  const capture=useMutation({mutationFn:()=>api.workspace.capture(captureText),onSuccess:r=>{setInitial(r);setEditing("new");toast(t("Review the extracted details before saving"));},onError:e=>toast(e.message,"err")});
  const [editing, setEditing] = useState<Application | null | "new">(null);
  const [dragged, setDragged] = useState<Application | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const grouped = useMemo(() => {
    const out = Object.fromEntries(APP_STATUSES.map((s) => [s, [] as Application[]])) as Record<AppStatus, Application[]>;
    for (const app of apps ?? []) out[app.status].push(app);
    return out;
  }, [apps]);

  const move = useMutation({
    mutationFn: ({ id, status }: { id: string; status: AppStatus }) => api.applications.update(id, { status }),
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: ["applications"] });
      const previous = queryClient.getQueryData<Application[]>(["applications"]);
      queryClient.setQueryData<Application[]>(["applications"], (cur) => cur?.map((a) => (a.id === id ? { ...a, status } : a)));
      return { previous };
    },
    onError: (_e, _v, ctx) => {
      queryClient.setQueryData(["applications"], ctx?.previous);
      toast(t("Could not move the card - try again."), "err");
    },
    onSuccess: (app) => {
      toast(app.status === "offer" ? t("Congratulations on your offer! 🎉") : t("Moved to {s}", { s: t(STATUS_LABEL[app.status]) }));
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const onDragEnd = (event: DragEndEvent) => {
    setDragged(null);
    const status = event.over?.id as AppStatus | undefined;
    const app = apps?.find((a) => a.id === event.active.id);
    if (status && app && app.status !== status) move.mutate({ id: app.id, status });
  };

  return (
    <div className="flex h-full flex-col px-5 py-8 sm:px-8">
      <PageHeader
        eyebrow={t("My apprenticeships")}
        title={t("Your path to an offer")}
        sub={t("Keep track of every company - from trial days to the offer. Drag cards to change their stage.")}
        actions={
          <Button variant="primary" onClick={() => {setInitial({});setEditing("new");}}>
            <Plus size={16} /> {t("Add apprenticeship")}
          </Button>
        }
      />
      <div className="mb-5 flex flex-wrap items-end gap-3 rounded-2xl border border-line-soft bg-card p-4">
        <div className="min-w-0 flex-1"><Field label={t("Found an apprenticeship? Paste the advert or its HTTPS link.")}><textarea className={`${inputClass} min-h-12 text-sm`} value={captureText} onChange={e=>setCaptureText(e.target.value)} maxLength={20000}/></Field></div>
        <Button variant="outline" disabled={captureText.trim().length<20||capture.isPending} onClick={()=>capture.mutate()}>{capture.isPending?<Spinner/>:null}{t("Extract with Apertus")}</Button>
      </div>
      {isLoading ? (
        <Spinner />
      ) : (
        <DndContext
          sensors={sensors}
          onDragStart={(e) => setDragged(apps?.find((a) => a.id === e.active.id) ?? null)}
          onDragEnd={onDragEnd}
        >
          <div className="flex flex-col gap-3 pb-4 sm:flex-1 sm:flex-row sm:snap-x sm:overflow-x-auto">
            {APP_STATUSES.map((status) => (
              <Column key={status} status={status} apps={grouped[status]} onOpen={(id) => setEditing(apps!.find((a) => a.id === id)!)} />
            ))}
          </div>
          <DragOverlay dropAnimation={null}>{dragged && <AppCard app={dragged} overlay />}</DragOverlay>
        </DndContext>
      )}
      {editing && <AppEditor initial={initial} app={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
