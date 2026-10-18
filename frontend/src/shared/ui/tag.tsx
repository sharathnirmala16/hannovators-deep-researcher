import type { ComponentProps } from 'react';

import { cn } from '@/shared/lib/cn';

/** Semantic hues; callers map status, certainty, RoB 2, and stance onto them. */
export type Tone =
  'positive' | 'negative' | 'caution' | 'info' | 'null' | 'neutral';

const TINT: Record<Tone, string> = {
  positive: 'bg-tone-positive/10 text-tone-positive',
  negative: 'bg-tone-negative/10 text-tone-negative',
  caution: 'bg-tone-caution/12 text-tone-caution',
  info: 'bg-tone-info/10 text-tone-info',
  null: 'bg-tone-null/10 text-tone-null',
  neutral: 'bg-muted text-muted-foreground',
};

const DOT: Record<Tone, string> = {
  positive: 'bg-tone-positive',
  negative: 'bg-tone-negative',
  caution: 'bg-tone-caution',
  info: 'bg-tone-info',
  null: 'bg-tone-null',
  neutral: 'bg-tone-neutral',
};

interface TagProps extends ComponentProps<'span'> {
  tone?: Tone;
  /** A pulsing dot for work in progress. */
  live?: boolean;
}

/** A small tinted label for one semantic value. */
function Tag({
  tone = 'neutral',
  live = false,
  className,
  children,
  ...props
}: TagProps) {
  return (
    <span
      data-slot="tag"
      className={cn(
        'inline-flex h-5 shrink-0 items-center gap-1.5 rounded-sm px-1.5 text-xs font-medium whitespace-nowrap',
        TINT[tone],
        className,
      )}
      {...props}
    >
      {live ? <ToneDot tone={tone} live /> : null}
      {children}
    </span>
  );
}

function ToneDot({
  tone,
  live = false,
  className,
}: {
  tone: Tone;
  live?: boolean;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        'inline-block size-1.5 shrink-0 rounded-full',
        DOT[tone],
        live && 'animate-pulse',
        className,
      )}
    />
  );
}

export { Tag, ToneDot };
