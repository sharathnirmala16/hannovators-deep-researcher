import type { Decomposition } from '@/domains/workspace';

import { PICOTS_FIELDS, SCOPE_FIELDS } from '../model/scopeFields';
import { ScopeFields } from './ScopeFields';

interface ScopeFieldListProps {
  value: Decomposition;
  question: string | null;
  editable: boolean;
  onChange: (next: Decomposition) => void;
}

/** Picks the PICOTS or the general scope fields for the decomposition. */
export function ScopeFieldList({
  value,
  question,
  editable,
  onChange,
}: ScopeFieldListProps) {
  if (value.mode === 'MEDICAL') {
    return (
      <ScopeFields
        fields={PICOTS_FIELDS}
        value={value}
        question={question}
        editable={editable}
        onChange={onChange}
      />
    );
  }
  return (
    <ScopeFields
      fields={SCOPE_FIELDS}
      value={value}
      question={question}
      editable={editable}
      onChange={onChange}
    />
  );
}
