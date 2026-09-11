import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// jsdom implements neither of these, and the audio player and dropzone both
// depend on them.
if (!('createObjectURL' in URL)) {
  Object.defineProperty(URL, 'createObjectURL', { writable: true, value: vi.fn(() => 'blob:mock') });
}
if (!('revokeObjectURL' in URL)) {
  Object.defineProperty(URL, 'revokeObjectURL', { writable: true, value: vi.fn() });
}

// jsdom's HTMLMediaElement throws "Not implemented" for these.
// Defined as plain functions rather than vi.fn(): `vi.restoreAllMocks()` in the
// afterEach above would otherwise reset them between tests, leaving `play()`
// returning undefined and every later `.catch()` throwing.
Object.defineProperty(HTMLMediaElement.prototype, 'play', {
  writable: true,
  value: () => Promise.resolve(),
});
Object.defineProperty(HTMLMediaElement.prototype, 'pause', { writable: true, value: () => {} });
Object.defineProperty(HTMLMediaElement.prototype, 'load', { writable: true, value: () => {} });

process.env.NEXT_PUBLIC_API_URL = 'http://api.test';
