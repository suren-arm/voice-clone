import type { ReadingRange } from '@/types';

/**
 * Session-level "resume reading" state -- the minimum bar this feature needs
 * (see README.md's Book Reader section): last document, last selected range,
 * last voice/language. Deliberately browser localStorage, not a database
 * table: it is per-viewer convenience, not data anyone else needs to read,
 * and the extracted document itself is already cleaned up server-side after
 * a retention window, so a table row would outlive the thing it points to.
 */
const STORAGE_KEY = 'book-reader:last-session';

export interface BookReaderSession {
  documentId: string;
  title: string | null;
  range: ReadingRange;
  voiceId: string;
  language: string;
}

export function loadBookReaderSession(): BookReaderSession | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<BookReaderSession>;
    if (!parsed.documentId || !parsed.range) return null;
    return parsed as BookReaderSession;
  } catch {
    // Private browsing, disabled storage, corrupted JSON -- resuming is a
    // convenience, never a requirement, so degrade to "nothing to resume".
    return null;
  }
}

export function saveBookReaderSession(session: BookReaderSession): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  } catch {
    // Ignore -- see loadBookReaderSession.
  }
}

export function clearBookReaderSession(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore -- see loadBookReaderSession.
  }
}
