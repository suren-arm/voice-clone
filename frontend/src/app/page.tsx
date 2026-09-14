'use client';

import Link from 'next/link';
import { Callout } from '@/components/Callout';
import { Card } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';
import { Spinner } from '@/components/Spinner';
import { useSystemInfo } from '@/hooks/useSystemInfo';

const MODE_TILES = [
  {
    href: '/generate',
    icon: '✍️',
    title: 'Text to Speech',
    description: 'Type or paste text and hear it in your cloned voice or a default voice.',
  },
  {
    href: '/fairy-tale',
    icon: '✨',
    title: 'Create Fairy Tale',
    description: 'Generate an original story in English or Հայերեն, then narrate it.',
  },
  {
    href: '/book-reader',
    icon: '📖',
    title: 'Book Reader',
    description: 'Upload a PDF or paste a public web link, then listen to it.',
  },
] as const;

const TILES = [
  {
    href: '/voices/new',
    icon: '🎙',
    title: 'Create Voice',
    description: 'Record 10–30 seconds, or upload a file.',
  },
  {
    href: '/voices',
    icon: '🗂',
    title: 'My Voices',
    description: 'Review, sample and delete your voice profiles.',
  },
  {
    href: '/history',
    icon: '🔊',
    title: 'Generated Audio',
    description: 'Replay and download everything you have made.',
  },
] as const;

export default function HomePage() {
  const { info, loading, error } = useSystemInfo();

  return (
    <div className="stack-5">
      <PageHeader
        title="Voice Story Studio"
        lede="Clone your own voice, or use a built-in default voice — no recording required. Write text or generate a fairy tale in English or Հայերեն, and narrate it with optional background ambience. Everything runs on your own backend."
      />

      <nav className="home-actions" aria-label="Main modes">
        {MODE_TILES.map((tile) => (
          <Link key={tile.href} href={tile.href} className="tile tile--primary">
            <span className="tile__icon" aria-hidden="true">
              {tile.icon}
            </span>
            <span className="tile__title">{tile.title}</span>
            <span className="tile__desc">{tile.description}</span>
          </Link>
        ))}
      </nav>

      <nav className="home-actions" aria-label="More actions">
        {TILES.map((tile) => (
          <Link key={tile.href} href={tile.href} className="tile">
            <span className="tile__icon" aria-hidden="true">
              {tile.icon}
            </span>
            <span className="tile__title">{tile.title}</span>
            <span className="tile__desc">{tile.description}</span>
          </Link>
        ))}
      </nav>

      <Callout kind="warning" title="Clone responsibly">
        Only create a voice from a recording of yourself, or one you have the speaker&apos;s explicit
        permission to use. Deleting a voice removes its reference audio, its speaker profile and
        every clip generated from it.
      </Callout>

      <Card title="Backend status">
        {loading && <Spinner label="Contacting the API…" />}
        {error && <Callout kind="error">{error}</Callout>}
        {info && (
          <div className="stat-grid" data-testid="system-status">
            <div>
              <div className="stat__label">Model</div>
              <div className="stat__value">
                {info.engine.name} / {info.engine.variant}
              </div>
            </div>
            <div>
              <div className="stat__label">Device</div>
              <div className="stat__value">{info.engine.device.toUpperCase()}</div>
            </div>
            <div>
              <div className="stat__label">Output</div>
              <div className="stat__value">{info.engine.sampleRate / 1000} kHz</div>
            </div>
            <div>
              <div className="stat__label">Languages</div>
              <div className="stat__value">{info.languages.length}</div>
            </div>
            <div>
              <div className="stat__label">Watermark</div>
              <div className="stat__value">{info.engine.watermarked ? 'Yes' : 'No'}</div>
            </div>
            <div>
              <div className="stat__label">Licence</div>
              <div className="stat__value" style={{ fontSize: '0.85rem' }}>
                {info.engine.license}
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
