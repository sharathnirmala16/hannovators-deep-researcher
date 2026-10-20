import { FileTextIcon, UploadIcon, XIcon } from 'lucide-react';
import { useId, useState, type DragEvent } from 'react';
import { toast } from 'sonner';

import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/button';

interface SeedDropZoneProps {
  files: readonly File[];
  onAdd: (files: readonly File[]) => number;
  onRemove: (file: File) => void;
  disabled?: boolean;
}

function fileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Drop or browse for seed PDFs (several at once). */
export function SeedDropZone({
  files,
  onAdd,
  onRemove,
  disabled = false,
}: SeedDropZoneProps) {
  const inputId = useId();
  const [over, setOver] = useState(false);

  const add = (list: FileList | null) => {
    if (!list || list.length === 0) return;
    const skipped = onAdd([...list]);
    if (skipped > 0) {
      toast.warning(
        `${skipped} file${skipped === 1 ? ' is' : 's are'} not a PDF and ${skipped === 1 ? 'was' : 'were'} skipped.`,
      );
    }
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setOver(false);
    if (!disabled) add(event.dataTransfer.files);
  };

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor={inputId}
        onDragOver={(event) => {
          event.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={cn(
          'flex cursor-pointer items-center gap-4 rounded-lg border border-dashed border-shade-3 bg-shade-0 px-5 py-5 transition-colors',
          'hover:border-shade-4 hover:bg-desk',
          'has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-ring',
          over && 'border-ring bg-tone-info-tint',
          disabled && 'pointer-events-none opacity-60',
        )}
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-background text-muted-foreground shadow-[0_0_0_1px_#dde3eb]">
          <UploadIcon aria-hidden className="size-4" />
        </span>
        <span className="flex flex-col">
          <span className="text-sm font-semibold">
            Drop PDFs here, or{' '}
            <span className="text-link underline underline-offset-2">
              browse
            </span>
          </span>
          <span className="text-xs text-muted-foreground">
            Several files at once. PDFs only.
          </span>
        </span>
        <input
          id={inputId}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          disabled={disabled}
          className="sr-only"
          onChange={(event) => {
            add(event.target.files);
            event.target.value = '';
          }}
        />
      </label>
      {files.length > 0 ? (
        <ul className="flex flex-col divide-y rounded-md bg-shade-0 px-3">
          {files.map((file) => (
            <li
              key={`${file.name}:${file.size}`}
              className="flex h-9 items-center gap-2 text-sm"
            >
              <FileTextIcon
                aria-hidden
                className="size-4 shrink-0 text-muted-foreground"
              />
              <span className="min-w-0 flex-1 truncate">{file.name}</span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {fileSize(file.size)}
              </span>
              <Button
                type="button"
                size="icon-xs"
                variant="ghost"
                aria-label={`Remove ${file.name}`}
                onClick={() => onRemove(file)}
                disabled={disabled}
              >
                <XIcon />
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
