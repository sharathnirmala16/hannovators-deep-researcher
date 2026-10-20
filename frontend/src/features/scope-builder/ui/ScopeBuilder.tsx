import { useWorkspace, type WorkspaceState } from '@/domains/workspace';
import { plainMath } from '@/shared/lib/plainMath';
import { SectionHeader } from '@/shared/ui/section-header';
import { EmptyState, SkeletonBlock } from '@/shared/ui/states';
import { Tag } from '@/shared/ui/tag';

import { SCOPE_TITLE } from '../model/scopeFields';
import { useScopeBuilder } from '../model/useScopeBuilder';
import { ScopeActions } from './ScopeActions';
import { ScopeFieldList } from './ScopeFieldList';

type Scope = ReturnType<typeof useScopeBuilder>;

function ScopeBody({ state, scope }: { state: WorkspaceState; scope: Scope }) {
  const question = plainMath(state.workspace.research_question);
  if (!scope.value) {
    if (state.workspace.status === 'RUNNING') {
      return <SkeletonBlock lines={5} label="Decomposing the question" />;
    }
    return (
      <EmptyState title="No scope yet">
        Start the run to split the question into its parts. You can review and
        edit them before the search begins.
      </EmptyState>
    );
  }
  if (!scope.editable) {
    return (
      <ScopeFieldList
        value={scope.value}
        question={question}
        editable={false}
        onChange={scope.change}
      />
    );
  }
  return (
    <div className="flex flex-col gap-3 rounded-md bg-desk p-3">
      <p className="rounded-[3px] bg-tone-caution-tint px-2 py-1.5 text-xs text-tone-caution">
        The run is waiting for your review. Edit the scope, then continue.
      </p>
      <ScopeFieldList
        value={scope.value}
        question={question}
        editable={scope.busy === null}
        onChange={scope.change}
      />
      <ScopeActions
        dirty={scope.dirty}
        busy={scope.busy}
        onSave={() => void scope.onSave()}
        onContinue={() => void scope.onContinue()}
      />
    </div>
  );
}

/** PICOTS or scope as a protocol box; editable at the review checkpoint. */
export function ScopeBuilder() {
  const { load } = useWorkspace();
  const scope = useScopeBuilder();
  if (load.status === 'error') return null;
  return (
    <section
      aria-labelledby="scope-title"
      className="flex min-w-0 flex-col gap-2"
    >
      <SectionHeader
        id="scope-title"
        title="Scope"
        meta={
          <>
            {scope.value ? <span>{SCOPE_TITLE[scope.value.mode]}</span> : null}
            {scope.editable && scope.value ? (
              <Tag tone="caution">Awaiting review</Tag>
            ) : null}
          </>
        }
      />
      {load.status === 'ready' ? (
        <ScopeBody state={load.state} scope={scope} />
      ) : (
        <SkeletonBlock lines={5} label="Loading the scope" />
      )}
    </section>
  );
}
