import { ArrowUpIcon, Loader2Icon } from 'lucide-react';
import { useId, type FormEvent } from 'react';

import { Button } from '@/shared/ui/button';

import type { CreatePhase } from '../model/createWorkspace';
import { MODE_HINT } from '../model/modes';
import { useNewWorkspaceForm } from '../model/useNewWorkspaceForm';
import { ExampleQuestions } from './ExampleQuestions';
import { RunOptions } from './RunOptions';
import { SeedPapers } from './SeedPapers';
import { TraceSpecimen } from './TraceSpecimen';

const PHASE_LABEL: Record<CreatePhase, string> = {
  creating: 'Creating the workspace',
  seeding: 'Adding seed papers',
  starting: 'Starting the research',
};

interface NewWorkspaceFormProps {
  onCreated: (workspaceId: string) => void;
}

/** The question composer, optional seed papers, and an example answer. */
export function NewWorkspaceForm({ onCreated }: NewWorkspaceFormProps) {
  const form = useNewWorkspaceForm(onCreated);
  const questionId = useId();
  const hintId = useId();
  const busy = form.phase !== null;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void form.submit();
  };

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-10">
      <div className="flex flex-col gap-3">
        <label
          htmlFor={questionId}
          className="reading text-3xl font-medium tracking-[-0.015em] text-balance text-foreground"
        >
          What do you want to find out?
        </label>
        <p className="max-w-[54ch] text-base text-muted-foreground">
          Ask in plain words. The researcher searches the literature, reads the
          strongest studies, and shows where every finding came from.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <div className="rounded-xl border border-input bg-background shadow-[0_1px_2px_rgba(24,34,58,0.06)] transition-[border-color,box-shadow] focus-within:border-ring focus-within:shadow-[0_0_0_4px_#e4eaf8]">
          <textarea
            id={questionId}
            value={form.question}
            disabled={busy}
            rows={3}
            required
            aria-describedby={hintId}
            placeholder="Is it safe to take creatine every day?"
            onChange={(event) => form.setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                onSubmit(event);
              }
            }}
            className="reading field-sizing-content block min-h-28 w-full resize-none rounded-t-xl bg-transparent px-5 pt-4 pb-3 text-lg leading-8 text-foreground placeholder:text-shade-4 focus-visible:outline-none disabled:opacity-60"
          />
          <div className="flex flex-wrap items-center gap-3 border-t border-border px-3 py-2.5">
            <RunOptions
              mode={form.mode}
              onModeChange={form.setMode}
              autoContinue={form.autoContinue}
              onAutoContinueChange={form.setAutoContinue}
              disabled={busy}
            />
            <Button
              type="submit"
              disabled={!form.canSubmit}
              className="ml-auto"
            >
              {busy ? (
                <Loader2Icon className="animate-spin" />
              ) : (
                <ArrowUpIcon />
              )}
              {form.phase ? PHASE_LABEL[form.phase] : 'Start research'}
            </Button>
          </div>
        </div>
        {form.error ? (
          <p id={hintId} role="alert" className="text-sm text-tone-negative">
            Could not create the workspace: {form.error}
          </p>
        ) : (
          <p id={hintId} className="text-xs text-muted-foreground">
            {MODE_HINT[form.mode]}{' '}
            <kbd className="font-sans font-semibold">Ctrl</kbd>+
            <kbd className="font-sans font-semibold">Enter</kbd> starts the
            research.
          </p>
        )}
        <ExampleQuestions onPick={form.setQuestion} disabled={busy} />
      </div>

      <SeedPapers
        files={form.files}
        onAddFiles={form.addFiles}
        onRemoveFile={form.removeFile}
        references={form.references}
        onAddReference={form.addReference}
        onRemoveReference={form.removeReference}
        disabled={busy}
      />

      <TraceSpecimen />
    </form>
  );
}
