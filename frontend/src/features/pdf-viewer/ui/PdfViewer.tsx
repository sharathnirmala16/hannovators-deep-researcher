import {
  useEvidenceSelection,
  type EvidenceSelection,
} from '@/domains/evidence';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/ui/card';

function describe(selection: EvidenceSelection): string {
  switch (selection.kind) {
    case 'none':
      return 'Nothing selected.';
    case 'source':
      return `Source ${selection.sourceId}, page ${selection.page ?? 1}.`;
    case 'claim':
      return `Claim ${selection.claimId} has no highlight.`;
    case 'highlight':
      return `Source ${selection.sourceId}, page ${selection.page}.`;
  }
}

/** Placeholder entry. Lane F5 builds the highlighted PDF iframe. */
export function PdfViewer() {
  const { selection } = useEvidenceSelection();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Source viewer</CardTitle>
        <CardDescription>
          Placeholder (F5): highlighted PDF at the selected page.
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm">{describe(selection)}</CardContent>
    </Card>
  );
}
