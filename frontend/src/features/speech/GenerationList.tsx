'use client';

import Link from 'next/link';
import { useState } from 'react';
import { AudioPlayer } from '@/components/AudioPlayer';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Card } from '@/components/Card';
import { EmptyState } from '@/components/EmptyState';
import { Spinner } from '@/components/Spinner';
import { useGenerations } from '@/hooks/useGenerations';
import { useToast } from '@/hooks/useToast';
import { generationAudioUrl, generationDownloadUrl } from '@/services/speech';
import { formatDuration, formatRelativeTime, truncate } from '@/utils/format';

export function GenerationList() {
  const { generations, loading, error, remove } = useGenerations();
  const { push } = useToast();
  const [pendingId, setPendingId] = useState<string | null>(null);

  async function handleDelete(id: string) {
    setPendingId(id);
    try {
      await remove(id);
      push('success', 'Deleted.');
    } catch {
      push('error', 'Could not delete that clip.');
    } finally {
      setPendingId(null);
    }
  }

  if (loading) {
    return (
      <Card>
        <Spinner label="Loading history…" large />
      </Card>
    );
  }

  if (error) return <Callout kind="error">{error}</Callout>;

  if (generations.length === 0) {
    return (
      <Card>
        <EmptyState
          icon="🔊"
          title="Nothing generated yet"
          description="Generated clips appear here so you can replay and download them."
          action={
            <Link href="/generate" className="btn btn--primary">
              Generate speech
            </Link>
          }
        />
      </Card>
    );
  }

  return (
    <Card flush>
      <ul className="list" data-testid="generation-list">
        {generations.map((generation) => (
          <li key={generation.id} className="list__item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
            <div className="row row--between">
              <span className="list__meta">
                <span className="badge">{generation.language}</span>
                <span>{formatDuration(generation.durationSeconds)}</span>
                <span>·</span>
                <span>{formatRelativeTime(generation.createdAt)}</span>
                {generation.experimental && <span className="badge badge--warning">Experimental</span>}
                {generation.watermarked && <span className="badge badge--success">Watermarked</span>}
              </span>
              <div className="row">
                <a
                  className="btn btn--ghost btn--sm"
                  href={generationDownloadUrl(generation)}
                  download={`${generation.id}.wav`}
                >
                  Download
                </a>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => void handleDelete(generation.id)}
                  loading={pendingId === generation.id}
                >
                  Delete
                </Button>
              </div>
            </div>

            <p className="list__body">{truncate(generation.text, 180)}</p>

            <AudioPlayer
              src={generationAudioUrl(generation)}
              durationSeconds={generation.durationSeconds}
              sunken
            />
          </li>
        ))}
      </ul>
    </Card>
  );
}
