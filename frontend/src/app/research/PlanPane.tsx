import { useWorkspace } from '@/domains/workspace';
import { DeepResearch } from '@/features/deep-research';
import { ScopeBuilder } from '@/features/scope-builder';
import { ScreeningFunnel } from '@/features/screening-funnel';
import { RunTimeline } from '@/features/workbench-shell';
import { Pane, PaneBody } from '@/shared/ui/pane';
import { SectionHeader } from '@/shared/ui/section-header';

/** Left pane: scope, run timeline, screening funnel, deep research. */
export function PlanPane() {
  const { load } = useWorkspace();
  const queries = load.status === 'ready' ? load.state.queries.length : 0;
  return (
    <Pane aria-labelledby="plan-pane-title" className="bg-desk">
      <SectionHeader
        variant="pane"
        id="plan-pane-title"
        title="Plan and progress"
        meta={queries > 0 ? <span>{queries} queries</span> : null}
      />
      <PaneBody>
        <div className="flex flex-col gap-8 px-4 py-4">
          <ScopeBuilder />
          <RunTimeline />
          <ScreeningFunnel />
          <DeepResearch />
        </div>
      </PaneBody>
    </Pane>
  );
}
