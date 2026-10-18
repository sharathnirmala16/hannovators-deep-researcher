import { useMemo, useState, type ReactNode } from 'react';

import {
  EvidenceSelectionContext,
  type EvidenceSelectionValue,
} from './evidenceSelectionContext';
import {
  NO_SELECTION,
  citationSelection,
  claimSelection,
  highlightSelection,
  sourceSelection,
  type EvidenceSelection,
} from './selection';

interface ScopedSelection {
  scope: string | null;
  selection: EvidenceSelection;
}

interface EvidenceSelectionProviderProps {
  /** The selection resets when the scope (the open workspace) changes. */
  scope: string | null;
  children: ReactNode;
}

export function EvidenceSelectionProvider({
  scope,
  children,
}: EvidenceSelectionProviderProps) {
  const [current, setCurrent] = useState<ScopedSelection>({
    scope,
    selection: NO_SELECTION,
  });

  const value = useMemo<EvidenceSelectionValue>(() => {
    const select = (selection: EvidenceSelection) =>
      setCurrent({ scope, selection });
    return {
      selection: current.scope === scope ? current.selection : NO_SELECTION,
      selectClaim: (claim, highlights) =>
        select(claimSelection(claim, highlights)),
      selectHighlight: (highlight) => select(highlightSelection(highlight)),
      selectCitation: (messageId, citation) =>
        select(citationSelection(messageId, citation)),
      selectSource: (sourceId, page = null) =>
        select(sourceSelection(sourceId, page)),
      clearSelection: () => select(NO_SELECTION),
    };
  }, [scope, current]);

  return (
    <EvidenceSelectionContext.Provider value={value}>
      {children}
    </EvidenceSelectionContext.Provider>
  );
}
