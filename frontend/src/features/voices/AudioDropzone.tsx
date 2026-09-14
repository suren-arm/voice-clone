'use client';

/** Click-or-drag file picker with client-side pre-validation. */

import { useCallback, useState } from 'react';
import { AudioPlayer } from '@/components/AudioPlayer';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Dropzone } from '@/components/Dropzone';
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
  const [selection, setSelection] = useState<SelectedFile | null>(null);
  const [error, setError] = useState<string | null>(null);

  const clear = useCallback(() => {
    setSelection((current) => {
      if (current) URL.revokeObjectURL(current.url);
      return null;
    });
    setError(null);
    onFileChange(null);
  }, [onFileChange]);

  const accept = useCallback(
    async (file: File) => {
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
      <Dropzone
        accept={ACCEPT_ATTRIBUTE}
        icon="🎧"
        title="Drop a sound file here, or click to choose one"
        hint={`${ACCEPTED_EXTENSIONS.map((ext) => ext.replace('.', '').toUpperCase()).join(', ')} · up to ${formatBytes(maxBytes)}`}
        inputLabel="Audio file"
        onFile={(file) => void accept(file)}
        zoneTestId="dropzone"
        inputTestId="file-input"
      />

      {error && <Callout kind="error">{error}</Callout>}
    </div>
  );
}
