import { useState } from 'react';
import { toast } from 'sonner';

import {
  useWorkspaceClient,
  type RequestedDomainMode,
} from '@/domains/workspace';
import { errorMessage } from '@/shared/lib/format';

import { createWorkspace, type CreatePhase } from './createWorkspace';
import type { SeedReference } from './seedReference';

const isPdf = (file: File) =>
  file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

const fileKey = (file: File) => `${file.name}:${file.size}`;

/** Draft, seeds, and submit state of the new-workspace form. */
export function useNewWorkspaceForm(onCreated: (id: string) => void) {
  const client = useWorkspaceClient();
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState<RequestedDomainMode>('AUTO');
  const [autoContinue, setAutoContinue] = useState(true);
  const [files, setFiles] = useState<File[]>([]);
  const [references, setReferences] = useState<SeedReference[]>([]);
  const [phase, setPhase] = useState<CreatePhase | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** Adds the PDFs among `incoming`; returns how many were not PDFs. */
  const addFiles = (incoming: readonly File[]): number => {
    const pdfs = incoming.filter(isPdf);
    setFiles((current) => {
      const known = new Set(current.map(fileKey));
      return [...current, ...pdfs.filter((file) => !known.has(fileKey(file)))];
    });
    return incoming.length - pdfs.length;
  };

  const removeFile = (file: File) =>
    setFiles((current) => current.filter((item) => item !== file));

  const addReference = (reference: SeedReference) =>
    setReferences((current) =>
      current.some(
        (item) =>
          item.kind === reference.kind && item.value === reference.value,
      )
        ? current
        : [...current, reference],
    );

  const removeReference = (reference: SeedReference) =>
    setReferences((current) => current.filter((item) => item !== reference));

  const submit = async () => {
    if (!question.trim() || phase) return;
    setError(null);
    try {
      const result = await createWorkspace(
        client,
        { question, mode, autoContinue, files, references },
        setPhase,
      );
      for (const warning of result.warnings) toast.warning(warning);
      onCreated(result.workspaceId);
    } catch (failure) {
      setError(errorMessage(failure));
      setPhase(null);
    }
  };

  return {
    question,
    setQuestion,
    mode,
    setMode,
    autoContinue,
    setAutoContinue,
    files,
    addFiles,
    removeFile,
    references,
    addReference,
    removeReference,
    phase,
    error,
    submit,
    canSubmit: question.trim().length > 0 && phase === null,
  };
}
