import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { AuthRequiredError, api, onUnauthorized } from "../api/client";
import type { User, UserUpdate } from "../api/types";
import { writeCachedNativeLang } from "./preferences";
import { _registerPatchUser } from "./user";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
}

export interface AuthContextValue extends AuthState {
  reload: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  signup: (input: {
    email: string;
    password: string;
    display_name?: string;
    native_language?: string;
    invite_token?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  patchUser: (patch: UserUpdate) => Promise<User>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMe = useCallback(async () => {
    try {
      const u = await api.getMe();
      setUser(u);
      writeCachedNativeLang(u.native_language);
      setError(null);
    } catch (e) {
      if (e instanceof AuthRequiredError) {
        setUser(null);
      } else {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMe();
    return onUnauthorized(() => {
      setUser(null);
    });
  }, [fetchMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      await api.login(email, password);
      await fetchMe();
    },
    [fetchMe],
  );

  const signup = useCallback(
    async (input: {
      email: string;
      password: string;
      display_name?: string;
      native_language?: string;
      invite_token?: string;
    }) => {
      await api.signup(input);
      // FastAPI-Users doesn't auto-login on register; do an explicit login so
      // the user lands authenticated and we don't have to bounce through /login.
      await api.login(input.email, input.password);
      await fetchMe();
    },
    [fetchMe],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const patchUser = useCallback(async (patch: UserUpdate): Promise<User> => {
    const updated = await api.updateMe(patch);
    setUser(updated);
    writeCachedNativeLang(updated.native_language);
    return updated;
  }, []);

  useEffect(() => {
    _registerPatchUser(patchUser);
  }, [patchUser]);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, error, reload: fetchMe, login, signup, logout, patchUser }),
    [user, loading, error, fetchMe, login, signup, logout, patchUser],
  );

  return createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used within an <AuthProvider>");
  }
  return ctx;
}
