import { llmPrompt } from '../model/bodies';
import type { JsonRecord } from '../model/json';
import { FactList } from './FactList';
import { LongText } from './LongText';
import { SectionTitle } from './SectionTitle';

/** Model, role, and the system and user prompts of an LLM call. */
export function LlmPromptView({ request }: { request: JsonRecord }) {
  const prompt = llmPrompt(request);
  if (!prompt.system && !prompt.user && !prompt.model) return null;
  return (
    <section className="flex flex-col gap-3">
      <FactList
        facts={[
          { label: 'Model', value: prompt.model },
          { label: 'Role', value: prompt.role },
        ]}
      />
      {prompt.system ? (
        <div className="flex flex-col gap-1.5">
          <SectionTitle title="System prompt" />
          <LongText text={prompt.system} />
        </div>
      ) : null}
      {prompt.user ? (
        <div className="flex flex-col gap-1.5">
          <SectionTitle title="User prompt" />
          <LongText text={prompt.user} />
        </div>
      ) : null}
    </section>
  );
}
