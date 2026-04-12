import { useState, useCallback, useEffect } from "react";

interface User {
  id: string;
  email: string;
  name: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
}

const TOKEN_KEY = "dr_access_token";
const REFRESH_KEY = "dr_refresh_token";

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: localStorage.getItem(TOKEN_KEY),
    isLoading: true,
  });

  // On mount, verify existing token
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      fetchMe(token).then((user) => {
        if (user) {
          setState({ user, token, isLoading: false });
        } else {
          // Token expired — try refresh
          tryRefresh().then((result) => {
            setState({
              user: result?.user || null,
              token: result?.token || null,
              isLoading: false,
            });
          });
        }
      });
    } else {
      setState((prev) => ({ ...prev, isLoading: false }));
    }
  }, []);

  const register = useCallback(
    async (email: string, password: string, name: string) => {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Registration failed");
      }
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(REFRESH_KEY, data.refresh_token);
      setState({ user: data.user, token: data.access_token, isLoading: false });
    },
    []
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Login failed");
      }
      const data = await res.json();
      localStorage.setItem(TOKEN_KEY, data.access_token);
      localStorage.setItem(REFRESH_KEY, data.refresh_token);
      setState({ user: data.user, token: data.access_token, isLoading: false });
    },
    []
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    setState({ user: null, token: null, isLoading: false });
  }, []);

  return {
    user: state.user,
    token: state.token,
    isLoading: state.isLoading,
    isAuthenticated: !!state.user,
    register,
    login,
    logout,
  };
}

async function fetchMe(token: string): Promise<User | null> {
  try {
    const res = await fetch("/api/auth/me", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) return res.json();
  } catch {}
  return null;
}

async function tryRefresh(): Promise<{ user: User; token: string } | null> {
  const refreshToken = localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return null;

  try {
    const res = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;

    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    localStorage.setItem(REFRESH_KEY, data.refresh_token);

    const user = await fetchMe(data.access_token);
    return user ? { user, token: data.access_token } : null;
  } catch {
    return null;
  }
}

/** Helper to get auth headers for API calls */
export function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}
