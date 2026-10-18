import type { UiComponentId } from '@/domains/workspace';
import { Card, CardDescription, CardHeader, CardTitle } from '@/shared/ui/card';

export type EvidenceTableView = Extract<
  UiComponentId,
  'evidence_profile_table' | 'claim_matrix' | 'synthesis_panel'
>;

const TITLES: Record<EvidenceTableView, string> = {
  evidence_profile_table: 'GRADE evidence profile',
  claim_matrix: 'Claim matrix',
  synthesis_panel: 'Synthesis',
};

interface EvidenceTableProps {
  view: EvidenceTableView;
}

/** Placeholder entry. Lane F4 builds the three evidence views. */
export function EvidenceTable({ view }: EvidenceTableProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{TITLES[view]}</CardTitle>
        <CardDescription>Placeholder (F4): {view}.</CardDescription>
      </CardHeader>
    </Card>
  );
}
