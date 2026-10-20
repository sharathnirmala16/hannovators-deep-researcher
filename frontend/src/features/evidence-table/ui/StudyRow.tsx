import { useEvidenceSelection } from '@/domains/evidence';
import type { SourceView, WorkspaceState } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { TableCell, TableRow } from '@/shared/ui/table';

import { RobLights } from './RobLights';
import { StudyCell } from './StudyCell';
import { StudyFindings } from './StudyFindings';
import { SELECTED_ROW } from './tableStyles';

interface StudyRowProps {
  source: SourceView;
  state: WorkspaceState;
  outcome: string;
}

/** One study: name, design, and stance, its results stacked below; RoB 2. */
export function StudyRow({ source, state, outcome }: StudyRowProps) {
  const { selection } = useEvidenceSelection();
  const selected =
    selection.kind !== 'none' && selection.sourceId === source.id;
  return (
    <TableRow
      data-state={selected ? 'selected' : undefined}
      className={cn('hover:bg-transparent', selected && SELECTED_ROW)}
    >
      <TableCell className="align-top whitespace-normal">
        <div className="flex min-w-0 flex-col gap-2">
          <StudyCell source={source} />
          <StudyFindings
            claims={state.claims}
            highlights={state.highlights}
            sourceId={source.id}
            outcome={outcome}
          />
        </div>
      </TableCell>
      <TableCell className="pt-2.5 align-top">
        <RobLights rob2={source.rob2} />
      </TableCell>
    </TableRow>
  );
}
