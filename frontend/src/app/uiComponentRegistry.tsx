import type { ReactNode } from 'react';

import type { UiComponentId } from '@/domains/workspace';
import { CitationGraph } from '@/features/citation-graph';
import { EvidenceTable } from '@/features/evidence-table';
import { PdfViewer } from '@/features/pdf-viewer';
import { ScopeBuilder } from '@/features/scope-builder';
import { ScreeningFunnel } from '@/features/screening-funnel';

export type PaneId = 'run' | 'evidence' | 'source';

interface RegistryEntry {
  pane: PaneId;
  render: () => ReactNode;
}

/**
 * Maps each backend `UiComponentId` to a feature entry and a pane. Feature
 * lanes change only their own entry component, never this file.
 */
export const uiComponentRegistry: Record<UiComponentId, RegistryEntry> = {
  scope_builder: { pane: 'run', render: () => <ScopeBuilder /> },
  screening_funnel: { pane: 'evidence', render: () => <ScreeningFunnel /> },
  evidence_profile_table: {
    pane: 'evidence',
    render: () => <EvidenceTable view="evidence_profile_table" />,
  },
  claim_matrix: {
    pane: 'evidence',
    render: () => <EvidenceTable view="claim_matrix" />,
  },
  synthesis_panel: {
    pane: 'evidence',
    render: () => <EvidenceTable view="synthesis_panel" />,
  },
  pdf_viewer: { pane: 'source', render: () => <PdfViewer /> },
  citation_graph: { pane: 'source', render: () => <CitationGraph /> },
};
