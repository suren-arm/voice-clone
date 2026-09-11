'use client';

import { useId } from 'react';
import type { ReactNode } from 'react';

interface FieldProps {
  label: string;
  hint?: ReactNode;
  error?: string | null;
  counter?: ReactNode;
  children: (props: { id: string; 'aria-invalid': boolean; 'aria-describedby': string | undefined }) => ReactNode;
}

/**
 * Label + control + hint/error, wired together for screen readers.
 *
 * Render-prop rather than cloning children so the control keeps full control
 * of its own props and `useId` guarantees unique, SSR-stable ids.
 */
export function Field({ label, hint, error, counter, children }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined;

  return (
    <div className="field">
      <div className="row row--between" style={{ gap: 8 }}>
        <label className="field__label" htmlFor={id}>
          {label}
        </label>
        {counter}
      </div>
      {children({ id, 'aria-invalid': Boolean(error), 'aria-describedby': describedBy })}
      {error ? (
        <p className="field__error" id={errorId} role="alert">
          {error}
        </p>
      ) : (
        hint && (
          <p className="field__hint" id={hintId}>
            {hint}
          </p>
        )
      )}
    </div>
  );
}
