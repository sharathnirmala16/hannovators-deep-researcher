import type { ReactNode } from 'react';

import {
  useWorkspace,
  type UiComponentId,
  type WorkspaceState,
} from '@/domains/workspace';
import { plural } from '@/shared/lib/format';
import { SectionHeader } from '@/shared/ui/section-header';
import { EmptyState, ErrorState, SkeletonBlock } from '@/shared/ui/states';

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
    'Studies per outcome, strongest design first. Click a marked value to open its sentence in the source.',
  claim_matrix:
    'Claims per outcome, strongest source first. Click a marked claim to open its sentence in the source.',
  synthesis_panel:
    'What the evidence supports, how certain it is, and where each statement comes from.',
};

function metaFor(panel: PanelId, state: WorkspaceState): string | null {
  const outcomes = state.synthesis?.pairwise_summaries.length ?? 0;
  if (panel === 'claim_matrix') {
    const claims = state.claims.filter(
      (claim) => claim.kind !== 'RECOMMENDATION',
    );
    return claims.length > 0 ? plural(claims.length, 'claim') : null;
  }
  return outcomes > 0 ? plural(outcomes, 'outcome') : null;
}

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
  const { load, reload } = useWorkspace();
  if (load.status === 'idle') {
    return (
      <div className="p-4">
        <EmptyState title="No workspace open">
          Open a workspace from the workspaces page to see its evidence.
        </EmptyState>
      </div>
    );
  }
  if (load.status === 'loading') {
    return (
      <div className="flex flex-col gap-4 p-4">
        <SkeletonBlock lines={2} label="Loading the evidence" />
        <SkeletonBlock lines={5} />
      </div>
    );
  }
  if (load.status === 'error') {
    return (
      <div className="p-4">
        <ErrorState
          title="The evidence could not be loaded"
          message={load.message}
          onRetry={reload}
        />
      </div>
    );
  }
  const panel = panelFor(view, load.state);
  const View = VIEWS[panel];
  return (
    <section
      aria-labelledby={`${panel}-title`}
      className="flex flex-col gap-4 py-4"
    >
      <div className="flex flex-col gap-0.5 px-4">
        <SectionHeader
          id={`${panel}-title`}
          title={TITLES[panel]}
          meta={metaFor(panel, load.state)}
        />
        <p className="text-xs text-muted-foreground">{HINTS[panel]}</p>
      </div>
      <View state={load.state} />
    </section>
  );
}
