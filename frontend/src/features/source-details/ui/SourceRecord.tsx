import type { ReactNode } from 'react';

import type {
  SourceDetail,
  SourceView,
  WorkspaceSettings,
} from '@/domains/workspace';
import { plural } from '@/shared/lib/format';

import { AbstractText } from './AbstractText';
import { AppraisalRecord } from './AppraisalRecord';
import { ScreeningDecision } from './ScreeningDecision';
import { SourceHeader } from './SourceHeader';
import { TrajectoryLinks } from './TrajectoryLinks';

export type SourceSlot = (source: SourceView) => ReactNode;

interface SourceRecordProps {
  detail: SourceDetail;
  settings: WorkspaceSettings | null;
  onOpenStep: (stepId: number) => void;
  renderDecision?: SourceSlot | undefined;
}

/** "RoB 2 overall SOME_CONCERNS" reads as "RoB 2 overall some concerns". */
const CODE = /\b[A-Z]+(?:_[A-Z]+)+\b/g;

function humanizeCodes(text: string): string {
  return text.replace(CODE, (code) => code.toLowerCase().replaceAll('_', ' '));
}

/** The audit record: who, what was decided and why, the abstract, the steps. */
export function SourceRecord({
  detail,
  settings,
  onOpenStep,
  renderDecision,
}: SourceRecordProps) {
  const { source } = detail;
  return (
    <article className="flex flex-col gap-6 p-4">
      <SourceHeader detail={detail} />
      {renderDecision?.(source)}
      {source.decision_explanation ? (
        <section className="flex flex-col gap-1 rounded-md bg-desk px-3 py-2">
          <h3 className="text-xs font-medium text-muted-foreground">
            {source.decision ? "The agent's decision" : 'Decision'}
          </h3>
          <p className="text-sm text-foreground">
            {humanizeCodes(source.decision_explanation)}
          </p>
        </section>
      ) : null}
      <ScreeningDecision
        detail={detail}
        votesNeeded={settings?.screen_votes_t ?? null}
      />
      <AppraisalRecord detail={detail} needed={settings?.appraise_m ?? null} />
      {detail.abstract ? <AbstractText text={detail.abstract} /> : null}
      <TrajectoryLinks
        stepIds={detail.trajectory_step_ids}
        onOpenStep={onOpenStep}
      />
      <p className="flex flex-wrap gap-x-3 text-xs text-muted-foreground tabular-nums">
        <span>{plural(detail.claim_ids.length, 'extracted claim')}</span>
        <span>{plural(detail.chunk_count, 'indexed passage')}</span>
      </p>
    </article>
  );
}
