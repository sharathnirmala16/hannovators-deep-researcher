import { ChevronRightIcon } from 'lucide-react';
import { useId, useState } from 'react';

import { cn } from '@/shared/lib/cn';

import type { SeedReference } from '../model/seedReference';
import { SeedDropZone } from './SeedDropZone';
import { SeedReferenceInput } from './SeedReferenceInput';

interface SeedPapersProps {
  files: readonly File[];
  onAddFiles: (files: readonly File[]) => number;
  onRemoveFile: (file: File) => void;
  references: readonly SeedReference[];
  onAddReference: (reference: SeedReference) => void;
  onRemoveReference: (reference: SeedReference) => void;
  disabled: boolean;
}

/** Optional papers to start from, folded away until asked for. */
export function SeedPapers(props: SeedPapersProps) {
  const count = props.files.length + props.references.length;
  const [open, setOpen] = useState(count > 0);
  const regionId = useId();
  return (
    <section className="flex flex-col gap-3">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={regionId}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center gap-1.5 self-start rounded-sm text-sm font-medium text-foreground"
      >
        <ChevronRightIcon
          aria-hidden
          className={cn(
            'size-4 text-muted-foreground transition-transform',
            open && 'rotate-90',
          )}
        />
        Start from papers you trust
        <span className="font-normal text-muted-foreground">
          {count > 0 ? `(${count} added)` : '(optional)'}
        </span>
      </button>
      {open ? (
        <div
          id={regionId}
          className="flex flex-col gap-4 rounded-xl border border-border bg-shade-0 p-4"
        >
          <p className="text-xs text-muted-foreground">
            The search starts from these papers, and they are read in full.
          </p>
          <SeedDropZone
            files={props.files}
            onAdd={props.onAddFiles}
            onRemove={props.onRemoveFile}
            disabled={props.disabled}
          />
          <SeedReferenceInput
            references={props.references}
            onAdd={props.onAddReference}
            onRemove={props.onRemoveReference}
            disabled={props.disabled}
          />
        </div>
      ) : null}
    </section>
  );
}
