import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { User, UserUpdate } from "../api/types";

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

  useEffect(() => {
    let active = true;
    listeners.add(setUser);
    if (cached === null) {
      setLoading(true);
      load()
        .then((u) => {
          if (active) {
            setUser(u);
            setError(null);
          }
        })
        .catch((e) => {
          if (active) setError(e instanceof Error ? e.message : String(e));
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }
    return () => {
      active = false;
      listeners.delete(setUser);
    };
  }, []);

  const reload = async () => {
    setLoading(true);
    try {
      const u = await refreshUser();
      setUser(u);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return { user, loading, error, reload };
}
