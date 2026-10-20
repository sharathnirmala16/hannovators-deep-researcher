import { useState } from 'react';

import type { GraphView } from '@/domains/workspace';
import { EmptyState, ErrorState } from '@/shared/ui/states';

import { canDrawCanvas } from '../model/environment';
import { GraphCanvas } from './GraphCanvas';
import { GraphLegend } from './GraphLegend';

/** The canvas and legend, or why there is nothing to draw. */
export function GraphBody({ graph }: { graph: GraphView }) {
  const [drawable, setDrawable] = useState(canDrawCanvas);
  if (graph.nodes.length === 0) {
    return (
      <EmptyState title="No sources to draw yet">
        The graph fills in as the search stage finds sources and links them to
        the seeds. Start the run from the plan pane.
      </EmptyState>
    );
  }
  if (!drawable) {
    return (
      <ErrorState
        title="The graph could not be drawn"
        message="This browser could not start a 2D canvas."
        onRetry={() => setDrawable(canDrawCanvas())}
      />
    );
  }
  return (
    <>
      <p className="text-xs text-muted-foreground">
        Each ring holds one evidence tier around the seeds. Point at a source to
        trace its links, and select it to open the document.
      </p>
      <GraphCanvas graph={graph} />
      <GraphLegend />
    </>
  );
}
