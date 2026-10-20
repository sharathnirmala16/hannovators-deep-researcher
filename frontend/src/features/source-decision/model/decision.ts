import type {
  SourceDecisionKind,
  SourceView,
  WorkspaceStatus,
} from '@/domains/workspace';

/** The action a source offers: include what is out, exclude what is in. */
export function nextDecision(source: SourceView): SourceDecisionKind | null {
  if (source.status === 'SEED') return null;
  return source.status === 'APPRAISE_PROMOTED' ? 'EXCLUDE' : 'INCLUDE';
}

/** Why the decision controls are disabled, or null when they work. */
export function unavailableReason(
  status: WorkspaceStatus | null,
): string | null {
  if (status === 'COMPLETED') return null;
  if (status === 'RUNNING') return 'Available when the run finishes.';
  return 'Available once the run is completed.';
}

export const DECISION_COPY: Record<
  SourceDecisionKind,
  { action: string; title: string; effect: string; done: string }
> = {
  INCLUDE: {
    action: 'Include source',
    title: 'Include this source',
    effect:
      'It joins the evidence base now. Re-synthesize to fetch its full text, appraise it, and update the synthesis.',
    done: 'Source included. Re-synthesize to update the synthesis.',
  },
  EXCLUDE: {
    action: 'Exclude source',
    title: 'Exclude this source',
    effect:
      'It leaves the evidence base now and its claims are hidden. Re-synthesize to update the synthesis.',
    done: 'Source excluded. Re-synthesize to update the synthesis.',
  },
};
