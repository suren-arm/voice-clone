'use client';

import { useCallback, useEffect, useState } from 'react';
import { ApiError } from '@/services/apiClient';
import { getSystemInfo } from '@/services/system';
import type { SystemInfo } from '@/types';

/**
 * Server capabilities: language list, limits, engine details.
 *
 * Cached in module scope because every screen needs it and it does not change
 * while the tab is open.
 */
let cached: SystemInfo | null = null;
let inflight: Promise<SystemInfo> | null = null;

export function resetSystemInfoCache() {
  cached = null;
  inflight = null;
}

function load(): Promise<SystemInfo> {
  if (cached) return Promise.resolve(cached);
  inflight ??= getSystemInfo()
    .then((info) => {
      cached = info;
      return info;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

export interface UseSystemInfo {
  info: SystemInfo | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useSystemInfo(): UseSystemInfo {
  const [info, setInfo] = useState<SystemInfo | null>(cached);
  const [loading, setLoading] = useState(!cached);
  const [error, setError] = useState<string | null>(null);

  const fetchInfo = useCallback(() => {
    let active = true;
    setLoading(true);
    setError(null);
    load()
      .then((result) => {
        if (active) setInfo(result);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof ApiError
            ? cause.message
            : 'Could not reach the server. Is the backend running?',
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => fetchInfo(), [fetchInfo]);

  const reload = useCallback(() => {
    resetSystemInfoCache();
    fetchInfo();
  }, [fetchInfo]);

  return { info, loading, error, reload };
}
