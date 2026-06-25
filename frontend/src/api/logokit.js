import api from "./client";

let cache = null;
let inflight = null;

export function getLogokit() {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = api
      .get("/settings/logokit")
      .then((r) => {
        cache = r.data;
        return cache;
      })
      .catch(() => {
        cache = { enabled: false };
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
  const base = (cfg.base_url || "https://img.logokit.com").replace(/\/+$/, "");
  return `${base}/${encodeURIComponent(domain)}?token=${encodeURIComponent(cfg.token)}&size=${size}`;
}
