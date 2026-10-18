import { useWorkspaceClient } from '@/domains/workspace';
import { NewWorkspaceForm } from '@/features/new-workspace';
import { WorkspaceList } from '@/features/workspace-list';
import { Pane, PaneBody } from '@/shared/ui/pane';
import { Tag } from '@/shared/ui/tag';

import { navigate, workspaceHref } from '../router/hashRoute';

/** `#/`: start a new workspace or reopen a recent one. */
export function WorkspacesPage() {
  const client = useWorkspaceClient();
  return (
    <>
      <header className="flex h-12 shrink-0 items-center gap-4 border-b px-6">
        <span className="text-sm font-semibold tracking-tight">
          Hannovators Deep Researcher
        </span>
        <span className="text-xs text-muted-foreground">
          Evidence synthesis you can check line by line
        </span>
        {client.source === 'fixtures' ? (
          <Tag tone="caution" className="ml-auto">
            Recorded fixtures
          </Tag>
        ) : null}
      </header>
      <main className="grid min-h-0 flex-1 grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <Pane aria-label="New workspace" className="border-r">
          <PaneBody>
            <div className="mx-auto w-full max-w-[640px] px-8 py-12">
              <NewWorkspaceForm
                onCreated={(id) => navigate(workspaceHref(id))}
              />
            </div>
          </PaneBody>
        </Pane>
        <WorkspaceList
          hrefFor={(id) => workspaceHref(id)}
          className="bg-desk"
        />
      </main>
    </>
  );
}
