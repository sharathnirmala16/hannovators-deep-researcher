import { useMemo, type ReactNode } from 'react';

import { parseMarkdown, type Block, type Inline } from '../model/markdown';

type RenderCitation = (n: number) => ReactNode;

interface InlinesProps {
  inlines: readonly Inline[];
  renderCitation: RenderCitation;
}

function InlineNode({
  inline,
  renderCitation,
}: {
  inline: Inline;
  renderCitation: RenderCitation;
}) {
  switch (inline.kind) {
    case 'text':
      return <>{inline.text}</>;
    case 'code':
      return (
        <code className="rounded-sm bg-muted px-1 font-mono text-[0.92em]">
          {inline.text}
        </code>
      );
    case 'strong':
      return (
        <strong className="font-semibold">
          <Inlines inlines={inline.children} renderCitation={renderCitation} />
        </strong>
      );
    case 'em':
      return (
        <em>
          <Inlines inlines={inline.children} renderCitation={renderCitation} />
        </em>
      );
    case 'cite':
      return <>{renderCitation(inline.n)}</>;
  }
}

function Inlines({ inlines, renderCitation }: InlinesProps) {
  return (
    <>
      {inlines.map((inline, index) => (
        <InlineNode
          key={index}
          inline={inline}
          renderCitation={renderCitation}
        />
      ))}
    </>
  );
}

function BlockNode({
  block,
  renderCitation,
}: {
  block: Block;
  renderCitation: RenderCitation;
}) {
  if (block.kind === 'paragraph' || block.kind === 'heading') {
    return (
      <p className={block.kind === 'heading' ? 'font-semibold' : undefined}>
        <Inlines inlines={block.inlines} renderCitation={renderCitation} />
      </p>
    );
  }
  const items = block.items.map((item, index) => (
    <li key={index}>
      <Inlines inlines={item} renderCitation={renderCitation} />
    </li>
  ));
  return block.ordered ? (
    <ol start={block.start} className="list-decimal space-y-1 pl-5">
      {items}
    </ol>
  ) : (
    <ul className="list-disc space-y-1 pl-5">{items}</ul>
  );
}

interface MarkdownProps {
  content: string;
  /** Renders a `[n]` marker, for example as a citation button. */
  renderCitation: RenderCitation;
}

/** Safe markdown subset rendered as React elements (no injected HTML). */
export function Markdown({ content, renderCitation }: MarkdownProps) {
  const blocks = useMemo(() => parseMarkdown(content), [content]);
  return (
    <div className="flex flex-col gap-2 text-sm leading-relaxed">
      {blocks.map((block, index) => (
        <BlockNode key={index} block={block} renderCitation={renderCitation} />
      ))}
    </div>
  );
}
