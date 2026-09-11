'use client';

/** Click-or-drag file picker with client-side pre-validation. */

import { useCallback, useRef, useState } from 'react';
import type { DragEvent } from 'react';
import { AudioPlayer } from '@/components/AudioPlayer';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { ACCEPTED_EXTENSIONS, ACCEPT_ATTRIBUTE, probeDuration, validateAudioFile } from '@/utils/audio';
import { formatBytes, formatDuration } from '@/utils/format';

export interface SelectedFile {
  file: File;
  url: string;
  durationSeconds: number | null;
}

interface AudioDropzoneProps {
  maxBytes: number;
  onFileChange: (selection: SelectedFile | null) => void;
}

export function AudioDropzone({ maxBytes, onFileChange }: AudioDropzoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [selection, setSelection] = useState<SelectedFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const clear = useCallback(() => {
    setSelection((current) => {
      if (current) URL.revokeObjectURL(current.url);
      return null;
    });
    setError(null);
    if (inputRef.current) inputRef.current.value = '';
    onFileChange(null);
  }, [onFileChange]);

  const accept = useCallback(
    async (file: File | undefined) => {
      if (!file) return;
      const result = validateAudioFile(file, { maxBytes });
      if (!result.ok) {
        setError(result.error ?? 'That file cannot be used.');
        onFileChange(null);
        return;
      }
      setError(null);
      const url = URL.createObjectURL(file);

      // Show the preview immediately. Duration is a nice-to-have that some
      // containers only reveal after a full decode, so probing it must never
      // gate the UI -- it is filled in below once (and if) it arrives.
      const next: SelectedFile = { file, url, durationSeconds: null };
      setSelection((current) => {
        if (current) URL.revokeObjectURL(current.url);
        return next;
      });
      onFileChange(next);

      const durationSeconds = await probeDuration(file);
      if (durationSeconds === null) return;
      setSelection((current) => (current?.url === url ? { ...current, durationSeconds } : current));
      onFileChange({ ...next, durationSeconds });
    },
    [maxBytes, onFileChange],
  );

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragOver(false);
    void accept(event.dataTransfer.files?.[0]);
  };

  if (selection) {
    return (
      <div className="stack">
        <AudioPlayer
          src={selection.url}
          durationSeconds={selection.durationSeconds ?? undefined}
          sunken
          label="the selected file"
        />
        <div className="row row--between">
          <span className="field__hint">
            {selection.file.name} · {formatBytes(selection.file.size)}
            {selection.durationSeconds ? ` · ${formatDuration(selection.durationSeconds)}` : ''}
          </span>
          <Button variant="secondary" onClick={clear} data-testid="choose-different-file">
            Choose a different file
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="stack">
      {/* The whole zone is a button so keyboard and pointer users get the same
          affordance; the input itself stays visually hidden. */}
      <div
        className={dragOver ? 'dropzone dropzone--over' : 'dropzone'}
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        data-testid="dropzone"
      >
        <span className="dropzone__icon" aria-hidden="true">
          ⬆
        </span>
        <span className="dropzone__title">Drop an audio file, or click to browse</span>
        <span className="dropzone__hint">
          {ACCEPTED_EXTENSIONS.map((ext) => ext.replace('.', '').toUpperCase()).join(', ')} · up to{' '}
          {formatBytes(maxBytes)}
        </span>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTRIBUTE}
        className="sr-only"
        aria-label="Audio file"
        onChange={(event) => void accept(event.target.files?.[0])}
        data-testid="file-input"
      />

      {error && <Callout kind="error">{error}</Callout>}
    </div>
  );
}
