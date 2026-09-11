/**
 * API contract types.
 *
 * These mirror the FastAPI response models one-for-one. The backend serialises
 * camelCase specifically so this file needs no translation layer, and so the
 * future Android/iOS clients can decode the same JSON without a shim.
 */

export interface Voice {
  id: string;
  name: string;
  language: string;
  createdAt: string;
  engine: string;
  engineVariant: string | null;
  referenceDurationSeconds: number;
  referenceSampleRate: number;
  source: 'upload' | 'record';
  generationCount: number;
  lastUsedAt: string | null;
  consentGiven: boolean;
  hasConditioningCache: boolean;
  sampleUrl: string | null;
}

export interface Generation {
  id: string;
  voiceId: string;
  text: string;
  language: string;
  createdAt: string;
  audioUrl: string;
  durationSeconds: number;
  sampleRate: number;
  sizeBytes: number;
  generationSeconds: number;
  realTimeFactor: number;
  engine: string;
  watermarked: boolean;
  experimental: boolean;
  notice: string | null;
}

export interface PageMeta {
  total: number;
  limit: number;
  offset: number;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

export interface LanguageOption {
  code: string;
  name: string;
  native: boolean;
  experimental: boolean;
  note: string | null;
}

export interface EngineDescription {
  name: string;
  variant: string;
  device: string;
  sampleRate: number;
  loaded: boolean;
  supportsStreaming: boolean;
  supportsCachedConditioning: boolean;
  watermarked: boolean;
  license: string;
  notes: string | null;
}

export interface Limits {
  maxUploadBytes: number;
  minReferenceSeconds: number;
  maxReferenceSeconds: number;
  maxTextChars: number;
  maxVoices: number;
  requireConsent: boolean;
}

export interface SystemInfo {
  appName: string;
  version: string;
  environment: string;
  engine: EngineDescription;
  deviceDetails: Record<string, unknown>;
  languages: LanguageOption[];
  limits: Limits;
  acceptedAudioFormats: string[];
}

export interface CreateVoiceInput {
  name: string;
  language: string;
  consent: boolean;
  source: 'upload' | 'record';
  audio: Blob;
  filename: string;
}

export interface GenerateSpeechInput {
  voiceId: string;
  text: string;
  language: string;
  exaggeration?: number;
  cfgWeight?: number;
  temperature?: number;
  seed?: number;
}

/** Shape of the backend's error envelope. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
