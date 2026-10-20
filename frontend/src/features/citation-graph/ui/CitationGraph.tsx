import { useWorkspace } from '@/domains/workspace';
import { plural } from '@/shared/lib/format';
import { ErrorState, SkeletonBlock } from '@/shared/ui/states';

import { linkCount } from '../model/toElements';
import { GraphBody } from './GraphBody';
import { GraphFrame } from './GraphFrame';

/** Cytoscape graph of how seeds connect to included, excluded, and web sources. */
export function CitationGraph() {
  const { load, reload } = useWorkspace();
  if (load.status === 'idle' || load.status === 'loading') {
    return (
      <GraphFrame>
        <SkeletonBlock lines={4} label="Loading the citation graph" />
      </GraphFrame>
    );
  }
  if (load.status === 'error') {
    return (
      <GraphFrame>
        <ErrorState
          title="The citation graph could not be loaded"
          message={load.message}
          onRetry={reload}
        />
      </GraphFrame>
    );
  }
  const { graph } = load;
  return (
    <GraphFrame
      meta={
        graph.nodes.length > 0 ? (
          <>
            <span>{plural(graph.nodes.length, 'source')}</span>
            <span>{plural(linkCount(graph), 'link')}</span>
          </>
        ) : null
      }
    >
      <GraphBody graph={graph} />
    </GraphFrame>
  );
}
