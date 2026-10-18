import { Loader2Icon, PlayIcon } from 'lucide-react';

import { useWorkspace, type Decomposition } from '@/domains/workspace';
import { Button } from '@/shared/ui/button';
import { SectionHeader } from '@/shared/ui/section-header';
import { EmptyState, SkeletonBlock } from '@/shared/ui/states';

import { PICOTS_FIELDS, SCOPE_FIELDS, SCOPE_TITLE } from '../model/scopeFields';
import { useScopeBuilder } from '../model/useScopeBuilder';
import { ScopeFields } from './ScopeFields';

function Fields({
  value,
  editable,
  onChange,
}: {
  value: Decomposition;
  editable: boolean;
  onChange: (next: Decomposition) => void;
}) {
  if (value.mode === 'MEDICAL') {
    return (
      <ScopeFields
        fields={PICOTS_FIELDS}
        value={value}
        editable={editable}
        onChange={onChange}
      />
    );
  }
  return (
    <ScopeFields
      fields={SCOPE_FIELDS}
      value={value}
      editable={editable}
      onChange={onChange}
    />
  );
}

/** PICOTS or scope chips; editable at the review checkpoint (Save, Continue). */
export function ScopeBuilder() {
  const { load } = useWorkspace();
  const scope = useScopeBuilder();
  const status = load.status === 'ready' ? load.state.workspace.status : null;

  if (!scope.value) {
    return (
      <section aria-labelledby="scope-title" className="flex flex-col gap-2">
        <SectionHeader id="scope-title" title="Scope" />
        {status === 'RUNNING' ? (
          <SkeletonBlock lines={4} label="Decomposing the question" />
        ) : (
          <EmptyState title="No scope yet">
            The question is split into its parts when the run starts.
          </EmptyState>
        )}
      </section>
    );
  }

  const busy = scope.busy !== null;
  return (
    <section aria-labelledby="scope-title" className="flex flex-col gap-2">
      <SectionHeader
        id="scope-title"
        title="Scope"
        meta={<span>{SCOPE_TITLE[scope.value.mode]}</span>}
        actions={
          scope.editable ? (
            <>
              <Button
                size="xs"
                variant="ghost"
                onClick={() => void scope.onSave()}
                disabled={!scope.dirty || busy}
              >
                {scope.busy === 'saving' ? 'Saving' : 'Save'}
              </Button>
              <Button
                size="xs"
                onClick={() => void scope.onContinue()}
                disabled={busy}
              >
                {scope.busy === 'continuing' ? (
                  <Loader2Icon className="animate-spin" />
                ) : (
                  <PlayIcon />
                )}
                Continue
              </Button>
            </>
          ) : null
        }
      />
      {scope.editable ? (
        <p className="rounded-sm bg-tone-caution/10 px-2 py-1 text-xs text-foreground">
          The run is waiting for your review. Edit the scope, then continue.
        </p>
      ) : null}
      <Fields
        value={scope.value}
        editable={scope.editable && !busy}
        onChange={scope.change}
      />
    </section>
  );
}
