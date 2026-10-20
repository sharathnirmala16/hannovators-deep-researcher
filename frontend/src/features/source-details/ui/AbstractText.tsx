import { plainMath } from '@/shared/lib/plainMath';
import { SectionHeader } from '@/shared/ui/section-header';

import { humanize } from '../model/record';

/** "RESULTS: Sixty patients..." keeps its heading, set in sentence case. */
const HEADING = /^([A-Z][A-Z /&-]{2,40}):\s*/;

function paragraphs(text: string): { heading: string | null; body: string }[] {
  return text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = HEADING.exec(line);
      return match?.[1]
        ? { heading: humanize(match[1]), body: line.slice(match[0].length) }
        : { heading: null, body: line };
    });
}

/** The abstract as reading text, structured headings kept. */
export function AbstractText({ text }: { text: string }) {
  return (
    <section aria-labelledby="source-abstract" className="flex flex-col gap-2">
      <SectionHeader id="source-abstract" title="Abstract" />
      <div className="reading flex max-w-[72ch] flex-col gap-2 text-sm leading-[22px] text-foreground">
        {paragraphs(plainMath(text)).map((paragraph, index) => (
          <p key={index}>
            {paragraph.heading ? (
              <span className="font-semibold">{paragraph.heading}. </span>
            ) : null}
            {paragraph.body}
          </p>
        ))}
      </div>
    </section>
  );
}
