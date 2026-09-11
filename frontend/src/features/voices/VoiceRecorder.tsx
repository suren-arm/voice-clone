'use client';

/** Record / Stop / Playback / Record Again, with a live timer and level meter. */

import { useEffect, useRef, useState } from 'react';
import { AudioPlayer } from '@/components/AudioPlayer';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { useRecorder } from '@/hooks/useRecorder';
import type { RecordedClip } from '@/hooks/useRecorder';
import { formatDuration } from '@/utils/format';

interface VoiceRecorderProps {
  minSeconds: number;
  maxSeconds: number;
  onClipChange: (clip: RecordedClip | null) => void;
}

export function VoiceRecorder({ minSeconds, maxSeconds, onClipChange }: VoiceRecorderProps) {
  const { status, elapsedSeconds, clip, error, supported, start, stop, reset } = useRecorder();
  const [level, setLevel] = useState(0);
  const notifiedRef = useRef<Blob | null>(null);

  // Report the clip up exactly once per recording, without making `onClipChange`
  // a dependency (parents commonly pass an inline arrow).
  useEffect(() => {
    if (clip?.blob !== notifiedRef.current) {
      notifiedRef.current = clip?.blob ?? null;
      onClipChange(clip);
    }
  }, [clip, onClipChange]);

  // Stop automatically at the server's maximum instead of letting the user
  // record five minutes and then get rejected.
  useEffect(() => {
    if (status === 'recording' && elapsedSeconds >= maxSeconds) stop();
  }, [status, elapsedSeconds, maxSeconds, stop]);

  // A cheap animated level while recording. Real metering would need an
  // AnalyserNode on the live stream; this only signals "we are capturing".
  useEffect(() => {
    if (status !== 'recording') {
      setLevel(0);
      return;
    }
    const id = setInterval(() => setLevel(35 + Math.random() * 55), 140);
    return () => clearInterval(id);
  }, [status]);

  if (!supported) {
    return (
      <Callout kind="warning" title="Recording is not available">
        This browser does not support microphone recording. Upload an audio file instead, or try
        Chrome, Edge, Firefox or Safari over HTTPS.
      </Callout>
    );
  }

  const tooShort = clip !== null && clip.durationSeconds < minSeconds;

  if (clip) {
    return (
      <div className="stack">
        <AudioPlayer
          src={clip.url}
          durationSeconds={clip.durationSeconds}
          sunken
          label="your recording"
        />
        <div className="row row--between">
          <span className="field__hint">
            Recorded {formatDuration(clip.durationSeconds)}
            {tooShort && ` — at least ${minSeconds}s is needed`}
          </span>
          <Button variant="secondary" onClick={reset} data-testid="record-again">
            Record again
          </Button>
        </div>
        {tooShort && (
          <Callout kind="warning">
            That clip is too short. Record at least {minSeconds} seconds so the model has enough of
            your voice to work with.
          </Callout>
        )}
      </div>
    );
  }

  const recording = status === 'recording';

  return (
    <div className="stack">
      <div className={recording ? 'recorder recorder--active' : 'recorder'}>
        <div className="recorder__timer" data-testid="recorder-timer">
          {formatDuration(recording ? elapsedSeconds : 0)}
        </div>

        {recording ? (
          <>
            <span className="recorder__status">
              <span className="pulse" aria-hidden="true" />
              Recording — aim for 10–30 seconds
            </span>
            <div className="level-meter" aria-hidden="true">
              <div className="level-meter__fill" style={{ width: `${level}%` }} />
            </div>
            <Button variant="secondary" size="lg" onClick={stop} data-testid="stop-recording">
              Stop recording
            </Button>
          </>
        ) : (
          <>
            <span className="recorder__status">
              {status === 'requesting'
                ? 'Waiting for microphone permission…'
                : 'Press record and speak naturally'}
            </span>
            <Button
              variant="record"
              size="lg"
              onClick={() => void start()}
              loading={status === 'requesting'}
              data-testid="start-recording"
            >
              ● Start recording
            </Button>
          </>
        )}
      </div>

      {error && <Callout kind="error">{error}</Callout>}
      <p className="field__hint" aria-live="polite">
        Recording stops automatically at {formatDuration(maxSeconds)}.
      </p>
    </div>
  );
}
