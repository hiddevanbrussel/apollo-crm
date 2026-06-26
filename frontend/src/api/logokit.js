import api from "./client";

let cache = null;
let inflight = null;

/** LogoKit only accepts 64, 128, or 256 — see https://docs.logokit.com/api-reference/logo-API */
function snapLogoSize(requested = 64) {
  if (requested <= 64) return 64;
  if (requested <= 128) return 128;
  return 256;
}

function normalizeDomain(domain) {
  if (!domain) return null;
  let value = String(domain).trim().toLowerCase();
  if (value.startsWith("www.")) value = value.slice(4);
  return value || null;
}

export function getLogokit() {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = api
      .get("/settings/logokit/client-config")
      .then((r) => {
        cache = r.data;
        return cache;
      })
      .catch(() => {
        cache = { enabled: false, configured: false };
        return cache;
      })
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}

export function resetLogokit() {
  cache = null;
  inflight = null;
}

export function logoUrl(cfg, domain, size = 64) {
  if (!cfg?.enabled || !cfg?.token || !domain) return null;
  const normalized = normalizeDomain(domain);
  if (!normalized) return null;
  const base = (cfg.base_url || "https://img.logokit.com").replace(/\/+$/, "");
  const params = new URLSearchParams({
    token: cfg.token,
    size: String(snapLogoSize(size)),
  });
  return `${base}/${encodeURIComponent(normalized)}?${params.toString()}`;
}
