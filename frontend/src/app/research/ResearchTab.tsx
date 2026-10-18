import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/shared/ui/resizable';

import { EvidencePane } from './EvidencePane';
import { PlanPane } from './PlanPane';
import { SourcePane } from './SourcePane';

interface ResearchTabProps {
  /** Open a trajectory step in the Trajectory tab. */
  onOpenStep: (stepId: number) => void;
}

/** Plan and progress | Evidence | Source, in three resizable panes. */
export function ResearchTab({ onOpenStep }: ResearchTabProps) {
  return (
    <ResizablePanelGroup orientation="horizontal" className="h-full">
      <ResizablePanel id="plan" defaultSize="24%" minSize="16%">
        <PlanPane />
      </ResizablePanel>
      <ResizableHandle />
      <ResizablePanel id="evidence" defaultSize="42%" minSize="28%">
        <EvidencePane />
      </ResizablePanel>
      <ResizableHandle />
      <ResizablePanel id="source" defaultSize="34%" minSize="22%">
        <SourcePane onOpenStep={onOpenStep} />
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
