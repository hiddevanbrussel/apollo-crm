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

function normalizeToken(token) {
  if (!token) return null;
  const value = String(token).trim();
  if (!value || value === "null" || value === "undefined") return null;
  return value.replace(/^Bearer\s+/i, "");
}

export function setToken(token) {
  const normalized = normalizeToken(token);
  if (normalized) {
    localStorage.setItem(TOKEN_KEY, normalized);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getToken() {
  return normalizeToken(localStorage.getItem(TOKEN_KEY));
}

export function isUnauthorized(error) {
  return error?.isAuthError === true || error?.response?.status === 401;
}

function isAuthMeRequest(url = "") {
  return url.includes("/auth/me");
}

function isAuthBootstrapRequest(url = "") {
  return isAuthMeRequest(url) || url.includes("/auth/azure/config");
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

      // Bootstrap auth failures are handled in AuthContext (avoid clearing a fresh token).
      if (!isAuthBootstrapRequest(url)) {
        setToken(null);
        authStateHandler?.({ type: "unauthorized" });

        if (!authBootstrapping && window.location.pathname !== "/login") {
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
