import type { RequestedDomainMode } from '@/domains/workspace';

/** What each research mode does, in plain words. */
export const MODE_HINT: Record<RequestedDomainMode, string> = {
  AUTO: 'Auto tells a health question from any other kind.',
  MEDICAL:
    'Medical reads clinical studies, checks them for bias, and grades how sure the evidence is.',
  GENERAL:
    'General works for any topic: it compares claims and checks how credible each source is.',
};
