import { useWorkspace } from '@/domains/workspace';
import { DeepResearch } from '@/features/deep-research';
import { ScopeBuilder } from '@/features/scope-builder';
import { ScreeningFunnel } from '@/features/screening-funnel';
import { RunTimeline } from '@/features/workbench-shell';
import { plural } from '@/shared/lib/format';
import { Pane, PaneBody } from '@/shared/ui/pane';
import { SectionHeader } from '@/shared/ui/section-header';
import { ErrorState } from '@/shared/ui/states';

/** Left pane: scope, run timeline, screening funnel, deep research. */
export function PlanPane() {
  const { load, reload } = useWorkspace();
  const queries = load.status === 'ready' ? load.state.queries.length : 0;
  return (
    <Pane aria-labelledby="plan-pane-title">
      <SectionHeader
        variant="pane"
        id="plan-pane-title"
        title="Plan and progress"
        meta={
          queries > 0 ? (
            <span>{plural(queries, 'query', 'queries')}</span>
          ) : null
        }
      />
      <PaneBody className="p-4">
        {load.status === 'error' ? (
          <ErrorState
            title="Could not load the workspace"
            message={load.message}
            onRetry={reload}
          />
        ) : (
          <div className="flex min-w-0 flex-col gap-6">
            <ScopeBuilder />
            <RunTimeline />
            <ScreeningFunnel />
            <DeepResearch />
          </div>
        )}
      </PaneBody>
    </Pane>
  );
}
