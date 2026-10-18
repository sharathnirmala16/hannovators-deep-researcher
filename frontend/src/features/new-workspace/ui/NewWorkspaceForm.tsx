import { Loader2Icon } from 'lucide-react';
import { useId, type FormEvent } from 'react';

import type { RequestedDomainMode } from '@/domains/workspace';
import { Button } from '@/shared/ui/button';
import { Segmented, type SegmentOption } from '@/shared/ui/segmented';
import { Switch } from '@/shared/ui/switch';

import type { CreatePhase } from '../model/createWorkspace';
import { useNewWorkspaceForm } from '../model/useNewWorkspaceForm';
import { SeedDropZone } from './SeedDropZone';
import { SeedReferenceInput } from './SeedReferenceInput';

const MODES: readonly SegmentOption<RequestedDomainMode>[] = [
  { value: 'AUTO', label: 'Auto' },
  { value: 'MEDICAL', label: 'Medical' },
  { value: 'GENERAL', label: 'General' },
];

const MODE_HINT: Record<RequestedDomainMode, string> = {
  AUTO: 'Picks medical or general from the question.',
  MEDICAL: 'PICOTS scope, RoB 2 appraisal, and a GRADE evidence profile.',
  GENERAL: 'Entities and claims, credibility checks, and a claim matrix.',
};

const PHASE_LABEL: Record<CreatePhase, string> = {
  creating: 'Creating the workspace',
  seeding: 'Adding seeds',
  starting: 'Starting the run',
};

interface NewWorkspaceFormProps {
  onCreated: (workspaceId: string) => void;
}

/** Question, mode, auto-continue, and seeds; Create starts the run. */
export function NewWorkspaceForm({ onCreated }: NewWorkspaceFormProps) {
  const form = useNewWorkspaceForm(onCreated);
  const questionId = useId();
  const switchId = useId();
  const busy = form.phase !== null;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void form.submit();
  };

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <label
          htmlFor={questionId}
          className="font-serif text-xl text-foreground"
        >
          What do you want to find out?
        </label>
        <textarea
          id={questionId}
          value={form.question}
          disabled={busy}
          rows={4}
          required
          placeholder="In adults with heart failure with reduced ejection fraction, do SGLT2 inhibitors reduce hospitalization compared with placebo?"
          onChange={(event) => form.setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
              onSubmit(event);
            }
          }}
          className="field-sizing-content min-h-32 w-full resize-none rounded-md bg-muted px-4 py-3 font-serif text-lg leading-relaxed text-foreground placeholder:text-muted-foreground/70 focus-visible:bg-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        />
      </div>

      <div className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-4 gap-y-4">
        <span className="text-sm font-medium" id={`${questionId}-mode`}>
          Mode
        </span>
        <div className="flex flex-wrap items-center gap-4">
          <Segmented
            label="Research mode"
            size="md"
            value={form.mode}
            options={MODES}
            onChange={form.setMode}
          />
          <span className="text-xs text-muted-foreground">
            {MODE_HINT[form.mode]}
          </span>
        </div>
        <label htmlFor={switchId} className="text-sm font-medium">
          Auto-continue
        </label>
        <div className="flex items-center gap-4">
          <Switch
            id={switchId}
            checked={form.autoContinue}
            onCheckedChange={form.setAutoContinue}
            disabled={busy}
          />
          <span className="text-xs text-muted-foreground">
            {form.autoContinue
              ? 'Runs straight through to the synthesis.'
              : 'Pauses after the scope so you can edit it.'}
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <SeedDropZone
          files={form.files}
          onAdd={form.addFiles}
          onRemove={form.removeFile}
          disabled={busy}
        />
        <SeedReferenceInput
          references={form.references}
          onAdd={form.addReference}
          onRemove={form.removeReference}
          disabled={busy}
        />
      </div>

      <div className="flex items-center gap-4">
        <Button type="submit" size="lg" disabled={!form.canSubmit}>
          {busy ? <Loader2Icon className="animate-spin" /> : null}
          {form.phase ? PHASE_LABEL[form.phase] : 'Create and start'}
        </Button>
        {form.error ? (
          <p role="alert" className="text-sm text-tone-negative">
            Could not create the workspace: {form.error}
          </p>
        ) : (
          <span className="text-xs text-muted-foreground">
            Ctrl+Enter also creates it.
          </span>
        )}
      </div>
    </form>
  );
}
