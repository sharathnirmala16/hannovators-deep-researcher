import { useState } from 'react';

import { useWorkspace } from '@/domains/workspace';
import { EvidenceTable } from '@/features/evidence-table';
import { ResearchChat } from '@/features/research-chat';
import { SourceTable } from '@/features/source-table';
import { Pane, PaneBody } from '@/shared/ui/pane';
import { SectionHeader } from '@/shared/ui/section-header';
import { Segmented, type SegmentOption } from '@/shared/ui/segmented';

import { useVisited } from '../useVisited';

type EvidenceView = 'evidence' | 'synthesis' | 'sources' | 'chat';

/** Center pane: evidence, synthesis, sources, and the cited chat. */
export function EvidencePane() {
  const { load } = useWorkspace();
  const [view, setView] = useState<EvidenceView>('evidence');
  const visited = useVisited(view);
  const sources = load.status === 'ready' ? load.state.sources.length : 0;
  const options: readonly SegmentOption<EvidenceView>[] = [
    { value: 'evidence', label: 'Evidence' },
    { value: 'synthesis', label: 'Synthesis' },
    { value: 'sources', label: 'Sources', count: sources },
    { value: 'chat', label: 'Chat' },
  ];

  return (
    <Pane aria-labelledby="evidence-pane-title">
      <SectionHeader
        variant="pane"
        id="evidence-pane-title"
        title="Evidence"
        actions={
          <Segmented
            label="Evidence view"
            value={view}
            options={options}
            onChange={setView}
          />
        }
      />
      <PaneBody hidden={view !== 'evidence'}>
        <EvidenceTable view="evidence" />
      </PaneBody>
      {visited.has('synthesis') ? (
        <PaneBody hidden={view !== 'synthesis'}>
          <EvidenceTable view="synthesis" />
        </PaneBody>
      ) : null}
      {visited.has('sources') ? (
        <PaneBody hidden={view !== 'sources'}>
          <SourceTable />
        </PaneBody>
      ) : null}
      {visited.has('chat') ? (
        <PaneBody scroll={false} hidden={view !== 'chat'}>
          <ResearchChat />
        </PaneBody>
      ) : null}
    </Pane>
  );
}
