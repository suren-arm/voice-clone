'use client';

import { Field } from '@/components/Field';
import type { BookDocument, ReadingRange, ReadingRangeKind, ReadingSpeed } from '@/types';

const SPEED_OPTIONS: ReadingSpeed[] = [0.75, 1, 1.25, 1.5];

interface ReadingRangeFieldsProps {
  document: BookDocument;
  range: ReadingRange;
  onRangeChange: (range: ReadingRange) => void;
  speed: ReadingSpeed;
  onSpeedChange: (speed: ReadingSpeed) => void;
  disabled?: boolean;
}

/**
 * "Entire Document" / "Pages" / "Selected Section" -- a PDF exposes page
 * numbers, an HTML article exposes sections instead (it has no pages), and
 * a document with only one section never bothers offering "Selected
 * Section" as a separate choice from "Entire Document".
 */
export function ReadingRangeFields({
  document,
  range,
  onRangeChange,
  speed,
  onSpeedChange,
  disabled = false,
}: ReadingRangeFieldsProps) {
  const hasPages = document.pageCount !== null;
  const canSelectSection = document.sectionCount > 1;

  const kinds: { value: ReadingRangeKind; label: string }[] = [
    { value: 'entire', label: hasPages ? 'Entire Book' : 'Entire Article' },
    ...(hasPages ? [{ value: 'pages' as const, label: 'Pages' }] : []),
    ...(canSelectSection ? [{ value: 'section' as const, label: 'Selected Section' }] : []),
  ];

  function setKind(kind: ReadingRangeKind) {
    if (kind === 'pages') {
      onRangeChange({ kind, fromPage: 1, toPage: Math.min(document.pageCount ?? 1, 5) });
    } else if (kind === 'section') {
      onRangeChange({ kind, sectionIndex: 0 });
    } else {
      onRangeChange({ kind: 'entire' });
    }
  }

  return (
    <div className="stack">
      <Field label="Reading Range">
        {() => (
          <div className="segmented" role="group" aria-label="Reading range">
            {kinds.map((option) => (
              <button
                key={option.value}
                type="button"
                className="segmented__option"
                aria-pressed={range.kind === option.value}
                disabled={disabled}
                onClick={() => setKind(option.value)}
                data-testid={`reading-range-${option.value}`}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </Field>

      {range.kind === 'pages' && (
        <div className="row" style={{ gap: 12 }}>
          <Field label="From">
            {(props) => (
              <input
                {...props}
                type="number"
                className="input"
                min={1}
                max={document.pageCount ?? undefined}
                value={range.fromPage ?? 1}
                disabled={disabled}
                onChange={(event) =>
                  onRangeChange({ ...range, fromPage: Number(event.target.value) })
                }
                data-testid="reading-range-from"
              />
            )}
          </Field>
          <Field label="To">
            {(props) => (
              <input
                {...props}
                type="number"
                className="input"
                min={1}
                max={document.pageCount ?? undefined}
                value={range.toPage ?? 1}
                disabled={disabled}
                onChange={(event) => onRangeChange({ ...range, toPage: Number(event.target.value) })}
                data-testid="reading-range-to"
              />
            )}
          </Field>
        </div>
      )}

      {range.kind === 'section' && (
        <Field label="Section" hint={`0-based index, 0 to ${document.sectionCount - 1}.`}>
          {(props) => (
            <input
              {...props}
              type="number"
              className="input"
              min={0}
              max={document.sectionCount - 1}
              value={range.sectionIndex ?? 0}
              disabled={disabled}
              onChange={(event) =>
                onRangeChange({ ...range, sectionIndex: Number(event.target.value) })
              }
              data-testid="reading-range-section"
            />
          )}
        </Field>
      )}

      <Field label="Reading Speed">
        {(props) => (
          <select
            {...props}
            className="select"
            value={speed}
            disabled={disabled}
            onChange={(event) => onSpeedChange(Number(event.target.value) as ReadingSpeed)}
            data-testid="reading-speed-select"
          >
            {SPEED_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}x
              </option>
            ))}
          </select>
        )}
      </Field>
    </div>
  );
}
