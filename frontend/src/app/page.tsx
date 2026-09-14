'use client';

import Link from 'next/link';
import { Callout } from '@/components/Callout';
import { Spinner } from '@/components/Spinner';
import { useSystemInfo } from '@/hooks/useSystemInfo';

/**
 * Four things you can actually do, each with its own colour so the app reads
 * as "pick an adventure" rather than "choose a menu item". Copy is written
 * for a child first -- the technical name for each feature lives on the page
 * it belongs to, not on the front door.
 */
const MODE_TILES = [
  {
    href: '/fairy-tale',
    icon: '✨',
    hue: 'tile--grape',
    title: 'Create a Fairy Tale',
    description: 'Pick who is in it and where it happens. We write the story.',
    cta: 'Start a story →',
  },
  {
    href: '/book-reader',
    icon: '📖',
    hue: 'tile--sky',
    title: 'Read a Book',
    description: 'Open a PDF or a web link and have it read out loud to you.',
    cta: 'Open a book →',
  },
  {
    href: '/generate',
    icon: '🗣️',
    hue: 'tile--mint',
    title: 'Speak My Text',
    description: 'Type anything you like and hear it in the voice you choose.',
    cta: 'Type something →',
  },
  {
    href: '/voices/new',
    icon: '🎤',
    hue: 'tile--coral',
    title: 'Make My Own Voice',
    description: 'Record a few seconds and stories can be read in your voice.',
    cta: 'Record my voice →',
  },
] as const;

const LIBRARY_TILES = [
  {
    href: '/voices',
    icon: '🗂',
    title: 'My Voices',
    description: 'Listen to, or remove, the voices you have made.',
  },
  {
    href: '/history',
    icon: '🎵',
    title: 'My Recordings',
    description: 'Play again or download anything you have created.',
  },
] as const;

export default function HomePage() {
  const { info, loading, error } = useSystemInfo();

  return (
    <div className="stack-5">
      <header className="hero">
        <h1 className="hero__title">
          Voice Story Studio <span aria-hidden="true">✨</span>
        </h1>
        <p className="hero__lede">
          Make up a story, open a book, or hear your own words out loud — in English or Հայերեն.
        </p>
      </header>

      <nav className="home-actions" aria-label="What would you like to do?">
        {MODE_TILES.map((tile) => (
          <Link key={tile.href} href={tile.href} className={`tile tile--primary ${tile.hue}`}>
            <span className="tile__icon" aria-hidden="true">
              {tile.icon}
            </span>
            <span className="tile__title">{tile.title}</span>
            <span className="tile__desc">{tile.description}</span>
            <span className="tile__cta" aria-hidden="true">
              {tile.cta}
            </span>
          </Link>
        ))}
      </nav>

      <nav className="home-actions" aria-label="Things you have made">
        {LIBRARY_TILES.map((tile) => (
          <Link key={tile.href} href={tile.href} className="tile">
            <span className="tile__icon" aria-hidden="true">
              {tile.icon}
            </span>
            <span className="tile__title">{tile.title}</span>
            <span className="tile__desc">{tile.description}</span>
          </Link>
        ))}
      </nav>

      <Callout kind="info" title="A note for grown-ups">
        Only make a voice from a recording of yourself, or of someone who has said yes. Deleting a
        voice removes its recording and everything made with it.
      </Callout>

      {/* Engine/device/licence detail is developer information, so it sits at
          the bottom behind a disclosure rather than greeting a child with a
          status dashboard. */}
      <details className="card">
        <summary className="card__title" style={{ cursor: 'pointer' }}>
          Studio status
        </summary>
        <div style={{ marginTop: 'var(--space-4)' }}>
          {loading && <Spinner label="Waking up the studio…" />}
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
        </div>
      </details>
    </div>
  );
}
