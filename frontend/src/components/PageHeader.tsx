import type { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  lede?: ReactNode;
  action?: ReactNode;
}

export function PageHeader({ title, lede, action }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="row row--between">
        <h1>{title}</h1>
        {action}
      </div>
      {lede && <p className="page-header__lede">{lede}</p>}
    </header>
  );
}
