import {
  isUnavailable,
  type RequestedDomainMode,
  type SeedReferenceRequest,
  type WorkspaceClient,
} from '@/domains/workspace';
import { errorMessage } from '@/shared/lib/format';

import { SEED_KIND_LABEL, type SeedReference } from './seedReference';

export interface WorkspaceDraft {
  question: string;
  mode: RequestedDomainMode;
  autoContinue: boolean;
  files: readonly File[];
  references: readonly SeedReference[];
}

export type CreatePhase = 'creating' | 'seeding' | 'starting';

export interface CreateResult {
  workspaceId: string;
  /** Steps that failed without stopping the workspace from opening. */
  warnings: string[];
}

function seedWarning(what: string, error: unknown): string {
  if (isUnavailable(error)) {
    return `${what} skipped: seed upload is not available on this server yet.`;
  }
  return `${what} not added: ${errorMessage(error)}`;
}

function requestBody({ kind, value }: SeedReference): SeedReferenceRequest {
  if (kind === 'pmid') return { pmid: value };
  if (kind === 'doi') return { doi: value };
  return { url: value };
}

async function addSeeds(
  client: WorkspaceClient,
  id: string,
  draft: WorkspaceDraft,
): Promise<string[]> {
  const warnings: string[] = [];
  if (draft.files.length > 0) {
    try {
      await client.uploadSeedFiles(id, draft.files);
    } catch (error) {
      warnings.push(seedWarning('Seed PDFs', error));
    }
  }
  for (const reference of draft.references) {
    try {
      await client.addSeedReference(id, requestBody(reference));
    } catch (error) {
      const label = `${SEED_KIND_LABEL[reference.kind]} ${reference.value}`;
      warnings.push(seedWarning(label, error));
    }
  }
  return warnings;
}

/**
 * Create -> upload seeds -> start the run. Only a failed create rejects;
 * seed and start failures come back as warnings so the workspace still opens.
 */
export async function createWorkspace(
  client: WorkspaceClient,
  draft: WorkspaceDraft,
  onPhase: (phase: CreatePhase) => void,
): Promise<CreateResult> {
  onPhase('creating');
  const workspace = await client.createWorkspace({
    research_question: draft.question.trim(),
    domain_mode: draft.mode,
    auto_continue: draft.autoContinue,
  });
  onPhase('seeding');
  const warnings = await addSeeds(client, workspace.id, draft);
  onPhase('starting');
  try {
    await client.runWorkspace(workspace.id);
  } catch (error) {
    warnings.push(
      `The run did not start (${errorMessage(error)}). Start it from the workspace.`,
    );
  }
  return { workspaceId: workspace.id, warnings };
}
