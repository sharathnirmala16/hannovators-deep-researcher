import { useMemo, useState } from 'react';

import { useEvidenceSelection } from '@/domains/evidence';
import { useWorkspace, type DeepResearchRecord } from '@/domains/workspace';
import { Button } from '@/shared/ui/button';

import { parseReport } from '../model/report';
import { ReportBlock } from './ReportBlock';
import { ReportSources } from './ReportSources';

type ReportSource = DeepResearchRecord['sources'][number];

const PREVIEW_BLOCKS = 4;

/** The Tavily report with numbered citations and its source list. */
export function DeepResearchReport({ record }: { record: DeepResearchRecord }) {
  const { recordAction } = useWorkspace();
  const { selectSource } = useEvidenceSelection();
  const blocks = useMemo(() => parseReport(record.content), [record.content]);
  const [expanded, setExpanded] = useState(false);
  const [active, setActive] = useState<number | null>(null);
  const shown = expanded ? blocks : blocks.slice(0, PREVIEW_BLOCKS);

  const open = (n: number, source: ReportSource | undefined) => {
    setActive(n);
    recordAction({
      name: 'user.citation.open',
      summary: `Opened deep research source [${n}]`,
      target: source?.url ?? null,
      source_ids: source?.source_id ? [source.source_id] : [],
      details: { report: 'deep_research', n },
    });
    if (source?.source_id) selectSource(source.source_id);
  };
  const onCite = (n: number) => {
    setExpanded(true);
    open(n, record.sources[n - 1]);
  };

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="reading flex min-w-0 flex-col gap-2 text-sm leading-6 break-words text-foreground">
        {shown.map((block, index) => (
          <ReportBlock
            key={index}
            block={block}
            active={active}
            onCite={onCite}
          />
        ))}
        {blocks.length > PREVIEW_BLOCKS ? (
          <Button
            size="xs"
            variant="ghost"
            className="self-start font-sans"
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? 'Show less' : 'Show the full report'}
          </Button>
        ) : null}
      </div>
      {record.sources.length > 0 ? (
        <ReportSources sources={record.sources} active={active} onOpen={open} />
      ) : null}
    </div>
  );
}
