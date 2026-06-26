import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api, { apiError } from "../api/client";
import { Icon } from "../components/icons";
import { CompanyLogo, EmptyState, Field, Modal, Pagination, PageLoader, SourceBadge, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";

const EMPTY = { name: "", domain: "", website: "", industry: "", country: "", city: "", phone: "", employee_count: "", description: "" };

const EMPTY_FILTERS = { industry: "", country: "", city: "", market_segment: "", employees: "", status: "" };

const EMPLOYEE_BUCKETS = [
  { id: "1-10", label: "1–10", min: 1, max: 10 },
  { id: "11-50", label: "11–50", min: 11, max: 50 },
  { id: "51-200", label: "51–200", min: 51, max: 200 },
  { id: "201-500", label: "201–500", min: 201, max: 500 },
  { id: "501-1000", label: "501–1,000", min: 501, max: 1000 },
  { id: "1001+", label: "1,000+", min: 1001, max: undefined },
];

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

export default function Companies() {
  const toast = useToast();
  const { isAdmin } = useAuth();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(params.get("search") || "");
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [filterOptions, setFilterOptions] = useState({ industries: [], countries: [], cities: [], segments: [] });
  const [showFilters, setShowFilters] = useState(true);
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [enrichOnImport, setEnrichOnImport] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [apolloReady, setApolloReady] = useState(false);
  const [bulkEnriching, setBulkEnriching] = useState(false);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);
  const fileInputRef = useRef(null);
  const pageSize = 20;

  useEffect(() => {
    api
      .get("/companies/filter-options")
      .then((res) => setFilterOptions(res.data))
      .catch(() => {});
    api
      .get("/apollo/status")
      .then((res) => setApolloReady(res.data.enabled && res.data.configured))
      .catch(() => setApolloReady(false));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const bucket = EMPLOYEE_BUCKETS.find((b) => b.id === filters.employees);
      const { data } = await api.get("/companies", {
        params: {
          search: search || undefined,
          enrichment_status: filters.status || undefined,
          industry: filters.industry || undefined,
          country: filters.country || undefined,
          city: filters.city || undefined,
          market_segment: filters.market_segment || undefined,
          min_employees: bucket?.min,
          max_employees: bucket?.max,
          page,
          page_size: pageSize,
        },
      });
      setData(data);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  }, [search, filters, page, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const onSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    setParams(search ? { search } : {});
    load();
  };

  const setFilter = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const clearFilters = () => {
    setFilters(EMPTY_FILTERS);
    setPage(1);
  };

  const activeFilterCount = Object.values(filters).filter(Boolean).length;

  const toggleOne = (id) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const toggleAllOnPage = () =>
    setSelected((prev) => {
      const next = new Set(prev);
      const ids = (data?.items || []).map((c) => c.id);
      const all = ids.length > 0 && ids.every((i) => next.has(i));
      ids.forEach((i) => (all ? next.delete(i) : next.add(i)));
      return next;
    });

  const clearSelection = () => setSelected(new Set());

  const allOnPageSelected = data?.items?.length > 0 && data.items.every((c) => selected.has(c.id));

  const bulkEnrich = async () => {
    const ids = [...selected];
    if (!ids.length) return;
    setBulkEnriching(true);
    try {
      const { data: res } = await api.post("/companies/enrich", { company_ids: ids });
      const parts = [`${res.enriched} enriched`];
      if (res.failed) parts.push(`${res.failed} failed`);
      if (res.skipped) parts.push(`${res.skipped} skipped (no domain)`);
      toast.success(parts.join(" · "));
      clearSelection();
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBulkEnriching(false);
    }
  };

  const bulkDelete = async () => {
    const ids = [...selected];
    if (!ids.length) return;
    if (!confirm(`Delete ${ids.length} selected company(ies) and their linked contacts?`)) return;
    setBulkDeleting(true);
    try {
      const { data: res } = await api.post("/companies/bulk-delete", { ids });
      toast.success(`${res.deleted} company(ies) deleted.`);
      clearSelection();
      setPage(1);
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBulkDeleting(false);
    }
  };

  const deleteAll = async () => {
    if (
      !confirm(
        "Delete ALL companies in the database (and all linked contacts)? This ignores current filters and cannot be undone."
      )
    ) {
      return;
    }
      return;
    }
    setDeletingAll(true);
    try {
      const { data: res } = await api.delete("/companies/all");
      toast.success(`${res.deleted} company(ies) deleted.`);
      clearSelection();
      setPage(1);
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setDeletingAll(false);
    }
  };

  const createCompany = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = { ...form };
      payload.employee_count = form.employee_count ? Number(form.employee_count) : null;
      Object.keys(payload).forEach((k) => payload[k] === "" && (payload[k] = null));
      await api.post("/companies", payload);
      toast.success("Company added.");
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

  const openImport = () => {
    setImportResult(null);
    setImportFile(null);
    setEnrichOnImport(false);
    setShowImport(true);
  };

  const runImport = async () => {
    if (!importFile) {
      toast.info("Please select a file first.");
      return;
    }
    setImporting(true);
    setImportResult(null);
    try {
      const fd = new FormData();
      fd.append("file", importFile);
      fd.append("enrich", enrichOnImport ? "true" : "false");
      const { data } = await api.post("/companies/import", fd);
      setImportResult(data);
      toast.success(
        `${data.created} created, ${data.updated} updated${data.enriched ? `, ${data.enriched} enriched` : ""}.`
      );
      setPage(1);
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setImporting(false);
    }
  };

  const remove = async (id) => {
    if (!confirm("Delete this company?")) return;
    try {
      await api.delete(`/companies/${id}`);
      toast.success("Company deleted.");
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Companies</h1>
          <p className="text-sm text-ink-500">Manage all companies in your CRM.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="btn-secondary text-red-600 hover:border-red-200 hover:bg-red-50"
            onClick={deleteAll}
            disabled={deletingAll || loading}
          >
            {deletingAll ? <Spinner className="h-4 w-4" /> : <Icon.Trash width={18} height={18} />}
            Delete all
          </button>
          <button className="btn-secondary" onClick={openImport}>
            <Icon.Upload width={18} height={18} /> Import
          </button>
          <button className="btn-primary" onClick={() => setShowCreate(true)}>
            <Icon.Plus width={18} height={18} /> New company
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-5 lg:flex-row">
      <div className="min-w-0 flex-1">
      <div className="card">
        <div className="flex flex-wrap items-center gap-3 border-b border-ink-100 p-4">
          <form onSubmit={onSearchSubmit} className="relative min-w-[240px] flex-1">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400">
              <Icon.Search width={18} height={18} />
            </span>
            <input
              className="input pl-10"
              placeholder="Search by name, domain, industry, country…"
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

        {selected.size > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 bg-brand-50/60 px-4 py-3">
            <span className="text-sm font-medium text-ink-700">{selected.size} selected</span>
            <div className="flex items-center gap-2">
              <button className="btn-ghost text-sm text-ink-500" onClick={clearSelection}>
                Clear selection
              </button>
              <button
                className="btn-secondary text-red-600 hover:border-red-200 hover:bg-red-50"
                onClick={bulkDelete}
                disabled={bulkDeleting}
              >
                {bulkDeleting ? <Spinner className="h-4 w-4" /> : <Icon.Trash width={18} height={18} />}
                Delete selected
              </button>
              {isAdmin && (
              <button
                className="btn-primary"
                onClick={bulkEnrich}
                disabled={bulkEnriching || !apolloReady}
                title={apolloReady ? undefined : "Enable Apollo in Settings to enrich."}
              >
                {bulkEnriching ? (
                  <Spinner className="h-4 w-4 border-white/40 border-t-white" />
                ) : (
                  <Icon.Bolt width={18} height={18} />
                )}
                Enrich via Apollo
              </button>
              )}
            </div>
          </div>
        )}

        {loading ? (
          <PageLoader />
        ) : data?.items.length === 0 ? (
          <EmptyState title="No companies found" description="Adjust your filters or add a new company." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-ink-100 bg-ink-50/50">
                <tr>
                  <th className="table-th w-10">
                    <input
                      type="checkbox"
                      className="h-4 w-4 cursor-pointer rounded border-ink-300 text-brand-600 focus:ring-brand-500"
                      checked={allOnPageSelected}
                      onChange={toggleAllOnPage}
                      aria-label="Select all on this page"
                    />
                  </th>
                  <th className="table-th">Company</th>
                  <th className="table-th">Industry</th>
                  <th className="table-th">Location</th>
                  <th className="table-th">Contacts</th>
                  <th className="table-th">Status</th>
                  <th className="table-th">Source</th>
                  <th className="table-th"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {data.items.map((c) => (
                  <tr key={c.id} className={`hover:bg-ink-50/60 ${selected.has(c.id) ? "bg-brand-50/40" : ""}`}>
                    <td className="table-td w-10">
                      <input
                        type="checkbox"
                        className="h-4 w-4 cursor-pointer rounded border-ink-300 text-brand-600 focus:ring-brand-500"
                        checked={selected.has(c.id)}
                        onChange={() => toggleOne(c.id)}
                        aria-label={`Select ${c.name}`}
                      />
                    </td>
                    <td className="table-td">
                      <div className="flex items-center gap-3">
                        <CompanyLogo domain={c.domain} name={c.name} size={32} />
                        <div className="min-w-0">
                          <Link to={`/companies/${c.id}`} className="font-medium text-ink-900 hover:text-brand-600">
                            {c.name}
                          </Link>
                          <p className="text-xs text-ink-400">{c.domain || "—"}</p>
                        </div>
                      </div>
                    </td>
                    <td className="table-td">{c.industry || "—"}</td>
                    <td className="table-td">{[c.city, c.country].filter(Boolean).join(", ") || "—"}</td>
                    <td className="table-td">{c.contact_count ?? 0}</td>
                    <td className="table-td"><StatusBadge status={c.enrichment_status} /></td>
                    <td className="table-td"><SourceBadge source={c.source} /></td>
                    <td className="table-td text-right">
                      <button className="btn-ghost px-2 py-1 text-red-500" onClick={() => remove(c.id)}>
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
              <FilterSection title="Industry" icon={Icon.Building} active={!!filters.industry} defaultOpen={!!filters.industry}>
                <select className="input" value={filters.industry} onChange={(e) => setFilter("industry", e.target.value)}>
                  <option value="">All industries</option>
                  {filterOptions.industries.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </FilterSection>
              <FilterSection title="# Employees" icon={Icon.Users} active={!!filters.employees} defaultOpen={!!filters.employees}>
                <select className="input" value={filters.employees} onChange={(e) => setFilter("employees", e.target.value)}>
                  <option value="">Any size</option>
                  {EMPLOYEE_BUCKETS.map((b) => (
                    <option key={b.id} value={b.id}>{b.label}</option>
                  ))}
                </select>
              </FilterSection>
              <FilterSection title="Market Segments" icon={Icon.Filter} active={!!filters.market_segment} defaultOpen={!!filters.market_segment}>
                <select className="input" value={filters.market_segment} onChange={(e) => setFilter("market_segment", e.target.value)}>
                  <option value="">All segments</option>
                  {filterOptions.segments.map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              </FilterSection>
              <FilterSection title="Account Location" icon={Icon.Globe} active={!!filters.country || !!filters.city} defaultOpen={!!filters.country || !!filters.city}>
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
              <FilterSection title="Enrichment status" icon={Icon.Bolt} active={!!filters.status} defaultOpen={!!filters.status}>
                <select className="input" value={filters.status} onChange={(e) => setFilter("status", e.target.value)}>
                  <option value="">All statuses</option>
                  <option value="enriched">Enriched</option>
                  <option value="none">Not enriched</option>
                  <option value="failed">Failed</option>
                </select>
              </FilterSection>
            </div>
          </div>
        </aside>
      )}
      </div>

      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="New company"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
            <button className="btn-primary" onClick={createCompany} disabled={saving}>
              {saving && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
            </button>
          </>
        }
      >
        <form onSubmit={createCompany} className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <Field label="Name *">
              <input className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
          </div>
          <Field label="Domain"><input className="input" value={form.domain} onChange={(e) => setForm({ ...form, domain: e.target.value })} /></Field>
          <Field label="Website"><input className="input" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} /></Field>
          <Field label="Industry"><input className="input" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} /></Field>
          <Field label="Employees"><input className="input" type="number" value={form.employee_count} onChange={(e) => setForm({ ...form, employee_count: e.target.value })} /></Field>
          <Field label="Country"><input className="input" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} /></Field>
          <Field label="City"><input className="input" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} /></Field>
          <Field label="Phone"><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
          <div className="col-span-2">
            <Field label="Description"><textarea className="input" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          </div>
        </form>
      </Modal>

      <Modal
        open={showImport}
        onClose={() => setShowImport(false)}
        title="Import companies"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setShowImport(false)}>Close</button>
            <button className="btn-primary" onClick={runImport} disabled={importing || !importFile}>
              {importing && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Import
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="rounded-lg border border-ink-100 bg-ink-50/60 p-4 text-sm text-ink-600">
            Upload an <strong>Excel (.xlsx)</strong> or <strong>CSV</strong> file. Recognized columns:{" "}
            <code className="rounded bg-white px-1.5 py-0.5 text-xs">customer_name</code>,{" "}
            <code className="rounded bg-white px-1.5 py-0.5 text-xs">country</code> and{" "}
            <code className="rounded bg-white px-1.5 py-0.5 text-xs">domain</code>. All other columns
            are stored as extra data. Existing companies (same name or domain) are
            <strong> updated</strong> instead of duplicated.
          </div>

          <div
            className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-ink-200 px-6 py-10 text-center hover:border-brand-300 hover:bg-brand-50/30"
            onClick={() => fileInputRef.current?.click()}
          >
            <Icon.Upload width={28} height={28} className="text-ink-400" />
            <p className="mt-2 text-sm font-medium text-ink-800">
              {importFile ? importFile.name : "Click to choose a file"}
            </p>
            <p className="mt-0.5 text-xs text-ink-400">.xlsx or .csv, max 5 MB</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xlsm,.csv"
              className="hidden"
              onChange={(e) => {
                setImportFile(e.target.files?.[0] || null);
                setImportResult(null);
              }}
            />
          </div>

          {isAdmin && (
          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-ink-100 p-3 hover:bg-ink-50/60">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-ink-300"
              checked={enrichOnImport}
              onChange={(e) => setEnrichOnImport(e.target.checked)}
            />
            <span className="text-sm text-ink-700">
              Enrich via Apollo right after import
              <span className="block text-xs text-ink-400">
                Fetches industry, employee count and revenue for each company with a domain.
                <strong> Uses Apollo credits.</strong> Apollo must be enabled in Settings.
              </span>
            </span>
          </label>
          )}

          {importResult && (
            <div className="space-y-2 rounded-lg border border-ink-100 p-4">
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
                <span className="text-green-700">Created: <strong>{importResult.created}</strong></span>
                <span className="text-brand-700">Updated: <strong>{importResult.updated}</strong></span>
                <span className="text-ink-500">Skipped: <strong>{importResult.skipped_duplicates}</strong></span>
                {importResult.enriched > 0 && (
                  <span className="text-purple-700">Enriched: <strong>{importResult.enriched}</strong></span>
                )}
                <span className="text-ink-500">Total rows: <strong>{importResult.total_rows}</strong></span>
              </div>
              {importResult.extra_columns?.length > 0 && (
                <p className="text-xs text-ink-400">
                  Stored as extra data: {importResult.extra_columns.join(", ")}
                </p>
              )}
              {importResult.errors?.length > 0 && (
                <ul className="mt-2 max-h-32 list-disc overflow-y-auto pl-5 text-xs text-amber-700">
                  {importResult.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
