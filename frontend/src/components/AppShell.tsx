'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

/**
 * Ordered the way someone actually uses the app -- the three things you can
 * make come first, then the things you have already made. "Book Reader" was
 * previously reachable only from the home page, which made it invisible from
 * every other screen.
 */
const NAV = [
  { href: '/', label: 'Home' },
  { href: '/fairy-tale', label: '✨ Fairy Tale' },
  { href: '/book-reader', label: '📖 Read a Book' },
  { href: '/generate', label: '🗣️ Speak Text' },
  { href: '/voices', label: 'My Voices' },
  { href: '/history', label: 'My Recordings' },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  const isCurrent = (href: string) =>
    href === '/' ? pathname === '/' : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <div className="shell">
      <header className="shell__header">
        <div className="shell__header-inner">
          <Link href="/" className="brand">
            <span className="brand__mark" aria-hidden="true">
              ✨
            </span>
            Voice Story Studio
          </Link>
          <nav className="nav" aria-label="Main">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="nav__link"
                aria-current={isCurrent(item.href) ? 'page' : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <main className="shell__main">{children}</main>

      <footer className="shell__footer">
        Made for storytelling. Only use a voice that is yours, or one you have permission to use.
      </footer>
    </div>
  );
}
