import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '@/hooks/useToast';
import { BookReaderForm } from '@/features/book-reader/BookReaderForm';
import type { BookDocument, BookSection, Generation, Voice } from '@/types';

const defaultVoice: Voice = {
  id: 'voice_default000001',
  name: 'English (Classic)',
  language: 'en',
  createdAt: '2026-09-11T12:00:00Z',
  engine: 'espeak-ng',
  engineVariant: 'en-us',
  referenceDurationSeconds: 0,
  referenceSampleRate: 22050,
  source: 'system',
  generationCount: 0,
  lastUsedAt: null,
  consentGiven: true,
  hasConditioningCache: false,
  sampleUrl: null,
};

const pdfDocument: BookDocument = {
  id: 'doc_abc123def456',
  title: 'Chapter One',
  sourceType: 'pdf_upload',
  sourceUrl: null,
  originalFilename: 'story.pdf',
  language: 'en',
  pageCount: 3,
  sectionCount: 3,
  charCount: 1200,
  createdAt: '2026-09-11T12:00:00Z',
};

const section0: BookSection = {
  index: 0,
  title: 'Chapter One',
  pageNumber: 1,
  charCount: 400,
  text: 'Once upon a time, a fox and a rabbit became friends.',
};

const generation: Generation = {
  id: 'gen_abc123def456',
  voiceId: defaultVoice.id,
  text: 'Once upon a time, a fox and a rabbit became friends.',
  language: 'en',
  createdAt: '2026-09-11T12:05:00Z',
  audioUrl: '/api/v1/generations/gen_abc123def456/audio',
  durationSeconds: 4.2,
  sampleRate: 22050,
  sizeBytes: 92400,
  generationSeconds: 0.4,
  realTimeFactor: 0.1,
  engine: 'espeak-ng',
  watermarked: false,
  experimental: false,
  notice: null,
  backgroundSound: 'none',
  backgroundApplied: false,
  backgroundNotice: null,
};

const fetchMock = vi.fn();

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

function defaultRoute(url: string) {
  if (url.includes('/voices/defaults')) return jsonResponse([defaultVoice]);
  if (url.includes('/voices')) return jsonResponse({ items: [], meta: { total: 0, limit: 100, offset: 0 } });
  if (url.includes('/books/upload') || url.includes('/books/from-url')) return jsonResponse(pdfDocument);
  if (url.match(/\/books\/.+\/sections\/\d+/)) return jsonResponse(section0);
  if (url.includes('/sections')) {
    return jsonResponse({
      items: [{ index: 0, title: 'Chapter One', pageNumber: 1, charCount: 400 }],
      meta: { total: 1, limit: 20, offset: 0 },
    });
  }
  if (url.includes('/narrate')) {
    return jsonResponse({
      generationId: generation.id,
      documentId: pdfDocument.id,
      range: { kind: 'entire' },
      audioUrl: generation.audioUrl,
      durationSeconds: generation.durationSeconds,
      notice: null,
      backgroundApplied: false,
      backgroundNotice: null,
    });
  }
  if (url.includes('/generations/')) return jsonResponse(generation);
  return jsonResponse({});
}

function renderForm() {
  return render(
    <ToastProvider>
      <BookReaderForm />
    </ToastProvider>,
  );
}

function pdfFile() {
  return new File(['%PDF-1.4 fake'], 'story.pdf', { type: 'application/pdf' });
}

