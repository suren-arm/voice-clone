'use client';

import Link from 'next/link';
import { useState } from 'react';
import { AudioPlayer } from '@/components/AudioPlayer';
import { Button } from '@/components/Button';
import { Callout } from '@/components/Callout';
import { Card } from '@/components/Card';
import { EmptyState } from '@/components/EmptyState';
import { Spinner } from '@/components/Spinner';
import { useToast } from '@/hooks/useToast';
import { useVoices } from '@/hooks/useVoices';
import { voiceSampleUrl } from '@/services/voices';
import { formatDuration, formatRelativeTime } from '@/utils/format';

export function VoiceList() {
  const { voices, loading, error, remove } = useVoices();
  const { push } = useToast();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  async function handleDelete(id: string, name: string) {
    const confirmed = window.confirm(
      `Delete "${name}"?\n\nThis permanently removes the reference audio, the voice profile and every clip generated with it.`,
    );
    if (!confirmed) return;

    setPendingId(id);
    try {
      await remove(id);
      push('success', `Deleted "${name}".`);
    } catch {
      push('error', `Could not delete "${name}".`);
    } finally {
      setPendingId(null);
    }
  }

  if (loading) {
    return (
      <Card>
        <Spinner label="Loading your voices…" large />
      </Card>
    );
  }

  if (error) {
    return <Callout kind="error">{error}</Callout>;
  }

  if (voices.length === 0) {
    return (
      <Card>
        <EmptyState
          title="No voices yet"
          description="Create one from a 10–30 second recording to get started."
          action={
            <Link href="/voices/new" className="btn btn--primary">
              Create voice
            </Link>
          }
        />
      </Card>
    );
  }

  return (
    <Card flush>
      <ul className="list" data-testid="voice-list">
        {voices.map((voice) => {
          const sampleUrl = voiceSampleUrl(voice);
          const expanded = expandedId === voice.id;
          return (
            <li key={voice.id} className="list__item">
              <div className="grow stack-2">
                <span className="list__title">{voice.name}</span>
                <span className="list__meta">
                  <span className="badge">{voice.language}</span>
                  <span>{formatDuration(voice.referenceDurationSeconds)} reference</span>
                  <span>·</span>
                  <span>
                    {voice.generationCount} generation{voice.generationCount === 1 ? '' : 's'}
                  </span>
                  <span>·</span>
                  <span>created {formatRelativeTime(voice.createdAt)}</span>
                </span>
                {expanded && sampleUrl && (
                  <div style={{ marginTop: 8 }}>
                    <AudioPlayer
                      src={sampleUrl}
                      durationSeconds={voice.referenceDurationSeconds}
                      sunken
                      label={`the reference for ${voice.name}`}
                    />
                  </div>
                )}
              </div>

              <div className="row">
                {sampleUrl && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setExpandedId(expanded ? null : voice.id)}
                    aria-expanded={expanded}
                  >
                    {expanded ? 'Hide sample' : 'Sample'}
                  </Button>
                )}
                <Link
                  href={`/generate?voiceId=${encodeURIComponent(voice.id)}`}
                  className="btn btn--secondary btn--sm"
                >
                  Generate
                </Link>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => void handleDelete(voice.id, voice.name)}
                  loading={pendingId === voice.id}
                  data-testid={`delete-${voice.id}`}
                >
                  Delete
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
