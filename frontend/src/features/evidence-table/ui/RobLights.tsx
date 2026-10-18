import type { RobJudgement, SourceView } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/ui/tooltip';

/** robvis convention: green +, yellow -, red x. */
const LIGHT: Record<RobJudgement, { className: string; glyph: string }> = {
  LOW: { className: 'bg-rob-low text-white', glyph: '+' },
  SOME_CONCERNS: { className: 'bg-rob-some text-ink', glyph: '−' },
  HIGH: { className: 'bg-rob-high text-white', glyph: '×' },
};

const JUDGEMENT_LABEL: Record<RobJudgement, string> = {
  LOW: 'Low risk',
  SOME_CONCERNS: 'Some concerns',
  HIGH: 'High risk',
};

function Light({
  judgement,
  title,
  overall = false,
}: {
  judgement: RobJudgement;
  title: string;
  overall?: boolean;
}) {
  const { className, glyph } = LIGHT[judgement];
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          aria-label={`${title}: ${JUDGEMENT_LABEL[judgement]}`}
          className={cn(
            'inline-flex items-center justify-center rounded-full text-[10px] leading-none font-bold focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
            overall ? 'size-[18px]' : 'size-3.5',
            className,
          )}
        >
          {glyph}
        </span>
      </TooltipTrigger>
      <TooltipContent>
        {title}: {JUDGEMENT_LABEL[judgement]}
      </TooltipContent>
    </Tooltip>
  );
}

/** RoB 2 traffic lights: one per domain (D1 to D5), then the overall one. */
export function RobLights({ rob2 }: { rob2: SourceView['rob2'] }) {
  if (!rob2) {
    return <span className="text-xs text-muted-foreground">Not assessed</span>;
  }
  return (
    <span className="inline-flex items-center gap-0.5">
      {Object.entries(rob2.domains).map(([domain, judgement], index) => (
        <Light
          key={domain}
          judgement={judgement}
          title={`D${index + 1} ${domain}`}
        />
      ))}
      <span aria-hidden className="mx-1 h-3 w-px bg-border" />
      <Light judgement={rob2.overall} title="Overall" overall />
    </span>
  );
}
