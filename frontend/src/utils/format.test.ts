import { describe, expect, it } from 'vitest';
import { formatBytes, formatDuration, formatRelativeTime, truncate } from '@/utils/format';

describe('formatDuration', () => {
  it.each([
    [0, '0:00'],
    [8, '0:08'],
    [65, '1:05'],
    [600, '10:00'],
    [3661, '1:01:01'],
  ])('formats %ss as %s', (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected);
  });

  it('handles invalid input without throwing', () => {
    expect(formatDuration(Number.NaN)).toBe('0:00');
    expect(formatDuration(-5)).toBe('0:00');
    expect(formatDuration(Number.POSITIVE_INFINITY)).toBe('0:00');
  });
});

describe('formatBytes', () => {
  it.each([
    [0, '0 B'],
    [512, '512 B'],
    [2048, '2.0 KB'],
    [1024 * 1024 * 3, '3.0 MB'],
    [1024 * 1024 * 25, '25 MB'],
  ])('formats %d as %s', (bytes, expected) => {
    expect(formatBytes(bytes)).toBe(expected);
  });
});

describe('formatRelativeTime', () => {
  const now = new Date('2026-09-11T12:00:00Z');

  it('says "just now" for very recent times', () => {
    expect(formatRelativeTime('2026-09-11T11:59:50Z', now)).toBe('just now');
  });

  it('reports minutes and days', () => {
    expect(formatRelativeTime('2026-09-11T11:30:00Z', now)).toContain('30 minutes ago');
    expect(formatRelativeTime('2026-09-09T12:00:00Z', now)).toContain('2 days ago');
  });

  it('returns an empty string for an unparseable date', () => {
    expect(formatRelativeTime('not-a-date', now)).toBe('');
  });
});

describe('truncate', () => {
  it('leaves short text alone', () => {
    expect(truncate('hello', 20)).toBe('hello');
  });

  it('collapses whitespace', () => {
    expect(truncate('a   b\n c', 20)).toBe('a b c');
  });

  it('cuts on a word boundary and appends an ellipsis', () => {
    const result = truncate('the quick brown fox jumps over the lazy dog', 20);
    expect(result.endsWith('…')).toBe(true);
    expect(result.length).toBeLessThanOrEqual(21);
  });
});
