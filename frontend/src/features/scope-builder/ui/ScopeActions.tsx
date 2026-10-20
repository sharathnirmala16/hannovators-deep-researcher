import { Loader2Icon, PlayIcon } from 'lucide-react';

import { Button } from '@/shared/ui/button';

interface ScopeActionsProps {
  dirty: boolean;
  busy: 'saving' | 'continuing' | null;
  onSave: () => void;
  onContinue: () => void;
}

/** Save the edited scope, or save and continue the run (primary). */
export function ScopeActions({
  dirty,
  busy,
  onSave,
  onContinue,
}: ScopeActionsProps) {
  return (
    <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
      {dirty ? (
        <span className="mr-auto text-xs text-tone-caution">
          Unsaved changes
        </span>
      ) : null}
      <Button
        size="sm"
        variant="outline"
        onClick={onSave}
        disabled={!dirty || busy !== null}
      >
        {busy === 'saving' ? <Loader2Icon className="animate-spin" /> : null}
        {busy === 'saving' ? 'Saving' : 'Save'}
      </Button>
      <Button size="sm" onClick={onContinue} disabled={busy !== null}>
        {busy === 'continuing' ? (
          <Loader2Icon className="animate-spin" />
        ) : (
          <PlayIcon />
        )}
        Continue run
      </Button>
    </div>
  );
}
