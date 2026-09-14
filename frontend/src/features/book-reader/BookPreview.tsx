'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { LanguageSelect } from '@/components/LanguageSelect';
import { Spinner } from '@/components/Spinner';
import { ApiError } from '@/services/apiClient';
import { getBookSection } from '@/services/books';
import type { BookDocument, BookSection, LanguageOption } from '@/types';

interface BookPreviewProps {
  document: BookDocument;
  language: string;
  languages: LanguageOption[];
  onLanguageChange: (language: string) => void;
}

/**
 * The extracted-text preview: one section (one PDF page, or one
 * heading-delimited HTML block) at a time, never the whole book in a single
 * textarea -- a long book can be hundreds of sections.
 */
export function BookPreview({
  document,
  language,
  languages,
  onLanguageChange,
}: BookPreviewProps) {
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
          <div className="stat__label">Book</div>
          <div className="stat__value">{document.title ?? 'Untitled'}</div>
        </div>
        <div>
          <div className="stat__label">Kind</div>
          <div className="stat__value">
            {document.sourceType === 'pdf_upload' && 'PDF you uploaded'}
            {document.sourceType === 'pdf_url' && 'PDF from a link'}
            {document.sourceType === 'html_url' && 'Page from the web'}
          </div>
        </div>
        <div>
          <div className="stat__label">Pages</div>
          <div className="stat__value">{document.pageCount ?? '—'}</div>
        </div>
      </div>

      <LanguageSelect
        languages={languages}
        value={language}
        onChange={onLanguageChange}
        label="What language is it in?"
        hint="We guessed this from the text. Change it if we got it wrong."
        testId="book-language-select"
      />

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

        {loading && <Spinner label="Turning the page…" />}
        {error && <Callout kind="error">{error}</Callout>}
        {!loading && !error && section && (
          <div className="storybook" style={{ minHeight: 200 }} data-testid="preview-text">
            {section.title && <strong>{section.title}</strong>}
            {section.title && <br />}
            {section.text || <em>(There are no words to read on this page.)</em>}
          </div>
        )}
      </div>
    </div>
  );
}
