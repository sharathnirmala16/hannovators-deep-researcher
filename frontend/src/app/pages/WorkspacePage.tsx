import { useCallback } from 'react';

import { EvidenceSelectionProvider } from '@/domains/evidence';
import { WorkspaceProvider, useWorkspace } from '@/domains/workspace';
import { RunHeader } from '@/features/run-header';
import { TrajectoryView } from '@/features/trajectory';
import { Segmented, type SegmentOption } from '@/shared/ui/segmented';
import { ErrorState, SkeletonBlock } from '@/shared/ui/states';

import { ResearchTab } from '../research/ResearchTab';
import {
  navigate,
  workspaceHref,
  type WorkspaceTab,
} from '../router/hashRoute';
import { useVisited } from '../useVisited';

const TABS: readonly SegmentOption<WorkspaceTab>[] = [
  { value: 'research', label: 'Research' },
  { value: 'trajectory', label: 'Trajectory' },
];

interface WorkspacePageProps {
  workspaceId: string;
  tab: WorkspaceTab;
  step: number | null;
}

function WorkspaceBody({ workspaceId, tab, step }: WorkspacePageProps) {
  const { load, reload, recordAction } = useWorkspace();
  const visited = useVisited(tab);

  const switchTab = (next: WorkspaceTab) => {
    if (next === tab) return;
    recordAction({
      name: 'user.tab.switch',
      summary: `Opened the ${next} tab`,
      details: { from: tab, to: next },
    });
    navigate(workspaceHref(workspaceId, next));
  };

  const openStep = useCallback(
    (stepId: number) =>
      navigate(workspaceHref(workspaceId, 'trajectory', stepId)),
    [workspaceId],
  );

  const openSource = useCallback(
    () => navigate(workspaceHref(workspaceId, 'research')),
    [workspaceId],
  );

  return (
    <>
      <RunHeader
        backHref="#/"
        tabs={
          <Segmented
            label="Workspace view"
            size="md"
            value={tab}
            options={TABS}
            onChange={switchTab}
          />
        }
      />
      {load.status === 'error' ? (
        <div className="p-8">
          <ErrorState
            title="Could not open this workspace"
            message={load.message}
            onRetry={reload}
          >
            <a href="#/" className="underline underline-offset-4">
              Back to workspaces
            </a>
          </ErrorState>
        </div>
      ) : load.status !== 'ready' ? (
        <SkeletonBlock
          lines={8}
          label="Loading the workspace"
          className="p-8"
        />
      ) : (
        <main className="relative min-h-0 flex-1">
          <div hidden={tab !== 'research'} className="absolute inset-0">
            <ResearchTab onOpenStep={openStep} />
          </div>
          {visited.has('trajectory') ? (
            <div
              hidden={tab !== 'trajectory'}
              className="absolute inset-0 flex flex-col overflow-hidden"
            >
              <TrajectoryView onOpenSource={openSource} step={step} />
            </div>
          ) : null}
        </main>
      )}
    </>
  );
}

/** `#/w/<id>`: header and the Research and Trajectory tabs. */
export function WorkspacePage(props: WorkspacePageProps) {
  const onOpenWorkspace = useCallback(
    (id: string | null) => navigate(id ? workspaceHref(id) : '#/'),
    [],
  );
  return (
    <WorkspaceProvider
      workspaceId={props.workspaceId}
      onOpenWorkspace={onOpenWorkspace}
    >
      <EvidenceSelectionProvider scope={props.workspaceId}>
        <WorkspaceBody {...props} />
      </EvidenceSelectionProvider>
    </WorkspaceProvider>
  );
}
