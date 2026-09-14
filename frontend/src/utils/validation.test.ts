import { describe, expect, it } from 'vitest';
import type { Limits } from '@/types';
import { validateText, validateVoiceName } from '@/utils/validation';

const limits: Limits = {
  maxUploadBytes: 1000,
  minReferenceSeconds: 3,
  maxReferenceSeconds: 120,
  maxTextChars: 50,
  maxVoices: 10,
  requireConsent: true,
  maxPdfBytes: 20971520,
  maxPdfPages: 500,
  maxRemoteDownloadBytes: 20971520,
  maxBookNarrationChars: 12000,
};

describe('validateVoiceName', () => {
  it('accepts a normal name', () => {
    expect(validateVoiceName('My Voice')).toBeNull();
  });

  it.each(['', '   '])('rejects blank input %j', (value) => {
    expect(validateVoiceName(value)).toMatch(/name/i);
  });

  it('rejects an overlong name', () => {
    expect(validateVoiceName('a'.repeat(81))).toMatch(/80 characters/);
  });
});

describe('validateText', () => {
  it('accepts text within the limit', () => {
    expect(validateText('Hello', limits)).toBeNull();
  });

  it('rejects empty text', () => {
    expect(validateText('  ', limits)).toMatch(/enter some text/i);
  });

  it('rejects text over the server limit', () => {
    expect(validateText('x'.repeat(51), limits)).toMatch(/limited to 50/);
  });

  it('falls back to a default limit when the server info is missing', () => {
    expect(validateText('x'.repeat(2001), null)).toMatch(/2,000/);
  });
});
