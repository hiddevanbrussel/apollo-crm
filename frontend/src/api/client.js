import axios from "axios";

// Empty baseURL in production: nginx proxies /auth, /companies, … to the backend.
const baseURL =
  import.meta.env.VITE_API_URL || (import.meta.env.DEV ? "http://localhost:8000" : "");

const api = axios.create({ baseURL });

const TOKEN_KEY = "apollo_crm_token";

let authBootstrapping = true;
let authStateHandler = null;

export function setAuthBootstrapping(value) {
  authBootstrapping = value;
}

export function setAuthStateHandler(handler) {
  authStateHandler = handler;
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, String(token).trim());
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getToken() {
  const token = localStorage.getItem(TOKEN_KEY);
  return token?.trim() || null;
}

export function isUnauthorized(error) {
  return error?.isAuthError === true || error?.response?.status === 401;
}

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = error.config?.url || "";

    if (status === 401 && !url.includes("/auth/login")) {
      error.isAuthError = true;
      setToken(null);
      authStateHandler?.({ type: "unauthorized" });

      const isAuthMe = url.includes("/auth/me");
      if (!authBootstrapping || !isAuthMe) {
        // Mid-session expiry: hard redirect so open tabs recover cleanly.
        if (window.location.pathname !== "/login") {
          window.location.replace("/login");
        }
      }
    }

    return Promise.reject(error);
  }
);

export function apiError(error, fallback = "Something went wrong.") {
  if (isUnauthorized(error)) {
    return null;
  }
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join(", ");
  }
  if (typeof detail === "object" && detail !== null) {
    return JSON.stringify(detail);
  }
  return detail || error?.message || fallback;
}

export default api;
