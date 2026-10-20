import { useId, useState, type FormEvent } from 'react';

import {
  SOURCE_DECISION_REASON_CHARS,
  SOURCE_STATUS,
  type SourceDecisionKind,
  type SourceView,
} from '@/domains/workspace';
import { plainMath } from '@/shared/lib/plainMath';
import { Button } from '@/shared/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog';
import { Textarea } from '@/shared/ui/textarea';

import { DECISION_COPY } from '../model/decision';
import type { DecisionControl } from '../model/useDecisionControl';

interface DecisionFormProps {
  source: SourceView;
  kind: SourceDecisionKind;
  busy: boolean;
  onSubmit: (reason: string) => void;
}

/** Mounted only while the dialog is open, so the reason starts empty each time. */
function DecisionForm({ source, kind, busy, onSubmit }: DecisionFormProps) {
  const [reason, setReason] = useState('');
  const fieldId = useId();
  const copy = DECISION_COPY[kind];
  const agentStatus = source.decision?.agent_status ?? source.status;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(reason);
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>{copy.title}</DialogTitle>
        <DialogDescription className="reading text-base text-foreground">
          {plainMath(source.title)}
        </DialogDescription>
      </DialogHeader>
      <div className="flex flex-col gap-1 text-sm text-muted-foreground">
        <p>The agent's decision: {SOURCE_STATUS[agentStatus].label}.</p>
        <p>{copy.effect}</p>
      </div>
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor={fieldId}
          className="text-sm font-medium text-foreground"
        >
          Reason{' '}
          <span className="font-normal text-muted-foreground">(optional)</span>
        </label>
        <Textarea
          id={fieldId}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          maxLength={SOURCE_DECISION_REASON_CHARS}
          placeholder="Saved with the decision in the trajectory"
          className="reading min-h-24 text-base md:text-base"
        />
      </div>
      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline" disabled={busy}>
            Cancel
          </Button>
        </DialogClose>
        <Button type="submit" disabled={busy}>
          {busy ? 'Saving' : copy.action}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** The include/exclude confirmation with an optional reason. */
export function DecisionDialog({
  source,
  control,
}: {
  source: SourceView;
  control: DecisionControl;
}) {
  if (!control.kind) return null;
  const { kind, busy, submit } = control;
  return (
    <Dialog open={control.open} onOpenChange={control.setOpen}>
      <DialogContent className="sm:max-w-md">
        <DecisionForm
          source={source}
          kind={kind}
          busy={busy}
          onSubmit={(reason) => void submit(reason)}
        />
      </DialogContent>
    </Dialog>
  );
}
