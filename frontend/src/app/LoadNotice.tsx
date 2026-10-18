import type { WorkspaceLoad } from '@/domains/workspace';

interface LoadNoticeProps {
  load: WorkspaceLoad;
}

/** Status text while no workspace data is ready. */
export function LoadNotice({ load }: LoadNoticeProps) {
  switch (load.status) {
    case 'ready':
      return null;
    case 'idle':
      return (
        <p className="text-sm text-muted-foreground">
          No workspace is open. Start a new run.
        </p>
      );
    case 'loading':
      return (
        <p role="status" className="text-sm text-muted-foreground">
          Loading the workspace...
        </p>
      );
    case 'error':
      return (
        <p role="alert" className="text-sm text-destructive">
          Could not load the workspace: {load.message}
        </p>
      );
  }
}
