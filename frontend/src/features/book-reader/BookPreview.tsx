'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Field } from '@/components/Field';
import { Spinner } from '@/components/Spinner';
import { ApiError } from '@/services/apiClient';
import { getBookSection } from '@/services/books';
import type { BookDocument, BookSection } from '@/types';

const LANGUAGE_OPTIONS: { value: string; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'hy', label: 'Հայերեն' },
];

interface BookPreviewProps {
  document: BookDocument;
  language: string;
  onLanguageChange: (language: string) => void;
}

/**
 * The extracted-text preview: one section (one PDF page, or one
 * heading-delimited HTML block) at a time, never the whole book in a single
 * textarea -- a long book can be hundreds of sections.
 */
export function BookPreview({ document, language, onLanguageChange }: BookPreviewProps) {
  const [index, setIndex] = useState(0);
  const [section, setSection] = useState<BookSection | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getBookSection(document.id, index)
      .then((result) => {
        if (!cancelled) setSection(result);
      })
      .catch((cause) => {
        if (cancelled) return;
        setError(cause instanceof ApiError ? cause.message : 'Could not load this section.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [document.id, index]);

  const total = document.sectionCount;

  return (
    <div className="stack">
      <div className="stat-grid">
        <div>
          <div className="stat__label">Title</div>
          <div className="stat__value">{document.title ?? 'Untitled'}</div>
        </div>
        <div>
          <div className="stat__label">Source Type</div>
          <div className="stat__value">
            {document.sourceType === 'pdf_upload' && 'PDF (uploaded)'}
            {document.sourceType === 'pdf_url' && 'PDF (from link)'}
            {document.sourceType === 'html_url' && 'Web article'}
          </div>
        </div>
        <div>
          <div className="stat__label">Pages</div>
          <div className="stat__value">{document.pageCount ?? '—'}</div>
        </div>
      </div>

      <Field
        label="Detected Language"
        hint="Override this if the automatic detection guessed wrong -- narration uses whichever language is selected here."
      >
        {(props) => (
          <select
            {...props}
            className="select"
            value={language}
            onChange={(event) => onLanguageChange(event.target.value)}
            data-testid="book-language-select"
          >
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
      </Field>

      <div className="field">
        <div className="row row--between" style={{ gap: 8 }}>
          <span className="field__label">
            Extracted Text — {document.sourceType === 'html_url' ? 'Section' : 'Page'}{' '}
            {index + 1} of {total}
          </span>
          <div className="row">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIndex((current) => Math.max(0, current - 1))}
              disabled={index === 0}
              data-testid="preview-prev"
            >
              ← Previous
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIndex((current) => Math.min(total - 1, current + 1))}
              disabled={index >= total - 1}
              data-testid="preview-next"
            >
              Next →
            </Button>
          </div>
        </div>

        {loading && <Spinner label="Loading section…" />}
        {error && <Callout kind="error">{error}</Callout>}
        {!loading && !error && section && (
          <div className="textarea" style={{ minHeight: 200, whiteSpace: 'pre-wrap' }} data-testid="preview-text">
            {section.title && <strong>{section.title}</strong>}
            {section.title && <br />}
            {section.text || <em>(This page has no extractable text.)</em>}
          </div>
        )}
      </div>
    </div>
  );
}
