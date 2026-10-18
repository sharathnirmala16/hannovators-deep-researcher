import type { ReactNode } from 'react';

import {
  useWorkspace,
  type UiComponentId,
  type WorkspaceState,
} from '@/domains/workspace';

import { ClaimMatrix } from './ClaimMatrix';
import { EvidenceProfile } from './EvidenceProfile';
import { SynthesisPanel } from './SynthesisPanel';

type PanelId = Extract<
  UiComponentId,
  'evidence_profile_table' | 'claim_matrix' | 'synthesis_panel'
>;

/** `evidence` shows the GRADE profile (MEDICAL) or the claim matrix (GENERAL). */
export type EvidenceTableView = 'evidence' | 'synthesis';

function panelFor(view: EvidenceTableView, state: WorkspaceState): PanelId {
  if (view === 'synthesis') return 'synthesis_panel';
  return state.decomposition?.mode === 'GENERAL'
    ? 'claim_matrix'
    : 'evidence_profile_table';
}

const TITLES: Record<PanelId, string> = {
  evidence_profile_table: 'GRADE evidence profile',
  claim_matrix: 'Claim matrix',
  synthesis_panel: 'Synthesis',
};

const HINTS: Record<PanelId, string> = {
  evidence_profile_table:
    'Click a number to open the highlighted sentence in its source.',
  claim_matrix: 'Click a claim to open the highlighted sentence in its source.',
  synthesis_panel: 'How the evidence adds up, and what to do about it.',
};

const VIEWS: Record<PanelId, (props: { state: WorkspaceState }) => ReactNode> =
  {
    evidence_profile_table: EvidenceProfile,
    claim_matrix: ClaimMatrix,
    synthesis_panel: SynthesisPanel,
  };

interface EvidenceTableProps {
  view: EvidenceTableView;
}

/** Evidence views: GRADE profile, claim matrix, or synthesis panel. */
export function EvidenceTable({ view }: EvidenceTableProps) {
  const { load } = useWorkspace();
  if (load.status !== 'ready') return null;
  const panel = panelFor(view, load.state);
  const View = VIEWS[panel];
  return (
    <section aria-labelledby={`${panel}-title`} className="flex flex-col gap-2">
      <header>
        <h2 id={`${panel}-title`} className="text-base font-semibold">
          {TITLES[panel]}
        </h2>
        <p className="text-xs text-muted-foreground">{HINTS[panel]}</p>
      </header>
      <View state={load.state} />
    </section>
  );
}
