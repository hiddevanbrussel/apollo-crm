import axios from "axios";

// Production: same-origin /api via nginx. Dev: backend on :8000 with /api prefix.
const baseURL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? "http://localhost:8000/api" : "/api");

const api = axios.create({ baseURL });

const TOKEN_KEY = "apollo_crm_token";

let authBootstrapping = true;
let authBootstrapDone = false;
let authBootstrapWaiters = [];
let authStateHandler = null;

function resolveAuthBootstrapWaiters() {
  authBootstrapWaiters.forEach((resolve) => resolve());
  authBootstrapWaiters = [];
}

export function setAuthBootstrapping(value) {
  authBootstrapping = value;
  if (!value) {
    authBootstrapDone = true;
    resolveAuthBootstrapWaiters();
  }
}

export function setAuthStateHandler(handler) {
  authStateHandler = handler;
}

function waitForAuthBootstrap() {
  if (authBootstrapDone || !authBootstrapping) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    authBootstrapWaiters.push(resolve);
  });
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

function isPublicRequest(url = "") {
  return (
    url.includes("/auth/login") ||
    url.includes("/auth/azure/config") ||
    url.includes("/health")
  );
}

function isAuthBootstrapRequest(url = "") {
  return isAuthMeRequest(url) || url.includes("/auth/azure/config");
}

function responseDetail(data) {
  if (data == null) return null;
  if (typeof data === "string") {
    const trimmed = data.trim();
    if (trimmed.startsWith("{")) {
      try {
        const parsed = JSON.parse(trimmed);
        if (parsed?.detail != null) return parsed.detail;
      } catch {
        // fall through
      }
    }
    return trimmed || null;
  }
  return data.detail ?? null;
}

api.interceptors.request.use(async (config) => {
  const url = config.url || "";
  // Bootstrap requests must not wait — /auth/me is what completes bootstrap.
  if (!isPublicRequest(url) && !isAuthBootstrapRequest(url)) {
    await waitForAuthBootstrap();
  }
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

      // During bootstrap only AuthContext handles /auth/me; never clear the token yet.
      if (!authBootstrapping && !isAuthBootstrapRequest(url)) {
        setToken(null);
        authStateHandler?.({ type: "unauthorized" });

        const path = window.location.pathname;
        if (path !== "/login" && !path.startsWith("/login/")) {
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
  const detail = responseDetail(error?.response?.data);
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join(", ");
  }
  if (typeof detail === "object" && detail !== null) {
    return JSON.stringify(detail);
  }
  return detail || error?.message || fallback;
}

/** Show a toast for an API error; silently ignores auth/session errors. */
export function notifyApiError(toast, error, fallback = "Something went wrong.") {
  const message = apiError(error, fallback);
  if (message) {
    toast.error(message);
  }
}

export default api;
