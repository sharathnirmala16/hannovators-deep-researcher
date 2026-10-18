import { RefreshCwIcon } from 'lucide-react';

import {
  DOMAIN_MODE,
  STAGE_LABEL,
  WORKSPACE_STATUS,
  type WorkspaceSummary,
} from '@/domains/workspace';
import { absoluteTime, plural, relativeTime } from '@/shared/lib/format';
import { Button } from '@/shared/ui/button';
import { Pane, PaneBody } from '@/shared/ui/pane';
import { SectionHeader } from '@/shared/ui/section-header';
import { EmptyState, ErrorState, SkeletonBlock } from '@/shared/ui/states';
import { Tag } from '@/shared/ui/tag';

import {
  useWorkspaceList,
  type WorkspaceListLoad,
} from '../model/useWorkspaceList';

interface WorkspaceListProps {
  /** Link target of one workspace (the app owns the routes). */
  hrefFor: (id: string) => string;
  className?: string;
}

function Row({ item, href }: { item: WorkspaceSummary; href: string }) {
  const status = WORKSPACE_STATUS[item.status];
  const stage =
    item.status === 'RUNNING' || item.status === 'AWAITING_REVIEW'
      ? item.current_stage
      : null;
  return (
    <li className="border-b last:border-b-0">
      <a
        href={href}
        className="group flex flex-col gap-2 px-6 py-4 transition-colors hover:bg-background focus-visible:bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-inset"
      >
        <span className="line-clamp-2 font-serif text-base text-foreground group-hover:underline group-hover:decoration-shade-4 group-hover:underline-offset-4">
          {item.research_question}
        </span>
        <span className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground tabular-nums">
          <Tag tone={status.tone} live={item.status === 'RUNNING'}>
            {status.label}
            {stage ? `: ${STAGE_LABEL[stage].toLowerCase()}` : ''}
          </Tag>
          <span>{DOMAIN_MODE[item.domain_mode]}</span>
          <span>
            {plural(item.source_count, 'source')}, {item.promoted_count}{' '}
            included
            {item.seed_count > 0 ? `, ${plural(item.seed_count, 'seed')}` : ''}
          </span>
          <time
            dateTime={item.updated_at}
            title={absoluteTime(item.updated_at)}
            className="ml-auto"
          >
            {relativeTime(item.updated_at)}
          </time>
        </span>
      </a>
    </li>
  );
}

function ListBody({
  load,
  reload,
  hrefFor,
}: {
  load: WorkspaceListLoad;
  reload: () => void;
  hrefFor: (id: string) => string;
}) {
  switch (load.status) {
    case 'loading':
      return <SkeletonBlock lines={6} className="px-6 py-4" />;
    case 'unavailable':
      return (
        <EmptyState
          className="mx-6 my-4"
          title="The workspace list is not available on this server yet"
        >
          New workspaces still open as usual.
        </EmptyState>
      );
    case 'error':
      return (
        <ErrorState
          className="mx-6 my-4"
          title="Could not load the workspaces"
          message={load.message}
          onRetry={reload}
        />
      );
    case 'ready':
      if (load.items.length === 0) {
        return (
          <EmptyState className="mx-6 my-4" title="No workspaces yet">
            Ask a question on the left to start the first one.
          </EmptyState>
        );
      }
      return (
        <ol>
          {load.items.map((item) => (
            <Row key={item.id} item={item} href={hrefFor(item.id)} />
          ))}
        </ol>
      );
  }
}

/** Recent workspaces: question, status and stage, mode, counts, updated. */
export function WorkspaceList({ hrefFor, className }: WorkspaceListProps) {
  const { load, reload } = useWorkspaceList();
  const count = load.status === 'ready' ? load.items.length : null;
  return (
    <Pane aria-labelledby="workspace-list-title" className={className}>
      <SectionHeader
        variant="pane"
        id="workspace-list-title"
        title="Recent workspaces"
        meta={count !== null ? <span>{count}</span> : null}
        className="px-6"
        actions={
          <Button
            size="icon-xs"
            variant="ghost"
            onClick={reload}
            aria-label="Refresh the list"
          >
            <RefreshCwIcon />
          </Button>
        }
      />
      <PaneBody>
        <ListBody load={load} reload={reload} hrefFor={hrefFor} />
      </PaneBody>
    </Pane>
  );
}
