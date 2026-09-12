/**
 * Capability gating for the voice-source / language combination.
 *
 * The cloning engine's transliteration bridge for Armenian is real but is an
 * approximation the product does not want to present as equivalent to a
 * supported combination (see docs/ARMENIAN.md) -- so the "Create Fairy Tale"
 * and "Text to Speech" screens disable cloned-voice narration for Armenian
 * outright and explain why, rather than letting the request through to an
 * obscure backend error.
 */
export const ARMENIAN_LANGUAGE_CODE = 'hy';

export const ARMENIAN_CLONING_BLOCKED_MESSAGE =
  'This cloned voice model currently does not support Armenian. Please choose an Armenian default voice.';

export function isClonedVoiceBlockedForLanguage(language: string): boolean {
  return language.toLowerCase() === ARMENIAN_LANGUAGE_CODE;
}

export const BACKGROUND_SOUND_OPTIONS: { value: 'none' | 'mystical'; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: 'mystical', label: 'Mystical' },
];

export const DEFAULT_BACKGROUND_VOLUME = 15;
