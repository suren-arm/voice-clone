import { describe, expect, it } from 'vitest';
import { filenameForMimeType, validateAudioFile } from '@/utils/audio';

function makeFile(name: string, type: string, size: number): File {
  const file = new File(['x'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
}

describe('validateAudioFile', () => {
  const maxBytes = 1024 * 1024;

  it('accepts a normal wav', () => {
    expect(validateAudioFile(makeFile('clip.wav', 'audio/wav', 1000), { maxBytes }).ok).toBe(true);
  });

  it('accepts a known extension even when the browser reports no MIME type', () => {
    expect(validateAudioFile(makeFile('clip.m4a', '', 1000), { maxBytes }).ok).toBe(true);
  });

  it('rejects an empty file', () => {
    const result = validateAudioFile(makeFile('clip.wav', 'audio/wav', 0), { maxBytes });
    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/empty/i);
  });

  it('rejects a file over the size limit', () => {
    const result = validateAudioFile(makeFile('big.wav', 'audio/wav', maxBytes + 1), { maxBytes });
    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/larger than/i);
  });

  it('rejects a non-audio file', () => {
    const result = validateAudioFile(makeFile('notes.pdf', 'application/pdf', 500), { maxBytes });
    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/does not look like an audio file/i);
  });
});

describe('filenameForMimeType', () => {
  it.each([
    ['audio/webm;codecs=opus', 'recording.webm'],
    ['audio/mp4', 'recording.m4a'],
    ['audio/ogg;codecs=opus', 'recording.ogg'],
    [undefined, 'recording.webm'],
  ])('maps %s to %s', (mimeType, expected) => {
    expect(filenameForMimeType(mimeType)).toBe(expected);
  });
});
