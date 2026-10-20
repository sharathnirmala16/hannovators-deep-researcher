import { Loader2Icon } from 'lucide-react';
import { useId, type FormEvent } from 'react';

import { Button } from '@/shared/ui/button';

import type { CreatePhase } from '../model/createWorkspace';
import { useNewWorkspaceForm } from '../model/useNewWorkspaceForm';
import { SeedDropZone } from './SeedDropZone';
import { RunOptions } from './RunOptions';
import { SeedReferenceInput } from './SeedReferenceInput';
import { TraceSpecimen } from './TraceSpecimen';

const PHASE_LABEL: Record<CreatePhase, string> = {
  creating: 'Creating the workspace',
  seeding: 'Adding seed papers',
  starting: 'Starting the research',
};

interface NewWorkspaceFormProps {
  onCreated: (workspaceId: string) => void;
}

/** Question, mode, auto-continue, and seeds; submitting starts the run. */
export function NewWorkspaceForm({ onCreated }: NewWorkspaceFormProps) {
  const form = useNewWorkspaceForm(onCreated);
  const questionId = useId();
  const busy = form.phase !== null;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void form.submit();
  };

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-9">
      <div className="flex flex-col gap-5">
        <label
          htmlFor={questionId}
          className="reading text-3xl font-medium tracking-[-0.01em] text-balance text-foreground"
        >
          What do you want to find out?
        </label>
        <TraceSpecimen />
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
          className="reading field-sizing-content mt-1 min-h-36 w-full resize-none rounded-lg border border-input bg-background px-5 py-4 text-xl leading-8 text-foreground transition-[border-color,box-shadow] placeholder:text-shade-4 focus-visible:border-ring focus-visible:shadow-[0_0_0_4px_#e4eaf8] focus-visible:outline-none disabled:opacity-60"
        />
      </div>

      <RunOptions
        mode={form.mode}
        onModeChange={form.setMode}
        autoContinue={form.autoContinue}
        onAutoContinueChange={form.setAutoContinue}
        disabled={busy}
      />

      <fieldset className="flex flex-col gap-4">
        <legend className="mb-1 flex flex-col gap-0.5">
          <span className="reading text-lg font-medium">Seed papers</span>
          <span className="text-xs text-muted-foreground">
            Optional. Papers you already trust: the search starts from them and
            they are read in full.
          </span>
        </legend>
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
      </fieldset>

      <div className="flex flex-wrap items-center gap-4 border-t pt-6">
        <Button
          type="submit"
          size="lg"
          disabled={!form.canSubmit}
          className="px-7"
        >
          {busy ? <Loader2Icon className="animate-spin" /> : null}
          {form.phase ? PHASE_LABEL[form.phase] : 'Start research'}
        </Button>
        {form.error ? (
          <p role="alert" className="text-sm text-tone-negative">
            Could not create the workspace: {form.error}
          </p>
        ) : (
          <span className="text-xs text-muted-foreground">
            <kbd className="font-sans font-semibold">Ctrl</kbd>+
            <kbd className="font-sans font-semibold">Enter</kbd> also starts it.
          </span>
        )}
      </div>
    </form>
  );
}
