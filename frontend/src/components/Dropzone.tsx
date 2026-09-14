'use client';

/**
 * The click-or-drag file target, shared by the audio picker and the Book
 * Reader's PDF picker.
 *
 * Both screens ask for exactly the same thing -- "give me one file" -- but the
 * PDF picker used to be a bare `<input type="file">`, so the newest feature
 * looked and behaved unlike the rest of the app and could not accept a drop at
 * all. This holds only the interaction; validation and previews stay with the
 * caller, which is the part that actually differs between the two.
 */

import { useRef, useState } from 'react';
import type { DragEvent, ReactNode } from 'react';

interface DropzoneProps {
  /** `accept` attribute for the underlying input, e.g. `application/pdf,.pdf`. */
  accept: string;
  icon: ReactNode;
  title: string;
  hint: ReactNode;
  /** Accessible name for the hidden input, e.g. "Audio file". */
  inputLabel: string;
  onFile: (file: File) => void;
  disabled?: boolean;
  zoneTestId?: string;
  inputTestId?: string;
}

export function Dropzone({
  accept,
  icon,
  title,
  hint,
  inputLabel,
  onFile,
  disabled = false,
  zoneTestId,
  inputTestId,
}: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const open = () => {
    if (!disabled) inputRef.current?.click();
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragOver(false);
    if (disabled) return;
    const file = event.dataTransfer.files?.[0];
    if (file) onFile(file);
  };

  return (
    <>
      {/* The whole zone is a button so keyboard and pointer users get the same
          affordance; the input itself stays visually hidden. */}
      <div
        className={dragOver ? 'dropzone dropzone--over' : 'dropzone'}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled || undefined}
        onClick={open}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            open();
          }
        }}
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        data-testid={zoneTestId}
      >
        <span className="dropzone__icon" aria-hidden="true">
          {icon}
        </span>
        <span className="dropzone__title">{title}</span>
        <span className="dropzone__hint">{hint}</span>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="sr-only"
        aria-label={inputLabel}
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          // Let the same file be picked again after it is cleared.
          event.target.value = '';
        }}
        data-testid={inputTestId}
      />
    </>
  );
}
