"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type CacheEntry<T> = {
  data?: T;
  ts: number;
  promise?: Promise<T>;
  error?: Error;
};

const store = new Map<string, CacheEntry<unknown>>();

const DEFAULT_STALE_MS = 15_000;

function staleMsForKey(key: string): number {
  if (key.startsWith("dashboard:")) return 10_000;
  if (key.startsWith("contracts:")) return 15_000;
  if (key.startsWith("contract:")) return 30_000;
  if (key.startsWith("obligations:")) return 30_000;
  if (key.startsWith("activity:")) return 15_000;
  if (key.startsWith("category:")) return Number.POSITIVE_INFINITY;
  return DEFAULT_STALE_MS;
}

export function mutate<T>(key: string, updater?: T | ((prev: T | undefined) => T | undefined)) {
  const entry = store.get(key) as CacheEntry<T> | undefined;
  if (!entry) return;
  if (typeof updater === "function") {
    entry.data = (updater as (prev: T | undefined) => T | undefined)(entry.data);
  } else if (updater !== undefined) {
    entry.data = updater;
  }
  entry.ts = Date.now();
}

export function invalidateByPrefix(prefix: string) {
  const keys = Array.from(store.keys());
  for (const key of keys) {
    if (key.startsWith(prefix)) {
      store.delete(key);
    }
  }
}

export function invalidateContract(contractId: string) {
  invalidateByPrefix(`contract:${contractId}`);
  invalidateByPrefix(`obligations:${contractId}`);
  invalidateByPrefix(`activity:${contractId}`);
  invalidateByPrefix("dashboard:");
  invalidateByPrefix("contracts:");
}

export function useCachedFetch<T>(
  key: string,
  fetcher: () => Promise<T>,
  opts?: { staleMs?: number; enabled?: boolean }
) {
  const enabled = opts?.enabled !== false;
  const staleMs = opts?.staleMs ?? staleMsForKey(key);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const [data, setData] = useState<T | null>(() => {
    const hit = store.get(key) as CacheEntry<T> | undefined;
    return (hit?.data as T | undefined) ?? null;
  });
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(() => {
    const hit = store.get(key);
    return enabled && !hit?.data;
  });
  const [isValidating, setIsValidating] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const revalidate = useCallback(
    async (keepPrevious: boolean) => {
      if (!enabled) return;
      let entry = store.get(key) as CacheEntry<T> | undefined;
      if (!entry) {
        entry = { ts: 0 };
        store.set(key, entry);
      }
      if (entry.promise) {
        try {
          const v = await entry.promise;
          setData(v);
          setIsLoading(false);
        } catch (e) {
          setError(e as Error);
          setIsLoading(false);
        }
        return;
      }

      if (keepPrevious && entry.data !== undefined) {
        setIsValidating(true);
      } else if (!entry.data) {
        setIsLoading(true);
      }

      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;

      const p = fetcherRef.current();
      store.set(key, { ...entry, promise: p });

      try {
        const result = await p;
        if (ac.signal.aborted) return;
        store.set(key, { data: result, ts: Date.now() });
        setData(result);
        setError(null);
      } catch (e) {
        if (ac.signal.aborted) return;
        const err = e instanceof Error ? e : new Error(String(e));
        store.set(key, { ...entry, error: err, promise: undefined });
        setError(err);
      } finally {
        const cur = store.get(key) as CacheEntry<T>;
        if (cur) cur.promise = undefined;
        setIsLoading(false);
        setIsValidating(false);
      }
    },
    [enabled, key]
  );

  useEffect(() => {
    if (!enabled) return;
    const entry = store.get(key) as CacheEntry<T> | undefined;
    const age = entry ? Date.now() - entry.ts : Infinity;
    const hasData = entry?.data !== undefined;
    if (!hasData) {
      void revalidate(false);
    } else {
      setData(entry!.data as T);
      setIsLoading(false);
      if (age > staleMs) {
        void revalidate(true);
      }
    }
    return () => {
      abortRef.current?.abort();
    };
  }, [enabled, key, revalidate, staleMs]);

  const refresh = useCallback(() => {
    store.delete(key);
    return revalidate(false);
  }, [key, revalidate]);

  const localMutate = useCallback(
    (updater?: T | ((prev: T | null) => T | null)) => {
      mutate(key, (prev) => {
        const p = prev as T | undefined;
        if (typeof updater === "function") {
          return (updater as (prev: T | null) => T | null)(p ?? null) ?? undefined;
        }
        return updater ?? undefined;
      });
      const hit = store.get(key) as CacheEntry<T> | undefined;
      setData((hit?.data as T | undefined) ?? null);
    },
    [key]
  );

  return { data, isLoading, isValidating, error, mutate: localMutate, refresh };
}
