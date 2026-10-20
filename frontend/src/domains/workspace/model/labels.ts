import type { Tone } from '@/shared/ui/tag';

import {
  evidenceLevelSchema,
  type EvidenceLevel,
  type EvidenceStance,
  type GradeCertainty,
  type RejectionCode,
  type RequestedDomainMode,
  type SearchIntent,
  type SourceDecisionKind,
  type SourceStatus,
  type WorkspaceStatus,
} from '../api/enums';
import type { SourceView } from '../api/schema';

interface Labelled {
  label: string;
  tone: Tone;
}

export const WORKSPACE_STATUS: Record<WorkspaceStatus, Labelled> = {
  CREATED: { label: 'Not started', tone: 'neutral' },
  RUNNING: { label: 'Running', tone: 'info' },
  AWAITING_REVIEW: { label: 'Awaiting review', tone: 'caution' },
  COMPLETED: { label: 'Completed', tone: 'positive' },
  FAILED: { label: 'Failed', tone: 'negative' },
};

/** Kept (green), removed (red), flagged (amber), still open (neutral). */
export const SOURCE_STATUS: Record<SourceStatus, Labelled> = {
  SEED: { label: 'Seed', tone: 'info' },
  RAW: { label: 'Not screened', tone: 'neutral' },
  SCREEN_PROMOTED: { label: 'Passed screening', tone: 'positive' },
  SCREEN_DISCOUNTED: { label: 'Screened out', tone: 'negative' },
  APPRAISE_PROMOTED: { label: 'Included', tone: 'positive' },
  APPRAISE_DISCOUNTED: { label: 'Excluded', tone: 'negative' },
  ACQUIRE_FAILED: { label: 'No full text', tone: 'caution' },
};

/** A researcher's override, named for the person who made it. */
export const SOURCE_DECISION: Record<SourceDecisionKind, Labelled> = {
  INCLUDE: { label: 'Included by you', tone: 'positive' },
  EXCLUDE: { label: 'Excluded by you', tone: 'negative' },
};

/** Sources whose manual decision no re-synthesis has used yet. */
export function pendingDecisions(sources: readonly SourceView[]): SourceView[] {
  return sources.filter((source) => source.decision?.applied === false);
}

export const EVIDENCE_LEVEL: Record<EvidenceLevel, string> = {
  META_ANALYSIS: 'Meta-analysis',
  SYSTEMATIC_REVIEW: 'Systematic review',
  RCT: 'RCT',
  NON_RANDOMIZED_TRIAL: 'Non-randomized trial',
  COHORT: 'Cohort',
  CASE_CONTROL: 'Case-control',
  CROSS_SECTIONAL: 'Cross-sectional',
  CASE_SERIES: 'Case series',
  GUIDELINE: 'Guideline',
  NARRATIVE_REVIEW: 'Narrative review',
  PRECLINICAL: 'Preclinical',
  WEB_REPORT: 'Web report',
  OTHER: 'Other',
};

export const STANCE: Record<EvidenceStance, Labelled> = {
  SUPPORTS: { label: 'Supports', tone: 'positive' },
  OPPOSES: { label: 'Opposes', tone: 'negative' },
  NULL_RESULT: { label: 'Null result', tone: 'null' },
  MIXED: { label: 'Mixed', tone: 'caution' },
  ALTERNATIVE: { label: 'Alternative', tone: 'info' },
  UNCLEAR: { label: 'Unclear', tone: 'neutral' },
};

export const SEARCH_INTENT: Record<
  SearchIntent,
  { label: string; hint: string }
> = {
  CORE: { label: 'Core', hint: 'The question as asked' },
  NEGATIVE: { label: 'Negative', hint: 'Null, harm, failed, or stopped' },
  ALTERNATIVE: { label: 'Alternatives', hint: 'Other options to compare' },
  SAFETY: { label: 'Safety', hint: 'Adverse effects and risks' },
  SEED_CITATION: { label: 'Seed citations', hint: 'Cited by the seeds' },
  DEEP_RESEARCH: { label: 'Deep research', hint: 'From the Tavily report' },
};

export const CERTAINTY_TONE: Record<GradeCertainty, Tone> = {
  HIGH: 'positive',
  MODERATE: 'info',
  LOW: 'caution',
  VERY_LOW: 'negative',
};

export const REJECTION: Record<RejectionCode, string> = {
  LOW_RELEVANCE: 'Low relevance',
  VOTES_BELOW_T: 'Too few screening votes',
  M_BELOW_THRESHOLD: 'Below the appraisal threshold',
  ANIMAL_STUDY: 'Animal study',
  REVIEW_OR_EDITORIAL: 'Review or editorial',
  OFF_TOPIC: 'Off topic',
  DUPLICATE: 'Duplicate',
  NO_FULL_TEXT: 'No full text',
  UNDERPOWERED: 'Underpowered',
  LOW_CREDIBILITY: 'Low credibility',
};

export const DOMAIN_MODE: Record<RequestedDomainMode, string> = {
  AUTO: 'Auto',
  MEDICAL: 'Medical',
  GENERAL: 'General',
};

const UNRANKED = 99;

/** Evidence rank (1 = strongest); unclassified sources sort last. */
export function evidenceRank(source: SourceView): number {
  if (source.evidence_rank !== null) return source.evidence_rank;
  if (source.evidence_level === null) return UNRANKED;
  return evidenceLevelSchema.options.indexOf(source.evidence_level) + 1;
}

/** Opposing, null, or mixed evidence: always shown, never collapsed. */
export function isCounterEvidence(source: SourceView): boolean {
  return (
    source.stance === 'OPPOSES' ||
    source.stance === 'NULL_RESULT' ||
    source.stance === 'MIXED'
  );
}

/** Seeds and sources kept by screening or appraisal. */
export function isKeptSource(source: SourceView): boolean {
  return (
    source.status === 'SEED' ||
    source.status === 'SCREEN_PROMOTED' ||
    source.status === 'APPRAISE_PROMOTED'
  );
}

/** "Heidenreich 2022", else the title. */
export function studyLabel(source: SourceView): string {
  const author = source.authors[0]?.split(' ')[0];
  if (author && source.year) return `${author} ${source.year}`;
  return source.title;
}
