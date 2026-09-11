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
    <Card title="Generated audio" hint={`${generation.engine} · ${generation.sampleRate / 1000} kHz`}>
      <div className="stack" data-testid="generation-result">
        {generation.notice && (
          <Callout kind="warning" title="Experimental output">
            {generation.notice}
          </Callout>
        )}

        <AudioPlayer
          src={generationAudioUrl(generation)}
          durationSeconds={generation.durationSeconds}
          label="the generated speech"
        />

        <div className="stat-grid">
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
        </div>

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
              Generate again
            </Button>
            {/* A plain link, not fetch+blob: the browser streams it straight to
                disk and the Content-Disposition header names the file. */}
            <a
              className="btn btn--primary"
              href={generationDownloadUrl(generation)}
              download={`${generation.id}.wav`}
              data-testid="download-wav"
            >
              Download WAV
            </a>
          </div>
        </div>
      </div>
    </Card>
  );
}
