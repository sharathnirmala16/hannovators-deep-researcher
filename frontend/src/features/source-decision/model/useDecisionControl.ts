import { useState } from 'react';
import { toast } from 'sonner';

import {
  useWorkspace,
  type SourceDecisionKind,
  type SourceView,
} from '@/domains/workspace';
import { errorMessage } from '@/shared/lib/format';

import { DECISION_COPY, nextDecision, unavailableReason } from './decision';

export interface DecisionControl {
  /** The action on offer, or null for seeds (they cannot be decided). */
  kind: SourceDecisionKind | null;
  /** Why the action is disabled, or null. */
  unavailable: string | null;
  open: boolean;
  setOpen: (open: boolean) => void;
  busy: boolean;
  submit: (reason: string) => Promise<void>;
}

/** State of one include/exclude control and its reason dialog. */
export function useDecisionControl(source: SourceView): DecisionControl {
  const { load, decideSource } = useWorkspace();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const kind = nextDecision(source);
  const status = load.status === 'ready' ? load.state.workspace.status : null;

  const submit = async (reason: string) => {
    if (!kind) return;
    setBusy(true);
    try {
      await decideSource(source.id, {
        decision: kind,
        reason: reason.trim() || null,
      });
      setOpen(false);
      toast.success(DECISION_COPY[kind].done);
    } catch (error) {
      toast.error(`The decision was not saved: ${errorMessage(error)}`);
    }
    setBusy(false);
  };

  return {
    kind,
    unavailable: unavailableReason(status),
    open,
    setOpen,
    busy,
    submit,
  };
}
