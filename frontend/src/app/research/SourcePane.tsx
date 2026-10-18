import { CitationGraph } from '@/features/citation-graph';
import { PdfViewer } from '@/features/pdf-viewer';
import { SourceDetails } from '@/features/source-details';
import { Pane, PaneBody } from '@/shared/ui/pane';
import { SectionHeader } from '@/shared/ui/section-header';
import { Segmented, type SegmentOption } from '@/shared/ui/segmented';

import { useVisited } from '../useVisited';
import { useSourceTab, type SourceTab } from './useSourceTab';

const OPTIONS: readonly SegmentOption<SourceTab>[] = [
  { value: 'document', label: 'Document' },
  { value: 'graph', label: 'Graph' },
  { value: 'details', label: 'Details' },
];

interface SourcePaneProps {
  onOpenStep: (stepId: number) => void;
}

/** Right pane: the selected source as a document, in the graph, or audited. */
export function SourcePane({ onOpenStep }: SourcePaneProps) {
  const [tab, setTab] = useSourceTab();
  const visited = useVisited(tab);
  return (
    <Pane aria-labelledby="source-pane-title">
      <SectionHeader
        variant="pane"
        id="source-pane-title"
        title="Source"
        actions={
          <Segmented
            label="Source view"
            value={tab}
            options={OPTIONS}
            onChange={setTab}
          />
        }
      />
      <PaneBody scroll={false} hidden={tab !== 'document'}>
        <PdfViewer />
      </PaneBody>
      {/* The graph mounts only while visible: cytoscape needs a sized box. */}
      {tab === 'graph' ? (
        <PaneBody scroll={false}>
          <CitationGraph />
        </PaneBody>
      ) : null}
      {visited.has('details') ? (
        <PaneBody hidden={tab !== 'details'}>
          <SourceDetails onOpenStep={onOpenStep} />
        </PaneBody>
      ) : null}
    </Pane>
  );
}
