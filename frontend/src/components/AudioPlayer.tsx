'use client';

/**
 * A small custom player rather than a bare `<audio controls>`.
 *
 * Native controls differ wildly between browsers and cannot show the duration
 * we already know from the API before metadata loads -- which matters here,
 * because Chrome reports `Infinity` for the duration of a freshly recorded
 * WebM blob. Passing `durationSeconds` lets the UI be correct immediately.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { formatDuration } from '@/utils/format';

interface AudioPlayerProps {
  src: string;
  /** Known duration, used until (or instead of) the element reporting one. */
  durationSeconds?: number;
  sunken?: boolean;
  label?: string;
}

export function AudioPlayer({ src, durationSeconds, sunken = false, label }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(durationSeconds ?? 0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setPlaying(false);
    setCurrentTime(0);
    setFailed(false);
    setDuration(durationSeconds ?? 0);
  }, [src, durationSeconds]);

  const toggle = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      // Older Safari returns undefined from play() instead of a promise.
      const played = audio.play() as Promise<void> | undefined;
      played?.catch(() => setFailed(true));
    } else {
      audio.pause();
    }
  }, []);

  const seek = useCallback((value: number) => {
    const audio = audioRef.current;
    if (!audio || !Number.isFinite(value)) return;
    audio.currentTime = value;
    setCurrentTime(value);
  }, []);

  const effectiveDuration = duration > 0 && Number.isFinite(duration) ? duration : 0;

  return (
    <div className={sunken ? 'player player--sunken' : 'player'} data-testid="audio-player">
      <button
        type="button"
        className="player__button"
        onClick={toggle}
        disabled={failed}
        aria-label={playing ? 'Pause' : `Play${label ? ` ${label}` : ''}`}
      >
        <span aria-hidden="true">{playing ? '❚❚' : '▶'}</span>
      </button>

      <span className="player__time">{formatDuration(currentTime)}</span>

      <input
        type="range"
        className="player__scrubber"
        min={0}
        max={effectiveDuration || 1}
        step={0.01}
        value={Math.min(currentTime, effectiveDuration || 1)}
        onChange={(event) => seek(Number(event.target.value))}
        disabled={!effectiveDuration || failed}
        aria-label="Seek"
      />

      <span className="player__time">{formatDuration(effectiveDuration)}</span>

      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          setPlaying(false);
          setCurrentTime(0);
        }}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
        onLoadedMetadata={(event) => {
          const value = event.currentTarget.duration;
          // Guard against Chrome's Infinity for MediaRecorder WebM.
          if (Number.isFinite(value) && value > 0) setDuration(value);
        }}
        onError={() => setFailed(true)}
      >
        <track kind="captions" />
      </audio>

      {failed && <span className="field__error">Playback failed</span>}
    </div>
  );
}
