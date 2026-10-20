import type { TrajectoryStatus } from '@/domains/workspace';
import { Tag } from '@/shared/ui/tag';

import { STATUS_LABEL } from '../model/vocabulary';
import { STATUS_TONE } from './tones';

interface StatusTagProps {
  status: TrajectoryStatus;
  /** Quiet: settled steps (OK, skipped) show plain text, not a tag. */
  quiet?: boolean;
}

/** Running is info with a live dot, errors are negative, the rest neutral. */
export function StatusTag({ status, quiet = false }: StatusTagProps) {
  const settled = status === 'OK' || status === 'SKIPPED';
  if (quiet && settled) {
    return (
      <span className="text-xs text-muted-foreground">
        {STATUS_LABEL[status]}
      </span>
    );
  }
  return (
    <Tag tone={STATUS_TONE[status]} live={status === 'RUNNING'}>
      {STATUS_LABEL[status]}
    </Tag>
  );
}
