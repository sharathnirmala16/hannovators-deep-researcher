import type { ReactNode } from 'react';

import { cn } from '@/shared/lib/cn';

interface FilterChipProps {
  pressed: boolean;
  onToggle: () => void;
  /** Count after the label; left out when null. */
  count?: string | null;
  children: ReactNode;
}

/**
 * A toggle chip: quiet on the desk tint, solid ink when pressed. A native
 * button, so Tab focuses it and Enter or Space toggles it.
 */
export function FilterChip({
  pressed,
  onToggle,
  count = null,
  children,
}: FilterChipProps) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onToggle}
      className={cn(
        'inline-flex h-6 items-center gap-1.5 rounded-md px-2 text-xs font-medium whitespace-nowrap transition-colors',
        pressed
          ? 'bg-primary text-primary-foreground hover:bg-primary-hover'
          : 'bg-desk text-foreground hover:bg-shade-2',
      )}
    >
      {children}
      {count !== null ? (
        <span
          className={cn(
            'font-normal tabular-nums',
            pressed
              ? 'text-primary-foreground opacity-75'
              : 'text-muted-foreground',
          )}
        >
          {count}
        </span>
      ) : null}
    </button>
  );
}
