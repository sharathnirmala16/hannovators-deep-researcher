import type { RobJudgement, SourceView } from '@/domains/workspace';
import { cn } from '@/shared/lib/cn';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/shared/ui/tooltip';

/** robvis convention: green +, yellow -, red x. */
const LIGHT: Record<RobJudgement, { className: string; glyph: string }> = {
  LOW: { className: 'bg-green-600 text-white', glyph: '+' },
  SOME_CONCERNS: { className: 'bg-yellow-400 text-yellow-950', glyph: '−' },
  HIGH: { className: 'bg-red-600 text-white', glyph: '×' },
};

const JUDGEMENT_LABEL: Record<RobJudgement, string> = {
  LOW: 'Low risk',
  SOME_CONCERNS: 'Some concerns',
  HIGH: 'High risk',
};

function Light({
  judgement,
  title,
  large = false,
}: {
  judgement: RobJudgement;
  title: string;
  large?: boolean;
}) {
  const { className, glyph } = LIGHT[judgement];
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          tabIndex={0}
          aria-label={`${title}: ${JUDGEMENT_LABEL[judgement]}`}
          className={cn(
            'inline-flex items-center justify-center rounded-full text-[10px] leading-none font-bold',
            large ? 'size-5 ring-2 ring-background ring-offset-1' : 'size-4',
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
    <TooltipProvider>
      <span className="inline-flex items-center gap-1">
        {Object.entries(rob2.domains).map(([domain, judgement], index) => (
          <Light
            key={domain}
            judgement={judgement}
            title={`D${index + 1} ${domain}`}
          />
        ))}
        <span aria-hidden className="mx-0.5 h-4 w-px bg-border" />
        <Light judgement={rob2.overall} title="Overall" large />
      </span>
    </TooltipProvider>
  );
}
