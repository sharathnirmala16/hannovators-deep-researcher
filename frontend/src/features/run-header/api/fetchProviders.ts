import { z } from 'zod';

/** `GET /api/health/providers` (routers/health.py). Never contains keys. */
const providerHealthSchema = z.object({
  provider_mode: z.string(),
  ports: z.record(
    z.string(),
    z.object({
      implementation: z.string(),
      provider: z.string(),
      key: z.string(),
      note: z.string().nullable().optional(),
    }),
  ),
});

export type ProviderHealth = z.infer<typeof providerHealthSchema>;

/** Null when the endpoint is missing or returns an unexpected shape. */
export async function fetchProviders(
  signal: AbortSignal,
): Promise<ProviderHealth | null> {
  try {
    const response = await fetch('/api/health/providers', { signal });
    if (!response.ok) return null;
    const decoded = providerHealthSchema.safeParse(await response.json());
    return decoded.success ? decoded.data : null;
  } catch {
    return null;
  }
}
