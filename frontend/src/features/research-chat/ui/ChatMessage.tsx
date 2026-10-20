import { useEvidenceSelection } from '@/domains/evidence';
import type { ChatMessageView, Citation } from '@/domains/workspace';
import { clockTime } from '@/shared/lib/format';

import { CitationButton, SourceList } from './Citations';
import { Markdown } from './Markdown';

/** The user's question, right-aligned in a tinted block. */
export function UserTurn({ content }: { content: string }) {
  return (
    <article aria-label="Your question" className="flex justify-end">
      <p className="max-w-[85%] rounded-md bg-muted px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap text-foreground">
        {content}
      </p>
    </article>
  );
}

function AssistantTurn({ message }: { message: ChatMessageView }) {
  const { selection, selectCitation } = useEvidenceSelection();
  const byNumber = new Map(message.citations.map((item) => [item.n, item]));
  const isActive = (n: number) =>
    selection.kind === 'citation' &&
    selection.messageId === message.id &&
    selection.n === n;
  const select = (citation: Citation) => selectCitation(message.id, citation);

  return (
    <article aria-label="Answer" className="flex flex-col gap-3">
      <Markdown
        content={message.content}
        renderCitation={(n) => (
          <CitationButton
            n={n}
            citation={byNumber.get(n)}
            active={isActive(n)}
            onSelect={select}
          />
        )}
      />
      <SourceList
        citations={message.citations}
        isActive={isActive}
        onSelect={select}
      />
      <p className="text-xs text-muted-foreground tabular-nums">
        {clockTime(message.created_at)}
      </p>
    </article>
  );
}

export function ChatMessage({ message }: { message: ChatMessageView }) {
  return message.role === 'USER' ? (
    <UserTurn content={message.content} />
  ) : (
    <AssistantTurn message={message} />
  );
}
