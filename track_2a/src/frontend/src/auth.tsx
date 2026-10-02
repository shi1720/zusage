/** Session state: who is signed in, plus server config (live vs offline). */

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, ApiError } from "./api";
import { useI18n } from "./lib/i18n";
import type { AppConfig, User } from "./types";

interface AuthState {
  user: User | null;
  config: AppConfig | null;
  ready: boolean;
  error: string | null;
  setUser: (user: User | null) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  config: null,
  ready: false,
  error: null,
  setUser: () => {},
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUserState] = useState<User | null>(null);
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const { setLang } = useI18n();

  const setUser = useCallback(
    (next: User | null) => {
      setUserState(next);
      if (next) setLang(next.ui_lang);
    },
    [setLang],
  );

  useEffect(() => {
    (async () => {
      try {
        setConfig(await api.config());
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : "API unreachable");
        setReady(true);
        return;
      }
      try {
        setUser(await api.auth.me());
      } catch (exc) {
        if (!(exc instanceof ApiError && exc.status === 401)) setError(String(exc));
      }
      setReady(true);
    })();
  }, [setUser]);

  const signOut = useCallback(async () => {
    await api.auth.logout();
    queryClient.clear();
    setUserState(null);
  }, [queryClient]);

  return (
    <AuthContext.Provider value={{ user, config, ready, error, setUser, signOut }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
