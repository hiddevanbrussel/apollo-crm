import { useMemo, useState } from "react";
import { Icon } from "./icons";

const SEARCH_MIN = 6;

function normalizeOptions(options) {
  return options.map((o) => (typeof o === "string" ? { value: o, label: o } : o));
}

function SearchInput({ value, onChange, placeholder }) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-400">
        <Icon.Search width={14} height={14} />
      </span>
      <input
        className="input py-1.5 pl-8 text-sm"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

/** Single-value filter with optional search for long option lists. */
export function FilterSearchSelect({
  value,
  onChange,
  options,
  allLabel = "All",
  placeholder = "Search…",
  searchMin = SEARCH_MIN,
}) {
  const [query, setQuery] = useState("");
  const normalized = useMemo(() => normalizeOptions(options), [options]);
  const showSearch = normalized.length >= searchMin;
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return normalized;
    return normalized.filter((o) => o.label.toLowerCase().includes(q));
  }, [normalized, query]);

  if (!showSearch) {
    return (
      <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{allLabel}</option>
        {normalized.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    );
  }

  return (
    <div className="space-y-2">
      <SearchInput value={query} onChange={setQuery} placeholder={placeholder} />
      <div className="max-h-44 overflow-y-auto rounded-lg border border-ink-100 p-1">
        <button
          type="button"
          className={`flex w-full rounded px-2 py-1.5 text-left text-sm ${
            !value ? "bg-brand-50 font-medium text-brand-700" : "text-ink-700 hover:bg-ink-50"
          }`}
          onClick={() => onChange("")}
        >
          {allLabel}
        </button>
        {filtered.map((o) => (
          <button
            key={o.value}
            type="button"
            className={`flex w-full rounded px-2 py-1.5 text-left text-sm ${
              String(value) === String(o.value)
                ? "bg-brand-50 font-medium text-brand-700"
                : "text-ink-700 hover:bg-ink-50"
            }`}
            onClick={() => onChange(String(o.value))}
          >
            {o.label}
          </button>
        ))}
        {filtered.length === 0 && <p className="px-2 py-1.5 text-xs text-ink-400">No matches</p>}
      </div>
    </div>
  );
}

/** Multi-select checkbox list with optional search for long option lists. */
export function FilterSearchCheckList({
  options,
  selected,
  onToggle,
  pinnedItems = [],
  placeholder = "Search…",
  searchMin = SEARCH_MIN,
  emptyLabel = "No options yet.",
}) {
  const [query, setQuery] = useState("");
  const showSearch = options.length >= searchMin;
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter((v) => v.toLowerCase().includes(q));
  }, [options, query]);

  return (
    <div className="space-y-2">
      {showSearch && <SearchInput value={query} onChange={setQuery} placeholder={placeholder} />}
      <div className="max-h-44 space-y-1 overflow-y-auto rounded-lg border border-ink-100 p-2">
        {pinnedItems.map((item) => (
          <label
            key={item.value}
            className="flex cursor-pointer items-start gap-2 rounded px-1 py-0.5 text-sm text-ink-700 hover:bg-ink-50"
          >
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-ink-300"
              checked={selected.includes(item.value)}
              onChange={() => onToggle(item.value)}
            />
            <span className={`leading-snug ${item.muted ? "text-ink-500 italic" : ""}`}>{item.label}</span>
          </label>
        ))}
        {options.length === 0 ? (
          <p className="px-1 py-1 text-xs text-ink-400">{emptyLabel}</p>
        ) : filtered.length === 0 ? (
          <p className="px-1 py-1 text-xs text-ink-400">No matches</p>
        ) : (
          filtered.map((v) => (
            <label
              key={v}
              className="flex cursor-pointer items-start gap-2 rounded px-1 py-0.5 text-sm text-ink-700 hover:bg-ink-50"
            >
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 rounded border-ink-300"
                checked={selected.includes(v)}
                onChange={() => onToggle(v)}
              />
              <span className="leading-snug">{v}</span>
            </label>
          ))
        )}
      </div>
    </div>
  );
}
