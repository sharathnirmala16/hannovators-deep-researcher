import { SectionHeader } from '@/shared/ui/section-header';

import { llmPrompt } from '../model/bodies';
import type { JsonRecord } from '../model/json';
import { FactList } from './FactList';
import { LongText } from './LongText';

/** Model, role, and the system and user prompts of an LLM call. */
export function LlmPromptView({ request }: { request: JsonRecord }) {
  const prompt = llmPrompt(request);
  if (!prompt.system && !prompt.user && !prompt.model) return null;
  return (
    <section className="flex flex-col gap-3">
      <SectionHeader title="Prompt" />
      <FactList
        facts={[
          {
            label: 'Model',
            value: prompt.model ? (
              <span className="font-mono text-xs">{prompt.model}</span>
            ) : null,
          },
          { label: 'Role', value: prompt.role },
        ]}
      />
      {prompt.system ? (
        <LongText label="System prompt" text={prompt.system} />
      ) : null}
      {prompt.user ? <LongText label="User prompt" text={prompt.user} /> : null}
    </section>
  );
}
