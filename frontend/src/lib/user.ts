import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { User, UserUpdate } from "../api/types";
import { writeCachedNativeLang } from "./preferences";

type Listener = (user: User | null) => void;

let cached: User | null = null;
let inflight: Promise<User> | null = null;
const listeners = new Set<Listener>();

function emit() {
  for (const l of listeners) l(cached);
}

async function load(): Promise<User> {
  if (cached) return cached;
  if (!inflight) {
    inflight = api.getMe().then((u) => {
      cached = u;
      writeCachedNativeLang(u.native_language);
      emit();
      return u;
    });
  }
  try {
    return await inflight;
  } finally {
    inflight = null;
  }
}

export async function refreshUser(): Promise<User> {
  cached = null;
  return load();
}

export async function patchUser(patch: UserUpdate): Promise<User> {
  const updated = await api.updateMe(patch);
  cached = updated;
  writeCachedNativeLang(updated.native_language);
  emit();
  return updated;
}

export interface UseUserResult {
  user: User | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

export function useUser(): UseUserResult {
  const [user, setUser] = useState<User | null>(cached);
  const [loading, setLoading] = useState<boolean>(cached === null);
  const [error, setError] = useState<string | null>(null);
  const activeRef = useRef(true);

  useEffect(() => {
    activeRef.current = true;
    listeners.add(setUser);
    if (cached === null) {
      setLoading(true);
      load()
        .then((u) => {
          if (activeRef.current) {
            setUser(u);
            setError(null);
          }
        })
        .catch((e) => {
          if (activeRef.current) setError(e instanceof Error ? e.message : String(e));
        })
        .finally(() => {
          if (activeRef.current) setLoading(false);
        });
    }
    return () => {
      activeRef.current = false;
      listeners.delete(setUser);
    };
  }, []);

  const reload = useCallback(async () => {
    if (activeRef.current) setLoading(true);
    try {
      const u = await refreshUser();
      if (activeRef.current) {
        setUser(u);
        setError(null);
      }
    } catch (e) {
      if (activeRef.current) setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (activeRef.current) setLoading(false);
    }
  }, []);

  return { user, loading, error, reload };
}
