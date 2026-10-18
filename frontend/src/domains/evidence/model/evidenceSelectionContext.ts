import { createContext, useContext } from 'react';

import type {
  EvidenceSelection,
  SelectableCitation,
  SelectableClaim,
  SelectableHighlight,
} from './selection';

export interface EvidenceSelectionValue {
  selection: EvidenceSelection;
  selectClaim: (
    claim: SelectableClaim,
    highlights: readonly SelectableHighlight[],
  ) => void;
  selectHighlight: (highlight: SelectableHighlight) => void;
  /** Open a chat citation `[n]` at its page with its rectangles drawn. */
  selectCitation: (messageId: string, citation: SelectableCitation) => void;
  selectSource: (sourceId: string, page?: number | null) => void;
  clearSelection: () => void;
}

export const EvidenceSelectionContext =
  createContext<EvidenceSelectionValue | null>(null);

export function useEvidenceSelection(): EvidenceSelectionValue {
  const value = useContext(EvidenceSelectionContext);
  if (!value) {
    throw new Error(
      'useEvidenceSelection must be used inside an EvidenceSelectionProvider.',
    );
  }
  return value;
}
