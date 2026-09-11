import type { ReactNode } from 'react';

interface CalloutProps {
  kind?: 'info' | 'warning' | 'error' | 'neutral';
  title?: ReactNode;
  children: ReactNode;
}

const ICONS = { info: 'ℹ', warning: '⚠', error: '⚠', neutral: '•' } as const;

export function Callout({ kind = 'neutral', title, children }: CalloutProps) {
  return (
    <div
      className={kind === 'neutral' ? 'callout' : `callout callout--${kind}`}
      role={kind === 'error' ? 'alert' : undefined}
    >
      <span aria-hidden="true">{ICONS[kind]}</span>
      <div>
        {title && <div className="callout__title">{title}</div>}
        <div>{children}</div>
      </div>
    </div>
  );
}
