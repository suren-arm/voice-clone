import type { ReactNode } from 'react';

interface CardProps {
  title?: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
  flush?: boolean;
  children: ReactNode;
}

export function Card({ title, hint, action, flush = false, children }: CardProps) {
  return (
    <section className={flush ? 'card card--flush' : 'card'}>
      {(title || action) && (
        <header className="card__header" style={flush ? { padding: '20px 24px 0' } : undefined}>
          <div>
            {title && <h2 className="card__title">{title}</h2>}
            {hint && <p className="card__hint">{hint}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}
