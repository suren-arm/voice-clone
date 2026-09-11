'use client';

import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '@/services/apiClient';
import { deleteGeneration as deleteGenerationRequest, listGenerations } from '@/services/speech';
import type { Generation } from '@/types';

export interface UseGenerations {
  generations: Generation[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  remove: (id: string) => Promise<void>;
  prepend: (generation: Generation) => void;
}

export function useGenerations(voiceId?: string): UseGenerations {
  const [generations, setGenerations] = useState<Generation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await listGenerations(voiceId);
      setGenerations(page.items);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Could not load generated audio.');
    } finally {
      setLoading(false);
    }
  }, [voiceId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const remove = useCallback(async (id: string) => {
    await deleteGenerationRequest(id);
    setGenerations((current) => current.filter((item) => item.id !== id));
  }, []);

  const prepend = useCallback((generation: Generation) => {
    setGenerations((current) => [generation, ...current]);
  }, []);

  return { generations, loading, error, reload, remove, prepend };
}
