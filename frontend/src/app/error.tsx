'use client';

import { useEffect } from 'react';
import { Button } from '@/components/Button';
import { EmptyState } from '@/components/EmptyState';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <EmptyState
      icon="⚠"
      title="Something went wrong"
      description="An unexpected error occurred while rendering this page."
      action={
        <Button variant="primary" onClick={reset}>
          Try again
        </Button>
      }
    />
  );
}
