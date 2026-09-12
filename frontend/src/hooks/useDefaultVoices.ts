'use client';

import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '@/services/apiClient';
import { getDefaultVoices } from '@/services/voices';
import type { Voice } from '@/types';

export interface UseDefaultVoices {
  defaultVoices: Voice[];
  loading: boolean;
  error: string | null;
}

/**
 * The fixed, built-in default-voice catalog (espeak-ng): a handful of rows
 * that never change during a session, so unlike useVoices there is no
 * mutation surface here -- just load once.
 */
export function useDefaultVoices(): UseDefaultVoices {
  const [defaultVoices, setDefaultVoices] = useState<Voice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getDefaultVoices();
      // Defensive: a malformed/unexpected response should degrade to "no
      // default voices available" rather than crash every screen that
      // renders VoiceAndBackgroundFields.
      setDefaultVoices(Array.isArray(result) ? result : []);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'Could not load default voices.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { defaultVoices, loading, error };
}
