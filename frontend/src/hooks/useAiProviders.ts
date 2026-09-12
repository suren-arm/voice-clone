'use client';

import { useEffect, useState } from 'react';
import { ApiError } from '@/services/apiClient';
import { getAiProviders } from '@/services/aiProviders';
import type { AiProvidersInfo } from '@/types';

export interface UseAiProviders {
  info: AiProvidersInfo | null;
  loading: boolean;
  error: string | null;
}

/** Loaded once per page: which AI providers are configured, and what "Auto" resolves to. */
export function useAiProviders(): UseAiProviders {
  const [info, setInfo] = useState<AiProvidersInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getAiProviders()
      .then((result) => {
        if (active) setInfo(result);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(cause instanceof ApiError ? cause.message : 'Could not load AI providers.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return { info, loading, error };
}
