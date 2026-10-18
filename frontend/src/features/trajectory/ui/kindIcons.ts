import {
  Binary,
  BrainCircuit,
  Download,
  Gavel,
  Globe,
  MessagesSquare,
  Milestone,
  MousePointerClick,
  Scale,
  Search,
  TextSearch,
  type LucideIcon,
} from 'lucide-react';

import type { TrajectoryKind } from '@/domains/workspace';

export const KIND_ICON: Record<TrajectoryKind, LucideIcon> = {
  STAGE: Milestone,
  LLM: BrainCircuit,
  DECISION: Scale,
  SEARCH: Search,
  FETCH: Globe,
  DOWNLOAD: Download,
  EMBED: Binary,
  RETRIEVE: TextSearch,
  VERDICT: Gavel,
  USER_ACTION: MousePointerClick,
  CHAT: MessagesSquare,
};
