import type { KeyboardEvent } from 'react';

import {
  EVIDENCE_LEVEL,
  SEARCH_INTENT,
  SOURCE_STATUS,
  STANCE,
  type SourceView,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { TableCell, TableRow } from '@/shared/ui/table';
import { Tag } from '@/shared/ui/tag';

import { SourceByline } from './SourceByline';

interface SourceRowProps {
  source: SourceView;
  selected: boolean;
  onOpen: (source: SourceView) => void;
}

const SELECTED =
  'bg-accent hover:bg-accent data-[state=selected]:bg-accent [&>td:first-child]:shadow-[inset_2px_0_0_rgba(24,34,58,1)]';

/** Title and study line; level and intent; status and stance; score. */
export function SourceRow({ source, selected, onOpen }: SourceRowProps) {
  const status = SOURCE_STATUS[source.status];
  const stance = source.stance ? STANCE[source.stance] : null;
  const intent = source.search_intent
    ? SEARCH_INTENT[source.search_intent]
    : null;
  const level = source.evidence_level
    ? EVIDENCE_LEVEL[source.evidence_level]
    : source.study_design;
  const onKeyDown = (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    onOpen(source);
  };
  return (
    <TableRow
      tabIndex={0}
      aria-current={selected ? 'true' : undefined}
      data-state={selected ? 'selected' : undefined}
      onClick={() => onOpen(source)}
      onKeyDown={onKeyDown}
      className={cn('cursor-pointer', selected && SELECTED)}
    >
      <TableCell className="align-top">
        <div
          className="truncate font-medium text-foreground"
          title={source.title}
        >
          {source.title}
        </div>
        <SourceByline source={source} />
      </TableCell>
      <TableCell className="align-top">
        <div className="flex flex-col items-start gap-1">
          <span
            className="line-clamp-1 text-xs leading-5 text-foreground"
            title={level ?? undefined}
          >
            {level ?? (
              <span className="text-muted-foreground">Not classified</span>
            )}
          </span>
          {intent ? <Tag title={intent.hint}>{intent.label}</Tag> : null}
        </div>
      </TableCell>
      <TableCell className="align-top">
        <div className="flex flex-col items-start gap-1">
          <Tag tone={status.tone}>{status.label}</Tag>
          {stance ? <Tag tone={stance.tone}>{stance.label}</Tag> : null}
        </div>
      </TableCell>
      <TableCell className="pt-2.5 text-right align-top text-xs tabular-nums">
        {source.screen_score === null ? (
          <span className="text-muted-foreground">None</span>
        ) : (
          source.screen_score.toFixed(2)
        )}
      </TableCell>
    </TableRow>
  );
}
