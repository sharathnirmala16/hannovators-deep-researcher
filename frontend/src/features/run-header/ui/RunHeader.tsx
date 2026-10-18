import { ArrowLeftIcon, PlayIcon } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { toast } from 'sonner';

import {
  DOMAIN_MODE,
  WORKSPACE_STATUS,
  stageStates,
  useWorkspace,
  type WorkspaceView,
} from '@/domains/workspace';
import { errorMessage } from '@/shared/lib/format';
import { Button } from '@/shared/ui/button';
import { Skeleton } from '@/shared/ui/states';
import { Tag } from '@/shared/ui/tag';

import { ProviderBadge } from './ProviderBadge';
import { StageStepper } from './StageStepper';

interface RunHeaderProps {
  /** Where "back to workspaces" goes (the app owns the routes). */
  backHref: string;
  /** The tab switch, rendered at the right. */
  tabs: ReactNode;
}

function StartButton() {
  const { startRun } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const start = () => {
    setBusy(true);
    startRun().then(
      () => setBusy(false),
      (error: unknown) => {
        setBusy(false);
        toast.error(`The run did not start: ${errorMessage(error)}`);
      },
    );
  };
  return (
    <Button size="xs" onClick={start} disabled={busy}>
      <PlayIcon />
      Start run
    </Button>
  );
}

function RunStatus({ workspace }: { workspace: WorkspaceView }) {
  const { events } = useWorkspace();
  const status = WORKSPACE_STATUS[workspace.status];
  return (
    <div className="flex shrink-0 items-center gap-4">
      <Tag
        tone={status.tone}
        live={workspace.status === 'RUNNING'}
        title={workspace.error ?? undefined}
      >
        {status.label}
      </Tag>
      <StageStepper states={stageStates(workspace, events)} />
      {workspace.status === 'CREATED' ? <StartButton /> : null}
    </div>
  );
}

/** Slim workspace header: back, question, status with stages, providers, tabs. */
export function RunHeader({ backHref, tabs }: RunHeaderProps) {
  const { load } = useWorkspace();
  const workspace = load.status === 'ready' ? load.state.workspace : null;
  const mode =
    load.status === 'ready'
      ? (load.state.decomposition?.mode ?? load.state.workspace.domain_mode)
      : null;
  return (
    <header className="flex h-12 shrink-0 items-center gap-4 border-b pr-4 pl-2">
      <Button asChild size="icon-sm" variant="ghost">
        <a href={backHref} aria-label="Back to workspaces">
          <ArrowLeftIcon />
        </a>
      </Button>
      <div className="flex min-w-0 flex-1 items-baseline gap-2">
        {workspace ? (
          <>
            <h1
              className="truncate font-serif text-lg text-foreground"
              title={workspace.research_question}
            >
              {workspace.research_question}
            </h1>
            <span className="shrink-0 text-xs text-muted-foreground">
              {mode ? DOMAIN_MODE[mode] : null}
            </span>
          </>
        ) : (
          <Skeleton className="h-4 w-96" />
        )}
      </div>
      {workspace ? <RunStatus workspace={workspace} /> : null}
      <ProviderBadge />
      <div className="h-5 w-px bg-border" aria-hidden />
      {tabs}
    </header>
  );
}
