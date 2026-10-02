/** Public landing + sign-in. The hero IS the product: a real-looking exchange
 * with the interviewer and the coach's evidence-quoted feedback. */

import { ArrowRight, GraduationCap, Lock, Mountain, School, Sparkles } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { LangSwitch } from "../components/Shell";
import { Wordmark } from "../components/Logo";
import { Button, Field, inputClass, Segmented, Spinner } from "../components/ui";
import { useI18n } from "../lib/i18n";

function HeroExchange() {
  const { t, lang } = useI18n();
  return (
    <div className="relative mx-auto w-full max-w-[460px]" aria-label={t("Example of a practice interview")}>
      <div className="ring-card animate-rise rounded-2xl bg-card p-5">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-raised text-lg">🌿</span>
          <div>
            <p className="text-sm font-bold">{lang === "en" ? "Ms Caduff" : "Frau Caduff"}</p>
            <p className="text-xs text-ink-3">{t("Vocational trainer · Pflegezentrum Calanda, Chur")}</p>
          </div>
        </div>
        <p className="mt-4 font-display text-[19px] leading-snug font-semibold">
          {{en:"Why is this apprenticeship right for you?",de:"Warum möchten Sie gerade diese Lehre machen?",fr:"Pourquoi cet apprentissage vous correspond-il ?",it:"Perché questo apprendistato è adatto a te?"}[lang]}
        </p>
      </div>

      <div className="animate-rise mt-3 ml-10 rounded-2xl bg-ink p-4 text-[15px] leading-relaxed text-white" style={{ animationDelay: "0.15s" }}>
        {{en:"During my trial day, I helped a resident with lunch. She smiled and thanked me. That moment made me want to work in care.",de:"In der Schnupperlehre habe ich einer älteren Frau beim Essen geholfen. Sie hat sich so gefreut. Da wusste ich, dass ich in der Pflege arbeiten möchte.",fr:"Pendant mon stage, j’ai aidé une résidente à déjeuner. Elle m’a souri et remercié. Ce moment m’a donné envie de travailler dans les soins.",it:"Durante il mio stage, ho aiutato una residente a pranzare. Mi ha sorriso e ringraziato. Quel momento mi ha fatto desiderare di lavorare nell’assistenza."}[lang]}
      </div>

      <div className="ring-card animate-rise mt-3 rounded-2xl border-l-4 border-dusk bg-card p-4" style={{ animationDelay: "0.3s" }}>
        <p className="font-sign text-[11px] text-dusk">{t("Your coach")}</p>
        <p className="mt-1 text-[14.5px] leading-snug">
          <span className="font-bold">{t("Strong:")}</span> {t("a real moment from your trial apprenticeship - that is convincing.")}
        </p>
        <p className="mt-1.5 text-[14.5px] leading-snug">
          <span className="font-bold">{t("Next time:")}</span> {t("add what YOU learned from it, e.g. patience.")}
        </p>
        <div className="mt-3 flex gap-1.5">
          {[t("Motivation") + " 4", t("Examples") + " 3", t("Clarity") + " 3"].map((chip) => (
            <span key={chip} className="rounded-full bg-score-4/10 px-2 py-0.5 font-mono text-[11px] text-score-4">
              {chip}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function AuthCard() {
  const navigate = useNavigate();
  const { t, lang } = useI18n();
  const { setUser, config } = useAuth();
  const [tab, setTab] = useState<"signin" | "signup" | "recover">("signin");
  const [role, setRole] = useState<"student" | "teacher">("student");
  const [form, setForm] = useState({ username: "", password: "", display_name: "", class_code: "", recovery_code: "" });
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (key: string, fn: () => Promise<Parameters<typeof setUser>[0]>) => {
    setBusy(key);
    setError(null);
    try {
      setUser(await fn());
      navigate("/", {replace:true});
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : t("Something went wrong - try again."));
    } finally {
      setBusy(null);
    }
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if(tab === "recover") {void run("form", async()=>{await api.workspace.recover(form.username,form.recovery_code,form.password);return api.auth.login(form.username,form.password);});return;}
    if (tab === "signin") void run("form", () => api.auth.login(form.username, form.password));
    else
      void run("form", () =>
        api.auth.register({
          username: form.username,
          password: form.password,
          display_name: form.display_name,
          role,
          class_code: form.class_code,
          ui_lang: lang,
        }),
      );
  };

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const openDemo = async (role: "student" | "teacher") => {
    await api.auth.demo(role);
    return api.me.update({ ui_lang: lang });
  };

  return (
    <div id="start" className="ring-card rounded-2xl bg-card p-6">
      {config?.demo && <div className="mb-5 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Button variant="sign" size="lg" onClick={() => void run("student", () => openDemo("student"))} disabled={!!busy}>
          {busy === "student" ? <Spinner /> : <GraduationCap size={18} />} {t("Try as student")}
        </Button>
        <Button variant="outline" size="lg" onClick={() => void run("teacher", () => openDemo("teacher"))} disabled={!!busy}>
          {busy === "teacher" ? <Spinner /> : <School size={18} />} {t("Try as teacher")}
        </Button>
      </div>}
      {config?.demo && <p className="mb-5 text-center text-xs text-ink-3">{t("Demo accounts with a fictional class - no sign-up needed.")}</p>}

      <div className="mb-4 flex gap-1 rounded-xl bg-raised p-1" role="tablist">
        {(["signin", "signup"] as const).map((key) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`flex-1 cursor-pointer rounded-lg py-2 text-sm font-bold transition-colors ${tab === key ? "bg-card text-ink shadow-sm" : "text-ink-3"}`}
          >
            {key === "signin" ? t("Sign in") : t("Create account")}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="space-y-3.5">
        {tab === "signup" && (
          <>
            <Segmented
              value={role}
              onChange={setRole}
              options={[
                { value: "student", label: t("I'm a student") },
                { value: "teacher", label: t("I'm a teacher") },
              ]}
            />
            <Field label={t("First name or nickname")}>
              <input className={inputClass} value={form.display_name} onChange={set("display_name")} required maxLength={60} />
            </Field>
          </>
        )}
        <Field label={t("Username")} hint={tab === "signup" ? t("No e-mail needed. Letters, digits, dot or dash.") : undefined}>
          <input className={inputClass} value={form.username} onChange={set("username")} autoComplete="username" required />
        </Field>
        {tab === "recover" && <Field label={t("Recovery code")}><input className={inputClass} value={form.recovery_code} onChange={set("recovery_code")} autoComplete="off" required/></Field>}
        <Field label={t(tab === "recover" ? "New password" : "Password")} hint={tab === "signup" ? t("At least 8 characters.") : undefined}>
          <input
            className={inputClass}
            type="password"
            value={form.password}
            onChange={set("password")}
            autoComplete={tab === "signin" ? "current-password" : "new-password"}
            minLength={tab !== "signin" ? 8 : undefined}
            required
          />
        </Field>
        {tab === "signup" && role === "student" && (
          <Field label={t("Class code (optional)")} hint={t("From your teacher. You can add it later.")}>
            <input className={`${inputClass} font-mono uppercase`} value={form.class_code} onChange={set("class_code")} maxLength={6} />
          </Field>
        )}
        {error && <p className="rounded-lg bg-blaze/10 px-3 py-2 text-sm text-blaze">{error}</p>}
        <Button variant="primary" size="lg" className="w-full" disabled={!!busy}>
          {busy === "form" ? <Spinner className="border-t-white" /> : <ArrowRight size={18} />}
          {t(tab === "signin" ? "Sign in" : tab === "recover" ? "Reset password & sign in" : "Create account")}
        </Button>
        <button type="button" className="block w-full cursor-pointer text-center text-xs text-lake hover:underline" onClick={()=>{setError(null);setTab(tab === "recover"?"signin":"recover");}}>{t(tab === "recover"?"Back to sign in":"Forgot your password?")}</button>
      </form>
    </div>
  );
}

export default function LandingPage() {
  const { t } = useI18n();
  return (
    <div className="min-h-screen">
      <div className="contours hero-grid">
        <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
          <Wordmark />
          <LangSwitch />
        </header>

        <section className="mx-auto grid max-w-6xl items-center gap-12 px-5 pt-6 pb-16 lg:grid-cols-[1.1fr_1fr] lg:pt-12">
          <div>
            <p className="signpost font-sign inline-block py-1.5 pl-3 text-[13px]">{t("Interview training for apprenticeships")}</p>
            <h1 className="font-hero mt-5 text-[48px] leading-[1.05] sm:text-[68px]">{t("Your next chapter")}<br /><span className="text-lake">{t("starts here.")}</span></h1>
            <p className="font-display mt-2 text-[22px] font-semibold text-ink-3 sm:text-[26px]">
              {t("A little practice. A lot more confidence.")}
            </p>
            <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-ink-2">
              {t(
                "Practise your apprenticeship interview as often as you like - in English, German, French, Italian or Swiss German. An AI interviewer asks real questions, a coach shows you what already works and what to try next.",
              )}
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <a href="#start">
                <Button variant="primary" size="lg">
                  {t("Start practising")} <ArrowRight size={18} />
                </Button>
              </a>
            </div>
            <div className="mt-8 flex flex-wrap gap-5 text-xs font-semibold text-ink-3"><span>12 {t("apprenticeships")}</span><span>5 {t("languages")}</span><span>{t("Your words. Your progress.")}</span></div>
          </div>
          <div className="relative rounded-[32px] border border-white/80 bg-white/40 p-4 shadow-[0_30px_80px_-30px_#6654e844] sm:p-7"><div className="mb-5 flex items-center justify-between text-xs font-semibold text-ink-3"><span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-fir"/> {t("Your personal practice room")}</span><span>Apertus 1.5</span></div><HeroExchange /></div>
        </section>
      </div>

      <section className="border-y border-line-soft bg-panel">
        <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 lg:grid-cols-[1fr_420px]">
          <div className="grid content-start gap-8 sm:grid-cols-2">
            {[
              {
                icon: <Mountain size={20} />,
                title: t("Practice that sticks"),
                text: t(
                  "Answer, see what worked, try again right away. Weak answers come back as 2-minute drills on day 1, 3 and 7 - spaced practice, like learning vocabulary.",
                ),
              },
              {
                icon: <Sparkles size={20} />,
                title: t("Feedback you can trust"),
                text: t(
                  "Feedback uses verified quotes from your own words and six criteria from Swiss vocational education. No grades, no shaming - one concrete next step.",
                ),
              },
              {
                icon: <School size={20} />,
                title: t("Made for the classroom"),
                text: t(
                  "Teachers see who practised and where the class struggles - transcripts only if a student agrees. Fits the career-choice lessons of Lehrplan 21.",
                ),
              },
              {
                icon: <Lock size={20} />,
                title: t("Swiss and private"),
                text: t(
                  "Powered by Apertus, Switzerland's open language model. No e-mail needed. This demo is hosted on Google Cloud; schools can also run it on their own server.",
                ),
              },
            ].map((item) => (
              <div key={item.title}>
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sign text-sign-ink">{item.icon}</div>
                <h2 className="font-display mt-3 text-lg font-bold">{item.title}</h2>
                <p className="mt-1.5 text-[15px] leading-relaxed text-ink-2">{item.text}</p>
              </div>
            ))}
          </div>
          <AuthCard />
        </div>
      </section>

      <footer className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-8 text-xs text-ink-3 sm:flex-row sm:justify-between">
        <span>{t("Built for Hack Apertus 2026 · FHGR challenge · Apache-2.0")}</span>
        <span>{t("Powered by Apertus (EPFL · ETH Zurich · CSCS)")}</span>
      </footer>
    </div>
  );
}
