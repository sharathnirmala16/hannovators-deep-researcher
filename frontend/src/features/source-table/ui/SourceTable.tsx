import { useWorkspace } from '@/domains/workspace';
import { EmptyState, ErrorState, SkeletonBlock } from '@/shared/ui/states';

import { SourceList, type RowAction } from './SourceList';

/** Every source in the workspace: sortable, filterable; a row opens it. */
export function SourceTable({ rowAction }: { rowAction?: RowAction }) {
  const { load, reload } = useWorkspace();
  if (load.status === 'idle' || load.status === 'loading') {
    return (
      <div className="flex flex-col gap-4 p-4">
        <SkeletonBlock lines={1} label="Loading sources" />
        <SkeletonBlock lines={5} />
      </div>
    );
  }
  if (load.status === 'error') {
    return (
      <div className="p-4">
        <ErrorState
          title="The sources could not be loaded"
          message={load.message}
          onRetry={reload}
        />
      </div>
    );
  }
  if (load.state.sources.length === 0) {
    return (
      <div className="p-4">
        <EmptyState title="No sources yet">
          Sources appear here as the search stage finds them. Start the run from
          the plan pane, or add seed documents when you create a workspace.
        </EmptyState>
      </div>
    );
  }
  return <SourceList sources={load.state.sources} rowAction={rowAction} />;
}
