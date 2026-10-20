import { plural } from '@/shared/lib/format';
import { Tag } from '@/shared/ui/tag';

import { CATEGORY_STYLE } from '../model/graphStyle';
import type { SourceNode } from '../model/toGraphData';

/** The source in focus: its full title, tier, and how many links it has. */
export function GraphReadout({ node }: { node: SourceNode }) {
  const style = CATEGORY_STYLE[node.category];
  return (
    <div className="pointer-events-none absolute bottom-2 left-2 flex max-w-[min(22rem,calc(100%-3.5rem))] flex-col gap-1 rounded-lg border border-border bg-background px-3 py-2 shadow-[0_4px_12px_rgba(24,34,58,0.12)]">
      <p className="reading line-clamp-2 text-sm font-medium text-foreground">
        {node.label}
      </p>
      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <Tag tone={style.tone}>{style.label}</Tag>
        <span className="tabular-nums">{plural(node.degree, 'link')}</span>
      </p>
    </div>
  );
}
