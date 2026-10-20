import { useState } from 'react';

import type { GraphView } from '@/domains/workspace';
import { errorMessage } from '@/shared/lib/format';
import { EmptyState, ErrorState } from '@/shared/ui/states';

import { GraphCanvas } from './GraphCanvas';
import { GraphLegend } from './GraphLegend';

/** The canvas and legend, or why there is nothing to draw. */
export function GraphBody({ graph }: { graph: GraphView }) {
  const [failure, setFailure] = useState<{ error: unknown } | null>(null);
  if (graph.nodes.length === 0) {
    return (
      <EmptyState title="No sources to draw yet">
        The graph fills in as the search stage finds sources and links them to
        the seeds. Start the run from the plan pane.
      </EmptyState>
    );
  }
  if (failure) {
    return (
      <ErrorState
        title="The graph could not be drawn"
        message={errorMessage(failure.error)}
        onRetry={() => setFailure(null)}
      />
    );
  }
  return (
    <>
      <p className="text-xs text-muted-foreground">
        Select a node to open the source. Seeds sit at the center, included
        studies next, excluded sources on the outer ring.
      </p>
      <GraphCanvas graph={graph} onError={(error) => setFailure({ error })} />
      <GraphLegend />
    </>
  );
}
