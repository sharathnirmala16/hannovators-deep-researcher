import { ChevronRight } from 'lucide-react';
import { useState } from 'react';

import { cn } from '@/shared/lib/cn';

import { isRecord } from '../model/json';
import { FOCUS_RING } from './statusStyles';

/** Strings longer than this collapse behind "Show all". */
const LONG_STRING = 280;
/** Containers deeper than this, or larger than `BIG`, start collapsed. */
const OPEN_DEPTH = 2;
const BIG = 40;

/** Pretty JSON with collapsible objects, arrays, and long strings. */
export function JsonView({ value }: { value: unknown }) {
  return (
    <div className="overflow-x-auto rounded-md bg-muted py-2 pr-3 pl-6 font-mono text-xs leading-5">
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
      <div className="flex min-w-0 gap-1">
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
      <div className="flex gap-1">
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
        className={cn(
          '-ml-4 flex items-center gap-1 rounded-sm text-left',
          FOCUS_RING,
        )}
      >
        <ChevronRight
          aria-hidden
          className={cn(
            'size-3 text-muted-foreground transition-transform',
            open && 'rotate-90',
          )}
        />
        {label !== undefined ? <Key label={label} /> : null}
        <span className="text-muted-foreground">
          {open ? opener : `${opener} ${size} ${closer}`}
        </span>
      </button>
      {open ? (
        <div className="ml-1 border-l border-border pl-4">
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
  return <span className="shrink-0 text-muted-foreground">{label}:</span>;
}

function Scalar({ value }: { value: unknown }) {
  if (typeof value === 'string') return <LongString value={value} />;
  return <span className="font-medium">{JSON.stringify(value) ?? 'null'}</span>;
}

function LongString({ value }: { value: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = value.length > LONG_STRING;
  const shown = long && !expanded ? `${value.slice(0, LONG_STRING)}…` : value;
  return (
    <span className="min-w-0 break-words whitespace-pre-wrap">
      &quot;{shown}&quot;
      {long ? (
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className={cn(
            'ml-2 rounded-sm font-sans text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground',
            FOCUS_RING,
          )}
        >
          {expanded
            ? 'Show less'
            : `Show all ${value.length.toLocaleString()} characters`}
        </button>
      ) : null}
    </span>
  );
}
