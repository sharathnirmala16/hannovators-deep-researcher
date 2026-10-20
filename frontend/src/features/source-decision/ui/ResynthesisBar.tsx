import { RefreshCwIcon } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { pendingDecisions, useWorkspace } from '@/domains/workspace';
import { errorMessage, plural } from '@/shared/lib/format';
import { Button } from '@/shared/ui/button';
import { ToneDot } from '@/shared/ui/tag';

/**
 * Shown while source decisions wait for a re-synthesis: how many, and the
 * action that applies them. While it runs, it says so.
 */
export function ResynthesisBar() {
  const { load, resynthesize } = useWorkspace();
  const [busy, setBusy] = useState(false);
  if (load.status !== 'ready') return null;
  const pending = pendingDecisions(load.state.sources).length;
  if (pending === 0) return null;
  const running = load.state.workspace.status === 'RUNNING';

  const start = () => {
    setBusy(true);
    resynthesize().then(
      () => setBusy(false),
      (error: unknown) => {
        setBusy(false);
        toast.error(`Re-synthesis did not start: ${errorMessage(error)}`);
      },
    );
  };

  return (
    <div
      role="status"
      className="flex shrink-0 items-center gap-3 border-b border-border bg-desk px-4 py-2 text-sm"
    >
      <ToneDot tone={running ? 'info' : 'caution'} live={running} />
      <p className="min-w-0 flex-1 text-foreground">
        {running
          ? `Re-synthesizing with ${plural(pending, 'decision')} of yours.`
          : `${plural(pending, 'decision')} of yours ${pending === 1 ? 'is' : 'are'} not in the synthesis yet.`}
      </p>
      {running ? null : (
        <Button size="xs" onClick={start} disabled={busy}>
          <RefreshCwIcon />
          Re-synthesize
        </Button>
      )}
    </div>
  );
}
