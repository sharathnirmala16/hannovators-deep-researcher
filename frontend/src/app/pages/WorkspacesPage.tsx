import { useWorkspaceClient } from '@/domains/workspace';
import { NewWorkspaceForm } from '@/features/new-workspace';
import { WorkspaceList } from '@/features/workspace-list';
import { Pane, PaneBody } from '@/shared/ui/pane';
import { Tag } from '@/shared/ui/tag';

import { Wordmark } from '../Wordmark';
import { navigate, workspaceHref } from '../router/hashRoute';

/** `#/`: start a new workspace or reopen a recent one. */
export function WorkspacesPage() {
  const client = useWorkspaceClient();
  return (
    <>
      <header className="flex h-14 shrink-0 items-center gap-4 border-b bg-background px-8">
        <Wordmark />
        {client.source === 'fixtures' ? (
          <Tag tone="caution" className="ml-auto">
            Recorded fixtures
          </Tag>
        ) : null}
      </header>
      <main className="grid min-h-0 flex-1 grid-cols-[minmax(0,7fr)_minmax(22rem,5fr)]">
        <Pane aria-label="New workspace" className="border-r">
          <PaneBody>
            <div className="mx-auto w-full max-w-[680px] px-10 pt-12 pb-16">
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
