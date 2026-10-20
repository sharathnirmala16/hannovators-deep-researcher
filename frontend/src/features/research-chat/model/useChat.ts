import { useCallback, useEffect, useRef, useState } from 'react';

import { useWorkspace, type ChatMessageView } from '@/domains/workspace';
import { errorMessage } from '@/shared/lib/format';

export type HistoryLoad =
  | { status: 'loading' }
  | { status: 'ready' }
  | { status: 'error'; message: string };

/** The question being answered, or the one whose answer failed. */
export type PendingTurn =
  | { status: 'sending'; question: string }
  | { status: 'failed'; question: string; message: string };

function userTurn(answer: ChatMessageView, question: string): ChatMessageView {
  return {
    ...answer,
    id: `local-${answer.id}`,
    role: 'USER',
    content: question,
    citations: [],
    trajectory_step_id: null,
  };
}

/**
 * The workspace chat: history (oldest first), the turn in flight, and send /
 * retry. Mount it under a `key` of the workspace ID so it resets per workspace.
 */
export function useChat() {
  const { client, workspaceId } = useWorkspace();
  const [history, setHistory] = useState<HistoryLoad>({ status: 'loading' });
  const [messages, setMessages] = useState<ChatMessageView[]>([]);
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const [token, setToken] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!workspaceId) return undefined;
    const controller = new AbortController();
    client.listChat(workspaceId, controller.signal).then(
      (list) => {
        setMessages(list);
        setHistory({ status: 'ready' });
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        setHistory({ status: 'error', message: errorMessage(error) });
      },
    );
    return () => controller.abort();
  }, [client, workspaceId, token]);

  const reloadHistory = useCallback(() => {
    setHistory({ status: 'loading' });
    setToken((value) => value + 1);
  }, []);

  const sending = pending?.status === 'sending';

  const send = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || !workspaceId || sending) return;
      setPending({ status: 'sending', question: text });
      try {
        const answer = await client.ask(workspaceId, text);
        if (!mounted.current) return;
        setMessages((previous) => [
          ...previous,
          userTurn(answer, text),
          answer,
        ]);
        setPending(null);
      } catch (error) {
        if (!mounted.current) return;
        const message = errorMessage(error);
        setPending({ status: 'failed', question: text, message });
      }
    },
    [client, workspaceId, sending],
  );

  const retry = useCallback(() => {
    if (pending?.status === 'failed') void send(pending.question);
  }, [pending, send]);

  const dismiss = useCallback(() => setPending(null), []);

  return {
    history,
    messages,
    pending,
    sending,
    send,
    retry,
    dismiss,
    reloadHistory,
  };
}
