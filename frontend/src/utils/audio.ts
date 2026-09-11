/**
 * Browser audio helpers for recording and upload validation.
 *
 * Client-side validation here is a *convenience*, not a control: it gives
 * instant feedback instead of a round trip. The backend re-validates every
 * byte with magic-number sniffing and a real decode, because anything the
 * browser checks can be bypassed.
 */

/** Extensions the UI offers in the file picker. */
export const ACCEPTED_EXTENSIONS = ['.wav', '.mp3', '.m4a', '.mp4', '.webm', '.ogg', '.opus', '.flac'];

export const ACCEPT_ATTRIBUTE = ['audio/*', ...ACCEPTED_EXTENSIONS].join(',');

/**
 * Pick a MediaRecorder container the browser actually supports.
 *
 * Chrome and Firefox produce WebM/Opus; Safari only offers MP4/AAC. Passing an
 * unsupported mimeType to MediaRecorder throws, and passing none leaves Safari
 * producing a container the server may not expect -- so probe instead.
 */
export function pickRecordingMimeType(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined;
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4;codecs=mp4a.40.2',
    'audio/mp4',
  ];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type));
}

/** Map a recording MIME type to a sensible upload filename. */
export function filenameForMimeType(mimeType: string | undefined): string {
  if (!mimeType) return 'recording.webm';
  if (mimeType.includes('mp4')) return 'recording.m4a';
  if (mimeType.includes('ogg')) return 'recording.ogg';
  if (mimeType.includes('wav')) return 'recording.wav';
  return 'recording.webm';
}

export function isRecordingSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    typeof navigator.mediaDevices?.getUserMedia === 'function' &&
    typeof MediaRecorder !== 'undefined'
  );
}

export interface FileValidationResult {
  ok: boolean;
  error?: string;
}

export function validateAudioFile(
  file: File,
  options: { maxBytes: number; acceptedExtensions?: string[] },
): FileValidationResult {
  const { maxBytes, acceptedExtensions = ACCEPTED_EXTENSIONS } = options;

  if (file.size === 0) {
    return { ok: false, error: 'That file is empty.' };
  }
  if (file.size > maxBytes) {
    const limitMb = Math.round(maxBytes / 1024 / 1024);
    return { ok: false, error: `That file is larger than the ${limitMb} MB limit.` };
  }

  const extension = file.name.includes('.')
    ? `.${file.name.split('.').pop()!.toLowerCase()}`
    : '';
  const typeLooksAudio = file.type.startsWith('audio/') || file.type.startsWith('video/mp4');

  // Accept if *either* signal looks right: browsers report an empty `type` for
  // some files, and some audio arrives with an unfamiliar extension.
  if (!typeLooksAudio && !acceptedExtensions.includes(extension)) {
    return {
      ok: false,
      error: `That does not look like an audio file. Accepted: ${acceptedExtensions.join(', ')}.`,
    };
  }
  return { ok: true };
}

/**
 * Read a blob's duration by decoding just its metadata.
 *
 * Chrome reports `Infinity` for the duration of a WebM stream produced by
 * MediaRecorder (the container has no duration header until it is remuxed), so
 * callers must treat `null` as "unknown" and fall back to the recorded timer.
 */
export function probeDuration(blob: Blob): Promise<number | null> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined' || typeof Audio === 'undefined') {
      resolve(null);
      return;
    }
    const url = URL.createObjectURL(blob);
    const audio = new Audio();
    const finish = (value: number | null) => {
      URL.revokeObjectURL(url);
      resolve(value);
    };
    audio.preload = 'metadata';
    audio.onloadedmetadata = () => {
      const { duration } = audio;
      finish(Number.isFinite(duration) && duration > 0 ? duration : null);
    };
    audio.onerror = () => finish(null);
    audio.src = url;
    // Cap the wait: a container we cannot decode must not stall the UI.
    setTimeout(() => finish(null), 2500);
  });
}
