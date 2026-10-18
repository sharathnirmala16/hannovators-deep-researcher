import { useState } from 'react';
import { toast } from 'sonner';

import {
  isUnavailable,
  useWorkspace,
  type Decomposition,
} from '@/domains/workspace';
import { errorMessage } from '@/shared/lib/format';

interface Draft {
  base: Decomposition | null;
  value: Decomposition;
}

type Busy = 'saving' | 'continuing' | null;

function failure(what: string, error: unknown): string {
  if (isUnavailable(error))
    return `${what} is not available on this server yet.`;
  return `${what} failed: ${errorMessage(error)}`;
}

/**
 * Scope draft over the server decomposition. Edits are allowed only while the
 * run waits at the review checkpoint; a new server value replaces the draft.
 */
export function useScopeBuilder() {
  const { client, workspaceId, load, reload, startRun } = useWorkspace();
  const state = load.status === 'ready' ? load.state : null;
  const base = state?.decomposition ?? null;
  const editable = state?.workspace.status === 'AWAITING_REVIEW';
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState<Busy>(null);

  const value = draft && draft.base === base ? draft.value : base;
  const dirty = value !== base;

  const change = (next: Decomposition) => setDraft({ base, value: next });

  const save = async (): Promise<boolean> => {
    if (!workspaceId || !value || !dirty) return true;
    try {
      await client.updateDecomposition(workspaceId, value);
      reload();
      return true;
    } catch (error) {
      toast.error(failure('Saving the scope', error));
      return false;
    }
  };

  const onSave = async () => {
    setBusy('saving');
    if (await save()) toast.success('Scope saved.');
    setBusy(null);
  };

  const onContinue = async () => {
    setBusy('continuing');
    try {
      if (await save()) await startRun();
    } catch (error) {
      toast.error(failure('Continuing the run', error));
    }
    setBusy(null);
  };

  return {
    value,
    editable,
    dirty,
    busy,
    change,
    onSave,
    onContinue,
  };
}
