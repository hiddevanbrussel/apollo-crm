import { useEffect, useState } from "react";
import { getLogokit, logoUrl } from "../api/logokit";
import { Icon } from "./icons";

export function CompanyLogo({ domain, name, size = 40, rounded = "rounded-lg", className = "" }) {
  const [cfg, setCfg] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let mounted = true;
    getLogokit().then((c) => mounted && setCfg(c));
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    setError(false);
  }, [domain]);

  const dim = { width: size, height: size };
  const url = logoUrl(cfg, domain, size * 2);

  if (url && !error) {
    return (
      <img
        src={url}
        alt={name || domain}
        style={dim}
        onError={() => setError(true)}
        className={`flex-shrink-0 border border-ink-100 bg-white object-contain ${rounded} ${className}`}
      />
    );
  }

  return (
    <div
      style={dim}
      className={`flex flex-shrink-0 items-center justify-center bg-brand-50 text-brand-500 ${rounded} ${className}`}
    >
      <Icon.Building width={Math.round(size * 0.5)} height={Math.round(size * 0.5)} />
    </div>
  );
}

export function Spinner({ className = "" }) {
  return (
    <div
      className={`inline-block h-5 w-5 animate-spin rounded-full border-2 border-ink-200 border-t-brand-600 ${className}`}
    />
  );
}

export function PageLoader() {
  return (
    <div className="flex h-64 items-center justify-center">
      <Spinner className="h-7 w-7" />
    </div>
  );
}

const STATUS_STYLES = {
  enriched: { wrap: "bg-green-50 text-green-700", dot: "bg-green-500" },
  none: { wrap: "bg-ink-100 text-ink-600", dot: "bg-ink-400" },
  pending: { wrap: "bg-amber-50 text-amber-700", dot: "bg-amber-500" },
  failed: { wrap: "bg-red-50 text-red-700", dot: "bg-red-500" },
};

const STATUS_LABELS = {
  enriched: "Enriched",
  none: "Not enriched",
  pending: "In progress",
  failed: "Failed",
};

export function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.none;
  return (
    <span className={`badge ${style.wrap}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {STATUS_LABELS[status] || status}
    </span>
  );
}

const SOURCE_LABELS = { apollo: "APOLLO", prospeo: "PROSPEO", seed: "DEMO", import: "IMPORT", manual: "MANUAL" };

const SOURCE_STYLES = {
  apollo: "border-accent-200 bg-accent-50 text-accent-600",
  prospeo: "border-violet-200 bg-violet-50 text-violet-700",
  import: "border-green-200 bg-green-50 text-green-700",
};

export function SourceBadge({ source }) {
  const style = SOURCE_STYLES[source] || "";
  return (
    <span className={`badge-mono ${style}`}>
      {SOURCE_LABELS[source] || source?.toUpperCase() || "MANUAL"}
    </span>
  );
}

export function DomainTags({ domains, primary, className = "" }) {
  const all = domains?.length
    ? domains
    : primary
      ? [primary]
      : [];
  if (!all.length) {
    return <span className="text-xs text-ink-400">—</span>;
  }
  return (
    <div className={`flex flex-wrap gap-1 ${className}`}>
      {all.map((d) => (
        <span
          key={d}
          className={`inline-flex items-center rounded-md px-2 py-0.5 font-mono text-xs ${
            d === primary
              ? "border border-brand-200 bg-brand-50 text-brand-700"
              : "border border-ink-200 bg-ink-50 text-ink-600"
          }`}
          title={d === primary ? "Primary domain" : "Additional domain"}
        >
          {d}
        </span>
      ))}
    </div>
  );
}

export function EmptyState({ title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <div className="mb-3 rounded-full bg-ink-100 p-3 text-ink-400">
        <Icon.Search width={24} height={24} />
      </div>
      <h3 className="text-sm font-semibold text-ink-800">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-ink-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="flex items-center justify-between border-t border-ink-100 px-4 py-3">
      <p className="text-sm text-ink-500">
        {from}–{to} of {total}
      </p>
      <div className="flex items-center gap-2">
        <button
          className="btn-secondary px-2 py-1.5"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          <Icon.ChevronLeft width={16} height={16} />
        </button>
        <span className="text-sm text-ink-600">
          {page} / {totalPages}
        </span>
        <button
          className="btn-secondary px-2 py-1.5"
          disabled={page >= totalPages}
          onClick={() => onPage(page + 1)}
        >
          <Icon.ChevronRight width={16} height={16} />
        </button>
      </div>
    </div>
  );
}

export function Modal({ open, onClose, title, children, footer, wide = false }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink-900/30 backdrop-blur-sm" onClick={onClose} />
      <div
        className={`relative z-10 w-full ${wide ? "max-w-3xl" : "max-w-lg"} rounded-xl bg-white shadow-soft`}
      >
        <div className="flex items-center justify-between border-b border-ink-100 px-5 py-4">
          <h3 className="text-base font-semibold text-ink-900">{title}</h3>
          <button className="btn-ghost px-2 py-1" onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-ink-100 px-5 py-3">{footer}</div>
        )}
      </div>
    </div>
  );
}

export function Field({ label, children }) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
    </div>
  );
}
