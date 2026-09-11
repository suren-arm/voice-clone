'use client';

/**
 * Microphone recording via `getUserMedia` + `MediaRecorder`.
 *
 * Two things this handles that a naive implementation does not:
 *
 * 1. **Track cleanup.** Every `getUserMedia` stream must have its tracks
 *    stopped, or the browser's recording indicator stays on after the user
 *    leaves the page. We stop them on stop, on cancel and on unmount.
 * 2. **Duration.** Chrome reports `Infinity` for the duration of a WebM blob
 *    from MediaRecorder, so the elapsed time is measured with a timer rather
 *    than read back from the file.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { filenameForMimeType, isRecordingSupported, pickRecordingMimeType } from '@/utils/audio';

export type RecorderStatus = 'idle' | 'requesting' | 'recording' | 'paused' | 'recorded' | 'error';

export interface RecordedClip {
  blob: Blob;
  url: string;
  durationSeconds: number;
  filename: string;
  mimeType: string;
}

export interface UseRecorder {
  status: RecorderStatus;
  elapsedSeconds: number;
  clip: RecordedClip | null;
  error: string | null;
  supported: boolean;
  start: () => Promise<void>;
  stop: () => void;
  reset: () => void;
}

const TICK_MS = 100;

export function useRecorder(): UseRecorder {
  const [status, setStatus] = useState<RecorderStatus>('idle');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [clip, setClip] = useState<RecordedClip | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [supported, setSupported] = useState(true);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAtRef = useRef(0);
  const clipUrlRef = useRef<string | null>(null);

  // `isRecordingSupported` touches `navigator`, so it must run after hydration
  // or the server and client markup disagree.
  useEffect(() => setSupported(isRecordingSupported()), []);

  const releaseStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const revokeClipUrl = useCallback(() => {
    if (clipUrlRef.current) {
      URL.revokeObjectURL(clipUrlRef.current);
      clipUrlRef.current = null;
    }
  }, []);

  useEffect(
    () => () => {
      clearTimer();
      releaseStream();
      revokeClipUrl();
    },
    [clearTimer, releaseStream, revokeClipUrl],
  );

  const start = useCallback(async () => {
    if (!isRecordingSupported()) {
      setSupported(false);
      setStatus('error');
      setError('This browser cannot record audio. Try Chrome, Edge, Firefox or Safari.');
      return;
    }

    setError(null);
    setStatus('requesting');
    revokeClipUrl();
    setClip(null);
    chunksRef.current = [];

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          // Browser DSP is designed for calls, not for cloning: it can smear
          // the timbre the model keys on. The backend does the cleanup we do
          // want (trimming, normalisation) on a clean signal.
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });
    } catch (cause) {
      setStatus('error');
      const name = cause instanceof DOMException ? cause.name : '';
      if (name === 'NotAllowedError' || name === 'SecurityError') {
        setError('Microphone access was denied. Allow it in your browser settings and try again.');
      } else if (name === 'NotFoundError') {
        setError('No microphone was found. Connect one and try again.');
      } else {
        setError('Could not start recording. Check your microphone and try again.');
      }
      return;
    }

    streamRef.current = stream;
    const mimeType = pickRecordingMimeType();
    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    } catch {
      releaseStream();
      setStatus('error');
      setError('This browser could not start a recording session.');
      return;
    }
    recorderRef.current = recorder;

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };

    recorder.onstop = () => {
      clearTimer();
      releaseStream();
      const type = recorder.mimeType || mimeType || 'audio/webm';
      const blob = new Blob(chunksRef.current, { type });
      chunksRef.current = [];

      if (blob.size === 0) {
        setStatus('error');
        setError('The recording came out empty. Please try again.');
        return;
      }
      const url = URL.createObjectURL(blob);
      clipUrlRef.current = url;
      setClip({
        blob,
        url,
        durationSeconds: (Date.now() - startedAtRef.current) / 1000,
        filename: filenameForMimeType(type),
        mimeType: type,
      });
      setStatus('recorded');
    };

    recorder.onerror = () => {
      clearTimer();
      releaseStream();
      setStatus('error');
      setError('Recording failed. Please try again.');
    };

    startedAtRef.current = Date.now();
    setElapsedSeconds(0);
    // A timeslice keeps chunks flowing, so a crashed tab does not lose
    // everything and `ondataavailable` fires predictably in every browser.
    recorder.start(250);
    setStatus('recording');
    timerRef.current = setInterval(
      () => setElapsedSeconds((Date.now() - startedAtRef.current) / 1000),
      TICK_MS,
    );
  }, [clearTimer, releaseStream, revokeClipUrl]);

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    } else {
      clearTimer();
      releaseStream();
    }
  }, [clearTimer, releaseStream]);

  const reset = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = null;
      recorder.stop();
    }
    clearTimer();
    releaseStream();
    revokeClipUrl();
    chunksRef.current = [];
    recorderRef.current = null;
    setClip(null);
    setElapsedSeconds(0);
    setError(null);
    setStatus('idle');
  }, [clearTimer, releaseStream, revokeClipUrl]);

  return { status, elapsedSeconds, clip, error, supported, start, stop, reset };
}
