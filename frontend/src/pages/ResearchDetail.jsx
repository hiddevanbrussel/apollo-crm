import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api, { apiError } from "../api/client";
import ApolloFilterForm from "../components/ApolloFilterForm";
import { Icon } from "../components/icons";
import { CompanyLogo, EmptyState, Field, Modal, PageLoader, Pagination, Spinner, StatusBadge } from "../components/ui";
import {
  PEOPLE_CONTACT_FIELDS,
  buildCriteria,
  emptyFilters,
  slug,
} from "../constants/apolloSearchFields";
import { useToast } from "../context/ToastContext";

const ORG_COLUMNS = [
  { key: "name", label: "Company" },
  { key: "domain", label: "Domain" },
  { key: "industry", label: "Industry" },
  { key: "employee_count", label: "Employees" },
  { key: "country", label: "Country" },
  { key: "city", label: "City" },
  { key: "website", label: "Website" },
  { key: "linkedin_url", label: "LinkedIn" },
];

const PEOPLE_COLUMNS = [
  { key: "name", label: "Name" },
  { key: "title", label: "Title" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "seniority", label: "Seniority" },
  { key: "organization_name", label: "Company" },
  { key: "organization_domain", label: "Domain" },
  { key: "city", label: "City" },
  { key: "country", label: "Country" },
  { key: "linkedin_url", label: "LinkedIn" },
];

