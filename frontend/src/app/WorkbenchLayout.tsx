import { EvidenceSelectionProvider } from '@/domains/evidence';
import { useWorkspace } from '@/domains/workspace';
import { ResearchChat } from '@/features/research-chat';
import { TrajectoryView } from '@/features/trajectory';
import { WorkbenchShell } from '@/features/workbench-shell';
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/shared/ui/resizable';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/ui/tabs';

import { LoadNotice } from './LoadNotice';
import { Pane } from './Pane';
import { PaneEntries } from './PaneEntries';

/**
 * Workspace view: a Research tab (3 panes) and a Trajectory tab (audit log).
 * Lane `ui-shell` redesigns this; lane `ui-trajectory-chat` fills the
 * trajectory and chat features (PLAN.md section 7.9).
 */
export function WorkbenchLayout() {
  const { workspaceId, load } = useWorkspace();
  const components = load.status === 'ready' ? load.state.ui_components : [];

  return (
    <EvidenceSelectionProvider scope={workspaceId}>
      <Tabs
        defaultValue="research"
        className="flex h-screen flex-col gap-0 bg-background text-foreground"
      >
        <header className="flex items-center gap-4 border-b px-4 py-2">
          <h1 className="text-sm font-semibold">Deep Research Workbench</h1>
          <TabsList>
            <TabsTrigger value="research">Research</TabsTrigger>
            <TabsTrigger value="trajectory">Trajectory</TabsTrigger>
          </TabsList>
        </header>
        <TabsContent value="research" className="min-h-0 flex-1">
          <ResizablePanelGroup orientation="horizontal" className="h-full">
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
                <ResearchChat />
              </Pane>
            </ResizablePanel>
            <ResizableHandle withHandle />
            <ResizablePanel id="source" defaultSize="30%" minSize="20%">
              <Pane label="Source">
                <PaneEntries pane="source" components={components} />
              </Pane>
            </ResizablePanel>
          </ResizablePanelGroup>
        </TabsContent>
        <TabsContent value="trajectory" className="min-h-0 flex-1">
          <TrajectoryView />
        </TabsContent>
      </Tabs>
    </EvidenceSelectionProvider>
  );
}
