'use client';

import { useState } from 'react';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Field } from '@/components/Field';
import { ApiError } from '@/services/apiClient';
import { createBookFromUrl, uploadBookPdf } from '@/services/books';
import type { BookDocument } from '@/types';

type SourceMode = 'upload' | 'url';

interface SourceFormProps {
  onLoaded: (document: BookDocument) => void;
}

/**
 * The Book Reader's own input step -- deliberately not the Text to Speech
 * text box. A PDF upload or a public URL is handed straight to the backend
 * extractor; nothing here ever sees the extracted text itself.
 */
export function SourceForm({ onLoaded }: SourceFormProps) {
  const [mode, setMode] = useState<SourceMode>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canLoad = mode === 'upload' ? file !== null : url.trim().length > 0;

  async function handleLoad() {
    if (!canLoad || loading) return;
    setLoading(true);
    setError(null);
    try {
      const document =
        mode === 'upload' && file
          ? await uploadBookPdf(file)
          : await createBookFromUrl(url.trim());
      onLoaded(document);
    } catch (cause) {
      const message =
        cause instanceof ApiError ? cause.message : 'Could not load this book. Please try again.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="stack">
      <Field label="How would you like to open your book?">
        {() => (
          <div className="segmented" role="group" aria-label="Book source">
            <button
              type="button"
              className="segmented__option"
              aria-pressed={mode === 'upload'}
              onClick={() => setMode('upload')}
              data-testid="book-source-upload"
            >
              📄 Upload a PDF
            </button>
            <button
              type="button"
              className="segmented__option"
              aria-pressed={mode === 'url'}
              onClick={() => setMode('url')}
              data-testid="book-source-url"
            >
              🔗 Open from a link
            </button>
          </div>
        )}
      </Field>

      {mode === 'upload' && (
        <Field label="Choose your book" hint="Pick a PDF from this device.">
          {(props) => (
            <input
              {...props}
              type="file"
              className="input"
              accept="application/pdf,.pdf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              data-testid="book-pdf-input"
            />
          )}
        </Field>
      )}

      {mode === 'url' && (
        <Field
          label="Paste a link"
          hint="A public web page or PDF link (starting with http:// or https://)."
        >
          {(props) => (
            <input
              {...props}
              type="url"
              className="input"
              value={url}
              placeholder="https://example.com/book-or-article"
              onChange={(event) => setUrl(event.target.value)}
              data-testid="book-url-input"
            />
          )}
        </Field>
      )}

      {error && <Callout kind="error">{error}</Callout>}

      <div className="row row--end">
        <Button
          variant="primary"
          size="lg"
          onClick={() => void handleLoad()}
          disabled={!canLoad || loading}
          loading={loading}
          data-testid="load-book-submit"
        >
          {loading ? '📖 Opening your book…' : '📖 Open My Book'}
        </Button>
      </div>
    </div>
  );
}
