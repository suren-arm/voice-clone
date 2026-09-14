import { del, getJson, postForm, postJson } from '@/services/apiClient';
import type {
  BookDocument,
  BookNarrationResult,
  BookSection,
  BookSectionSummary,
  NarrateBookInput,
  Page,
} from '@/types';

const BASE = '/api/v1/books';

export function uploadBookPdf(file: File): Promise<BookDocument> {
  const form = new FormData();
  form.append('file', file, file.name);
  // PDF parsing (a whole book) can take real time on a large file.
  return postForm<BookDocument>(`${BASE}/upload`, form, { timeoutMs: 120_000 });
}

export function createBookFromUrl(url: string): Promise<BookDocument> {
  // Fetching + extracting a remote page/PDF is one round trip server-side.
  return postJson<BookDocument>(`${BASE}/from-url`, { url }, { timeoutMs: 60_000 });
}

export function getBook(documentId: string): Promise<BookDocument> {
  return getJson<BookDocument>(`${BASE}/${encodeURIComponent(documentId)}`);
}

export function listBookSections(
  documentId: string,
  limit = 20,
  offset = 0,
): Promise<Page<BookSectionSummary>> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return getJson<Page<BookSectionSummary>>(
    `${BASE}/${encodeURIComponent(documentId)}/sections?${params}`,
  );
}

export function getBookSection(documentId: string, index: number): Promise<BookSection> {
  return getJson<BookSection>(`${BASE}/${encodeURIComponent(documentId)}/sections/${index}`);
}

export function narrateBook(
  documentId: string,
  input: NarrateBookInput,
): Promise<BookNarrationResult> {
  // Generation is synchronous server-side; a book-sized text budget needs
  // real room on a CPU instance -- same reasoning as services/speech.ts.
  return postJson<BookNarrationResult>(`${BASE}/${encodeURIComponent(documentId)}/narrate`, input, {
    timeoutMs: 300_000,
  });
}

export function deleteBook(documentId: string): Promise<{ id: string; deleted: boolean }> {
  return del(`${BASE}/${encodeURIComponent(documentId)}`);
}
