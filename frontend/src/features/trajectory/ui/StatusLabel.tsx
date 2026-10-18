import type { TrajectoryStatus } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { STATUS_LABEL } from '../model/vocabulary';
import { STATUS_DOT, STATUS_TEXT } from './statusStyles';

export function StatusLabel({ status }: { status: TrajectoryStatus }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 text-xs',
        STATUS_TEXT[status],
      )}
    >
      <span
        aria-hidden
        className={cn('size-1.5 shrink-0 rounded-full', STATUS_DOT[status])}
      />
      {STATUS_LABEL[status]}
    </span>
  );
}
