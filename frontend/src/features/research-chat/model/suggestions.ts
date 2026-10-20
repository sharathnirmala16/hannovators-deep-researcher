import type {
  PicotsDecomposition,
  ScopeDecomposition,
  WorkspaceState,
} from '@/domains/workspace';

const MAX_SUGGESTIONS = 3;
/** Scope terms can be whole sentences; longer questions read as noise. */
const MAX_SUGGESTION_CHARS = 120;

const GENERIC = [
  'What is the strongest evidence for the main finding?',
  'Which sources report opposing or null results?',
  'What are the main limitations of the included evidence?',
];

function lowerFirst(text: string): string {
  return text.charAt(0).toLowerCase() + text.slice(1);
}

function picotsQuestions(scope: PicotsDecomposition): string[] {
  const pair = scope.ic_pairs[0];
  const intervention = pair?.intervention ?? scope.interventions[0];
  const comparison = pair?.comparison ?? scope.comparisons[0];
  const [first, second] = scope.outcomes;
  const questions: string[] = [];
  if (intervention && comparison && first) {
    questions.push(
      `What is the effect of ${intervention} versus ${lowerFirst(comparison)} on ${lowerFirst(first)}?`,
    );
  }
  if (second) {
    questions.push(`What do the trials report for ${lowerFirst(second)}?`);
  }
  if (intervention) {
    questions.push(`Is there evidence against ${intervention}?`);
  }
  return questions;
}

function scopeQuestions(scope: ScopeDecomposition): string[] {
  const [claim] = scope.claims;
  const [counter] = scope.counter_hypotheses;
  const [metric] = scope.metrics;
  const questions: string[] = [];
  if (claim) questions.push(`What evidence supports this: ${claim}?`);
  if (counter) questions.push(`How strong is the counter-view: ${counter}?`);
  if (metric) {
    questions.push(`What do the sources report for ${lowerFirst(metric)}?`);
  }
  return questions;
}

/** Two or three first questions derived from the workspace scope. */
export function suggestedQuestions(state: WorkspaceState | null): string[] {
  const scope = state?.decomposition;
  const derived = !scope
    ? []
    : scope.mode === 'MEDICAL'
      ? picotsQuestions(scope)
      : scopeQuestions(scope);
  const short = derived.filter((q) => q.length <= MAX_SUGGESTION_CHARS);
  return [...new Set([...short, ...GENERIC])].slice(0, MAX_SUGGESTIONS);
}
