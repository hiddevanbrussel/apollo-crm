import { useEffect, useState } from "react";
import api, { apiError } from "../api/client";
import { Icon } from "../components/icons";
import { EmptyState, Field, Modal, Spinner } from "../components/ui";
import { useToast } from "../context/ToastContext";

function splitList(value) {
  return (value || "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

function slug(name) {
  return (name || "research").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "research";
}

const ORG_EMPTY = { q_organization_name: "", organization_domains: "", organization_industries: "", organization_locations: "", organization_num_employees_ranges: "" };
const PEOPLE_EMPTY = { person_titles: "", person_seniorities: "", person_departments: "", person_locations: "", q_organization_name: "", organization_domains: "", organization_industries: "" };

export default function MarketResearch() {
  const toast = useToast();
  const [status, setStatus] = useState(null);
  const [mode, setMode] = useState("organizations");
  const [name, setName] = useState("");
  const [maxRecords, setMaxRecords] = useState(500);
  const [orgFilters, setOrgFilters] = useState(ORG_EMPTY);
  const [peopleFilters, setPeopleFilters] = useState(PEOPLE_EMPTY);
  const [running, setRunning] = useState(false);

  const [searches, setSearches] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const disabled = !status?.enabled || !status?.configured;

  useEffect(() => {
    api.get("/apollo/status").then((res) => setStatus(res.data)).catch(() => setStatus(null));
    loadList();
  }, []);

  const loadList = async () => {
    setLoadingList(true);
    try {
      const { data } = await api.get("/research/searches");
      setSearches(data.items);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoadingList(false);
    }
  };

  const buildCriteria = () => {
    if (mode === "organizations") {
      return {
        q_organization_name: orgFilters.q_organization_name || undefined,
        organization_domains: splitList(orgFilters.organization_domains),
        organization_industries: splitList(orgFilters.organization_industries),
        organization_locations: splitList(orgFilters.organization_locations),
        organization_num_employees_ranges: splitList(orgFilters.organization_num_employees_ranges),
      };
    }
    return {
      person_titles: splitList(peopleFilters.person_titles),
      person_seniorities: splitList(peopleFilters.person_seniorities),
      person_departments: splitList(peopleFilters.person_departments),
      person_locations: splitList(peopleFilters.person_locations),
      q_organization_name: peopleFilters.q_organization_name || undefined,
      organization_domains: splitList(peopleFilters.organization_domains),
      organization_industries: splitList(peopleFilters.organization_industries),
    };
  };

  const run = async (e) => {
    e?.preventDefault();
    if (!name.trim()) {
      toast.info("Give your research a name first.");
      return;
    }
    if (!confirm(`Run this search and capture up to ${maxRecords} records? This uses Apollo credits.`)) return;
    setRunning(true);
    try {
      const { data } = await api.post("/research/searches", {
        name: name.trim(),
        query_type: mode,
        criteria: buildCriteria(),
        max_records: Number(maxRecords),
      });
      toast.success(`Captured ${data.result_count} records${data.total_available ? ` (of ${data.total_available} available)` : ""}.`);
      setName("");
      setOrgFilters(ORG_EMPTY);
      setPeopleFilters(PEOPLE_EMPTY);
      loadList();
      setDetail(data);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setRunning(false);
    }
  };

  const openDetail = async (id) => {
    setLoadingDetail(true);
    setDetail({ loading: true });
    try {
      const { data } = await api.get(`/research/searches/${id}`);
      setDetail(data);
    } catch (err) {
      toast.error(apiError(err));
      setDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  const exportSearch = async (s, format) => {
    try {
      const res = await api.get(`/research/searches/${s.id}/export`, { params: { format }, responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${slug(s.name)}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const remove = async (s) => {
    if (!confirm(`Delete research "${s.name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/research/searches/${s.id}`);
      toast.success("Research deleted.");
      loadList();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Market Research</h1>
        <p className="text-sm text-ink-500">
          Search Apollo by criteria, capture the results as a dataset, and export them later.
        </p>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-ink-200 bg-white px-4 py-3 text-sm text-ink-600">
        <Icon.Sparkles width={18} height={18} className="mt-0.5 text-brand-500" />
        <p>
          Each research run calls Apollo and <strong>uses credits</strong> (more records = more
          credits). Captured data is stored separately from your CRM and can be exported to CSV or
          Excel.
        </p>
      </div>

      {disabled && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          The Apollo integration is {status?.configured ? "disabled" : "not configured"}. Go to{" "}
          <a href="/settings" className="font-medium underline">Settings</a> to enable it.
        </div>
      )}

      {/* New research form */}
      <form onSubmit={run} className="card p-5">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <button type="button" className={mode === "organizations" ? "btn-primary" : "btn-secondary"} onClick={() => setMode("organizations")}>
            <Icon.Building width={18} height={18} /> Companies
          </button>
          <button type="button" className={mode === "people" ? "btn-primary" : "btn-secondary"} onClick={() => setMode("people")}>
            <Icon.Users width={18} height={18} /> People
          </button>
        </div>

        {mode === "organizations" ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Company name"><input className="input" value={orgFilters.q_organization_name} onChange={(e) => setOrgFilters({ ...orgFilters, q_organization_name: e.target.value })} /></Field>
            <Field label="Domains (comma-separated)"><input className="input" placeholder="acme.com, foo.io" value={orgFilters.organization_domains} onChange={(e) => setOrgFilters({ ...orgFilters, organization_domains: e.target.value })} /></Field>
            <Field label="Industries"><input className="input" placeholder="software, fintech" value={orgFilters.organization_industries} onChange={(e) => setOrgFilters({ ...orgFilters, organization_industries: e.target.value })} /></Field>
            <Field label="Locations"><input className="input" placeholder="Netherlands, Germany" value={orgFilters.organization_locations} onChange={(e) => setOrgFilters({ ...orgFilters, organization_locations: e.target.value })} /></Field>
            <Field label="Employee ranges"><input className="input" placeholder="1,10 · 11,50 · 51,200" value={orgFilters.organization_num_employees_ranges} onChange={(e) => setOrgFilters({ ...orgFilters, organization_num_employees_ranges: e.target.value })} /></Field>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Job titles"><input className="input" placeholder="Head of Sales, CTO" value={peopleFilters.person_titles} onChange={(e) => setPeopleFilters({ ...peopleFilters, person_titles: e.target.value })} /></Field>
            <Field label="Seniorities"><input className="input" placeholder="vp, director" value={peopleFilters.person_seniorities} onChange={(e) => setPeopleFilters({ ...peopleFilters, person_seniorities: e.target.value })} /></Field>
            <Field label="Departments"><input className="input" placeholder="sales, marketing" value={peopleFilters.person_departments} onChange={(e) => setPeopleFilters({ ...peopleFilters, person_departments: e.target.value })} /></Field>
            <Field label="Locations"><input className="input" placeholder="Netherlands" value={peopleFilters.person_locations} onChange={(e) => setPeopleFilters({ ...peopleFilters, person_locations: e.target.value })} /></Field>
            <Field label="Company name"><input className="input" value={peopleFilters.q_organization_name} onChange={(e) => setPeopleFilters({ ...peopleFilters, q_organization_name: e.target.value })} /></Field>
            <Field label="Industries"><input className="input" value={peopleFilters.organization_industries} onChange={(e) => setPeopleFilters({ ...peopleFilters, organization_industries: e.target.value })} /></Field>
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-end gap-4 border-t border-ink-100 pt-4">
          <div className="min-w-[220px] flex-1">
            <Field label="Research name *">
              <input className="input" placeholder="e.g. Dutch fintech VPs Q3" value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
          </div>
          <Field label="Max records">
            <select className="input w-auto" value={maxRecords} onChange={(e) => setMaxRecords(Number(e.target.value))}>
              <option value={100}>100</option>
              <option value={250}>250</option>
              <option value={500}>500</option>
              <option value={1000}>1,000</option>
              <option value={2000}>2,000</option>
            </select>
          </Field>
          <button type="submit" className="btn-primary" disabled={disabled || running}>
            {running ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : <Icon.Search width={18} height={18} />}
            Run & save
          </button>
        </div>
      </form>

      {/* Saved research */}
      <div className="card">
        <div className="border-b border-ink-100 px-5 py-4">
          <h2 className="text-sm font-semibold text-ink-900">Saved research</h2>
        </div>
        {loadingList ? (
          <div className="flex justify-center py-10"><Spinner className="h-6 w-6" /></div>
        ) : searches.length === 0 ? (
          <EmptyState title="No research yet" description="Run a search above to capture your first dataset." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-ink-100 bg-ink-50/50">
                <tr>
                  <th className="table-th">Name</th>
                  <th className="table-th">Type</th>
                  <th className="table-th">Records</th>
                  <th className="table-th">Created</th>
                  <th className="table-th"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {searches.map((s) => (
                  <tr key={s.id} className="hover:bg-ink-50/60">
                    <td className="table-td">
                      <button className="font-medium text-ink-900 hover:text-brand-600" onClick={() => openDetail(s.id)}>
                        {s.name}
                      </button>
                    </td>
                    <td className="table-td capitalize">{s.query_type === "people" ? "People" : "Companies"}</td>
                    <td className="table-td">
                      {s.result_count}
                      {s.total_available ? <span className="text-ink-400"> / {s.total_available}</span> : null}
                    </td>
                    <td className="table-td text-ink-500">{new Date(s.created_at).toLocaleString()}</td>
                    <td className="table-td">
                      <div className="flex items-center justify-end gap-1">
                        <button className="btn-ghost px-2 py-1 text-sm" onClick={() => openDetail(s.id)} title="View">
                          View
                        </button>
                        <button className="btn-ghost px-2 py-1 text-sm" onClick={() => exportSearch(s, "csv")} title="Export CSV">
                          <Icon.Download width={15} height={15} /> CSV
                        </button>
                        <button className="btn-ghost px-2 py-1 text-sm" onClick={() => exportSearch(s, "xlsx")} title="Export Excel">
                          <Icon.Download width={15} height={15} /> Excel
                        </button>
                        <button className="btn-ghost px-2 py-1 text-red-500" onClick={() => remove(s)} title="Delete">
                          <Icon.Trash width={15} height={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal
        open={!!detail}
        onClose={() => setDetail(null)}
        title={detail && !detail.loading ? detail.name : "Research"}
        wide
        footer={
          detail && !detail.loading ? (
            <>
              <button className="btn-secondary" onClick={() => exportSearch(detail, "csv")}>
                <Icon.Download width={16} height={16} /> CSV
              </button>
              <button className="btn-primary" onClick={() => exportSearch(detail, "xlsx")}>
                <Icon.Download width={16} height={16} /> Excel
              </button>
            </>
          ) : null
        }
      >
        {loadingDetail || detail?.loading ? (
          <div className="flex justify-center py-10"><Spinner className="h-6 w-6" /></div>
        ) : detail ? (
          <div>
            <p className="mb-3 text-sm text-ink-500">
              {detail.result_count} records{detail.total_available ? ` of ${detail.total_available} available` : ""}.
            </p>
            <div className="max-h-[60vh] overflow-auto rounded-lg border border-ink-100">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-ink-50">
                  <tr>
                    {detail.columns.map((c) => (
                      <th key={c} className="whitespace-nowrap px-3 py-2 text-left font-semibold text-ink-600">{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {detail.rows.map((row, i) => (
                    <tr key={i} className="hover:bg-ink-50/60">
                      {detail.columns.map((c) => (
                        <td key={c} className="whitespace-nowrap px-3 py-1.5 text-ink-700">
                          {row[c] === null || row[c] === undefined || row[c] === "" ? "—" : String(row[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
