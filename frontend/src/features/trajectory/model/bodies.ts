/**
 * Readers for the request and response bodies that PLAN.md section 5.3 lists
 * per kind. Bodies are free-form JSON, so every reader is tolerant: it returns
 * what it can find and the UI always shows the raw JSON as well.
 */
import {
  asArray,
  asNumber,
  asText,
  isRecord,
  numberOf,
  pick,
  textOf,
  type JsonRecord,
} from './json';

export interface DecisionAnswerView {
  key: string;
  instructions: string | null;
  type: string | null;
  /** The chosen option, score, or yes/no probability as text. */
  answer: string | null;
  confidence: number | null;
  /** Options with their probabilities, highest first. */
  probabilities: readonly (readonly [string, number])[];
}

function probabilitiesOf(answer: JsonRecord): [string, number][] {
  const raw = pick(answer, ['probabilities', 'distribution']);
  if (!isRecord(raw)) return [];
  return Object.entries(raw)
    .flatMap(([label, value]): [string, number][] => {
      const p = asNumber(value);
      return p === null ? [] : [[label, p]];
    })
    .sort((a, b) => b[1] - a[1]);
}

function answerText(answer: JsonRecord): string | null {
  const noul = numberOf(answer, ['noul']);
  if (noul !== null) return `yes ${Math.round(noul * 100)}%`;
  return textOf(answer, ['choice', 'score', 'answer', 'value']);
}

function questionsOf(request: JsonRecord): JsonRecord {
  const questions = pick(request, ['questions']);
  return isRecord(questions) ? questions : {};
}

/** Jev answers keyed by question (`response.answers` or the body itself). */
export function decisionAnswers(
  request: JsonRecord,
  response: JsonRecord,
): DecisionAnswerView[] {
  const nested = pick(response, ['answers', 'decisions']);
  const answers = isRecord(nested) ? nested : response;
  const questions = questionsOf(request);
  return Object.entries(answers).flatMap(([key, value]) => {
    if (!isRecord(value)) return [];
    const question = questions[key];
    return [
      {
        key,
        instructions: isRecord(question)
          ? textOf(question, ['instructions', 'question'])
          : null,
        type: textOf(value, ['type']),
        answer: answerText(value),
        confidence: numberOf(value, ['confidence']),
        probabilities: probabilitiesOf(value),
      },
    ];
  });
}

export interface SearchHit {
  title: string;
  url: string | null;
  snippet: string | null;
}

export interface SearchView {
  provider: string | null;
  query: string | null;
  hitCount: number | null;
  hits: readonly SearchHit[];
}

function hitOf(value: unknown): SearchHit[] {
  const url = asText(value);
  if (url) return [{ title: url, url, snippet: null }];
  if (!isRecord(value)) return [];
  const link = textOf(value, ['url', 'link', 'pdf_url']);
  const title = textOf(value, ['title', 'name', 'external_id']) ?? link;
  if (!title) return [];
  return [
    { title, url: link, snippet: textOf(value, ['snippet', 'abstract']) },
  ];
}

export function searchView(
  request: JsonRecord,
  response: JsonRecord,
): SearchView {
  const raw = pick(response, ['results', 'hits', 'records', 'candidates']);
  const urls = pick(response, ['result_urls', 'urls']);
  const hits = asArray(raw ?? urls).flatMap(hitOf);
  return {
    provider: textOf(response, ['provider']) ?? textOf(request, ['provider']),
    query: textOf(request, ['query', 'q', 'term']),
    hitCount:
      numberOf(response, ['hit_count', 'count', 'total', 'hits_total']) ??
      (raw === undefined && urls === undefined ? null : hits.length),
    hits,
  };
}

export interface VerdictFact {
  label: string;
  value: string;
}

const VERDICT_FACTS: readonly (readonly [string, readonly string[]])[] = [
  ['Rejection code', ['rejection_code', 'code']],
  ['Votes', ['votes', 'screen_votes', 'vote_count']],
  ['z-score', ['z', 'z_score', 'screen_z']],
  ['M-score', ['m_score', 'm']],
  ['Relevance', ['relevance', 'screen_score', 'score']],
  ['Evidence level', ['evidence_level']],
  ['Stance', ['stance']],
  ['Search intent', ['search_intent', 'intent']],
  ['Directness', ['directness']],
  ['RoB 2', ['rob2', 'rob']],
];

function factValue(value: unknown): string | null {
  const number = asNumber(value);
  if (typeof value === 'number' && number !== null) {
    return Number.isInteger(number) ? String(number) : number.toFixed(2);
  }
  if (isRecord(value) || Array.isArray(value)) return JSON.stringify(value);
  return asText(value);
}

export interface VerdictView {
  reason: string | null;
  facts: readonly VerdictFact[];
}

export function verdictView(response: JsonRecord): VerdictView {
  return {
    reason: textOf(response, [
      'reason',
      'explanation',
      'decision_explanation',
      'message',
    ]),
    facts: VERDICT_FACTS.flatMap(([label, keys]) => {
      const value = factValue(pick(response, keys));
      return value === null ? [] : [{ label, value }];
    }),
  };
}

export interface LlmPrompt {
  role: string | null;
  model: string | null;
  system: string | null;
  user: string | null;
}

export function llmPrompt(request: JsonRecord): LlmPrompt {
  return {
    role: textOf(request, ['role']),
    model: textOf(request, ['model']),
    system: textOf(request, ['system', 'system_prompt']),
    user: textOf(request, ['user', 'user_prompt', 'prompt']),
  };
}

export interface ReplySection {
  label: string;
  value: unknown;
}

/** Top-level sections of the parsed reply (`parsed`, `reply`, or the body). */
export function llmReply(response: JsonRecord): ReplySection[] {
  const parsed = pick(response, ['parsed', 'reply', 'output', 'content']);
  if (parsed === undefined) {
    return Object.entries(response).map(([label, value]) => ({ label, value }));
  }
  if (!isRecord(parsed)) return [{ label: 'Reply', value: parsed }];
  return Object.entries(parsed).map(([label, value]) => ({ label, value }));
}
