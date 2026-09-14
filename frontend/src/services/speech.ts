import { absoluteUrl, del, getJson, postJson } from '@/services/apiClient';
import type { GenerateSpeechInput, Generation, Page } from '@/types';

export function generateSpeech(input: GenerateSpeechInput): Promise<Generation> {
  // Generation is synchronous server-side; give it room for long text on CPU.
  return postJson<Generation>('/api/v1/speech', input, { timeoutMs: 300_000 });
}

export function listGenerations(voiceId?: string, limit = 50, offset = 0): Promise<Page<Generation>> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (voiceId) params.set('voiceId', voiceId);
  return getJson<Page<Generation>>(`/api/v1/generations?${params}`);
}

/**
 * A Book Reader narration returns a lightweight book-specific wrapper
 * (see services/books.ts's narrateBook), not a full Generation -- this
 * fetches the real one so the existing player/download UI can be reused
 * completely unchanged.
 */
export function getGeneration(id: string): Promise<Generation> {
  return getJson<Generation>(`/api/v1/generations/${encodeURIComponent(id)}`);
}

export function deleteGeneration(id: string): Promise<{ id: string; deleted: boolean }> {
  return del(`/api/v1/generations/${encodeURIComponent(id)}`);
}

export function generationAudioUrl(generation: Generation): string {
  return absoluteUrl(generation.audioUrl);
}

export function generationDownloadUrl(generation: Generation): string {
  return `${absoluteUrl(generation.audioUrl)}?download=true`;
}
