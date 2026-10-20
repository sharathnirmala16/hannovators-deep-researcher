import { useEffect, useRef, type ReactNode } from 'react';

import type { ChatMessageView } from '@/domains/workspace';
import { EmptyState, ErrorState, SkeletonBlock } from '@/shared/ui/states';

import type { HistoryLoad, PendingTurn } from '../model/useChat';
import { ChatMessage } from './ChatMessage';
import { TurnStatus } from './TurnStatus';

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

interface MessageListProps {
  history: HistoryLoad;
  messages: readonly ChatMessageView[];
  pending: PendingTurn | null;
  suggestions: readonly string[];
  onAsk: (question: string) => void;
  onRetryHistory: () => void;
  onRetry: () => void;
  onEdit: (question: string) => void;
}

function Suggestions({
  suggestions,
  onAsk,
}: Pick<MessageListProps, 'suggestions' | 'onAsk'>) {
  return (
    <EmptyState title="Ask about the evidence">
      <p>
        Answers come from the sources in this workspace. Every claim cites its
        source: click a number to open the highlighted passage.
      </p>
      {suggestions.length > 0 ? (
        <ul
          aria-label="Suggested questions"
          className="mt-3 flex flex-col gap-1"
        >
          {suggestions.map((question) => (
            <li key={question}>
              <button
                type="button"
                onClick={() => onAsk(question)}
                className="w-full rounded-md bg-background px-3 py-2 text-left text-sm text-foreground transition-colors outline-none hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring"
              >
                {question}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </EmptyState>
  );
}

function HistoryBody(props: MessageListProps): ReactNode {
  const { history, messages, pending } = props;
  if (history.status === 'loading') {
    return <SkeletonBlock lines={4} label="Loading the chat" />;
  }
  if (history.status === 'error') {
    return (
      <ErrorState
        title="The chat history did not load"
        message={history.message}
        onRetry={props.onRetryHistory}
      />
    );
  }
  if (messages.length === 0 && !pending) {
    return <Suggestions suggestions={props.suggestions} onAsk={props.onAsk} />;
  }
  return messages.map((message) => (
    <ChatMessage key={message.id} message={message} />
  ));
}

/** The one scroll container of the chat; it follows the newest turn. */
export function MessageList(props: MessageListProps) {
  const { history, messages, pending } = props;
  const scrollRef = useRef<HTMLDivElement>(null);
  const turns = messages.length;
  const phase = pending ? `${pending.status}:${pending.question}` : '';
  const ready = history.status === 'ready';

  useEffect(() => {
    const element = scrollRef.current;
    if (!element || !ready) return;
    element.scrollTo({
      top: element.scrollHeight,
      behavior: prefersReducedMotion() ? 'auto' : 'smooth',
    });
  }, [ready, turns, phase]);

  return (
    <div
      ref={scrollRef}
      role="log"
      aria-label="Chat messages"
      aria-busy={pending?.status === 'sending'}
      className="scroll-y min-h-0 flex-1"
    >
      <div className="flex flex-col gap-6 px-4 py-4">
        <HistoryBody {...props} />
        {ready && pending ? (
          <TurnStatus
            pending={pending}
            onRetry={props.onRetry}
            onEdit={props.onEdit}
          />
        ) : null}
      </div>
    </div>
  );
}
