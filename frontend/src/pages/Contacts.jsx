import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { apiError } from "../api/client";
import { Icon } from "../components/icons";
import { EmptyState, Field, Modal, Pagination, PageLoader, SourceBadge, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";

const EMPTY = { first_name: "", last_name: "", title: "", email: "", phone: "", linkedin_url: "", city: "", country: "", seniority: "", department: "", company_id: "" };

const EMPTY_FILTERS = {
  company_id: "",
  tier: "",
  source: "",
  status: "",
  country: "",
  city: "",
  seniority: "",
  department: "",
  titles: [],
};

const NO_TITLE_FILTER = "__no_title__";

function formatWhen(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

function buildJobFilters(search, filters) {
  const f = {};
  if (search?.trim()) f.search = search.trim();
  if (filters.company_id) f.company_id = Number(filters.company_id);
  if (filters.tier) f.tier = filters.tier;
  if (filters.source) f.source = filters.source;
  if (filters.status) f.enrichment_status = filters.status;
  if (filters.country) f.country = filters.country;
  if (filters.city) f.city = filters.city;
  if (filters.seniority) f.seniority = filters.seniority;
  if (filters.department) f.department = filters.department;
  if (filters.titles?.length) f.titles = filters.titles;
  return f;
}

function formatJobTime(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString();
}

function contactQueryParams({ search, filters, page, pageSize }) {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (filters.status) params.set("enrichment_status", filters.status);
  if (filters.source) params.set("source", filters.source);
  if (filters.company_id) params.set("company_id", filters.company_id);
  if (filters.tier) params.set("tier", filters.tier);
  if (filters.country) params.set("country", filters.country);
  if (filters.city) params.set("city", filters.city);
  if (filters.seniority) params.set("seniority", filters.seniority);
  if (filters.department) params.set("department", filters.department);
  (filters.titles || []).forEach((t) => params.append("titles", t));
  if (page) params.set("page", String(page));
  if (pageSize) params.set("page_size", String(pageSize));
  return params;
}

function normalizePresetFilters(raw = {}) {
  const next = { ...EMPTY_FILTERS, ...raw };
  if (raw.title && (!next.titles || next.titles.length === 0)) {
    next.titles = [raw.title];
  }
  delete next.title;
  if (!Array.isArray(next.titles)) next.titles = [];
  return next;
}

function countActiveFilters(filters, search) {
  let n = search ? 1 : 0;
  Object.entries(filters).forEach(([key, value]) => {
    if (key === "titles") {
      if (value?.length) n += 1;
      return;
    }
    if (value) n += 1;
  });
  return n;
}

function FilterSection({ title, icon: IconCmp, active, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-ink-50/60"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-ink-700">
          {IconCmp && <IconCmp width={16} height={16} className="text-ink-400" />}
          {title}
          {active && <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />}
        </span>
        <span className={`text-ink-400 transition-transform ${open ? "rotate-90" : ""}`}>
          <Icon.ChevronRight width={16} height={16} />
        </span>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

function presetsKey(userId) {
  return `apollo-contact-filter-presets-${userId || "default"}`;
}

function loadPresets(userId) {
  try {
    const raw = localStorage.getItem(presetsKey(userId));
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function storePresets(userId, presets) {
  localStorage.setItem(presetsKey(userId), JSON.stringify(presets));
}

export default function Contacts() {
  const toast = useToast();
  const { user, isAdmin } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [filterOptions, setFilterOptions] = useState({
    countries: [],
    cities: [],
    seniorities: [],
    departments: [],
    titles: [],
    tiers: [],
    companies: [],
  });
  const [enrichReady, setEnrichReady] = useState(false);
  const [showFilters, setShowFilters] = useState(true);
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [companies, setCompanies] = useState([]);
  const [saving, setSaving] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);
  const [deletingSelected, setDeletingSelected] = useState(false);
  const [enrichingSelected, setEnrichingSelected] = useState(false);
  const [enrichingUnenriched, setEnrichingUnenriched] = useState(false);
  const [waterfallStatus, setWaterfallStatus] = useState(null);
  const [showWaterfallLog, setShowWaterfallLog] = useState(true);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [exporting, setExporting] = useState(false);
  const [savedPresets, setSavedPresets] = useState([]);
  const [showSavePreset, setShowSavePreset] = useState(false);
  const [presetName, setPresetName] = useState("");
  const pageSize = 20;

  useEffect(() => {
    setSavedPresets(loadPresets(user?.id));
  }, [user?.id]);

  useEffect(() => {
    api
      .get("/contacts/filter-options")
      .then((res) => setFilterOptions(res.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    api
      .get("/settings/status")
      .then((res) => {
        const apollo = res.data.apollo?.enabled && res.data.apollo?.configured;
        const prospeo = res.data.prospeo?.enabled && res.data.prospeo?.configured;
        setEnrichReady(apollo || prospeo);
      })
      .catch(() => {
        setEnrichReady(false);
      });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const qs = contactQueryParams({ search, filters, page, pageSize });
      const { data } = await api.get(`/contacts?${qs.toString()}`);
      setData(data);
      setSelectedIds(new Set());
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  }, [search, filters, page, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const loadWaterfallStatus = useCallback(async () => {
    try {
      const { data } = await api.get("/contacts/waterfall-status");
      setWaterfallStatus(data);
    } catch {
      setWaterfallStatus(null);
    }
  }, []);

  useEffect(() => {
    loadWaterfallStatus();
  }, [loadWaterfallStatus]);

  useEffect(() => {
    if (!waterfallStatus?.pending) return;
    const timer = setInterval(loadWaterfallStatus, 3000);
    return () => clearInterval(timer);
  }, [waterfallStatus?.pending, loadWaterfallStatus]);

  const setFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const toggleTitle = (title) => {
    setFilters((prev) => {
      const has = prev.titles.includes(title);
      return {
        ...prev,
        titles: has ? prev.titles.filter((t) => t !== title) : [...prev.titles, title],
      };
    });
    setPage(1);
  };

  const clearFilters = () => {
    setFilters(EMPTY_FILTERS);
    setSearch("");
    setPage(1);
  };

  const activeFilterCount = countActiveFilters(filters, search);

  const applyPreset = (preset) => {
    setSearch(preset.search || "");
    setFilters(normalizePresetFilters(preset.filters));
    setPage(1);
    toast.success(`Filter "${preset.name}" applied.`);
  };

  const savePreset = () => {
    const name = presetName.trim();
    if (!name) {
      toast.info("Enter a name for this filter.");
      return;
    }
    const preset = {
      id: crypto.randomUUID(),
      name,
      search,
      filters: { ...filters },
      savedAt: new Date().toISOString(),
    };
    const next = [...savedPresets.filter((p) => p.name !== name), preset];
    setSavedPresets(next);
    storePresets(user?.id, next);
    setPresetName("");
    setShowSavePreset(false);
    toast.success(`Filter "${name}" saved.`);
  };

  const deletePreset = (id) => {
    const next = savedPresets.filter((p) => p.id !== id);
    setSavedPresets(next);
    storePresets(user?.id, next);
  };

  const exportCsv = async () => {
    setExporting(true);
    try {
      const qs = contactQueryParams({ search, filters });
      const response = await api.get(`/contacts/export?${qs.toString()}`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(response.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = "contacts-export.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Export downloaded.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setExporting(false);
    }
  };

  const openCreate = async () => {
    setShowCreate(true);
    try {
      const { data } = await api.get("/companies", { params: { page_size: 100 } });
      setCompanies(data.items);
    } catch {
      /* ignore */
    }
  };

  const createContact = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = { ...form };
      payload.company_id = form.company_id ? Number(form.company_id) : null;
      Object.keys(payload).forEach((k) => payload[k] === "" && (payload[k] = null));
      await api.post("/contacts", payload);
      toast.success("Contact added.");
      setShowCreate(false);
      setForm(EMPTY);
      setPage(1);
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id) => {
    if (!confirm("Delete this contact?")) return;
    try {
      await api.delete(`/contacts/${id}`);
      toast.success("Contact deleted.");
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const deleteAll = async () => {
    if (!confirm("Delete ALL contacts in the database? This ignores current filters and cannot be undone.")) return;
    setDeletingAll(true);
    try {
      const { data: res } = await api.delete("/contacts/all");
      toast.success(`${res.deleted} contact(s) deleted.`);
      setPage(1);
      setSelectedIds(new Set());
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setDeletingAll(false);
    }
  };

  const toggleSelected = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAllOnPage = () => {
    if (!data?.items?.length) return;
    const pageIds = data.items.map((c) => c.id);
    const allSelected = pageIds.every((id) => selectedIds.has(id));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allSelected) pageIds.forEach((id) => next.delete(id));
      else pageIds.forEach((id) => next.add(id));
      return next;
    });
  };

  const deleteSelected = async () => {
    const ids = [...selectedIds];
    if (!ids.length) return;
    if (!confirm(`Delete ${ids.length} selected contact(s)? This cannot be undone.`)) return;
    setDeletingSelected(true);
    try {
      const { data: res } = await api.post("/contacts/bulk-delete", { ids });
      toast.success(`${res.deleted} contact(s) deleted.`);
      setSelectedIds(new Set());
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setDeletingSelected(false);
    }
  };

  const enrichSelected = async () => {
    const ids = [...selectedIds];
    if (!ids.length) return;
    if (
      !confirm(
        `Match ${ids.length} selected contact(s) one at a time in the background?`
      )
    ) {
      return;
    }
    setEnrichingSelected(true);
    try {
      const { data } = await api.post("/contacts/enrich/jobs", { ids });
      if (!data.started) {
        toast.info("An enrichment job is already running. See Settings → Activity for progress.");
      } else {
        toast.success(
          `Job started for ${data.job.total_contacts} contacts (one at a time). Track progress in Settings → Activity.`
        );
        setSelectedIds(new Set());
      }
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setEnrichingSelected(false);
    }
  };

  const enrichUnenriched = async () => {
    setEnrichingUnenriched(true);
    try {
      const qs = contactQueryParams({ search, filters });
      qs.set("limit", "0");
      const { data: preview } = await api.post(`/contacts/bulk-enrich-unenriched?${qs.toString()}`);
      if (!preview.total_matched) {
        toast.info("No contacts to enrich for the current filters.");
        return;
      }
      if (
        !confirm(
          `Match ${preview.total_matched} contact(s) one at a time in the background?`
        )
      ) {
        return;
      }
      const jobFilters = buildJobFilters(search, filters);
      const { data } = await api.post("/contacts/enrich/jobs", {
        filters: Object.keys(jobFilters).length ? jobFilters : undefined,
      });
      if (!data.started) {
        toast.info("An enrichment job is already running. See Settings → Activity for progress.");
      } else {
        toast.success(
          `Job started for ${data.job.total_contacts} contacts (one at a time). Track progress in Settings → Activity.`
        );
      }
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setEnrichingUnenriched(false);
    }
  };

  const pageIds = data?.items?.map((c) => c.id) || [];
  const allOnPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id));
  const someOnPageSelected = pageIds.some((id) => selectedIds.has(id));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Contacts</h1>
          <p className="text-sm text-ink-500">Manage all contacts in your CRM.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-secondary" onClick={() => setShowSavePreset(true)}>
            <Icon.Bookmark width={18} height={18} /> Save filter
          </button>
          <button className="btn-secondary" onClick={exportCsv} disabled={exporting || loading}>
            {exporting ? <Spinner className="h-4 w-4" /> : <Icon.Download width={18} height={18} />}
            Export
          </button>
          {isAdmin && (
            <button
              className="btn-secondary"
              onClick={enrichUnenriched}
              disabled={enrichingUnenriched || !enrichReady || loading}
              title={
                enrichReady
                  ? "Match all not-enriched contacts (respects current filters)"
                  : "Enable Apollo or Prospeo in Settings"
              }
            >
              {enrichingUnenriched ? (
                <Spinner className="h-4 w-4" />
              ) : (
                <Icon.Sparkles width={18} height={18} />
              )}
              Match unenriched
            </button>
          )}
          <button
            className="btn-secondary text-red-600 hover:border-red-200 hover:bg-red-50"
            onClick={deleteAll}
            disabled={deletingAll || loading}
          >
            {deletingAll ? <Spinner className="h-4 w-4" /> : <Icon.Trash width={18} height={18} />}
            Delete all
          </button>
          <button className="btn-primary" onClick={openCreate}>
            <Icon.Plus width={18} height={18} /> New contact
          </button>
        </div>
      </div>

      {selectedIds.size > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-brand-200 bg-brand-50 px-4 py-3">
          <span className="text-sm font-medium text-brand-800">
            {selectedIds.size} contact{selectedIds.size === 1 ? "" : "s"} selected
          </span>
          <div className="flex items-center gap-2">
            {isAdmin && (
              <button
                className="btn-primary"
                onClick={enrichSelected}
                disabled={enrichingSelected || !enrichReady}
                title={enrichReady ? "Match selected contacts" : "Enable Apollo or Prospeo in Settings"}
              >
                {enrichingSelected ? (
                  <Spinner className="h-4 w-4 border-white/40 border-t-white" />
                ) : (
                  <Icon.Sparkles width={18} height={18} />
                )}
                Match selected
              </button>
            )}
            <button className="btn-secondary" onClick={() => setSelectedIds(new Set())}>
              Clear selection
            </button>
            <button
              className="btn-secondary text-red-600 hover:border-red-200 hover:bg-red-50"
              onClick={deleteSelected}
              disabled={deletingSelected}
            >
              {deletingSelected ? <Spinner className="h-4 w-4" /> : <Icon.Trash width={18} height={18} />}
              Delete selected
            </button>
          </div>
        </div>
      )}

      {savedPresets.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-ink-400">Saved filters:</span>
          {savedPresets.map((p) => (
            <span key={p.id} className="inline-flex items-center gap-1 rounded-full border border-ink-200 bg-white pl-3 pr-1 py-1 text-xs">
              <button type="button" className="font-medium text-ink-700 hover:text-brand-600" onClick={() => applyPreset(p)}>
                {p.name}
              </button>
              <button type="button" className="rounded-full px-1.5 py-0.5 text-ink-400 hover:bg-red-50 hover:text-red-600" onClick={() => deletePreset(p.id)} title="Remove">
                ✕
              </button>
            </span>
          ))}
        </div>
      )}

      {waterfallStatus &&
        (waterfallStatus.waterfall_enabled || waterfallStatus.total_triggered > 0) && (
          <div className="card overflow-hidden">
            <button
              type="button"
              className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-ink-50/60"
              onClick={() => setShowWaterfallLog((v) => !v)}
            >
              <div>
                <p className="text-sm font-semibold text-ink-900">Apollo waterfall log</p>
                <p className="mt-0.5 text-xs text-ink-500">
                  {waterfallStatus.pending} pending · {waterfallStatus.completed} completed ·{" "}
                  {waterfallStatus.total_triggered} triggered
                  {waterfallStatus.pending > 0 && " · auto-refreshing"}
                </p>
              </div>
              <span className={`text-ink-400 transition-transform ${showWaterfallLog ? "rotate-90" : ""}`}>
                <Icon.ChevronRight width={18} height={18} />
              </span>
            </button>
            {showWaterfallLog && (
              <div className="border-t border-ink-100 px-4 py-3">
                {waterfallStatus.waterfall_enabled && !waterfallStatus.webhook_configured && (
                  <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    Waterfall is enabled but PUBLIC_BASE_URL is not set. Apollo cannot deliver webhook results until
                    your public URL is configured.
                  </p>
                )}
                {waterfallStatus.items.length === 0 ? (
                  <p className="text-sm text-ink-400">No waterfall enrichments yet.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-ink-100 text-left text-xs text-ink-400">
                          <th className="pb-2 pr-4 font-medium">Contact</th>
                          <th className="pb-2 pr-4 font-medium">Waterfall</th>
                          <th className="pb-2 pr-4 font-medium">Requested</th>
                          <th className="pb-2 pr-4 font-medium">Completed</th>
                          <th className="pb-2 font-medium">Request ID</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-ink-100">
                        {waterfallStatus.items.map((item) => (
                          <tr key={item.id}>
                            <td className="py-2 pr-4">
                              <Link to={`/contacts/${item.id}`} className="font-medium text-brand-600 hover:underline">
                                {item.full_name || item.email || `#${item.id}`}
                              </Link>
                              {item.company_name && <p className="text-xs text-ink-400">{item.company_name}</p>}
                            </td>
                            <td className="py-2 pr-4">
                              <StatusBadge
                                status={item.waterfall_status === "completed" ? "enriched" : "pending"}
                              />
                            </td>
                            <td className="py-2 pr-4 text-xs text-ink-500">{formatWhen(item.requested_at)}</td>
                            <td className="py-2 pr-4 text-xs text-ink-500">
                              {item.waterfall_status === "completed" ? (
                                <>
                                  {formatWhen(item.completed_at)}
                                  {item.webhook_updated === false && (
                                    <span className="mt-0.5 block text-ink-400">No new data</span>
                                  )}
                                </>
                              ) : (
                                "—"
                              )}
                            </td>
                            <td className="py-2 font-mono text-xs text-ink-400">{item.request_id || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

      <div className="flex flex-col gap-5 lg:flex-row">
        <div className="min-w-0 flex-1">
          <div className="card">
            <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 p-4">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setPage(1);
                  load();
                }}
                className="relative min-w-[240px] flex-1"
              >
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400">
                  <Icon.Search width={18} height={18} />
                </span>
                <input
                  className="input pl-10"
                  placeholder="Search by name, title, email…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </form>
              <button
                className={`btn-secondary ${showFilters ? "border-brand-300 text-brand-700" : ""}`}
                onClick={() => setShowFilters((v) => !v)}
              >
                <Icon.Filter width={18} height={18} /> Filters
                {activeFilterCount > 0 && (
                  <span className="ml-1 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-brand-600 px-1.5 text-xs font-semibold text-white">
                    {activeFilterCount}
                  </span>
                )}
              </button>
            </div>

            {loading ? (
              <PageLoader />
            ) : data?.items.length === 0 ? (
              <EmptyState title="No contacts found" description="Adjust your filters or add a new contact." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b border-ink-100 bg-ink-50/50">
                    <tr>
                      <th className="table-th w-10">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-ink-300"
                          checked={allOnPageSelected}
                          ref={(el) => {
                            if (el) el.indeterminate = someOnPageSelected && !allOnPageSelected;
                          }}
                          onChange={toggleSelectAllOnPage}
                          aria-label="Select all on this page"
                        />
                      </th>
                      <th className="table-th">Name</th>
                      <th className="table-th">Title</th>
                      <th className="table-th">Company</th>
                      <th className="table-th">Email</th>
                      <th className="table-th">Status</th>
                      <th className="table-th">Source</th>
                      <th className="table-th"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-100">
                    {data.items.map((ct) => (
                      <tr key={ct.id} className={`hover:bg-ink-50/60 ${selectedIds.has(ct.id) ? "bg-brand-50/40" : ""}`}>
                        <td className="table-td">
                          <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-ink-300"
                            checked={selectedIds.has(ct.id)}
                            onChange={() => toggleSelected(ct.id)}
                            aria-label={`Select ${ct.full_name || ct.email || "contact"}`}
                          />
                        </td>
                        <td className="table-td">
                          <Link to={`/contacts/${ct.id}`} className="font-medium text-ink-900 hover:text-brand-600">
                            {ct.full_name || `${ct.first_name || ""} ${ct.last_name || ""}`.trim() || "—"}
                          </Link>
                        </td>
                        <td className="table-td">{ct.title || "—"}</td>
                        <td className="table-td">
                          {ct.company ? (
                            <Link to={`/companies/${ct.company.id}`} className="text-brand-600 hover:underline">
                              {ct.company.name}
                            </Link>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="table-td">{ct.email || "—"}</td>
                        <td className="table-td"><StatusBadge status={ct.enrichment_status} /></td>
                        <td className="table-td"><SourceBadge source={ct.source} /></td>
                        <td className="table-td text-right">
                          <button className="btn-ghost px-2 py-1 text-red-500" onClick={() => remove(ct.id)}>
                            <Icon.Trash width={16} height={16} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {data && <Pagination page={page} pageSize={pageSize} total={data.total} onPage={setPage} />}
          </div>
        </div>

        {showFilters && (
          <aside className="w-full shrink-0 lg:w-72">
            <div className="card overflow-hidden">
              <div className="flex items-center justify-between border-b border-ink-100 px-4 py-3">
                <h3 className="text-sm font-semibold text-ink-900">Filters</h3>
                {activeFilterCount > 0 && (
                  <button className="text-xs font-medium text-brand-600 hover:underline" onClick={clearFilters}>
                    Clear ({activeFilterCount})
                  </button>
                )}
              </div>
              <div className="divide-y divide-ink-100">
                <FilterSection title="Company" icon={Icon.Building} active={!!filters.company_id} defaultOpen={!!filters.company_id}>
                  <select className="input" value={filters.company_id} onChange={(e) => setFilter("company_id", e.target.value)}>
                    <option value="">All companies</option>
                    {filterOptions.companies.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </FilterSection>
                <FilterSection title="Company tier" icon={Icon.Sparkles} active={!!filters.tier} defaultOpen={!!filters.tier}>
                  <select className="input" value={filters.tier} onChange={(e) => setFilter("tier", e.target.value)}>
                    <option value="">All tiers</option>
                    {filterOptions.tiers.map((v) => (
                      <option key={v} value={v}>{v}</option>
                    ))}
                  </select>
                  <p className="mt-1.5 text-xs text-ink-400">
                    Shows contacts linked to companies with this tier.
                  </p>
                </FilterSection>
                <FilterSection title="Source" icon={Icon.Sparkles} active={!!filters.source} defaultOpen={!!filters.source}>
                  <select className="input" value={filters.source} onChange={(e) => setFilter("source", e.target.value)}>
                    <option value="">All sources</option>
                    <option value="import">Imported</option>
                    <option value="apollo">Apollo</option>
                    <option value="manual">Manual</option>
                  </select>
                </FilterSection>
                <FilterSection title="Enrichment status" icon={Icon.Bolt} active={!!filters.status} defaultOpen={!!filters.status}>
                  <select className="input" value={filters.status} onChange={(e) => setFilter("status", e.target.value)}>
                    <option value="">All statuses</option>
                    <option value="enriched">Enriched</option>
                    <option value="pending">In progress (waterfall)</option>
                    <option value="none">Not enriched</option>
                    <option value="failed">Failed</option>
                  </select>
                </FilterSection>
                <FilterSection title="Location" icon={Icon.Globe} active={!!filters.country || !!filters.city} defaultOpen={!!filters.country || !!filters.city}>
                  <div className="space-y-3">
                    <div>
                      <p className="mb-1 text-xs font-medium text-ink-400">Country</p>
                      <select className="input" value={filters.country} onChange={(e) => setFilter("country", e.target.value)}>
                        <option value="">All countries</option>
                        {filterOptions.countries.map((v) => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <p className="mb-1 text-xs font-medium text-ink-400">City</p>
                      <select className="input" value={filters.city} onChange={(e) => setFilter("city", e.target.value)}>
                        <option value="">All cities</option>
                        {filterOptions.cities.map((v) => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </FilterSection>
                <FilterSection title="Role" icon={Icon.Users} active={filters.titles.length > 0 || !!filters.seniority || !!filters.department} defaultOpen={filters.titles.length > 0 || !!filters.seniority || !!filters.department}>
                  <div className="space-y-3">
                    <div>
                      <div className="mb-1 flex items-center justify-between">
                        <p className="text-xs font-medium text-ink-400">Title</p>
                        {filters.titles.length > 0 && (
                          <button
                            type="button"
                            className="text-xs font-medium text-brand-600 hover:underline"
                            onClick={() => setFilter("titles", [])}
                          >
                            Clear ({filters.titles.length})
                          </button>
                        )}
                      </div>
                      <div className="max-h-44 space-y-1 overflow-y-auto rounded-lg border border-ink-100 p-2">
                        <label className="flex cursor-pointer items-start gap-2 rounded px-1 py-0.5 text-sm text-ink-700 hover:bg-ink-50">
                          <input
                            type="checkbox"
                            className="mt-0.5 h-4 w-4 rounded border-ink-300"
                            checked={filters.titles.includes(NO_TITLE_FILTER)}
                            onChange={() => toggleTitle(NO_TITLE_FILTER)}
                          />
                          <span className="leading-snug text-ink-500 italic">No title</span>
                        </label>
                        {filterOptions.titles.length === 0 ? (
                          <p className="px-1 py-1 text-xs text-ink-400">No titled contacts yet.</p>
                        ) : (
                          filterOptions.titles.map((v) => (
                            <label key={v} className="flex cursor-pointer items-start gap-2 rounded px-1 py-0.5 text-sm text-ink-700 hover:bg-ink-50">
                              <input
                                type="checkbox"
                                className="mt-0.5 h-4 w-4 rounded border-ink-300"
                                checked={filters.titles.includes(v)}
                                onChange={() => toggleTitle(v)}
                              />
                              <span className="leading-snug">{v}</span>
                            </label>
                          ))
                        )}
                      </div>
                    </div>
                    <div>
                      <p className="mb-1 text-xs font-medium text-ink-400">Seniority</p>
                      <select className="input" value={filters.seniority} onChange={(e) => setFilter("seniority", e.target.value)}>
                        <option value="">All</option>
                        {filterOptions.seniorities.map((v) => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <p className="mb-1 text-xs font-medium text-ink-400">Department</p>
                      <select className="input" value={filters.department} onChange={(e) => setFilter("department", e.target.value)}>
                        <option value="">All</option>
                        {filterOptions.departments.map((v) => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </FilterSection>
              </div>
            </div>
          </aside>
        )}
      </div>

      <Modal
        open={showSavePreset}
        onClose={() => setShowSavePreset(false)}
        title="Save filter"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setShowSavePreset(false)}>Cancel</button>
            <button className="btn-primary" onClick={savePreset}>Save</button>
          </>
        }
      >
        <Field label="Filter name">
          <input
            className="input"
            placeholder="e.g. Imported Tier 1 contacts"
            value={presetName}
            onChange={(e) => setPresetName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && savePreset()}
          />
        </Field>
        <p className="mt-2 text-xs text-ink-400">
          Saves your current search and filter selections. Stored in this browser for your account.
        </p>
      </Modal>

      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="New contact"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
            <button className="btn-primary" onClick={createContact} disabled={saving}>
              {saving && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
            </button>
          </>
        }
      >
        <form onSubmit={createContact} className="grid grid-cols-2 gap-4">
          <Field label="First name"><input className="input" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} /></Field>
          <Field label="Last name"><input className="input" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} /></Field>
          <Field label="Title"><input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <Field label="Email"><input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Phone"><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
          <Field label="LinkedIn"><input className="input" value={form.linkedin_url} onChange={(e) => setForm({ ...form, linkedin_url: e.target.value })} /></Field>
          <Field label="Seniority"><input className="input" value={form.seniority} onChange={(e) => setForm({ ...form, seniority: e.target.value })} /></Field>
          <Field label="Department"><input className="input" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} /></Field>
          <Field label="City"><input className="input" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} /></Field>
          <Field label="Country"><input className="input" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} /></Field>
          <div className="col-span-2">
            <Field label="Company">
              <select className="input" value={form.company_id} onChange={(e) => setForm({ ...form, company_id: e.target.value })}>
                <option value="">— None —</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </Field>
          </div>
        </form>
      </Modal>
    </div>
  );
}
