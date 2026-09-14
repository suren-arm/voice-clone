import type { BackgroundSound, LanguageOption, Voice } from '@/types';

/**
 * Which voices can speak which language.
 *
 * Every answer here comes from the backend's capability flags
 * (`GET /api/v1/system/info` -> `languages[].supportsClonedVoice` /
 * `supportsDefaultVoice`), which are read off the real engines. Nothing is
 * hardcoded: this file used to assert "Armenian is blocked for cloned
 * voices" as a literal, which happened to be true but would have gone
 * silently wrong the moment a model gained Armenian, or a different
 * Chatterbox variant changed what cloning could do.
 */

export function findLanguage(
  languages: LanguageOption[],
  code: string,
): LanguageOption | undefined {
  return languages.find((language) => language.code === code);
}

/** The name a speaker of the language would recognise, for messages. */
export function languageName(languages: LanguageOption[], code: string): string {
  return findLanguage(languages, code)?.name ?? code;
}

export function isClonedVoiceBlockedForLanguage(
  languages: LanguageOption[],
  code: string,
): boolean {
  const language = findLanguage(languages, code);
  // Unknown language: don't claim it is blocked, let the backend answer.
  return language ? !language.supportsClonedVoice : false;
}

/**
 * Names the language and the next step, never the model that cannot do it
 * -- this is read by a child. The technical reason stays in the server logs.
 */
export function clonedVoiceBlockedMessage(languages: LanguageOption[], code: string): string {
  return `This voice cannot speak ${languageName(languages, code)}. Please choose another voice.`;
}

/** Voices that genuinely speak `code` -- what the voice picker should show. */
export function voicesForLanguage(voices: Voice[], code: string): Voice[] {
  return voices.filter((voice) => voice.language === code);
}

/**
 * A child picking "Mystical" from a row of words has no idea what it will
 * sound like, so each option carries a picture of the place it evokes.
 */
export const BACKGROUND_SOUND_OPTIONS: { value: BackgroundSound; label: string }[] = [
  { value: 'none', label: '🔇 Just the voice' },
  { value: 'mystical', label: '🔮 Magical' },
  { value: 'calm', label: '🌊 Calm' },
  { value: 'forest', label: '🌳 Forest' },
  { value: 'bedtime', label: '🌙 Bedtime' },
];

/**
 * Conservative on purpose. The ambience is atmosphere, not a second voice;
 * the backend additionally caps and ducks it (see ai/audio_mix.py) so this
 * is a starting point rather than the only safeguard.
 */
export const DEFAULT_BACKGROUND_VOLUME = 15;
