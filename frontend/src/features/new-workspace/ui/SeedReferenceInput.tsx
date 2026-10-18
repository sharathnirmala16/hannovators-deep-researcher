import { PlusIcon, XIcon } from 'lucide-react';
import { useId, useState, type FormEvent } from 'react';

import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';

import {
  SEED_KIND_LABEL,
  parseSeedReference,
  type SeedReference,
} from '../model/seedReference';

interface SeedReferenceInputProps {
  references: readonly SeedReference[];
  onAdd: (reference: SeedReference) => void;
  onRemove: (reference: SeedReference) => void;
  disabled?: boolean;
}

/** PMID, DOI, or URL seeds. The kind is detected from the text. */
export function SeedReferenceInput({
  references,
  onAdd,
  onRemove,
  disabled = false,
}: SeedReferenceInputProps) {
  const inputId = useId();
  const hintId = useId();
  const [text, setText] = useState('');
  const [invalid, setInvalid] = useState(false);
  const parsed = parseSeedReference(text);

  const add = (event?: FormEvent) => {
    event?.preventDefault();
    if (!text.trim()) return;
    if (!parsed) {
      setInvalid(true);
      return;
    }
    onAdd(parsed);
    setText('');
    setInvalid(false);
  };

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={inputId} className="text-sm font-medium">
        Seed references
      </label>
      <div className="flex items-center gap-2">
        <Input
          id={inputId}
          value={text}
          disabled={disabled}
          aria-invalid={invalid}
          aria-describedby={hintId}
          placeholder="PMID, DOI, or URL"
          className="font-mono text-sm"
          onChange={(event) => {
            setText(event.target.value);
            setInvalid(false);
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') add(event);
          }}
        />
        <Button
          type="button"
          variant="outline"
          onClick={() => add()}
          disabled={disabled || !text.trim()}
        >
          <PlusIcon />
          Add {parsed ? SEED_KIND_LABEL[parsed.kind] : 'seed'}
        </Button>
      </div>
      <p
        id={hintId}
        className={
          invalid
            ? 'text-xs text-tone-negative'
            : 'text-xs text-muted-foreground'
        }
      >
        {invalid
          ? 'Enter a PubMed ID (digits), a DOI starting with 10., or a web address.'
          : 'For example 35363499, 10.1056/NEJMoa1911303, or a report URL.'}
      </p>
      {references.length > 0 ? (
        <ul className="flex flex-wrap gap-2">
          {references.map((reference) => (
            <li
              key={`${reference.kind}:${reference.value}`}
              className="inline-flex h-7 max-w-full items-center gap-2 rounded-sm bg-muted pr-1 pl-2 text-xs"
            >
              <span className="text-muted-foreground">
                {SEED_KIND_LABEL[reference.kind]}
              </span>
              <span className="truncate font-mono">{reference.value}</span>
              <Button
                type="button"
                size="icon-xs"
                variant="ghost"
                aria-label={`Remove ${reference.value}`}
                onClick={() => onRemove(reference)}
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
