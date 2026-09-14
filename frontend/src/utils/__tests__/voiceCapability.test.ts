import { describe, expect, it } from 'vitest';
import type { LanguageOption, Voice } from '@/types';
import {
  clonedVoiceBlockedMessage,
  isClonedVoiceBlockedForLanguage,
  languageName,
  voicesForLanguage,
} from '@/utils/voiceCapability';

const LANGUAGES: LanguageOption[] = [
  {
    code: 'en',
    name: 'English',
    englishName: 'English',
    supportsDefaultVoice: true,
    supportsClonedVoice: true,
  },
  {
    code: 'hy',
    name: 'Հայերեն',
    englishName: 'Armenian',
    supportsDefaultVoice: true,
    supportsClonedVoice: false,
  },
  {
    code: 'ru',
    name: 'Русский',
    englishName: 'Russian',
    supportsDefaultVoice: true,
    supportsClonedVoice: false,
  },
];

function voice(id: string, language: string): Voice {
  return { id, language, name: id } as Voice;
}

describe('voiceCapability', () => {
  it('reads cloning capability from the catalogue, not a hardcoded language', () => {
    expect(isClonedVoiceBlockedForLanguage(LANGUAGES, 'en')).toBe(false);
    expect(isClonedVoiceBlockedForLanguage(LANGUAGES, 'hy')).toBe(true);
    expect(isClonedVoiceBlockedForLanguage(LANGUAGES, 'ru')).toBe(true);
  });

  it('follows the catalogue when a model gains a language', () => {
    // The old implementation hardcoded "hy is blocked" and would have kept
    // saying so here, which is the bug this shape prevents.
    const withArmenianCloning = LANGUAGES.map((language) =>
      language.code === 'hy' ? { ...language, supportsClonedVoice: true } : language,
    );
    expect(isClonedVoiceBlockedForLanguage(withArmenianCloning, 'hy')).toBe(false);
  });

  it('does not claim a language it has never heard of is blocked', () => {
    expect(isClonedVoiceBlockedForLanguage(LANGUAGES, 'de')).toBe(false);
  });

  it('names languages the way their speakers write them', () => {
    expect(languageName(LANGUAGES, 'hy')).toBe('Հայերեն');
    expect(languageName(LANGUAGES, 'ru')).toBe('Русский');
    expect(languageName(LANGUAGES, 'de')).toBe('de');
  });

  it('explains a blocked voice without naming a model or a code', () => {
    const message = clonedVoiceBlockedMessage(LANGUAGES, 'hy');
    expect(message).toBe('This voice cannot speak Հայերեն. Please choose another voice.');
    expect(message).not.toMatch(/model|engine|\bhy\b/i);
  });

  it('filters voices to the ones that speak the chosen language', () => {
    const voices = [voice('a', 'en'), voice('b', 'hy'), voice('c', 'ru'), voice('d', 'hy')];
    expect(voicesForLanguage(voices, 'hy').map((v) => v.id)).toEqual(['b', 'd']);
    expect(voicesForLanguage(voices, 'ru').map((v) => v.id)).toEqual(['c']);
    expect(voicesForLanguage(voices, 'de')).toEqual([]);
  });
});
