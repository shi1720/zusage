/** Shared primitives. One button system, one card, one modal. */

import { X } from "lucide-react";
import { useEffect, useRef } from "react";

import { cn } from "../lib/format";

type ButtonVariant = "primary" | "sign" | "ghost" | "outline" | "danger";

export function Button({
  variant = "ghost",
  size = "md",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: "sm" | "md" | "lg" }) {
  return (
    <button
      className={cn(
        "inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl font-semibold whitespace-nowrap transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-45",
        size === "sm" && "px-3 py-1.5 text-sm",
        size === "md" && "px-4 py-2.5 text-[15px]",
        size === "lg" && "px-6 py-3.5 text-base",
        variant === "primary" && "bg-lake text-white shadow-[0_6px_18px_-8px_#5643d680] hover:bg-[#4633ba] hover:-translate-y-0.5",
        variant === "sign" && "bg-sign text-sign-ink shadow-sm hover:bg-[#dcd8ff]",
        variant === "ghost" && "text-ink-2 hover:bg-raised hover:text-ink",
        variant === "outline" && "border border-line bg-card text-ink hover:border-ink-3",
        variant === "danger" && "text-blaze hover:bg-blaze/10",
        className,
      )}
      {...props}
    />
  );
}

export function Card({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("ring-card min-w-0 rounded-2xl bg-card", className)} {...props}>
      {children}
    </div>
  );
}

export function Eyebrow({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={cn("font-sign text-[12px] text-ink-3", className)}>{children}</p>;
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={cn("inline-block h-4 w-4 animate-spin rounded-full border-2 border-line border-t-ink", className)}
      aria-label="Loading"
    />
  );
}

export function Typing() {
  return (
    <span className="inline-flex items-center gap-1" aria-label="…">
      {[0, 1, 2].map((i) => (
        <span key={i} className="typing-dot h-1.5 w-1.5 rounded-full bg-ink-3" style={{ animationDelay: `${i * 0.15}s` }} />
      ))}
    </span>
  );
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-line bg-panel/60 px-6 py-12 text-center">
      <div className="text-ink-3">{icon}</div>
      <p className="font-display text-base font-bold text-ink">{title}</p>
      {hint && <p className="max-w-sm text-sm text-ink-2">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  wide,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const dialog = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const priorOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () => Array.from(dialog.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex="0"]'
    ) ?? []).filter((el) => el.getClientRects().length > 0);
    focusable()[0]?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;
      const items = focusable();
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = priorOverflow;
      before?.focus();
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-4">
      <div className="absolute inset-0 bg-ink/40 backdrop-blur-[2px]" onClick={onClose} />
      <div
        role="dialog"
        ref={dialog}
        aria-modal="true"
        aria-label={title}
        className={cn(
          "ring-card animate-rise relative max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-card p-6 sm:rounded-2xl",
          wide ? "sm:max-w-2xl" : "sm:max-w-md",
        )}
      >
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="font-display text-lg font-bold">{title}</h2>
          <Button onClick={onClose} aria-label="Close" className="!p-1.5">
            <X size={18} />
          </Button>
        </div>
        {children}
      </div>
    </div>
  );
}

export const inputClass =
  "w-full rounded-xl border border-line bg-card px-3.5 py-2.5 text-base text-ink placeholder:text-ink-3 transition-colors focus:border-ink focus:outline-none";

export function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-bold text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-3">{hint}</span>}
    </label>
  );
}

/** Pill-style single choice. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  className,
}: {
  value: T;
  options: { value: T; label: React.ReactNode; hint?: string }[];
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div role="radiogroup" className={cn("flex flex-wrap gap-2", className)}>
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role="radio"
          aria-checked={value === opt.value}
          onClick={() => onChange(opt.value)}
          className={cn(
            "cursor-pointer rounded-xl border px-3.5 py-2 text-left text-sm transition-all",
            value === opt.value
              ? "border-ink bg-ink text-white"
              : "border-line bg-card text-ink hover:border-ink-3",
          )}
        >
          <span className="block font-bold">{opt.label}</span>
          {opt.hint && (
            <span className={cn("block text-xs", value === opt.value ? "text-white/70" : "text-ink-3")}>{opt.hint}</span>
          )}
        </button>
      ))}
    </div>
  );
}

export function Badge({ children, tone = "neutral", className }: {
  children: React.ReactNode;
  tone?: "neutral" | "sign" | "fir" | "blaze" | "lake";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold",
        tone === "neutral" && "bg-raised text-ink-2",
        tone === "sign" && "bg-sign text-sign-ink",
        tone === "fir" && "bg-fir/12 text-fir",
        tone === "blaze" && "bg-blaze/10 text-blaze",
        tone === "lake" && "bg-lake/10 text-lake",
        className,
      )}
    >
      {children}
    </span>
  );
}