describe('BookReaderForm', () => {
  beforeEach(() => {
    window.localStorage.clear();
    fetchMock.mockReset();
    fetchMock.mockImplementation((input: RequestInfo | URL) =>
      Promise.resolve(defaultRoute(String(input))),
    );
    vi.stubGlobal('fetch', fetchMock);
  });

  it('uploads a PDF and shows the extracted preview', async () => {
    renderForm();
    await userEvent.upload(screen.getByTestId('book-pdf-input'), pdfFile());
    await userEvent.click(screen.getByTestId('load-book-submit'));

    expect(await screen.findByRole('heading', { name: 'Chapter One' })).toBeInTheDocument();
    expect(screen.getByTestId('preview-text')).toHaveTextContent(
      'Once upon a time, a fox and a rabbit became friends.',
    );
  });

  it('loads a book from a URL', async () => {
    renderForm();
    await userEvent.click(screen.getByTestId('book-source-url'));
    await userEvent.type(screen.getByTestId('book-url-input'), 'https://example.com/book.pdf');
    await userEvent.click(screen.getByTestId('load-book-submit'));

    expect(await screen.findByRole('heading', { name: 'Chapter One' })).toBeInTheDocument();
  });

  it('offers a Pages range for a PDF with page numbers', async () => {
    renderForm();
    await userEvent.upload(screen.getByTestId('book-pdf-input'), pdfFile());
    await userEvent.click(screen.getByTestId('load-book-submit'));

    await screen.findByTestId('reading-range-pages');
    await userEvent.click(screen.getByTestId('reading-range-pages'));
    expect(screen.getByTestId('reading-range-from')).toBeInTheDocument();
    expect(screen.getByTestId('reading-range-to')).toBeInTheDocument();
  });

  it('narrates the book and shows the playable result', async () => {
    renderForm();
    await userEvent.upload(screen.getByTestId('book-pdf-input'), pdfFile());
    await userEvent.click(screen.getByTestId('load-book-submit'));
    await screen.findByRole('heading', { name: 'Chapter One' });

    await waitFor(() =>
      expect(screen.getByTestId('default-voice-select')).toHaveValue(defaultVoice.id),
    );
    await userEvent.click(screen.getByTestId('narrate-book-submit'));

    expect(await screen.findByTestId('generation-result')).toBeInTheDocument();
    expect(screen.getByTestId('audio-player')).toBeInTheDocument();
  });

  it('applies the bedtime preset (slower speed, calm-ish background, lower volume)', async () => {
    renderForm();
    await userEvent.upload(screen.getByTestId('book-pdf-input'), pdfFile());
    await userEvent.click(screen.getByTestId('load-book-submit'));
    await screen.findByRole('heading', { name: 'Chapter One' });

    await userEvent.click(screen.getByTestId('preset-bedtime'));
    expect(screen.getByTestId('reading-speed-select')).toHaveValue('0.75');
    expect(screen.getByTestId('background-bedtime')).toHaveAttribute('aria-pressed', 'true');
  });

  it('blocks cloned-voice narration for Armenian with a clear explanation', async () => {
    renderForm();
    await userEvent.upload(screen.getByTestId('book-pdf-input'), pdfFile());
    await userEvent.click(screen.getByTestId('load-book-submit'));
    await screen.findByRole('heading', { name: 'Chapter One' });

    await userEvent.selectOptions(screen.getByTestId('book-language-select'), 'hy');
    await userEvent.click(screen.getByTestId('voice-source-cloned'));

    expect(await screen.findByText(/does not support Armenian/i)).toBeInTheDocument();
    expect(screen.getByTestId('narrate-book-submit')).toBeDisabled();
  });

  it('surfaces a clear error when loading the book fails', async () => {
    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/books/upload')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              error: { code: 'document_scanned', message: 'This PDF appears to contain scanned pages.' },
            }),
            { status: 422, headers: { 'Content-Type': 'application/json' } },
          ),
        );
      }
      return Promise.resolve(defaultRoute(url));
    });

    renderForm();
    await userEvent.upload(screen.getByTestId('book-pdf-input'), pdfFile());
    await userEvent.click(screen.getByTestId('load-book-submit'));

    expect(await screen.findByText(/scanned pages/i)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Chapter One' })).not.toBeInTheDocument();
  });

  it('offers to resume the last book after a successful narration', async () => {
    renderForm();
    await userEvent.upload(screen.getByTestId('book-pdf-input'), pdfFile());
    await userEvent.click(screen.getByTestId('load-book-submit'));
    await screen.findByRole('heading', { name: 'Chapter One' });
    await waitFor(() =>
      expect(screen.getByTestId('default-voice-select')).toHaveValue(defaultVoice.id),
    );
    await userEvent.click(screen.getByTestId('narrate-book-submit'));
    await screen.findByTestId('generation-result');

    expect(window.localStorage.getItem('book-reader:last-session')).toContain(pdfDocument.id);
  });
});
