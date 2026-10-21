import { useMemo, type ReactNode } from 'react';

import { cn } from '@/shared/lib/cn';
import {
  parseMarkdown,
  type Align,
  type Block,
  type Inline,
} from '@/shared/lib/markdown';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/ui/table';

export interface MarkdownRenderers {
  /** Renders a `[n]` marker, for example as a citation button. */
  citation?: ((n: number) => ReactNode) | undefined;
  /** Renders a run of plain text, for example with a quote marked. */
  text?: ((text: string) => ReactNode) | undefined;
}

interface NodeProps {
  renderers: MarkdownRenderers;
}

const HEADING_CLASS: Record<number, string> = {
  1: 'text-lg leading-snug',
  2: 'text-base leading-snug',
};

const HEADING_TAG = ['h3', 'h4', 'h5', 'h6'] as const;

const ALIGN_CLASS: Record<Exclude<Align, null>, string> = {
  left: 'text-left',
  center: 'text-center',
  right: 'text-right',
};

function InlineNode({ inline, renderers }: NodeProps & { inline: Inline }) {
  switch (inline.kind) {
    case 'text':
      return <>{renderers.text ? renderers.text(inline.text) : inline.text}</>;
    case 'code':
      return (
        <code className="rounded-sm bg-muted px-1 font-mono text-[0.92em]">
          {inline.text}
        </code>
      );
    case 'strong':
      return (
        <strong className="font-semibold">
          <Inlines inlines={inline.children} renderers={renderers} />
        </strong>
      );
    case 'em':
      return (
        <em>
          <Inlines inlines={inline.children} renderers={renderers} />
        </em>
      );
    case 'link':
      return (
        <a
          href={inline.href}
          target="_blank"
          rel="noreferrer noopener"
          className="text-link underline decoration-1 underline-offset-2 hover:decoration-2"
        >
          <Inlines inlines={inline.children} renderers={renderers} />
        </a>
      );
    case 'cite':
      return renderers.citation ? (
        <>{renderers.citation(inline.n)}</>
      ) : (
        <span className="font-sans text-xs text-muted-foreground tabular-nums">
          [{inline.n}]
        </span>
      );
  }
}

function Inlines({
  inlines,
  renderers,
}: NodeProps & { inlines: readonly Inline[] }) {
  return (
    <>
      {inlines.map((inline, index) => (
        <InlineNode key={index} inline={inline} renderers={renderers} />
      ))}
    </>
  );
}

function MarkdownTable({
  block,
  renderers,
}: NodeProps & { block: Extract<Block, { kind: 'table' }> }) {
  const align = (index: number) => {
    const value = block.align[index];
    return value ? ALIGN_CLASS[value] : undefined;
  };
  const cell =
    'min-w-32 px-3 py-2 align-top whitespace-normal first:pl-3 last:pr-3';
  return (
    <div className="min-w-0 overflow-x-auto rounded-md border border-border">
      <Table className="font-sans text-xs leading-5">
        <TableHeader className="bg-muted">
          <TableRow>
            {block.header.map((inlines, index) => (
              <TableHead
                key={index}
                className={cn(
                  cell,
                  'h-auto font-semibold text-foreground',
                  align(index),
                )}
              >
                <Inlines inlines={inlines} renderers={renderers} />
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {block.rows.map((row, rowIndex) => (
            <TableRow key={rowIndex} className="hover:bg-transparent">
              {row.map((inlines, index) => (
                <TableCell key={index} className={cn(cell, align(index))}>
                  <Inlines inlines={inlines} renderers={renderers} />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

/** A list item: a leading paragraph flows inline; nested blocks follow. */
function ListItem({ blocks, renderers }: NodeProps & { blocks: Block[] }) {
  const [first, ...rest] = blocks;
  const lead = first?.kind === 'paragraph' ? first : null;
  const body = lead ? rest : blocks;
  return (
    <li className="pl-0.5">
      {lead ? <Inlines inlines={lead.inlines} renderers={renderers} /> : null}
      {body.length > 0 ? (
        <div className="mt-1 flex flex-col gap-1.5">
          <BlockList blocks={body} renderers={renderers} />
        </div>
      ) : null}
    </li>
  );
}

function BlockNode({ block, renderers }: NodeProps & { block: Block }) {
  switch (block.kind) {
    case 'heading': {
      // Rendered inside a pane section, so a document h1 becomes an h3.
      const Heading = HEADING_TAG[Math.min(block.level, 4) - 1] ?? 'h6';
      return (
        <Heading
          className={cn(
            'mt-2 font-sans font-semibold text-foreground first:mt-0',
            HEADING_CLASS[block.level] ?? 'text-sm',
          )}
        >
          <Inlines inlines={block.inlines} renderers={renderers} />
        </Heading>
      );
    }
    case 'paragraph':
      return (
        <p>
          <Inlines inlines={block.inlines} renderers={renderers} />
        </p>
      );
    case 'list': {
      const items = block.items.map((blocks, index) => (
        <ListItem key={index} blocks={blocks} renderers={renderers} />
      ));
      return block.ordered ? (
        <ol
          start={block.start}
          className="flex list-decimal flex-col gap-1 pl-5 marker:text-muted-foreground"
        >
          {items}
        </ol>
      ) : (
        <ul className="flex list-disc flex-col gap-1 pl-5 marker:text-muted-foreground">
          {items}
        </ul>
      );
    }
    case 'quote':
      return (
        <blockquote className="flex flex-col gap-2 border-l-2 border-border pl-3 text-muted-foreground">
          <BlockList blocks={block.blocks} renderers={renderers} />
        </blockquote>
      );
    case 'rule':
      return <hr className="my-1 border-border" />;
    case 'code':
      return (
        <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs leading-5">
          <code>{block.text}</code>
        </pre>
      );
    case 'table':
      return <MarkdownTable block={block} renderers={renderers} />;
  }
}

function BlockList({
  blocks,
  renderers,
}: NodeProps & { blocks: readonly Block[] }) {
  return (
    <>
      {blocks.map((block, index) => (
        <BlockNode key={index} block={block} renderers={renderers} />
      ))}
    </>
  );
}

interface MarkdownBlocksProps extends MarkdownRenderers {
  blocks: readonly Block[];
  className?: string;
}

/** Parsed markdown blocks as React elements (no injected HTML). */
export function MarkdownBlocks({
  blocks,
  className,
  citation,
  text,
}: MarkdownBlocksProps) {
  return (
    <div className={cn('flex min-w-0 flex-col gap-3 break-words', className)}>
      <BlockList blocks={blocks} renderers={{ citation, text }} />
    </div>
  );
}

interface MarkdownProps extends MarkdownRenderers {
  content: string;
  className?: string;
}

/**
 * Safe GitHub-flavored markdown: headings, lists, quotes, rules, code, pipe
 * tables, links, and `[n]` citations. Images are dropped.
 */
export function Markdown({ content, ...props }: MarkdownProps) {
  const blocks = useMemo(() => parseMarkdown(content), [content]);
  return <MarkdownBlocks blocks={blocks} {...props} />;
}
