/** Profile, story bank, class membership and privacy controls. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus, ShieldCheck, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { AccountSettings } from "../components/AccountSettings";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { PageHeader } from "../components/Shell";
import { useToast } from "../components/Toast";
import { useCatalog } from "../components/useCatalog";
import { Button, Card, Eyebrow, Field, inputClass, Modal, Segmented, Spinner } from "../components/ui";
import { cn } from "../lib/format";
import { LANG_LABEL, loc, useI18n } from "../lib/i18n";
import type { InterviewLang, ProfileData } from "../types";

export default function ProfilePage() {
  const { t, lang } = useI18n();
  const toast = useToast();
  const { user, setUser, signOut } = useAuth();
  const queryClient = useQueryClient();
  const { data: catalog } = useCatalog();
  const { data } = useQuery({ queryKey: ["profile"], queryFn: api.me.profile, enabled: user?.role === "student" });
  const [profile, setProfile] = useState<ProfileData>({});
  const [hobby, setHobby] = useState("");
  const [code, setCode] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    if (data) setProfile(data.data);
  }, [data]);

  const save = useMutation({
    mutationFn: () => api.me.saveProfile(profile),
    onError: (e) => toast(e.message, "err"),
    onSuccess: (res) => {
      queryClient.setQueryData(["profile"], res);
      toast(t("Profile saved"));
    },
  });
  const updateMe = useMutation({
    mutationFn: api.me.update,
    onError: (e) => toast(e.message, "err"),
    onSuccess: (u) => {
      setUser(u);
      toast(t("Saved"));
    },
  });
  const join = useMutation({
    mutationFn: () => api.me.joinClass(code),
    onSuccess: (u) => {
      setUser(u);
      setCode("");
      toast(t("You joined {name}", { name: u.classroom?.name ?? "" }));
    },
    onError: (exc) => toast(exc instanceof ApiError ? exc.message : t("Class code not found"), "err"),
  });
  const leave = useMutation({ mutationFn: api.me.leaveClass, onSuccess: setUser });
  const remove = useMutation({
    mutationFn: api.me.remove,
    onSuccess: async () => {
      await signOut();
    },
  });

  const exportData = async () => {
    const blob = new Blob([JSON.stringify(await api.me.export(), null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `zusage-${user?.username}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const stories = profile.stories ?? [];
  const setStory = (i: number, text: string) =>
    setProfile((p) => ({ ...p, stories: stories.map((s, j) => (j === i ? { ...s, text } : s)) }));

  if (!user) return null;
  const student = user.role === "student";

  return (
    <div className="mx-auto max-w-4xl px-5 py-8 sm:px-8">
      <PageHeader eyebrow={t("Profile & privacy")} title={user.display_name} sub={`@${user.username}`} />

      <div className="space-y-5">
        <AccountSettings/>
        {student && (
          <Card className="p-6">
            <Eyebrow className="mb-1">{t("About you")}</Eyebrow>
            <p className="mb-5 text-sm text-ink-2">{t("Your interviewer uses this to ask personal questions. Share only what you're comfortable with - no addresses or phone numbers needed.")}</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("Age")}>
                <input
                  type="number"
                  min={13}
                  max={25}
                  className={inputClass}
                  value={profile.age ?? ""}
                  onChange={(e) => setProfile((p) => ({ ...p, age: e.target.value ? Number(e.target.value) : undefined }))}
                />
              </Field>
              <Field label={t("School / class")} hint={t("e.g. Sek A, 3rd year")}>
                <input className={inputClass} value={profile.school ?? ""} onChange={(e) => setProfile((p) => ({ ...p, school: e.target.value }))} />
              </Field>
              <Field label={t("Dream apprenticeship")}>
                <select
                  className={inputClass}
                  value={profile.target_occupation_id ?? ""}
                  onChange={(e) => setProfile((p) => ({ ...p, target_occupation_id: e.target.value }))}
                >
                  <option value="">-</option>
                  {catalog?.occupations.map((o) => (
                    <option key={o.id} value={o.id}>
                      {loc(o.name, lang)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t("Preferred interview language")}>
                <select
                  className={inputClass}
                  value={profile.interview_language ?? lang}
                  onChange={(e) => setProfile((p) => ({ ...p, interview_language: e.target.value as InterviewLang }))}
                >
                  {(["de", "fr", "it", "en", "gsw"] as InterviewLang[]).map((l) => (
                    <option key={l} value={l}>
                      {LANG_LABEL[l]}
                    </option>
                  ))}
                </select>
              </Field>
              <div className="sm:col-span-2">
                <Field label={t("Hobbies")}>
                  <div className="flex flex-wrap items-center gap-2">
                    {(profile.hobbies ?? []).map((h) => (
                      <span key={h} className="flex items-center gap-1 rounded-full bg-raised px-3 py-1 text-sm">
                        {h}
                        <button
                          type="button"
                          aria-label={t("Remove")}
                          onClick={() => setProfile((p) => ({ ...p, hobbies: (p.hobbies ?? []).filter((x) => x !== h) }))}
                          className="cursor-pointer text-ink-3"
                        >
                          <X size={13} />
                        </button>
                      </span>
                    ))}
                    <input
                      className={cn(inputClass, "w-48")}
                      value={hobby}
                      placeholder={t("Add a hobby + Enter")}
                      onChange={(e) => setHobby(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && hobby.trim()) {
                          e.preventDefault();
                          setProfile((p) => ({ ...p, hobbies: [...(p.hobbies ?? []), hobby.trim()].slice(0, 8) }));
                          setHobby("");
                        }
                      }}
                    />
                  </div>
                </Field>
              </div>
              <div className="sm:col-span-2">
                <Field label={t("Trial apprenticeships & experience")} hint={t("Where did you do a Schnupperlehre? What did you do there?")}>
                  <textarea
                    className={cn(inputClass, "min-h-20")}
                    value={profile.experience ?? ""}
                    onChange={(e) => setProfile((p) => ({ ...p, experience: e.target.value }))}
                  />
                </Field>
              </div>
            </div>

            <div className="mt-6">
              <p className="text-sm font-bold">{t("Story bank")}</p>
              <p className="mb-3 text-sm text-ink-2">{t("Short real moments you can use as examples: a problem you solved, a time you helped someone. The hint button reminds you of them during interviews.")}</p>
              <div className="space-y-2">
                {stories.map((s, i) => (
                  <div key={i} className="flex gap-2">
                    <textarea className={cn(inputClass, "min-h-14")} value={s.text} onChange={(e) => setStory(i, e.target.value)} maxLength={400} />
                    <Button
                      variant="ghost"
                      aria-label={t("Remove")}
                      onClick={() => setProfile((p) => ({ ...p, stories: stories.filter((_, j) => j !== i) }))}
                    >
                      <Trash2 size={16} />
                    </Button>
                  </div>
                ))}
              </div>
              {stories.length < 6 && (
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={() => setProfile((p) => ({ ...p, stories: [...stories, { title: "", text: "" }] }))}
                >
                  <Plus size={14} /> {t("Add a story")}
                </Button>
              )}
            </div>
            <Button variant="primary" className="mt-6" onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending && <Spinner className="border-t-white" />} {t("Save profile")}
            </Button>
          </Card>
        )}

        <Card className="p-6">
          <Eyebrow className="mb-3">{t("Language of the app")}</Eyebrow>
          <Segmented
            value={user.ui_lang}
            onChange={(v) => updateMe.mutate({ ui_lang: v })}
            options={(["de", "fr", "it", "en"] as const).map((l) => ({ value: l, label: LANG_LABEL[l] }))}
          />
        </Card>

        {student && (
          <Card className="p-6">
            <Eyebrow className="mb-3">{t("Class")}</Eyebrow>
            {user.classroom ? (
              <>
                <p className="text-[15px]">
                  {t("You are in")} <span className="font-bold">{user.classroom.name}</span> · {user.classroom.school}
                </p>
                <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl bg-raised p-4">
                  <input
                    type="checkbox"
                    className="mt-1 h-5 w-5 accent-[var(--color-ink)]"
                    checked={user.consent_share}
                    onChange={(e) => updateMe.mutate({ consent_share: e.target.checked })}
                  />
                  <span>
                    <span className="block font-bold">{t("Let my teacher read my interview answers")}</span>
                    <span className="block text-sm text-ink-2">
                      {t("Your teacher always sees scores and how often you practise. Your actual answers only if you tick this. You can change it any time.")}
                    </span>
                  </span>
                </label>
                <Button variant="ghost" size="sm" className="mt-3" onClick={() => leave.mutate()}>
                  {t("Leave class")}
                </Button>
              </>
            ) : (
              <form
                className="flex flex-wrap gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  join.mutate();
                }}
              >
                <input
                  className={cn(inputClass, "w-40 font-mono uppercase")}
                  placeholder="CHUR26"
                  value={code}
                  maxLength={6}
                  onChange={(e) => setCode(e.target.value)}
                />
                <Button variant="primary" disabled={code.length < 6 || join.isPending}>
                  {t("Join class")}
                </Button>
              </form>
            )}
          </Card>
        )}

        <Card className="p-6">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 shrink-0 text-fir" />
            <div>
              <Eyebrow className="mb-1">{t("Your data")}</Eyebrow>
              <p className="text-[15px] text-ink-2">
                {t("Zusage uses Apertus through the Hack Apertus inference service. This demo stores your data on Google Cloud. Schools can deploy locally. Transcript text older than 180 days is removed during server maintenance; scores remain for your progress.")}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={() => void exportData()}>
                  <Download size={15} /> {t("Download my data")}
                </Button>
                <Button variant="danger" size="sm" onClick={() => setConfirmDelete(true)}>
                  <Trash2 size={15} /> {t("Delete my account")}
                </Button>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {confirmDelete && (
        <Modal title={t("Delete your account?")} onClose={() => setConfirmDelete(false)}>
          <p className="text-[15px] text-ink-2">{t("This permanently deletes your account, interviews, drills and apprenticeships. It cannot be undone.")}</p>
          <div className="mt-5 flex gap-2">
            <Button variant="danger" className="border border-blaze" onClick={() => remove.mutate()} disabled={remove.isPending}>
              {t("Delete permanently")}
            </Button>
            <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
              {t("Cancel")}
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
