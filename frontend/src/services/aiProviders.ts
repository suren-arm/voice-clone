import { getJson } from '@/services/apiClient';
import type { AiProvidersInfo } from '@/types';

/**
 * The frontend never guesses which AI providers are configured -- it reads
 * this once and builds the provider selector from the response, the same
 * pattern services/system.ts already uses for languages/limits.
 */
export function getAiProviders(): Promise<AiProvidersInfo> {
  return getJson<AiProvidersInfo>('/api/v1/ai/providers');
}
