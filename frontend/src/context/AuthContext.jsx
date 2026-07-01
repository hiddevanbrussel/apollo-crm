import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import api, { getToken, setAuthBootstrapping, setAuthStateHandler, setToken } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const loadSeq = useRef(0);

  const loadMe = useCallback(async () => {
    const seq = ++loadSeq.current;
    setAuthBootstrapping(true);
    setLoading(true);

    const token = getToken();
    if (!token) {
      if (seq === loadSeq.current) {
        setUser(null);
        setAuthBootstrapping(false);
        setLoading(false);
      }
      return;
    }

    try {
      const { data } = await api.get("/auth/me");
      if (seq !== loadSeq.current) return;
      setUser(data);
    } catch {
      if (seq !== loadSeq.current) return;
      // Only clear the token if it is still the one this request used.
      if (getToken() === token) {
        setToken(null);
      }
      setUser(null);
    } finally {
      if (seq === loadSeq.current) {
        setAuthBootstrapping(false);
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadMe();
  }, [loadMe]);

  useEffect(() => {
    setAuthStateHandler(({ type }) => {
      if (type === "unauthorized") {
        setUser(null);
      }
    });
    return () => setAuthStateHandler(null);
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    setToken(data.access_token);
    setUser(data.user);
    setAuthBootstrapping(false);
    return data.user;
  };

  const completeSession = async (accessToken) => {
    setToken(accessToken);
    await loadMe();
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    setAuthBootstrapping(false);
  };

  const isAdmin = user?.role === "admin";

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, completeSession, isAdmin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
