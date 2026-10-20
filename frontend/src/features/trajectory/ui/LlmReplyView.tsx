import { SectionHeader } from '@/shared/ui/section-header';

import { llmReply } from '../model/bodies';
import type { JsonRecord } from '../model/json';
import { JsonView } from './JsonView';
import { LongText } from './LongText';

/** The parsed reply, one labeled block per top-level field. */
export function LlmReplyView({ response }: { response: JsonRecord }) {
  const sections = llmReply(response);
  if (sections.length === 0) return null;
  return (
    <section className="flex flex-col gap-3">
      <SectionHeader title="Reply" />
      {sections.map((section) =>
        isScalar(section.value) ? (
          <LongText
            key={section.label}
            label={humanize(section.label)}
            text={String(section.value)}
          />
        ) : (
          <div key={section.label} className="flex flex-col gap-1.5">
            <h4 className="text-xs font-semibold text-muted-foreground">
              {humanize(section.label)}
            </h4>
            <JsonView value={section.value} />
          </div>
        ),
      )}
    </section>
  );
}

/** Text, numbers, booleans, and null read as prose; containers as JSON. */
function isScalar(value: unknown): boolean {
  return value === null || typeof value !== 'object';
}

/** `pairwise_summaries` -> `Pairwise summaries`. */
function humanize(label: string): string {
  const words = label.replace(/[_-]+/g, ' ').trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : label;
}
