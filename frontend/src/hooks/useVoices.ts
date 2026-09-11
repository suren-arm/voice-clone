'use client';

import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '@/services/apiClient';
import { deleteVoice as deleteVoiceRequest, listVoices } from '@/services/voices';
import type { Voice } from '@/types';

export interface UseVoices {
  voices: Voice[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  remove: (voiceId: string) => Promise<void>;
}

export function useVoices(): UseVoices {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await listVoices();
      setVoices(page.items);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Could not load your voices.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const remove = useCallback(async (voiceId: string) => {
    await deleteVoiceRequest(voiceId);
    // Optimistic local removal: the server has already confirmed the delete,
    // so a refetch would only add a round trip.
    setVoices((current) => current.filter((voice) => voice.id !== voiceId));
  }, []);

  return { voices, loading, error, reload, remove };
}
