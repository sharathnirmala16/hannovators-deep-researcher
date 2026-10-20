import { cn } from '@/shared/lib/cn';

import type { Block } from '../model/report';

interface ReportBlockProps {
  block: Block;
  /** The citation currently open, drawn with the highlighter. */
  active: number | null;
  onCite: (n: number) => void;
}

/** One heading, list item, or paragraph with `[n]` citation buttons. */
export function ReportBlock({ block, active, onCite }: ReportBlockProps) {
  const text = block.inline.map((part, index) =>
    part.kind === 'text' ? (
      <span key={index}>{part.text}</span>
    ) : (
      <button
        key={index}
        type="button"
        onClick={() => onCite(part.n)}
        aria-label={`Source ${part.n}`}
        className={cn(
          'mx-px rounded-[3px] font-sans text-xs font-semibold text-foreground tabular-nums underline decoration-marker decoration-2 underline-offset-[3px] transition-colors hover:marked-soft',
          active === part.n && 'marked',
        )}
      >
        [{part.n}]
      </button>
    ),
  );
  if (block.kind === 'heading') {
    return (
      <h4 className="pt-2 font-sans text-sm font-semibold text-foreground">
        {text}
      </h4>
    );
  }
  if (block.kind === 'item') {
    return (
      <p className="relative pl-4 before:absolute before:left-1 before:text-muted-foreground before:content-['•']">
        {text}
      </p>
    );
  }
  return <p>{text}</p>;
}