function CellValue({ column, row, isOrg, searchId }) {
  const value = row[column.key];
  if (value === null || value === undefined || value === "") return "—";

  if (column.key === "name" && isOrg) {
    return (
      <Link
        to={`/research/${searchId}/companies/${row.id}`}
        className="flex items-center gap-3 hover:text-brand-600"
      >
        <CompanyLogo domain={row.domain} name={value} size={32} />
        <span className="font-medium text-ink-900">{value}</span>
      </Link>
    );
  }

  if (column.key === "website" || column.key === "linkedin_url") {
    const href = column.key === "website" && !String(value).startsWith("http") ? `https://${value}` : value;
    return (
      <a href={href} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">
        {String(value).replace(/^https?:\/\//, "")}
      </a>
    );
  }

  return String(value);
}

export default function ResearchDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [showContacts, setShowContacts] = useState(false);
  const [domainInfo, setDomainInfo] = useState(null);
  const [contactName, setContactName] = useState("");
  const [contactMaxRecords, setContactMaxRecords] = useState(500);
  const [contactFilters, setContactFilters] = useState(() => emptyFilters(PEOPLE_CONTACT_FIELDS));
  const [runningContacts, setRunningContacts] = useState(false);

  const [apolloReady, setApolloReady] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [enriching, setEnriching] = useState(false);
  const [enrichingId, setEnrichingId] = useState(null);

  const [showAddCompany, setShowAddCompany] = useState(false);
  const [companyForm, setCompanyForm] = useState({
    name: "",
    domain: "",
    country: "",
    industry: "",
    city: "",
    website: "",
    linkedin_url: "",
  });
  const [savingCompany, setSavingCompany] = useState(false);
  const [importing, setImporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data: res } = await api.get(`/research/searches/${id}/results`, {
        params: { page, page_size: pageSize },
      });
      setData(res);
    } catch (err) {
      toast.error(apiError(err));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [id, page, toast]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api
      .get("/apollo/status")
      .then((res) => setApolloReady(res.data.enabled && res.data.configured))
      .catch(() => setApolloReady(false));
  }, []);

  useEffect(() => {
    setSelected(new Set());
  }, [page, id]);

  const exportSearch = async (format) => {
    try {
      const res = await api.get(`/research/searches/${id}/export`, {
        params: { format },
        responseType: "blob",
      });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${slug(data?.search?.name)}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const remove = async () => {
    if (!confirm(`Delete research "${data?.search?.name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/research/searches/${id}`);
      toast.success("Research deleted.");
      navigate("/research");
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const openContactsModal = async () => {
    try {
      const { data: res } = await api.get(`/research/searches/${id}/domains`);
      const domains = res.domains || [];
      if (!domains.length) {
        toast.info("No domains in this dataset to search contacts for.");
        return;
      }
      setDomainInfo({
        companyCount: data?.search?.result_count || domains.length,
        domainCount: domains.length,
      });
      setContactName(`${data?.search?.name || "Research"} — contacts`);
      setContactFilters(emptyFilters(PEOPLE_CONTACT_FIELDS));
      setShowContacts(true);
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const runContactSearch = async (e) => {
    e?.preventDefault();
    if (!contactName.trim()) {
      toast.info("Give this contact search a name first.");
      return;
    }
    if (
      !confirm(
        `Search contacts at ${domainInfo?.domainCount || 0} companies and save up to ${contactMaxRecords} records? People API Search does not consume credits.`
      )
    ) {
      return;
    }

    setRunningContacts(true);
    try {
      const { data: created } = await api.post(`/research/searches/${id}/people`, {
        name: contactName.trim(),
        criteria: buildCriteria(contactFilters, PEOPLE_CONTACT_FIELDS),
        max_records: Number(contactMaxRecords),
      });
      toast.success(
        `Captured ${created.result_count} contacts${created.total_available ? ` (of ${created.total_available} available)` : ""}.`
      );
      setShowContacts(false);
      navigate(`/research/${created.id}`);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setRunningContacts(false);
    }
  };

  const toggleOne = (rowId) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(rowId) ? next.delete(rowId) : next.add(rowId);
      return next;
    });

  const toggleAllOnPage = () =>
    setSelected((prev) => {
      const next = new Set(prev);
      const ids = (data?.items || []).map((row) => row.id);
      const all = ids.length > 0 && ids.every((rowId) => next.has(rowId));
      ids.forEach((rowId) => (all ? next.delete(rowId) : next.add(rowId)));
      return next;
    });

  const clearSelection = () => setSelected(new Set());

  const enrichOne = async (rowId) => {
    if (!confirm("Fetch complete profile from Apollo? This may consume credits.")) return;
    setEnrichingId(rowId);
    try {
      await api.post(`/research/searches/${id}/results/${rowId}/enrich`);
      toast.success("Record enriched.");
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setEnrichingId(null);
    }
  };

  const enrichSelected = async () => {
    const ids = [...selected];
    if (!ids.length) return;
    if (!confirm(`Enrich ${ids.length} selected record(s) via Apollo? This may consume credits.`)) return;
    setEnriching(true);
    try {
      const { data: res } = await api.post(`/research/searches/${id}/enrich`, { result_ids: ids });
      const parts = [`${res.enriched} enriched`];
      if (res.skipped) parts.push(`${res.skipped} skipped`);
      if (res.failed) parts.push(`${res.failed} failed`);
      toast.success(parts.join(" · "));
      if (res.errors?.length) toast.info(res.errors.slice(0, 3).join(" · "));
      clearSelection();
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setEnriching(false);
    }
  };

  const enrichAllUnenriched = async () => {
    if (!confirm("Enrich all records in this dataset that are not yet enriched? This may consume many Apollo credits.")) return;
    setEnriching(true);
    try {
      const { data: res } = await api.post(`/research/searches/${id}/enrich`, { all_unenriched: true });
      const parts = [`${res.enriched} enriched`];
      if (res.skipped) parts.push(`${res.skipped} skipped`);
      if (res.failed) parts.push(`${res.failed} failed`);
      toast.success(parts.join(" · "));
      if (res.errors?.length) toast.info(res.errors.slice(0, 3).join(" · "));
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setEnriching(false);
    }
  };

  const addCompany = async (e) => {
    e?.preventDefault();
    if (!companyForm.name.trim()) {
      toast.info("Company name is required.");
      return;
    }
    setSavingCompany(true);
    try {
      await api.post(`/research/searches/${id}/results`, {
        name: companyForm.name.trim(),
        domain: companyForm.domain || null,
        website: companyForm.website || null,
        industry: companyForm.industry || null,
        country: companyForm.country || null,
        city: companyForm.city || null,
        linkedin_url: companyForm.linkedin_url || null,
      });
      toast.success("Company added.");
      setShowAddCompany(false);
      setCompanyForm({ name: "", domain: "", country: "", industry: "", city: "", website: "", linkedin_url: "" });
      setPage(1);
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSavingCompany(false);
    }
  };

  const runImport = async (file) => {
    if (!file) {
      toast.info("Select a file first.");
      return;
    }
    setImporting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data: res } = await api.post(`/research/searches/${id}/import`, fd);
      toast.success(`${res.added} added${res.skipped ? `, ${res.skipped} skipped` : ""}.`);
      if (res.errors?.length) toast.info(res.errors.slice(0, 3).join(" · "));
      setPage(1);
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setImporting(false);
    }
  };

  const removeResult = async (rowId) => {
    if (!confirm("Remove this company from the dataset?")) return;
    try {
      await api.delete(`/research/searches/${id}/results/${rowId}`);
      toast.success("Company removed.");
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const search = data?.search;
  const isOrg = search?.query_type === "organizations";
  const isManualDataset = search?.criteria?._dataset_source === "manual";
  const columns = isOrg ? ORG_COLUMNS : PEOPLE_COLUMNS;
  const sourceSearchId = search?.criteria?._source_search_id;
  const sourceSearchName = search?.criteria?._source_search_name;
  const sourceCompanyResultId = search?.criteria?._source_company_result_id;
  const sourceCompanyName = search?.criteria?._source_company_name;
  const allOnPageSelected = data?.items?.length > 0 && data.items.every((row) => selected.has(row.id));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/research" className="mb-2 inline-flex items-center gap-1 text-sm text-ink-500 hover:text-brand-600">
            <Icon.ChevronRight width={16} height={16} className="rotate-180" /> Back to Market Research
          </Link>
          <h1 className="text-xl font-semibold text-ink-900">{search?.name || "Research"}</h1>
          <p className="text-sm text-ink-500">
            {isManualDataset ? "Manual company list" : isOrg ? "Companies" : "People"} · {search?.result_count ?? 0}{" "}
            records captured
            {search?.total_available ? ` of ${search.total_available} available` : ""}
          </p>
          {sourceSearchId ? (
            <p className="mt-1 text-sm text-ink-500">
              Based on company research{" "}
              <Link to={`/research/${sourceSearchId}`} className="font-medium text-brand-600 hover:underline">
                {sourceSearchName || `#${sourceSearchId}`}
              </Link>
              {sourceCompanyResultId ? (
                <>
                  {" · "}
                  <Link
                    to={`/research/${sourceSearchId}/companies/${sourceCompanyResultId}`}
                    className="font-medium text-brand-600 hover:underline"
                  >
                    {sourceCompanyName || "Company"}
                  </Link>
                </>
              ) : null}
            </p>
          ) : null}
          <p className="mt-1 text-xs text-ink-400">
            Optional: enrich records via Apollo complete profile APIs (
            {isOrg ? "organizations" : "people"}). This may consume credits and requires a master API key.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isManualDataset && (
            <>
              <button className="btn-secondary" onClick={() => setShowAddCompany(true)}>
                <Icon.Plus width={18} height={18} /> Add company
              </button>
              <label className={`btn-secondary cursor-pointer ${importing ? "pointer-events-none opacity-60" : ""}`}>
                {importing ? <Spinner className="h-4 w-4" /> : <Icon.Upload width={18} height={18} />} Import
                <input
                  type="file"
                  accept=".csv,.xlsx,.xlsm"
                  className="hidden"
                  disabled={importing}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) runImport(f);
                    e.target.value = "";
                  }}
                />
              </label>
            </>
          )}
          {isOrg && (
            <button className="btn-primary" onClick={openContactsModal} title="Find contacts at these companies">
              <Icon.Users width={18} height={18} /> Find contacts
            </button>
          )}
          <button
            className="btn-secondary"
            onClick={enrichAllUnenriched}
            disabled={enriching || !apolloReady}
            title={apolloReady ? undefined : "Enable Apollo in Settings to enrich."}
          >
            {enriching ? <Spinner className="h-4 w-4" /> : <Icon.Bolt width={18} height={18} />}
            Enrich all
          </button>
          <button className="btn-secondary" onClick={() => exportSearch("csv")}>
            <Icon.Download width={18} height={18} /> CSV
          </button>
          <button className="btn-secondary" onClick={() => exportSearch("xlsx")}>
            <Icon.Download width={18} height={18} /> Excel
          </button>
          <button className="btn-secondary text-red-600 hover:border-red-200 hover:bg-red-50" onClick={remove}>
            <Icon.Trash width={18} height={18} /> Delete
          </button>
        </div>
      </div>

      <div className="card">
        {selected.size > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-100 bg-brand-50/60 px-4 py-3">
            <span className="text-sm font-medium text-ink-700">{selected.size} selected</span>
            <div className="flex items-center gap-2">
              <button className="btn-ghost text-sm text-ink-500" onClick={clearSelection}>
                Clear selection
              </button>
              <button className="btn-primary" onClick={enrichSelected} disabled={enriching || !apolloReady}>
                {enriching ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : <Icon.Bolt width={18} height={18} />}
                Enrich selected
              </button>
            </div>
          </div>
        )}
        {loading ? (
          <PageLoader />
        ) : !data?.items?.length ? (
          <EmptyState
            title="No records yet"
            description={
              isManualDataset
                ? "Add companies manually or import a CSV/Excel file to get started."
                : "This research dataset is empty."
            }
            action={
              isManualDataset ? (
                <div className="flex flex-wrap justify-center gap-2">
                  <button className="btn-primary" onClick={() => setShowAddCompany(true)}>
                    <Icon.Plus width={18} height={18} /> Add company
                  </button>
                </div>
              ) : null
            }
          />
        ) : (
          <>
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
                    <th className="table-th">Status</th>
                    {columns.map((col) => (
                      <th key={col.key} className="table-th">
                        {col.label}
                      </th>
                    ))}
                    <th className="table-th"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {data.items.map((row) => (
                    <tr key={row.id} className="hover:bg-ink-50/60">
                      <td className="table-td">
                        <input
                          type="checkbox"
                          className="h-4 w-4 cursor-pointer rounded border-ink-300 text-brand-600 focus:ring-brand-500"
                          checked={selected.has(row.id)}
                          onChange={() => toggleOne(row.id)}
                          aria-label={`Select ${row.name || row.id}`}
                        />
                      </td>
                      <td className="table-td">
                        <StatusBadge status={row.enriched ? "enriched" : "none"} />
                      </td>
                      {columns.map((col) => (
                        <td key={col.key} className="table-td">
                          <CellValue column={col} row={row} isOrg={isOrg} searchId={id} />
                        </td>
                      ))}
                      <td className="table-td">
                        <div className="flex items-center gap-1">
                          {!row.enriched && (
                            <button
                              className="btn-ghost px-2 py-1 text-sm"
                              onClick={() => enrichOne(row.id)}
                              disabled={!apolloReady || enrichingId === row.id}
                              title="Fetch complete Apollo profile"
                            >
                              {enrichingId === row.id ? (
                                <Spinner className="h-4 w-4" />
                              ) : (
                                <Icon.Bolt width={15} height={15} />
                              )}
                            </button>
                          )}
                          {isManualDataset && (
                            <button
                              className="btn-ghost px-2 py-1 text-red-500"
                              onClick={() => removeResult(row.id)}
                              title="Remove from dataset"
                            >
                              <Icon.Trash width={15} height={15} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="border-t border-ink-100 px-4 py-3">
              <Pagination page={page} pageSize={pageSize} total={data.total} onPage={setPage} />
            </div>
          </>
        )}
      </div>

      <Modal
        open={showContacts}
        onClose={() => !runningContacts && setShowContacts(false)}
        title="Find contacts at these companies"
        wide
        footer={
          <>
            <button className="btn-secondary" onClick={() => setShowContacts(false)} disabled={runningContacts}>
              Cancel
            </button>
            <button className="btn-primary" onClick={runContactSearch} disabled={runningContacts}>
              {runningContacts ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : <Icon.Search width={18} height={18} />}
              Run & save
            </button>
          </>
        }
      >
        <form onSubmit={runContactSearch} className="space-y-4">
          <div className="rounded-lg border border-brand-100 bg-brand-50/50 px-4 py-3 text-sm text-ink-600">
            Searches contacts only at the <strong>{domainInfo?.domainCount ?? 0}</strong> domains from this company
            research ({domainInfo?.companyCount ?? 0} companies). Add filters below to narrow by title, seniority,
            location, and more.
          </div>

          <ApolloFilterForm
            fields={PEOPLE_CONTACT_FIELDS}
            values={contactFilters}
            onChange={(key, value) => setContactFilters((prev) => ({ ...prev, [key]: value }))}
          />

          <div className="grid grid-cols-1 gap-4 border-t border-ink-100 pt-4 sm:grid-cols-2">
            <Field label="Research name *">
              <input className="input" value={contactName} onChange={(e) => setContactName(e.target.value)} />
            </Field>
            <Field label="Max records">
              <select
                className="input"
                value={contactMaxRecords}
                onChange={(e) => setContactMaxRecords(Number(e.target.value))}
              >
                <option value={100}>100</option>
                <option value={250}>250</option>
                <option value={500}>500</option>
                <option value={1000}>1,000</option>
                <option value={2000}>2,000</option>
              </select>
            </Field>
          </div>
        </form>
      </Modal>

      <Modal
        open={showAddCompany}
        onClose={() => !savingCompany && setShowAddCompany(false)}
        title="Add company"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setShowAddCompany(false)} disabled={savingCompany}>
              Cancel
            </button>
            <button className="btn-primary" onClick={addCompany} disabled={savingCompany}>
              {savingCompany && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
            </button>
          </>
        }
      >
        <form onSubmit={addCompany} className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <Field label="Company name *">
              <input
                className="input"
                required
                value={companyForm.name}
                onChange={(e) => setCompanyForm({ ...companyForm, name: e.target.value })}
              />
            </Field>
          </div>
          <Field label="Domain">
            <input
              className="input"
              placeholder="example.com"
              value={companyForm.domain}
              onChange={(e) => setCompanyForm({ ...companyForm, domain: e.target.value })}
            />
          </Field>
          <Field label="Website">
            <input
              className="input"
              value={companyForm.website}
              onChange={(e) => setCompanyForm({ ...companyForm, website: e.target.value })}
            />
          </Field>
          <Field label="Country">
            <input
              className="input"
              value={companyForm.country}
              onChange={(e) => setCompanyForm({ ...companyForm, country: e.target.value })}
            />
          </Field>
          <Field label="City">
            <input
              className="input"
              value={companyForm.city}
              onChange={(e) => setCompanyForm({ ...companyForm, city: e.target.value })}
            />
          </Field>
          <Field label="Industry">
            <input
              className="input"
              value={companyForm.industry}
              onChange={(e) => setCompanyForm({ ...companyForm, industry: e.target.value })}
            />
          </Field>
          <Field label="LinkedIn">
            <input
              className="input"
              value={companyForm.linkedin_url}
              onChange={(e) => setCompanyForm({ ...companyForm, linkedin_url: e.target.value })}
            />
          </Field>
        </form>
      </Modal>
    </div>
  );
}
