import { useEffect, useState } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import {
  EVIDENCE_LEVEL,
  SOURCE_STATUS,
  isUnavailable,
  studyLabel,
  useWorkspace,
  type SourceDetail,
} from '@/domains/workspace';
import { EmptyState, ErrorState, SkeletonBlock } from '@/shared/ui/states';
import { Tag } from '@/shared/ui/tag';

type DetailLoad =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; detail: SourceDetail }
  | { status: 'error'; error: unknown };

interface SourceDetailsProps {
  onOpenStep: (stepId: number) => void;
}

function JsonBlock({ title, value }: { title: string; value: object }) {
  if (Object.keys(value).length === 0) return null;
  return (
    <section className="flex flex-col gap-1">
      <h3 className="text-xs font-medium text-muted-foreground">{title}</h3>
      <pre className="overflow-x-auto rounded-sm bg-muted/50 p-2 font-mono text-xs whitespace-pre-wrap">
        {JSON.stringify(value, null, 2)}
      </pre>
    </section>
  );
}

/** Audit record of the selected source: decisions, reasons, and steps. */
export function SourceDetails({ onOpenStep }: SourceDetailsProps) {
  const { client, workspaceId } = useWorkspace();
  const { selection } = useEvidenceSelection();
  const sourceId = selection.kind === 'none' ? null : selection.sourceId;
  const [load, setLoad] = useState<DetailLoad>({ status: 'idle' });

  useEffect(() => {
    if (!workspaceId || !sourceId) return;
    const controller = new AbortController();
    setLoad({ status: 'loading' });
    client.getSource(workspaceId, sourceId, controller.signal).then(
      (detail) => setLoad({ status: 'ready', detail }),
      (error: unknown) => {
        if (!controller.signal.aborted) setLoad({ status: 'error', error });
      },
    );
    return () => controller.abort();
  }, [client, workspaceId, sourceId]);

  if (!sourceId) {
    return (
      <EmptyState title="No source selected">
        Select a source in the evidence table, the source list, or the graph.
      </EmptyState>
    );
  }
  if (load.status === 'error') {
    return (
      <ErrorState title="Source details are not available">
        {isUnavailable(load.error)
          ? 'This needs the live API.'
          : 'The server could not load this source.'}
      </ErrorState>
    );
  }
  if (load.status !== 'ready') return <SkeletonBlock lines={6} />;
  const { detail } = load;
  const { source } = detail;
  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h2 className="text-sm font-semibold">{studyLabel(source)}</h2>
        <p className="text-xs text-muted-foreground">{source.title}</p>
        <div className="flex flex-wrap gap-1">
          <Tag tone={SOURCE_STATUS[source.status].tone}>
            {SOURCE_STATUS[source.status].label}
          </Tag>
          {source.evidence_level ? (
            <Tag>{EVIDENCE_LEVEL[source.evidence_level]}</Tag>
          ) : null}
          <Tag>{detail.chunk_count} chunks</Tag>
        </div>
      </header>
      {source.decision_explanation ? (
        <p className="text-sm">{source.decision_explanation}</p>
      ) : null}
      {detail.abstract ? (
        <section className="flex flex-col gap-1">
          <h3 className="text-xs font-medium text-muted-foreground">
            Abstract
          </h3>
          <p className="text-sm leading-relaxed">{detail.abstract}</p>
        </section>
      ) : null}
      <JsonBlock title="Screening" value={detail.screen} />
      <JsonBlock title="Appraisal" value={detail.appraisal} />
      {detail.trajectory_step_ids.length > 0 ? (
        <section className="flex flex-col gap-1">
          <h3 className="text-xs font-medium text-muted-foreground">
            Trajectory steps
          </h3>
          <div className="flex flex-wrap gap-1">
            {detail.trajectory_step_ids.map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => onOpenStep(id)}
                className="rounded-sm bg-muted px-1.5 font-mono text-xs hover:bg-muted/70"
              >
                #{id}
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
