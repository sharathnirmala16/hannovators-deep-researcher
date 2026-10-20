import type { DecisionAnswerView } from '../model/bodies';
import { formatPercent } from '../model/timing';
import { ProbabilityBar } from './ProbabilityBar';

/** The chosen option: the named answer when it is an option, else the top one. */
function chosenOption(answer: DecisionAnswerView): string | undefined {
  const named = answer.probabilities.find(
    ([option]) => option === answer.answer,
  );
  return named?.[0] ?? answer.probabilities[0]?.[0];
}

/** One question: its instructions, the answer, and the option probabilities. */
export function DecisionAnswer({ answer }: { answer: DecisionAnswerView }) {
  const chosen = chosenOption(answer);
  return (
    <div className="flex flex-col gap-2 rounded-md bg-shade-0 px-3 py-3">
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-xs text-foreground">{answer.key}</span>
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
        <p className="max-w-prose text-sm text-foreground">
          {answer.instructions}
        </p>
      ) : null}
      {answer.answer ? (
        <p className="text-sm">
          <span className="text-muted-foreground">Answer </span>
          <span className="font-semibold text-tone-null">{answer.answer}</span>
        </p>
      ) : null}
      {answer.probabilities.length > 0 ? (
        <ul aria-label="Option probabilities" className="flex flex-col gap-1.5">
          {answer.probabilities.map(([option, p]) => (
            <ProbabilityBar
              key={option}
              option={option}
              probability={p}
              chosen={option === chosen}
            />
          ))}
        </ul>
      ) : null}
    </div>
  );
}
