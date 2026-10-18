import type { ReactNode } from 'react';

import type { TrajectoryStep } from '@/domains/workspace';

import type { StepDetail } from '../model/useStepDetail';
import { BodySkeleton } from './BodySkeleton';
import { CopyJsonButton } from './CopyJsonButton';
import { DecisionAnswers } from './DecisionAnswers';
import { JsonView } from './JsonView';
import { LlmPromptView } from './LlmPromptView';
import { LlmReplyView } from './LlmReplyView';
import { Notice } from './Notice';
import { SearchResults } from './SearchResults';
import { SectionTitle } from './SectionTitle';
import { VerdictSummary } from './VerdictSummary';

type Part = 'request' | 'response';

interface BodyTabProps {
  part: Part;
  detail: StepDetail;
}

/** The kind-specific reading of a body, shown above the raw JSON. */
function specialized(step: TrajectoryStep, part: Part): ReactNode {
  const { kind, request, response } = step;
  if (part === 'request') {
    return kind === 'LLM' ? <LlmPromptView request={request} /> : null;
  }
  switch (kind) {
    case 'DECISION':
      return <DecisionAnswers request={request} response={response} />;
    case 'SEARCH':
      return <SearchResults request={request} response={response} />;
    case 'VERDICT':
      return <VerdictSummary step={step} />;
    case 'LLM':
      return <LlmReplyView response={response} />;
    default:
      return null;
  }
}

export function BodyTab({ part, detail }: BodyTabProps) {
  if (detail.phase === 'idle' || detail.phase === 'loading') {
    return <BodySkeleton />;
  }
  if (detail.phase !== 'ready') {
    const title =
      detail.phase === 'unavailable'
        ? 'Step bodies are not available yet'
        : 'The step bodies could not be loaded';
    return (
      <Notice
        title={title}
        tone={detail.phase === 'error' ? 'error' : 'neutral'}
      >
        {detail.message}
      </Notice>
    );
  }
  const body = detail.step[part];
  const empty = Object.keys(body).length === 0;
  return (
    <div className="flex flex-col gap-4">
      {specialized(detail.step, part)}
      <section className="flex flex-col gap-2">
        <SectionTitle
          title={part === 'request' ? 'Request JSON' : 'Response JSON'}
          actions={empty ? null : <CopyJsonButton value={body} />}
        />
        {empty ? (
          <p className="text-xs text-muted-foreground">
            No {part} body was recorded for this step.
          </p>
        ) : (
          <JsonView value={body} />
        )}
      </section>
    </div>
  );
}
