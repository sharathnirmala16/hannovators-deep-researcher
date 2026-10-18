import { useMemo, useState } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import { useWorkspace, type DeepResearchRecord } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { Button } from '@/shared/ui/button';

import { parseReport, type Block, type Inline } from '../model/report';

type ReportSource = DeepResearchRecord['sources'][number];

const PREVIEW_BLOCKS = 4;

function InlineText({
  parts,
  onCite,
}: {
  parts: Inline[];
  onCite: (n: number) => void;
}) {
  return parts.map((part, index) =>
    part.kind === 'text' ? (
      <span key={index}>{part.text}</span>
    ) : (
      <button
        key={index}
        type="button"
        onClick={() => onCite(part.n)}
        aria-label={`Source ${part.n}`}
        className="mx-px rounded-sm px-0.5 align-super font-sans text-[10px] leading-none font-semibold text-tone-info hover:bg-marker/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        {part.n}
      </button>
    ),
  );
}

function ReportBlock({
  block,
  onCite,
}: {
  block: Block;
  onCite: (n: number) => void;
}) {
  const text = <InlineText parts={block.inline} onCite={onCite} />;
  if (block.kind === 'heading') {
    return <h4 className="pt-2 font-sans text-sm font-semibold">{text}</h4>;
  }
  if (block.kind === 'item') {
    return (
      <p className="relative pl-4 before:absolute before:left-1 before:content-['•']">
        {text}
      </p>
    );
  }
  return <p>{text}</p>;
}

/** The Tavily report with numbered citations and its source list. */
export function DeepResearchReport({ record }: { record: DeepResearchRecord }) {
  const { recordAction } = useWorkspace();
  const { selectSource } = useEvidenceSelection();
  const blocks = useMemo(() => parseReport(record.content), [record.content]);
  const [expanded, setExpanded] = useState(false);
  const [active, setActive] = useState<number | null>(null);
  const shown = expanded ? blocks : blocks.slice(0, PREVIEW_BLOCKS);

  const open = (n: number, source: ReportSource | undefined) => {
    setActive(n);
    recordAction({
      name: 'user.citation.open',
      summary: `Opened deep research source [${n}]`,
      target: source?.url ?? null,
      source_ids: source?.source_id ? [source.source_id] : [],
      details: { report: 'deep_research', n },
    });
    if (source?.source_id) selectSource(source.source_id);
  };
  const onCite = (n: number) => {
    setExpanded(true);
    open(n, record.sources[n - 1]);
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2 font-serif text-sm leading-relaxed">
        {shown.map((block, index) => (
          <ReportBlock key={index} block={block} onCite={onCite} />
        ))}
        {blocks.length > PREVIEW_BLOCKS ? (
          <Button
            size="xs"
            variant="ghost"
            className="self-start font-sans"
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? 'Show less' : 'Show the full report'}
          </Button>
        ) : null}
      </div>
      {record.sources.length > 0 ? (
        <ol className="flex flex-col gap-1" aria-label="Report sources">
          {record.sources.map((source, index) => (
            <li
              key={`${source.url}-${index}`}
              className={cn(
                'flex gap-2 rounded-sm px-1 py-0.5 text-xs',
                active === index + 1 && 'marked',
              )}
            >
              <span className="w-5 shrink-0 text-right text-muted-foreground tabular-nums">
                {index + 1}
              </span>
              <span className="flex min-w-0 flex-col">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  onClick={() => open(index + 1, source)}
                  className="truncate text-foreground hover:underline"
                  title={source.title}
                >
                  {source.title || source.url}
                </a>
                <span className="truncate font-mono text-[11px] text-muted-foreground">
                  {source.url}
                </span>
              </span>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
