import type {
  RecommendationDirection,
  RecommendationStrength,
  WorkspaceState,
} from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';

import { studyLabel } from '@/domains/workspace';

import { indexById } from '../model/evidence';
import { CertaintyBadge } from './CertaintyBadge';
import { ClaimCell } from './ClaimCell';

const DIRECTION: Record<RecommendationDirection, string> = {
  FOR: 'For',
  AGAINST: 'Against',
  NONE: 'No direction',
};

const STRENGTH: Record<RecommendationStrength, string> = {
  STRONG: 'Strong',
  CONDITIONAL: 'Conditional',
};

const DIRECTION_TONE: Record<RecommendationDirection, string> = {
  FOR: 'border-emerald-800 bg-emerald-800 text-white',
  AGAINST: 'border-rose-800 bg-rose-800 text-white',
  NONE: 'border-foreground/40 bg-background text-foreground',
};

/** Pairwise summaries, then the analysis, then the recommendation. */
export function SynthesisPanel({ state }: { state: WorkspaceState }) {
  const { synthesis } = state;
  if (!synthesis) {
    return (
      <p className="text-sm text-muted-foreground">
        The synthesis appears after the synthesis stage.
      </p>
    );
  }
  const sources = indexById(state.sources);
  const recommendationClaim = state.claims.find(
    (claim) => claim.kind === 'RECOMMENDATION',
  );
  const { recommendation, provenance } = synthesis;
  return (
    <article className="flex flex-col gap-4 rounded-lg border bg-card p-4 text-sm">
      <ol className="flex flex-col gap-3">
        {synthesis.pairwise_summaries.map((summary) => (
          <li
            key={`${summary.intervention}|${summary.outcome}`}
            className="border-l-2 border-foreground/20 pl-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">
                {summary.intervention} vs {summary.comparison}
              </span>
              <CertaintyBadge certainty={summary.grade.certainty} />
            </div>
            <p className="text-xs text-muted-foreground">{summary.outcome}</p>
            <p className="mt-1">{summary.summary}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {summary.source_ids
                .map((id) => sources.get(id))
                .filter((source) => source !== undefined)
                .map(studyLabel)
                .join(', ')}
            </p>
          </li>
        ))}
      </ol>
      <section>
        <h3 className="mb-1 font-semibold">Analysis</h3>
        <p className="leading-relaxed">{synthesis.analysis}</p>
      </section>
      <section className="rounded-md border border-foreground/15 bg-muted/40 p-3">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <h3 className="font-semibold">Recommendation</h3>
          <span
            className={cn(
              'rounded-md border px-2 py-0.5 text-xs font-semibold',
              DIRECTION_TONE[recommendation.direction],
            )}
          >
            {STRENGTH[recommendation.strength]}{' '}
            {DIRECTION[recommendation.direction].toLowerCase()}
          </span>
        </div>
        {recommendationClaim ? (
          <ClaimCell
            claim={recommendationClaim}
            highlights={state.highlights}
            className="leading-relaxed"
          >
            {recommendation.text}
          </ClaimCell>
        ) : (
          <p className="leading-relaxed">{recommendation.text}</p>
        )}
      </section>
      <footer className="flex flex-wrap gap-x-4 gap-y-1 border-t pt-3 text-xs text-muted-foreground">
        <span>
          Canary <code className="text-foreground">{provenance.canary}</code>
        </span>
        {Object.entries(provenance.models).map(([role, model]) => (
          <span key={role}>
            {role.toLowerCase()}{' '}
            <code className="text-foreground">{model}</code>
          </span>
        ))}
        <span>
          Generated {new Date(provenance.generated_at).toLocaleString()}
        </span>
      </footer>
    </article>
  );
}
