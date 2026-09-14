'use client';

import { AudioPlayer } from '@/components/AudioPlayer';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Card } from '@/components/Card';
import { generationAudioUrl, generationDownloadUrl } from '@/services/speech';
import type { Generation } from '@/types';
import { formatBytes, formatDuration } from '@/utils/format';

interface GenerationResultProps {
  generation: Generation;
  onGenerateAgain: () => void;
}

export function GenerationResult({ generation, onGenerateAgain }: GenerationResultProps) {
  return (
    <Card
      title="🎵 Your recording is ready!"
      hint={`${formatDuration(generation.durationSeconds)} of audio — press play.`}
    >
      <div className="stack" data-testid="generation-result">
        {generation.notice && (
          <Callout kind="warning" title="Experimental output">
            {generation.notice}
          </Callout>
        )}

        {generation.backgroundNotice && (
          <Callout kind="info" title="Background sound">
            {generation.backgroundNotice}
          </Callout>
        )}

        <AudioPlayer
          src={generationAudioUrl(generation)}
          durationSeconds={generation.durationSeconds}
          label="your recording"
        />

        <div className="row row--between">
          <span className="list__meta">
            {generation.watermarked ? (
              <span className="badge badge--success">Watermarked</span>
            ) : (
              <span className="badge">No watermark</span>
            )}
            {generation.experimental && <span className="badge badge--warning">Experimental</span>}
          </span>

          <div className="row">
            <Button variant="secondary" onClick={onGenerateAgain} data-testid="generate-again">
              ↺ Make another
            </Button>
            {/* A plain link, not fetch+blob: the browser streams it straight to
                disk and the Content-Disposition header names the file. */}
            <a
              className="btn btn--primary"
              href={generationDownloadUrl(generation)}
              download={`${generation.id}.wav`}
              data-testid="download-wav"
            >
              ⬇ Download
            </a>
          </div>
        </div>

        {/* Render time, real-time factor and file size are engineering
            telemetry. They are genuinely useful when tuning the engine, so
            they stay -- just not as the thing a child sees first. */}
        <details>
          <summary className="field__hint" style={{ cursor: 'pointer' }}>
            Technical details
          </summary>
          <div className="stat-grid" style={{ marginTop: 'var(--space-3)' }}>
            <div>
              <div className="stat__label">Duration</div>
              <div className="stat__value">{formatDuration(generation.durationSeconds)}</div>
            </div>
            <div>
              <div className="stat__label">Generated in</div>
              <div className="stat__value">{generation.generationSeconds.toFixed(1)}s</div>
            </div>
            <div>
              <div className="stat__label" title="Generation time / audio duration">
                RTF
              </div>
              <div className="stat__value">{generation.realTimeFactor.toFixed(2)}</div>
            </div>
            <div>
              <div className="stat__label">Size</div>
              <div className="stat__value">{formatBytes(generation.sizeBytes)}</div>
            </div>
            <div>
              <div className="stat__label">Engine</div>
              <div className="stat__value">{generation.engine}</div>
            </div>
            <div>
              <div className="stat__label">Output</div>
              <div className="stat__value">{generation.sampleRate / 1000} kHz</div>
            </div>
          </div>
        </details>
      </div>
    </Card>
  );
}
