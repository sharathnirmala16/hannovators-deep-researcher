import { useEvidenceSelection } from '@/domains/evidence';
import { isUnavailable, useWorkspace } from '@/domains/workspace';
import { errorMessage } from '@/shared/lib/format';
import { EmptyState, ErrorState, SkeletonBlock } from '@/shared/ui/states';

import { useSourceDetail } from '../model/useSourceDetail';
import { SourceRecord, type SourceSlot } from './SourceRecord';

interface SourceDetailsProps {
  onOpenStep: (stepId: number) => void;
  /** Rendered under the header, for example the researcher's decision. */
  renderDecision?: SourceSlot | undefined;
}

/** Changes whenever the workspace state reports a new status or decision. */
function sourceVersion(
  load: ReturnType<typeof useWorkspace>['load'],
  sourceId: string | null,
): string {
  if (load.status !== 'ready' || !sourceId) return '';
  const source = load.state.sources.find((item) => item.id === sourceId);
  const decision = source?.decision;
  return `${source?.status ?? ''}|${decision?.decided_at ?? ''}|${String(decision?.applied ?? '')}`;
}

/** Audit record of the selected source: decisions, reasons, and steps. */
export function SourceDetails({
  onOpenStep,
  renderDecision,
}: SourceDetailsProps) {
  const { load: workspace } = useWorkspace();
  const { selection } = useEvidenceSelection();
  const sourceId = selection.kind === 'none' ? null : selection.sourceId;
  const { load, retry } = useSourceDetail(
    sourceId,
    sourceVersion(workspace, sourceId),
  );

  if (!sourceId) {
    return (
      <div className="p-4">
        <EmptyState title="No source selected">
          Select a study in the evidence profile, a row in Sources, or a node in
          the graph to see how it was screened and appraised.
        </EmptyState>
      </div>
    );
  }
  if (load.status === 'error') {
    return (
      <div className="p-4">
        {isUnavailable(load.error) ? (
          <ErrorState title="Source details are not available">
            Source details need the live API; fixture mode does not include
            them.
          </ErrorState>
        ) : (
          <ErrorState
            title="Source details could not be loaded"
            message={errorMessage(load.error)}
            onRetry={retry}
          />
        )}
      </div>
    );
  }
  if (load.status === 'loading') {
    return (
      <div className="flex flex-col gap-6 p-4">
        <SkeletonBlock lines={3} label="Loading source details" />
        <SkeletonBlock lines={5} />
      </div>
    );
  }
  return (
    <SourceRecord
      detail={load.detail}
      settings={
        workspace.status === 'ready' ? workspace.state.workspace.settings : null
      }
      onOpenStep={onOpenStep}
      renderDecision={renderDecision}
    />
  );
}
