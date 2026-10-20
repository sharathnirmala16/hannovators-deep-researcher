import type { WorkspaceState } from '@/domains/workspace';
import { plural } from '@/shared/lib/format';
import { SectionHeader } from '@/shared/ui/section-header';
import { EmptyState } from '@/shared/ui/states';

import { AnalysisProse } from './AnalysisProse';
import { citationIndex } from './citations';
import { PairwiseSummary } from './PairwiseSummary';
import { Provenance } from './Provenance';
import { RecommendationLead } from './RecommendationLead';

/** The one intervention the recommendation is about (MEDICAL only). */
function subjectOf(state: WorkspaceState): string | null {
  const { decomposition, synthesis } = state;
  if (decomposition?.mode !== 'MEDICAL' || !synthesis) return null;
  const compared = new Set(
    synthesis.pairwise_summaries.map((summary) => summary.intervention),
  );
  if (compared.size === 1) return [...compared][0] ?? null;
  return decomposition.interventions.length === 1
    ? (decomposition.interventions[0] ?? null)
    : null;
}

/** Recommendation first, then the analysis, the comparisons, provenance. */
export function SynthesisPanel({ state }: { state: WorkspaceState }) {
  const { synthesis } = state;
  if (!synthesis) {
    return (
      <EmptyState className="mx-4" title="No synthesis yet">
        The recommendation and its GRADE assessment are written in the synthesis
        stage. Run or continue the workspace from the plan pane.
      </EmptyState>
    );
  }
  const citations = citationIndex(state);
  const summaries = synthesis.pairwise_summaries;
  return (
    <article className="flex flex-col gap-6 px-4">
      <RecommendationLead
        recommendation={synthesis.recommendation}
        subject={subjectOf(state)}
        citations={citations}
      />
      <section
        aria-labelledby="synthesis-analysis"
        className="flex flex-col gap-2"
      >
        <SectionHeader id="synthesis-analysis" title="Analysis" />
        <AnalysisProse text={synthesis.analysis} citations={citations} />
      </section>
      {summaries.length > 0 ? (
        <section
          aria-labelledby="synthesis-comparisons"
          className="flex flex-col gap-4"
        >
          <SectionHeader
            id="synthesis-comparisons"
            title="Comparisons"
            meta={plural(summaries.length, 'outcome')}
          />
          <div className="flex flex-col gap-8">
            {summaries.map((summary) => (
              <PairwiseSummary
                key={`${summary.intervention}|${summary.comparison}|${summary.outcome}`}
                summary={summary}
                citations={citations}
              />
            ))}
          </div>
        </section>
      ) : null}
      <Provenance provenance={synthesis.provenance} />
    </article>
  );
}
