import { useWorkspace, type WorkspaceLoad } from '@/domains/workspace';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/ui/card';

function describe(load: WorkspaceLoad): string {
  switch (load.status) {
    case 'idle':
      return 'none open';
    case 'loading':
      return 'loading';
    case 'error':
      return `error: ${load.message}`;
    case 'ready':
      return `${load.state.workspace.status}: ${load.state.workspace.research_question}`;
  }
}

/** Placeholder entry. Lane F1 builds the new-run form and trace timeline. */
export function WorkbenchShell() {
  const { client, load, events, eventStatus } = useWorkspace();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Workbench</CardTitle>
        <CardDescription>
          Placeholder (F1): new run, mode toggle, and trace timeline.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        <p>Data source: {client.source}</p>
        <p>Workspace: {describe(load)}</p>
        <p>
          Trace events: {events.length} ({eventStatus})
        </p>
      </CardContent>
    </Card>
  );
}
