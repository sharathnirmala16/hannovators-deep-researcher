import { useEffect, useState } from 'react';

import {
  useEvidenceSelection,
  type EvidenceSelection,
} from '@/domains/evidence';
import { useWorkspace } from '@/domains/workspace';

export type SourceTab = 'document' | 'graph' | 'details';

const OPENS_DOCUMENT: ReadonlySet<EvidenceSelection['kind']> = new Set([
  'claim',
  'highlight',
  'citation',
]);

/**
 * The right pane's view. Selecting a claim, highlight, or chat citation
 * (from any feature) switches it to Document. A citation selection is also
 * recorded as `user.citation.open`, in one place for every citation button.
 */
export function useSourceTab() {
  const { selection } = useEvidenceSelection();
  const { recordAction } = useWorkspace();
  const [tab, setTab] = useState<SourceTab>('document');
  const [seen, setSeen] = useState(selection);

  if (seen !== selection) {
    setSeen(selection);
    if (OPENS_DOCUMENT.has(selection.kind)) setTab('document');
  }

  useEffect(() => {
    if (selection.kind !== 'citation') return;
    recordAction({
      name: 'user.citation.open',
      summary: `Opened citation [${selection.n}]`,
      target: selection.sourceId,
      source_ids: [selection.sourceId],
      details: {
        message_id: selection.messageId,
        n: selection.n,
        page: selection.page,
      },
    });
  }, [selection, recordAction]);

  return [tab, setTab] as const;
}
