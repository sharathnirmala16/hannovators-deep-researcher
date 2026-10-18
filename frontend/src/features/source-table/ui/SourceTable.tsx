import { useMemo, useState } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import {
  EVIDENCE_LEVEL,
  SEARCH_INTENT,
  SOURCE_STATUS,
  STANCE,
  evidenceRank,
  studyLabel,
  useWorkspace,
  type SourceView,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { EmptyState } from '@/shared/ui/states';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';
import { Tag } from '@/shared/ui/tag';

type SortKey = 'title' | 'level' | 'stance' | 'status' | 'score';

const SORTERS: Record<SortKey, (a: SourceView, b: SourceView) => number> = {
  title: (a, b) => studyLabel(a).localeCompare(studyLabel(b)),
  level: (a, b) => evidenceRank(a) - evidenceRank(b),
  stance: (a, b) => (a.stance ?? 'ZZ').localeCompare(b.stance ?? 'ZZ'),
  status: (a, b) => a.status.localeCompare(b.status),
  score: (a, b) => (b.screen_score ?? -1) - (a.screen_score ?? -1),
};

const COLUMNS: readonly { key: SortKey; label: string }[] = [
  { key: 'title', label: 'Source' },
  { key: 'level', label: 'Evidence' },
  { key: 'stance', label: 'Stance' },
  { key: 'status', label: 'Status' },
  { key: 'score', label: 'Screen' },
];

/** Every source in the workspace, sortable; a row opens the source. */
export function SourceTable() {
  const { load, recordAction } = useWorkspace();
  const { selection, selectSource } = useEvidenceSelection();
  const [sort, setSort] = useState<SortKey>('level');
  const sources = useMemo(
    () =>
      load.status === 'ready'
        ? [...load.state.sources].sort(SORTERS[sort])
        : [],
    [load, sort],
  );
  if (sources.length === 0) {
    return (
      <EmptyState title="No sources yet">
        Sources appear here as the search stage finds them.
      </EmptyState>
    );
  }
  const selectedId = selection.kind === 'none' ? null : selection.sourceId;
  const open = (source: SourceView) => {
    selectSource(source.id);
    recordAction({
      name: 'user.source.open',
      summary: `Opened ${studyLabel(source)}`,
      target: source.url,
      source_ids: [source.id],
    });
  };
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {COLUMNS.map((column) => (
            <TableHead key={column.key}>
              <button
                type="button"
                onClick={() => setSort(column.key)}
                className={cn(
                  'text-xs font-medium',
                  sort === column.key && 'text-foreground underline',
                )}
              >
                {column.label}
              </button>
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sources.map((source) => (
          <TableRow
            key={source.id}
            tabIndex={0}
            data-state={selectedId === source.id ? 'selected' : undefined}
            onClick={() => open(source)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') open(source);
            }}
            className="cursor-pointer"
          >
            <TableCell className="max-w-72">
              <div className="truncate font-medium" title={source.title}>
                {studyLabel(source)}
              </div>
              {source.search_intent ? (
                <div className="text-xs text-muted-foreground">
                  {SEARCH_INTENT[source.search_intent].label}
                </div>
              ) : null}
            </TableCell>
            <TableCell className="text-xs">
              {source.evidence_level
                ? EVIDENCE_LEVEL[source.evidence_level]
                : (source.study_design ?? '-')}
            </TableCell>
            <TableCell>
              {source.stance ? (
                <Tag tone={STANCE[source.stance].tone}>
                  {STANCE[source.stance].label}
                </Tag>
              ) : null}
            </TableCell>
            <TableCell>
              <Tag tone={SOURCE_STATUS[source.status].tone}>
                {SOURCE_STATUS[source.status].label}
              </Tag>
            </TableCell>
            <TableCell className="text-xs tabular-nums">
              {source.screen_score === null
                ? '-'
                : source.screen_score.toFixed(2)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
