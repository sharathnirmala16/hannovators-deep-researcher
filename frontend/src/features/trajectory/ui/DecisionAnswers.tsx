import { cn } from '@/shared/lib/cn';

import { decisionAnswers, type DecisionAnswerView } from '../model/bodies';
import type { JsonRecord } from '../model/json';
import { formatPercent } from '../model/timing';
import { SectionTitle } from './SectionTitle';

interface DecisionAnswersProps {
  request: JsonRecord;
  response: JsonRecord;
}

/** Jev answers: one block per question with probability bars. */
export function DecisionAnswers({ request, response }: DecisionAnswersProps) {
  const answers = decisionAnswers(request, response);
  if (answers.length === 0) return null;
  return (
    <section className="flex flex-col gap-3">
      <SectionTitle title="Answers" meta={String(answers.length)} />
      {answers.map((answer) => (
        <Answer key={answer.key} answer={answer} />
      ))}
    </section>
  );
}

function Answer({ answer }: { answer: DecisionAnswerView }) {
  const top = answer.probabilities[0]?.[0];
  return (
    <div className="flex flex-col gap-1.5 rounded-md bg-muted/40 px-3 py-2">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-xs">{answer.key}</span>
        {answer.type ? (
          <span className="text-xs text-muted-foreground">{answer.type}</span>
        ) : null}
        {answer.confidence !== null ? (
          <span className="ml-auto text-xs text-muted-foreground tabular-nums">
            Confidence {formatPercent(answer.confidence)}
          </span>
        ) : null}
      </div>
      {answer.instructions ? (
        <p className="text-[13px] text-foreground/80">{answer.instructions}</p>
      ) : null}
      {answer.answer ? (
        <p className="text-[13px]">
          <span className="text-muted-foreground">Answer </span>
          <span className="font-medium">{answer.answer}</span>
        </p>
      ) : null}
      {answer.probabilities.length > 0 ? (
        <ul className="flex flex-col gap-1">
          {answer.probabilities.map(([option, p]) => (
            <li
              key={option}
              className="grid grid-cols-[minmax(0,10rem)_1fr_3rem] items-center gap-2 text-xs"
            >
              <span className="truncate" title={option}>
                {option}
              </span>
              <span className="h-1.5 overflow-hidden rounded-full bg-foreground/10">
                <span
                  className={cn(
                    'block h-full rounded-full',
                    option === top ? 'bg-foreground/70' : 'bg-foreground/30',
                  )}
                  style={{ width: `${Math.min(Math.max(p, 0), 1) * 100}%` }}
                />
              </span>
              <span className="text-right tabular-nums">
                {formatPercent(p)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
