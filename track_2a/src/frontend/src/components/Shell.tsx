/** App chrome: sidebar (desktop) / slide-over (mobile), language switch,
 * model badge. The interview room renders WITHOUT this shell (focus mode). */

import { BarChart3, BellRing, Briefcase, Compass, Cpu, FileUp, PenLine, TrendingUp, LogOut, Menu, Mic, School, Sunrise, UserRound, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { useAuth } from "../auth";
import { api } from "../api";
import { useToast } from "./Toast";
import { cn, initials } from "../lib/format";
import { useI18n } from "../lib/i18n";
import type { Lang } from "../types";
import { Walkthrough, replayTour } from "./Walkthrough";
import { Wordmark } from "./Logo";

export function LangSwitch({ className }: { className?: string }) {
  const { lang, setLang } = useI18n();
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const choose = async (code: Lang) => {
    setLang(code);
    if (!user) return;
    setSaving(true);
    try { setUser(await api.me.update({ ui_lang: code })); }
    catch (error) { toast(error instanceof Error ? error.message : "Could not save language", "err"); }
    finally { setSaving(false); }
  };
  return (
    <div className={cn("flex gap-1", className)} role="group" aria-label="Language">
      {(["en", "de", "fr", "it"] as Lang[]).map((code) => (
        <button
          key={code}
          onClick={() => void choose(code)}
          disabled={saving}
          aria-pressed={lang === code}
          className={cn(
            "cursor-pointer rounded-md px-2 py-1 font-mono text-xs uppercase transition-colors",
            lang === code ? "bg-ink text-white" : "text-ink-3 hover:bg-raised hover:text-ink",
          )}
        >
          {code}
        </button>
      ))}
    </div>
  );
}

export function ModelBadge() {
  const { config } = useAuth();
  const { t } = useI18n();
  if (!config) return null;
  const live = config.mode === "live";
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-xl border px-3 py-2 text-[12px] leading-snug",
        live ? "border-fir/25 bg-fir/5 text-ink-2" : "border-sign-deep/40 bg-sign/15 text-ink-2",
      )}
    >
      <Cpu size={14} className={cn("mt-0.5 shrink-0", live ? "text-fir" : "text-sign-deep")} />
      <span>
        {live ? (
          <>
            <span className="font-bold text-ink">{t("Coach: Apertus")}</span>
            <br />
            <span className="font-mono text-[11px]">{config.model.replace("swiss-ai/", "")}</span>
          </>
        ) : (
          <>
            <span className="font-bold text-ink">{t("Offline demo coach")}</span>
            <br />
            {t("Rule-based stand-in. Connect Apertus for real feedback.")}
          </>
        )}
      </span>
    </div>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, signOut } = useAuth();
  const { t } = useI18n();
  const teacher = user?.role !== "student";
  const nav = teacher
    ? [
        { to: "/", label: t("My class"), icon: School },
        { to: "/practice", label: t("Try the coach"), icon: Mic },
      ]
    : [
        { to: "/", label: t("Today"), icon: Sunrise },
        { to: "/practice", label: t("Practice interview"), icon: Mic },
        { to: "/applications", label: t("My apprenticeships"), icon: Briefcase },
        { to: "/progress", label: t("Progress"), icon: BarChart3 },
        { to: "/outreach", label: t("Writing studio"), icon: PenLine },
        { to: "/nudges", label: t("Follow-ups"), icon: BellRing },
        { to: "/import", label: t("Import & export"), icon: FileUp },
        { to: "/analytics", label: t("Application insights"), icon: TrendingUp },
      ];

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-line-soft bg-panel">
      <div className="px-5 pt-5 pb-5">
        <Wordmark />
        <p className="mt-2 text-[12.5px] leading-snug text-ink-3">{t("Interview coach for your apprenticeship")}</p>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-3">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] transition-colors",
                isActive ? "bg-sign/70 font-bold text-lake" : "text-ink-2 hover:bg-raised/70 hover:text-ink",
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={18} className={cn(isActive ? "text-lake" : "text-ink-3")} />
                {label}
                {isActive && <span className="ml-auto h-4 w-1.5 rounded-sm blaze" aria-hidden />}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-3 px-3 pb-3">
        <button onClick={()=>{onNavigate?.();replayTour();}} className="flex w-full cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm text-ink-2 hover:bg-raised"><Compass size={16}/>{t("Take a tour")}</button>
        <ModelBadge />
        <LangSwitch className="px-1" />
      </div>

      <div className="border-t border-line-soft p-3">
        <div className="flex items-center gap-1">
          <NavLink
            to="/profile"
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "flex min-w-0 flex-1 items-center gap-3 rounded-xl px-2 py-2 transition-colors",
                isActive ? "bg-card ring-card" : "hover:bg-raised/70",
              )
            }
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-sign font-display text-sm font-bold text-sign-ink">
              {initials(user?.display_name ?? "?")}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-bold text-ink">{user?.display_name}</span>
              <span className="flex items-center gap-1 truncate text-[12px] text-ink-3">
                <UserRound size={11} /> {user?.classroom ? user.classroom.name : t("Profile & privacy")}
              </span>
            </span>
          </NavLink>
          <button
            onClick={() => void signOut()}
            aria-label={t("Sign out")}
            title={t("Sign out")}
            className="cursor-pointer rounded-lg p-2 text-ink-3 transition-colors hover:bg-raised hover:text-ink"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>
    </aside>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const mainRef = useRef<HTMLElement>(null);
  const location = useLocation();
  useEffect(() => {
    setOpen(false);
    mainRef.current?.scrollTo(0, 0);
  }, [location.pathname]);

  return (
    <div className="flex h-dvh flex-col overflow-hidden md:flex-row">
      <header className="no-print flex items-center justify-between border-b border-line-soft bg-panel px-4 py-2.5 md:hidden">
        <Wordmark size={28} />
        <button onClick={() => setOpen(true)} aria-label="Menu" className="cursor-pointer rounded-lg p-2 text-ink-2 hover:bg-raised">
          <Menu size={22} />
        </button>
      </header>
      <div className="no-print hidden md:flex">
        <Sidebar />
      </div>
      {open && (
        <div className="fixed inset-0 z-[60] md:hidden">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
          <div className="animate-rise absolute inset-y-0 left-0 flex">
            <Sidebar onNavigate={() => setOpen(false)} />
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close"
            className="absolute top-3 right-3 cursor-pointer rounded-lg bg-card p-2 text-ink-2"
          >
            <X size={18} />
          </button>
        </div>
      )}
      <main ref={mainRef} className="min-h-0 flex-1 overflow-y-auto">{children}</main><Walkthrough/>
    </div>
  );
}

export function PageHeader({
  eyebrow,
  title,
  sub,
  actions,
}: {
  eyebrow?: string;
  title: string;
  sub?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <p className="font-sign mb-1.5 text-[12px] text-ink-3">{eyebrow}</p>}
        <h1 className="font-display text-[28px] leading-tight font-extrabold sm:text-[32px]">{title}</h1>
        {sub && <p className="mt-1.5 max-w-2xl text-[15px] text-ink-2">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
