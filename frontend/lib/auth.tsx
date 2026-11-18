"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  api,
  clearAccessToken,
  getAccessToken,
  getCurrentSessionId,
  setAccessToken,
  subscribeSession,
  type User,
} from "@/lib/api";

type AuthContextValue = {
  user: User | null;
  isAuthenticated: boolean;
  currentSessionId: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  clearSession: () => void;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);

  const clearSession = useCallback(() => {
    clearAccessToken();
    setUser(null);
    setCurrentSessionId(null);
  }, []);

  useEffect(
    () =>
      subscribeSession(() => {
        setCurrentSessionId(getCurrentSessionId());
        if (!getAccessToken()) setUser(null);
      }),
    [],
  );

  const refreshUser = useCallback(async () => {
    if (!getAccessToken()) return;
    const tokenBeforeRequest = getAccessToken();
    const currentUser = await api.getMe();
    if (getAccessToken() === tokenBeforeRequest) setUser(currentUser);
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const token = await api.login({ email, password });
      setAccessToken(token.access_token);
      setUser(null);
      setCurrentSessionId(getCurrentSessionId());
      try {
        const currentUser = await api.getMe();
        if (getAccessToken() === token.access_token) setUser(currentUser);
      } catch (error: unknown) {
        if (getAccessToken() === token.access_token) clearSession();
        throw error;
      }
    },
    [clearSession],
  );

  const register = useCallback(
    async (username: string, email: string, password: string) => {
      await api.register({ username, email, password });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    const tokenAtLogout = getAccessToken();
    try {
      if (tokenAtLogout) await api.logout();
    } finally {
      if (getAccessToken() === tokenAtLogout) clearSession();
    }
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      currentSessionId,
      login,
      register,
      logout,
      clearSession,
      refreshUser,
    }),
    [user, currentSessionId, login, register, logout, clearSession, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider.");
  return context;
}
