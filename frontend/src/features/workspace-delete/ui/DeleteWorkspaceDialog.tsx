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

import type { DeleteWorkspaceControl } from '../model/useDeleteWorkspace';

/** Confirms the deletion; names the question and what goes with it. */
export function DeleteWorkspaceDialog({
  question,
  control,
}: {
  question: string;
  control: DeleteWorkspaceControl;
}) {
  const { open, setOpen, busy, confirm } = control;
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-md" showCloseButton={!busy}>
        <DialogHeader>
          <DialogTitle>Delete this workspace?</DialogTitle>
          <p className="reading line-clamp-4 text-base text-foreground">
            {plainMath(question)}
          </p>
          <DialogDescription>
            This removes its sources, files, chat, and audit trail. You cannot
            undo this.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline" disabled={busy}>
              Cancel
            </Button>
          </DialogClose>
          <Button
            type="button"
            variant="destructive"
            disabled={busy}
            onClick={() => void confirm()}
          >
            {busy ? 'Deleting' : 'Delete workspace'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
