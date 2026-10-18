import { EvidenceSelectionProvider } from '@/domains/evidence';
import { useWorkspace } from '@/domains/workspace';
import { WorkbenchShell } from '@/features/workbench-shell';
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/shared/ui/resizable';

import { LoadNotice } from './LoadNotice';
import { Pane } from './Pane';
import { PaneEntries } from './PaneEntries';

/** 3-pane shell: run controls | evidence | source viewer and graph. */
export function WorkbenchLayout() {
  const { workspaceId, load } = useWorkspace();
  const components = load.status === 'ready' ? load.state.ui_components : [];

  return (
    <EvidenceSelectionProvider scope={workspaceId}>
      <div className="flex h-screen flex-col bg-background text-foreground">
        <header className="border-b px-4 py-2">
          <h1 className="text-sm font-semibold">Deep Research Workbench</h1>
        </header>
        <ResizablePanelGroup
          orientation="horizontal"
          className="min-h-0 flex-1"
        >
          <ResizablePanel id="run" defaultSize="25%" minSize="18%">
            <Pane label="Run">
              <WorkbenchShell />
              <PaneEntries pane="run" components={components} />
            </Pane>
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel id="evidence" defaultSize="45%" minSize="25%">
            <Pane label="Evidence">
              <LoadNotice load={load} />
              <PaneEntries pane="evidence" components={components} />
            </Pane>
          </ResizablePanel>
          <ResizableHandle withHandle />
          <ResizablePanel id="source" defaultSize="30%" minSize="20%">
            <Pane label="Source">
              <PaneEntries pane="source" components={components} />
            </Pane>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>
    </EvidenceSelectionProvider>
  );
}
