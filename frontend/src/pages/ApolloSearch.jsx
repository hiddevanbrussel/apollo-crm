import { useEffect, useState } from "react";
import api, { apiError } from "../api/client";
import { Icon } from "../components/icons";
import { EmptyState, Field, Spinner } from "../components/ui";
import { useToast } from "../context/ToastContext";

function splitList(value) {
  return value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

export default function ApolloSearch() {
  const toast = useToast();
  const [mode, setMode] = useState("organizations");
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState({});
  const [saving, setSaving] = useState(false);
  const [searched, setSearched] = useState(false);

  const [orgFilters, setOrgFilters] = useState({ q_organization_name: "", organization_domains: "", organization_industries: "", organization_locations: "" });
  const [peopleFilters, setPeopleFilters] = useState({ q_organization_name: "", organization_domains: "", person_titles: "", person_seniorities: "", person_departments: "", person_locations: "", organization_industries: "" });

  useEffect(() => {
    api.get("/apollo/status").then((res) => setStatus(res.data)).catch(() => setStatus(null));
  }, []);

  const disabled = !status?.enabled || !status?.configured;

  const reset = () => {
    setResults([]);
    setSelected({});
    setSearched(false);
  };

  const switchMode = (m) => {
    setMode(m);
    reset();
  };

  const search = async (e) => {
    e?.preventDefault();
    setLoading(true);
    reset();
    try {
      let payload;
      let url;
      if (mode === "organizations") {
        url = "/apollo/search/organizations";
        payload = {
          q_organization_name: orgFilters.q_organization_name || undefined,
          organization_domains: splitList(orgFilters.organization_domains),
          organization_industries: splitList(orgFilters.organization_industries),
          organization_locations: splitList(orgFilters.organization_locations),
          per_page: 25,
        };
      } else {
        url = "/apollo/search/people";
        payload = {
          q_organization_name: peopleFilters.q_organization_name || undefined,
          organization_domains: splitList(peopleFilters.organization_domains),
          person_titles: splitList(peopleFilters.person_titles),
          person_seniorities: splitList(peopleFilters.person_seniorities),
          person_departments: splitList(peopleFilters.person_departments),
          person_locations: splitList(peopleFilters.person_locations),
          organization_industries: splitList(peopleFilters.organization_industries),
          per_page: 25,
        };
      }
      const { data } = await api.post(url, payload);
      setResults(data.results || []);
      setSearched(true);
      if ((data.results || []).length === 0) toast.info("No results found.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  const toggle = (idx) => setSelected((prev) => ({ ...prev, [idx]: !prev[idx] }));
  const toggleAll = () => {
    if (Object.values(selected).filter(Boolean).length === results.length) {
      setSelected({});
    } else {
      setSelected(Object.fromEntries(results.map((_, i) => [i, true])));
    }
  };

  const saveSelected = async () => {
    const chosen = results.filter((_, i) => selected[i]);
    if (chosen.length === 0) {
      toast.info("Select results to save first.");
      return;
    }
    setSaving(true);
    try {
      const url = mode === "organizations" ? "/apollo/save/organizations" : "/apollo/save/people";
      const { data } = await api.post(url, { results: chosen });
      toast.success(`${data.saved} of ${data.total} saved to CRM.`);
      setSelected({});
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  const saveOne = async (idx) => {
    setSaving(true);
    try {
      const url = mode === "organizations" ? "/apollo/save/organizations" : "/apollo/save/people";
      const { data } = await api.post(url, { results: [results[idx]] });
      toast.success(data.saved ? "Saved to CRM." : "Not saved (incomplete data).");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSaving(false);
    }
  };

  const selectedCount = Object.values(selected).filter(Boolean).length;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Apollo Search</h1>
        <p className="text-sm text-ink-500">Search companies and people via Apollo and save selected results.</p>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-ink-200 bg-white px-4 py-3 text-sm text-ink-600">
        <Icon.Sparkles width={18} height={18} className="mt-0.5 text-brand-500" />
        <p>
          Apollo is <strong>only called when you click “Search”</strong>. Nothing happens
          automatically — so you decide when credits are used. Saving results to your
          CRM costs <strong>no</strong> extra credits.
        </p>
      </div>

      {disabled && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          The Apollo integration is {status?.configured ? "disabled" : "not configured"}. Go to{" "}
          <a href="/settings" className="font-medium underline">Settings</a> to enable it.
        </div>
      )}

      <div className="flex gap-2">
        <button
          className={mode === "organizations" ? "btn-primary" : "btn-secondary"}
          onClick={() => switchMode("organizations")}
        >
          <Icon.Building width={18} height={18} /> Companies
        </button>
        <button
          className={mode === "people" ? "btn-primary" : "btn-secondary"}
          onClick={() => switchMode("people")}
        >
          <Icon.Users width={18} height={18} /> People
        </button>
      </div>

      <form onSubmit={search} className="card p-5">
        {mode === "organizations" ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Company name"><input className="input" value={orgFilters.q_organization_name} onChange={(e) => setOrgFilters({ ...orgFilters, q_organization_name: e.target.value })} /></Field>
            <Field label="Domain (comma-separated)"><input className="input" placeholder="acme.com, foo.io" value={orgFilters.organization_domains} onChange={(e) => setOrgFilters({ ...orgFilters, organization_domains: e.target.value })} /></Field>
            <Field label="Industry"><input className="input" value={orgFilters.organization_industries} onChange={(e) => setOrgFilters({ ...orgFilters, organization_industries: e.target.value })} /></Field>
            <Field label="Country / location"><input className="input" placeholder="Netherlands" value={orgFilters.organization_locations} onChange={(e) => setOrgFilters({ ...orgFilters, organization_locations: e.target.value })} /></Field>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Job title"><input className="input" placeholder="Head of Sales" value={peopleFilters.person_titles} onChange={(e) => setPeopleFilters({ ...peopleFilters, person_titles: e.target.value })} /></Field>
            <Field label="Seniority"><input className="input" placeholder="vp, director" value={peopleFilters.person_seniorities} onChange={(e) => setPeopleFilters({ ...peopleFilters, person_seniorities: e.target.value })} /></Field>
            <Field label="Department"><input className="input" placeholder="sales, marketing" value={peopleFilters.person_departments} onChange={(e) => setPeopleFilters({ ...peopleFilters, person_departments: e.target.value })} /></Field>
            <Field label="Country / location"><input className="input" placeholder="Netherlands" value={peopleFilters.person_locations} onChange={(e) => setPeopleFilters({ ...peopleFilters, person_locations: e.target.value })} /></Field>
            <Field label="Company name"><input className="input" value={peopleFilters.q_organization_name} onChange={(e) => setPeopleFilters({ ...peopleFilters, q_organization_name: e.target.value })} /></Field>
            <Field label="Domain"><input className="input" placeholder="acme.com" value={peopleFilters.organization_domains} onChange={(e) => setPeopleFilters({ ...peopleFilters, organization_domains: e.target.value })} /></Field>
            <Field label="Industry"><input className="input" value={peopleFilters.organization_industries} onChange={(e) => setPeopleFilters({ ...peopleFilters, organization_industries: e.target.value })} /></Field>
          </div>
        )}
        <div className="mt-4 flex justify-end">
          <button type="submit" className="btn-primary" disabled={disabled || loading}>
            {loading ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : <Icon.Search width={18} height={18} />}
            Search
          </button>
        </div>
      </form>

      {results.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between border-b border-ink-100 p-4">
            <div className="flex items-center gap-3">
              <button className="btn-secondary" onClick={toggleAll}>
                {selectedCount === results.length ? "Deselect all" : "Select all"}
              </button>
              <span className="text-sm text-ink-500">{selectedCount} selected · {results.length} results</span>
            </div>
            <button className="btn-primary" onClick={saveSelected} disabled={saving || selectedCount === 0}>
              {saving ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : <Icon.Check width={18} height={18} />}
              Save to CRM ({selectedCount})
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-ink-100 bg-ink-50/50">
                <tr>
                  <th className="table-th w-10"></th>
                  {mode === "organizations" ? (
                    <>
                      <th className="table-th">Company</th>
                      <th className="table-th">Industry</th>
                      <th className="table-th">Employees</th>
                      <th className="table-th">Location</th>
                    </>
                  ) : (
                    <>
                      <th className="table-th">Name</th>
                      <th className="table-th">Title</th>
                      <th className="table-th">Company</th>
                      <th className="table-th">Location</th>
                    </>
                  )}
                  <th className="table-th"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {results.map((r, i) => (
                  <tr key={i} className={`hover:bg-ink-50/60 ${selected[i] ? "bg-brand-50/40" : ""}`}>
                    <td className="table-td">
                      <input type="checkbox" className="h-4 w-4 rounded border-ink-300" checked={!!selected[i]} onChange={() => toggle(i)} />
                    </td>
                    {mode === "organizations" ? (
                      <>
                        <td className="table-td">
                          <p className="font-medium text-ink-900">{r.name || "—"}</p>
                          <p className="text-xs text-ink-400">{r.primary_domain || r.website_url || "—"}</p>
                        </td>
                        <td className="table-td">{r.industry || "—"}</td>
                        <td className="table-td">{r.estimated_num_employees?.toLocaleString() || "—"}</td>
                        <td className="table-td">{[r.city, r.country].filter(Boolean).join(", ") || "—"}</td>
                      </>
                    ) : (
                      <>
                        <td className="table-td">
                          <p className="font-medium text-ink-900">{r.name || `${r.first_name || ""} ${r.last_name || ""}`}</p>
                          <p className="text-xs text-ink-400">{r.email && !String(r.email).includes("not_unlocked") ? r.email : "Email locked"}</p>
                        </td>
                        <td className="table-td">{r.title || "—"}</td>
                        <td className="table-td">{r.organization?.name || "—"}</td>
                        <td className="table-td">{[r.city, r.country].filter(Boolean).join(", ") || "—"}</td>
                      </>
                    )}
                    <td className="table-td text-right">
                      <button className="btn-secondary px-2.5 py-1.5 text-xs" onClick={() => saveOne(i)} disabled={saving}>
                        Save to CRM
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {searched && results.length === 0 && (
        <div className="card">
          <EmptyState title="No results" description="Adjust your search filters and try again." />
        </div>
      )}
    </div>
  );
}
