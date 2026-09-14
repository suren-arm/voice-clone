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
  /** "system" is a built-in default voice (espeak-ng), not a user recording. */
  source: 'upload' | 'record' | 'system';
  generationCount: number;
  lastUsedAt: string | null;
  consentGiven: boolean;
  hasConditioningCache: boolean;
  sampleUrl: string | null;
}

/** "none" plus every background track the backend actually has an asset for. */
export type BackgroundSound = 'none' | 'mystical' | 'calm' | 'forest' | 'bedtime';

export type VoiceSource = 'cloned' | 'default';

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
  backgroundSound: BackgroundSound;
  backgroundApplied: boolean;
  backgroundNotice: string | null;
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
  maxPdfBytes: number;
  maxPdfPages: number;
  maxRemoteDownloadBytes: number;
  maxBookNarrationChars: number;
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
  backgroundSound?: BackgroundSound;
  backgroundVolume?: number;
}

export type StoryLanguage = 'en' | 'hy';
export type StoryLength = 'short' | 'medium' | 'long';
export type StoryAgeGroup = '3-5' | '6-8' | '9-12';
export type StoryTone = 'magical' | 'funny' | 'adventure' | 'educational' | 'bedtime';

/** "auto" plus any AiProvider.id the backend reports. */
export type AiProviderId = string;

export interface GenerateStoryInput {
  provider: AiProviderId;
  language: StoryLanguage;
  characters: string;
  idea: string;
  ageGroup: StoryAgeGroup;
  length: StoryLength;
  tone: StoryTone;
}

export interface Story {
  title: string;
  text: string;
  language: StoryLanguage;
  wordCount: number;
  provider: string;
  providerName: string;
}

export interface AiProvider {
  id: AiProviderId;
  name: string;
  kind: 'paid' | 'free-tier' | 'local';
  available: boolean;
}

export interface AiProvidersInfo {
  providers: AiProvider[];
  autoResolvesTo: AiProviderId | null;
}

/** Shape of the backend's error envelope. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

// -- Book Reader --------------------------------------------------------------

export type BookSourceType = 'pdf_upload' | 'pdf_url' | 'html_url';

export interface BookDocument {
  id: string;
  title: string | null;
  sourceType: BookSourceType;
  sourceUrl: string | null;
  originalFilename: string | null;
  language: string;
  pageCount: number | null;
  sectionCount: number;
  charCount: number;
  createdAt: string;
}

export interface BookSectionSummary {
  index: number;
  title: string | null;
  pageNumber: number | null;
  charCount: number;
}

export interface BookSection extends BookSectionSummary {
  text: string;
}

export type ReadingRangeKind = 'entire' | 'pages' | 'section';

export interface ReadingRange {
  kind: ReadingRangeKind;
  fromPage?: number;
  toPage?: number;
  sectionIndex?: number;
}

/** Only the speeds ai.audio_mix's atempo filter is verified reliable at. */
export type ReadingSpeed = 0.75 | 1 | 1.25 | 1.5;

export interface NarrateBookInput {
  voiceId: string;
  language: string;
  range: ReadingRange;
  speed?: ReadingSpeed;
  backgroundSound?: BackgroundSound;
  backgroundVolume?: number;
}

export interface BookNarrationResult {
  generationId: string;
  documentId: string;
  range: ReadingRange;
  audioUrl: string;
  durationSeconds: number;
  notice: string | null;
  backgroundApplied: boolean;
  backgroundNotice: string | null;
}
