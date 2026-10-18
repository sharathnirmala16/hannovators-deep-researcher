import type { ComponentProps } from 'react';

import { cn } from '@/shared/lib/cn';

/**
 * A layout region that never scrolls itself: `min-h-0 overflow-hidden`, so
 * exactly one `PaneBody` (or a child that owns its scroll) scrolls inside.
 */
function Pane({ className, ...props }: ComponentProps<'section'>) {
  return (
    <section
      data-slot="pane"
      className={cn(
        'flex h-full min-h-0 min-w-0 flex-col overflow-hidden',
        className,
      )}
      {...props}
    />
  );
}

interface PaneBodyProps extends ComponentProps<'div'> {
  /** False when a child owns the scroll (PDF pages, chat, tables). */
  scroll?: boolean;
}

/** The pane's single scroll area. */
function PaneBody({ scroll = true, className, ...props }: PaneBodyProps) {
  return (
    <div
      data-slot="pane-body"
      className={cn(
        'min-h-0 flex-1',
        scroll ? 'scroll-y' : 'flex flex-col overflow-hidden',
        className,
      )}
      {...props}
    />
  );
}

export { Pane, PaneBody };
