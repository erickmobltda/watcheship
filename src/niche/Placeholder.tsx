/** Shown when an item has no photo: a plain watch face, so the layout stays put. */
export function Placeholder() {
  return (
    <svg viewBox="0 0 80 80" className="h-3/4 opacity-40" aria-hidden>
      <rect x="30" y="4" width="20" height="16" rx="3" fill="hsl(var(--muted-foreground))" />
      <rect x="30" y="60" width="20" height="16" rx="3" fill="hsl(var(--muted-foreground))" />
      <circle cx="40" cy="40" r="22" fill="hsl(var(--card))" stroke="hsl(var(--primary))" strokeWidth="4" />
      <path d="M40 40 L30 33 M40 40 L50 30" stroke="hsl(var(--foreground))" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}
