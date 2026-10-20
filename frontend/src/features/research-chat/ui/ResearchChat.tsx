import { useMemo, useState } from 'react';

import { useWorkspace } from '@/domains/workspace';

import { suggestedQuestions } from '../model/suggestions';
import { useChat } from '../model/useChat';
import { Composer } from './Composer';
import { MessageList } from './MessageList';

function ChatPanel() {
  const { load } = useWorkspace();
  const chat = useChat();
  const [draft, setDraft] = useState('');
  const state = load.status === 'ready' ? load.state : null;
  const suggestions = useMemo(() => suggestedQuestions(state), [state]);

  const ask = (question: string) => {
    if (!question.trim() || chat.sending) return;
    setDraft('');
    void chat.send(question);
  };

  const edit = (question: string) => {
    chat.dismiss();
    setDraft(question);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <MessageList
        history={chat.history}
        messages={chat.messages}
        pending={chat.pending}
        suggestions={suggestions}
        onAsk={ask}
        onRetryHistory={chat.reloadHistory}
        onRetry={chat.retry}
        onEdit={edit}
      />
      <Composer
        value={draft}
        onChange={setDraft}
        onSubmit={ask}
        sending={chat.sending}
        disabled={chat.history.status !== 'ready'}
      />
    </div>
  );
}

/** Cited research chat: questions answered from the workspace's sources. */
export function ResearchChat() {
  const { workspaceId } = useWorkspace();
  if (!workspaceId) {
    return (
      <p className="p-4 text-sm text-muted-foreground">
        Open a workspace to ask about its evidence.
      </p>
    );
  }
  return <ChatPanel key={workspaceId} />;
}
