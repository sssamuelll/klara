import { useAuth } from "./auth";
import type { User, UserUpdate } from "../api/types";

export interface UseUserResult {
  user: User | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

export function useUser(): UseUserResult {
  const { user, loading, error, reload } = useAuth();
  return { user, loading, error, reload };
}

// Backwards-compat shim — components call patchUser() directly. We keep the
// imperative API so we don't have to thread useAuth through every consumer.
let _patchFn: ((patch: UserUpdate) => Promise<User>) | null = null;

export function _registerPatchUser(fn: (patch: UserUpdate) => Promise<User>): void {
  _patchFn = fn;
}

export async function patchUser(patch: UserUpdate): Promise<User> {
  if (_patchFn === null) {
    throw new Error("patchUser called before AuthProvider mounted");
  }
  return _patchFn(patch);
}
