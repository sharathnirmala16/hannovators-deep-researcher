import type { TrajectoryKind } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { KIND_LABEL } from '../model/vocabulary';
import { KIND_ICON } from './kindIcons';

interface KindBadgeProps {
  kind: TrajectoryKind;
  className?: string;
}

/** Kind as an icon and a word; kinds stay neutral so status color stands out. */
export function KindBadge({ kind, className }: KindBadgeProps) {
  const Icon = KIND_ICON[kind];
  return (
    <span
      className={cn(
        'inline-flex min-w-0 items-center gap-1.5 text-xs text-foreground/80',
        className,
      )}
    >
      <Icon aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
      <span className="truncate">{KIND_LABEL[kind]}</span>
    </span>
  );
}
