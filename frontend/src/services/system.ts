import { getJson } from '@/services/apiClient';
import type { SystemInfo } from '@/types';

/**
 * The UI reads its language list, upload limits and character limits from the
 * server rather than hardcoding them, so swapping the engine (or enabling the
 * experimental Armenian path) needs no frontend change.
 */
export function getSystemInfo(): Promise<SystemInfo> {
  return getJson<SystemInfo>('/api/v1/system/info');
}
