import { Trash2Icon } from 'lucide-react';
import type { SyntheticEvent } from 'react';

import type { WorkspaceStatus } from '@/domains/workspace';
import { plainMath } from '@/shared/lib/plainMath';
import { Button } from '@/shared/ui/button';

import { useDeleteWorkspace } from '../model/useDeleteWorkspace';
import { DeleteWorkspaceDialog } from './DeleteWorkspaceDialog';

const RUNNING_HINT = 'Stop or wait for the run to finish first.';

const stop = (event: SyntheticEvent) => event.stopPropagation();

interface DeleteWorkspaceButtonProps {
  workspaceId: string;
  question: string;
  status: WorkspaceStatus;
  /** Called after the API deleted the workspace (refresh or navigate away). */
  onDeleted: () => void;
  /** `row`: a list row action; `header`: the workspace header. */
  variant?: 'row' | 'header';
}

/** A trash icon button that confirms, then deletes the workspace. */
export function DeleteWorkspaceButton({
  workspaceId,
  question,
  status,
  onDeleted,
  variant = 'row',
}: DeleteWorkspaceButtonProps) {
  const control = useDeleteWorkspace(workspaceId, onDeleted);
  const running = status === 'RUNNING';
  const label = `Delete ${plainMath(question)}`;
  return (
    // A row may be a link or open something on click; the button must not.
    <span
      onClick={stop}
      onKeyDown={stop}
      className="inline-flex"
      title={running ? RUNNING_HINT : undefined}
    >
      <Button
        size={variant === 'row' ? 'icon-xs' : 'icon-sm'}
        variant="ghost"
        aria-label={label}
        title={running ? undefined : 'Delete workspace'}
        disabled={running}
        onClick={() => control.setOpen(true)}
        className="hover:text-destructive"
      >
        <Trash2Icon className={variant === 'row' ? 'size-3.5' : undefined} />
      </Button>
      <DeleteWorkspaceDialog question={question} control={control} />
    </span>
  );
}
