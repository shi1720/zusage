export function LogoMark({ size = 32 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
    <defs><linearGradient id="zusage-mark" x2="32" y2="32"><stop stopColor="#7964ed"/><stop offset="1" stopColor="#4d3bcc"/></linearGradient></defs>
    <rect width="32" height="32" rx="10" fill="#6654e8"/>
    <path d="M9 10h14L10 22h13" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
    <circle cx="25" cy="7" r="3" fill="#b4e7d8"/>
  </svg>;
}
export function Wordmark({ size = 32, light = false }: { size?: number; light?: boolean }) {
  return <span className="flex items-center gap-2.5"><LogoMark size={size}/><span className={`font-display text-[23px] font-extrabold tracking-tight ${light ? "text-white" : "text-ink"}`}>Zusage<span className="text-lake">.</span></span></span>;
}
