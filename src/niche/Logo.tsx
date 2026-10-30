import { cn } from '@/lib/utils';

/** Watcheship mark: a watch face at ten past ten. */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn('size-7', className)} aria-hidden>
      <rect width="64" height="64" rx="14" fill="hsl(var(--card))" />
      <rect x="25" y="6" width="14" height="10" rx="2" fill="hsl(var(--muted-foreground))" />
      <rect x="25" y="48" width="14" height="10" rx="2" fill="hsl(var(--muted-foreground))" />
      <circle cx="32" cy="32" r="16" fill="hsl(var(--background))" stroke="hsl(var(--primary))" strokeWidth="3" />
      <path d="M32 32 L24 26 M32 32 L40 24" stroke="hsl(var(--foreground))" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="32" cy="32" r="1.8" fill="hsl(var(--primary))" />
    </svg>
  );
}
