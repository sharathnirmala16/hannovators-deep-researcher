import { ChevronRight } from 'lucide-react';
import { useState } from 'react';

import { cn } from '@/shared/lib/cn';

import { isRecord } from '../model/json';
import { JsonString } from './JsonString';

/** Containers deeper than this, or larger than `BIG`, start collapsed. */
const OPEN_DEPTH = 2;
const BIG = 40;

/**
 * Pretty JSON with collapsible objects and arrays. Keys in ink, strings in
 * the positive tone, numbers in the info tone; long lines wrap, so the panel
 * never scrolls sideways.
 */
export function JsonView({ value }: { value: unknown }) {
  return (
    <div className="rounded-md bg-shade-0 py-3 pr-3 pl-7 font-mono text-xs leading-5 [overflow-wrap:anywhere] text-foreground">
      <JsonNode value={value} depth={0} />
    </div>
  );
}

interface JsonNodeProps {
  value: unknown;
  depth: number;
  label?: string | undefined;
}

function JsonNode({ value, depth, label }: JsonNodeProps) {
  const entries = containerEntries(value);
  if (entries === null) {
    return (
      <div className="flex min-w-0 gap-1.5">
        {label !== undefined ? <Key label={label} /> : null}
        <Scalar value={value} />
      </div>
    );
  }
  return (
    <Container value={value} entries={entries} depth={depth} label={label} />
  );
}

function containerEntries(value: unknown): [string, unknown][] | null {
  if (Array.isArray(value)) return value.map((item, i) => [String(i), item]);
  return isRecord(value) ? Object.entries(value) : null;
}

interface ContainerProps extends JsonNodeProps {
  entries: [string, unknown][];
}

function Container({ value, entries, depth, label }: ContainerProps) {
  const [open, setOpen] = useState(depth < OPEN_DEPTH && entries.length <= BIG);
  const isArray = Array.isArray(value);
  const [opener, closer] = isArray ? ['[', ']'] : ['{', '}'];
  if (entries.length === 0) {
    return (
      <div className="flex gap-1.5">
        {label !== undefined ? <Key label={label} /> : null}
        <span className="text-muted-foreground">{`${opener}${closer}`}</span>
      </div>
    );
  }
  const size = `${entries.length} ${isArray ? 'items' : 'keys'}`;
  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="-ml-4 flex items-center gap-1.5 rounded-sm text-left hover:bg-shade-2"
      >
        <ChevronRight
          aria-hidden
          className={cn(
            'size-3 shrink-0 text-muted-foreground transition-transform',
            open && 'rotate-90',
          )}
        />
        {label !== undefined ? <Key label={label} /> : null}
        <span className="text-muted-foreground">
          {open ? opener : `${opener} ${size} ${closer}`}
        </span>
      </button>
      {open ? (
        <div className="pl-4">
          {entries.map(([key, item]) => (
            <JsonNode
              key={key}
              value={item}
              depth={depth + 1}
              label={isArray ? undefined : key}
            />
          ))}
        </div>
      ) : null}
      {open ? <span className="text-muted-foreground">{closer}</span> : null}
    </div>
  );
}

function Key({ label }: { label: string }) {
  return (
    <span className="shrink-0 font-medium text-foreground">
      {label}
      <span className="text-muted-foreground">:</span>
    </span>
  );
}

function Scalar({ value }: { value: unknown }) {
  if (typeof value === 'string') return <JsonString value={value} />;
  const tone = typeof value === 'number' ? 'text-tone-info' : 'text-tone-null';
  return <span className={tone}>{JSON.stringify(value) ?? 'null'}</span>;
}
