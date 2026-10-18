import { llmReply } from '../model/bodies';
import type { JsonRecord } from '../model/json';
import { JsonView } from './JsonView';
import { LongText } from './LongText';
import { SectionTitle } from './SectionTitle';

/** The parsed reply, one section per top-level field. */
export function LlmReplyView({ response }: { response: JsonRecord }) {
  const sections = llmReply(response);
  if (sections.length === 0) return null;
  return (
    <section className="flex flex-col gap-3">
      {sections.map((section) => (
        <div key={section.label} className="flex flex-col gap-1.5">
          <SectionTitle title={humanize(section.label)} />
          {typeof section.value === 'string' ? (
            <LongText text={section.value} />
          ) : (
            <JsonView value={section.value} />
          )}
        </div>
      ))}
    </section>
  );
}

/** `pairwise_summaries` -> `Pairwise summaries`. */
function humanize(label: string): string {
  const words = label.replace(/[_-]+/g, ' ').trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : label;
}
