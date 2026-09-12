'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

const NAV = [
  { href: '/', label: 'Home' },
  { href: '/generate', label: 'Text to Speech' },
  { href: '/fairy-tale', label: 'Create Fairy Tale' },
  { href: '/voices/new', label: 'Create Voice' },
  { href: '/voices', label: 'My Voices' },
  { href: '/history', label: 'History' },
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
              ◉
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
        Open-source voice cloning. Only clone a voice you own or have explicit permission to use.
      </footer>
    </div>
  );
}
