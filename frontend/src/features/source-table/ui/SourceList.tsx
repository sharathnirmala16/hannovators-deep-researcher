import { useEvidenceSelection } from '@/domains/evidence';
import { studyLabel, useWorkspace, type SourceView } from '@/domains/workspace';
import { plural } from '@/shared/lib/format';
import { SectionHeader } from '@/shared/ui/section-header';
import { Segmented } from '@/shared/ui/segmented';
import { EmptyState } from '@/shared/ui/states';
import { Table, TableBody } from '@/shared/ui/table';

import type { StatusFilter } from '../model/sources';
import { useSourceRows } from '../model/useSourceRows';
import { SourceRow } from './SourceRow';
import { SourceTableHeader } from './SourceTableHeader';

const EMPTY_FILTER: Record<StatusFilter, string> = {
  all: 'No sources yet.',
  kept: 'No source has passed screening or appraisal yet.',
  removed: 'No source has been screened out or excluded.',
  seeds: 'This workspace has no seed documents.',
};

/** The source table with its status filter; a row opens the source. */
export function SourceList({ sources }: { sources: readonly SourceView[] }) {
  const { recordAction } = useWorkspace();
  const { selection, selectSource } = useEvidenceSelection();
  const { rows, sort, onSort, filter, setFilter, options } =
    useSourceRows(sources);
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
    <section
      aria-labelledby="source-table-title"
      className="flex flex-col gap-3 py-4"
    >
      <SectionHeader
        id="source-table-title"
        className="px-4"
        title="Sources"
        meta={plural(rows.length, 'source')}
        actions={
          <Segmented
            label="Filter sources by status"
            value={filter}
            options={options}
            onChange={setFilter}
          />
        }
      />
      {rows.length === 0 ? (
        <EmptyState className="mx-4" title="Nothing in this filter">
          {EMPTY_FILTER[filter]} Choose All to see every source.
        </EmptyState>
      ) : (
        <Table className="table-fixed border-separate border-spacing-0 [&_td]:border-b [&_tbody_tr:last-child_td]:border-b-0">
          <SourceTableHeader sort={sort} onSort={onSort} />
          <TableBody>
            {rows.map((source) => (
              <SourceRow
                key={source.id}
                source={source}
                selected={selectedId === source.id}
                onOpen={open}
              />
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
