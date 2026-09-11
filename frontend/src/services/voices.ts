import { absoluteUrl, del, getJson, postForm } from '@/services/apiClient';
import type { CreateVoiceInput, Page, Voice } from '@/types';

const BASE = '/api/v1/voices';

export function listVoices(limit = 100, offset = 0): Promise<Page<Voice>> {
  return getJson<Page<Voice>>(`${BASE}?limit=${limit}&offset=${offset}`);
}

export function getVoice(voiceId: string): Promise<Voice> {
  return getJson<Voice>(`${BASE}/${encodeURIComponent(voiceId)}`);
}

export function createVoice(input: CreateVoiceInput): Promise<Voice> {
  const form = new FormData();
  form.append('name', input.name);
  form.append('language', input.language);
  form.append('consent', String(input.consent));
  form.append('source', input.source);
  form.append('audio', input.audio, input.filename);
  // Conditioning runs the speaker encoder; on CPU that is not instant.
  return postForm<Voice>(BASE, form, { timeoutMs: 180_000 });
}

export function deleteVoice(voiceId: string): Promise<{ id: string; deleted: boolean }> {
  return del(`${BASE}/${encodeURIComponent(voiceId)}`);
}

export function voiceSampleUrl(voice: Voice): string | null {
  return voice.sampleUrl ? absoluteUrl(voice.sampleUrl) : null;
}
