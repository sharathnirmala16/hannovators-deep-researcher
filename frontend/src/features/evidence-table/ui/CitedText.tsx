import { plainMath } from '@/shared/lib/plainMath';

import { citedSegments, type CitationIndex } from './citations';
import { SourceCitation } from './SourceCitation';

/** Prose with its source citations drawn as marked buttons. */
export function CitedText({
  text,
  citations,
}: {
  text: string;
  citations: CitationIndex;
}) {
  return (
    <>
      {citedSegments(plainMath(text), citations).map((segment, index) =>
        segment.kind === 'text' ? (
          <span key={`t${index}`}>{segment.text}</span>
        ) : (
          <SourceCitation key={`c${segment.key}`} source={segment.source} />
        ),
      )}
    </>
  );
}
