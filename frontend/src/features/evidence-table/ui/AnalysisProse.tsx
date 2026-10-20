import type { CitationIndex } from './citations';
import { CitedText } from './CitedText';

interface Block {
  lead: string[];
  items: string[];
}

/** Paragraphs split on blank lines; "- " lines become a list. */
function blocks(text: string): Block[] {
  return text
    .split(/\n\s*\n/)
    .map((paragraph) => paragraph.split('\n').filter((line) => line.trim()))
    .filter((lines) => lines.length > 0)
    .map((lines) => ({
      lead: lines.filter((line) => !line.trimStart().startsWith('- ')),
      items: lines
        .filter((line) => line.trimStart().startsWith('- '))
        .map((line) => line.trimStart().slice(2)),
    }));
}

/** The synthesis analysis as reading prose, about 72 characters wide. */
export function AnalysisProse({
  text,
  citations,
}: {
  text: string;
  citations: CitationIndex;
}) {
  return (
    <div className="reading flex max-w-[72ch] flex-col gap-3 text-sm leading-[22px] text-foreground">
      {blocks(text).map((block, index) => (
        <div key={index} className="flex flex-col gap-1">
          {block.lead.length > 0 ? (
            <p className={block.items.length > 0 ? 'font-medium' : undefined}>
              <CitedText text={block.lead.join(' ')} citations={citations} />
            </p>
          ) : null}
          {block.items.length > 0 ? (
            <ul className="flex list-disc flex-col gap-1 pl-5 marker:text-muted-foreground">
              {block.items.map((item) => (
                <li key={item}>
                  <CitedText text={item} citations={citations} />
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ))}
    </div>
  );
}
