import type { ReactNode } from 'react';

import { cn } from '@/shared/lib/cn';

interface SectionHeaderProps {
  title: ReactNode;
  /** Short facts next to the title: counts, status, time. */
  meta?: ReactNode;
  actions?: ReactNode;
  /** `pane`: the 40 px bar at the top of a pane, ruled below. */
  variant?: 'pane' | 'section';
  id?: string;
  className?: string;
}

/** The one header pattern: title, meta, actions. */
export function SectionHeader({
  title,
  meta,
  actions,
  variant = 'section',
  id,
  className,
}: SectionHeaderProps) {
  const pane = variant === 'pane';
  const Heading = pane ? 'h2' : 'h3';
  return (
    <header
      className={cn(
        'flex min-w-0 items-center gap-2',
        pane ? 'h-11 shrink-0 border-b bg-background px-4' : 'min-h-8',
        className,
      )}
    >
      <Heading
        id={id}
        className={cn(
          'shrink-0 truncate font-semibold text-foreground',
          pane ? 'text-sm' : 'reading text-base',
        )}
      >
        {title}
      </Heading>
      {meta ? (
        <div className="flex min-w-0 items-center gap-2 truncate text-xs text-muted-foreground tabular-nums">
          {meta}
        </div>
      ) : null}
      {actions ? (
        <div className="ml-auto flex shrink-0 items-center gap-2">
          {actions}
        </div>
      ) : null}
    </header>
  );
}
