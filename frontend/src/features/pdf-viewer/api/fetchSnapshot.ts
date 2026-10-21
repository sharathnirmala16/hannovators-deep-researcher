/** Reads a web snapshot (`snapshot.md`) served under `/files/`. */
export async function fetchSnapshot(
  url: string,
  signal: AbortSignal,
): Promise<string> {
  const response = await fetch(url, { signal });
  const type = response.headers.get('content-type') ?? '';
  if (!response.ok || type.includes('text/html')) {
    throw new Error(`Snapshot is not available (HTTP ${response.status}).`);
  }
  const text = await response.text();
  if (
    type.includes('application/pdf') ||
    text.trimStart().startsWith('%PDF-')
  ) {
    throw new Error(
      'This snapshot holds PDF data, not text. Acquire the source again to view it as a PDF.',
    );
  }
  return text;
}
