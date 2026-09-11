import type { Limits } from '@/types';

export interface FieldError {
  field: string;
  message: string;
}

export function validateVoiceName(name: string): string | null {
  const trimmed = name.trim();
  if (!trimmed) return 'Give this voice a name.';
  if (trimmed.length > 80) return 'Names are limited to 80 characters.';
  return null;
}

export function validateText(text: string, limits: Limits | null): string | null {
  const trimmed = text.trim();
  if (!trimmed) return 'Enter some text to speak.';
  const max = limits?.maxTextChars ?? 2000;
  if (trimmed.length > max) return `Text is limited to ${max.toLocaleString()} characters.`;
  return null;
}

/** Guidance shown on the Create Voice screen. */
export const RECORDING_TIPS = [
  'Record approximately 10-30 seconds.',
  'Speak naturally, at your normal pace.',
  'Use a quiet room.',
  'Avoid music and background voices.',
  'Do not heavily process the recording.',
] as const;

export const CONSENT_LABEL =
  'I confirm that this is my voice, or I have permission from the speaker to clone it.';
