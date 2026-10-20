import { SectionHeader } from '@/shared/ui/section-header';

import { decisionAnswers } from '../model/bodies';
import type { JsonRecord } from '../model/json';
import { DecisionAnswer } from './DecisionAnswer';

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
      <SectionHeader title="Answers" meta={<span>{answers.length}</span>} />
      {answers.map((answer) => (
        <DecisionAnswer key={answer.key} answer={answer} />
      ))}
    </section>
  );
}
