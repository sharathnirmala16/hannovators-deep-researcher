import { useState } from 'react';
import { toast } from 'sonner';

import { useWorkspaceClient } from '@/domains/workspace';
import { errorMessage } from '@/shared/lib/format';

export interface DeleteWorkspaceControl {
  open: boolean;
  setOpen: (open: boolean) => void;
  busy: boolean;
  confirm: () => Promise<void>;
}

/** State of one delete action: the confirm dialog and the API call. */
export function useDeleteWorkspace(
  workspaceId: string,
  onDeleted: () => void,
): DeleteWorkspaceControl {
  const client = useWorkspaceClient();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const confirm = async () => {
    setBusy(true);
    try {
      await client.deleteWorkspace(workspaceId);
      setBusy(false);
      setOpen(false);
      toast.success('Workspace deleted.');
      onDeleted();
    } catch (error) {
      setBusy(false);
      toast.error(`The workspace was not deleted: ${errorMessage(error)}`);
    }
  };

  // The dialog stays open while the request runs.
  const changeOpen = (next: boolean) => {
    if (!busy) setOpen(next);
  };

  return { open, setOpen: changeOpen, busy, confirm };
}
