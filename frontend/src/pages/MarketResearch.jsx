import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import api, { apiError } from "../api/client";
import ApolloFilterForm from "../components/ApolloFilterForm";
import { Icon } from "../components/icons";
import { EmptyState, Field, Spinner } from "../components/ui";
import {
  ORG_FILTER_FIELDS,
  PEOPLE_FILTER_FIELDS,
  buildCriteria,
  emptyFilters,
  slug,
} from "../constants/apolloSearchFields";
import { useToast } from "../context/ToastContext";

export default function MarketResearch() {
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const [status, setStatus] = useState(null);
  const [mode, setMode] = useState("organizations");
  const [name, setName] = useState("");
  const [maxRecords, setMaxRecords] = useState(500);
  const [orgFilters, setOrgFilters] = useState(() => emptyFilters(ORG_FILTER_FIELDS));
  const [peopleFilters, setPeopleFilters] = useState(() => emptyFilters(PEOPLE_FILTER_FIELDS));
  const [running, setRunning] = useState(false);
  const [searches, setSearches] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [createMode, setCreateMode] = useState("apollo");
  const [datasetName, setDatasetName] = useState("");
  const [creatingDataset, setCreatingDataset] = useState(false);

  const disabled = !status?.enabled || !status?.configured;
  const activeFields = mode === "organizations" ? ORG_FILTER_FIELDS : PEOPLE_FILTER_FIELDS;
  const activeFilters = mode === "organizations" ? orgFilters : peopleFilters;

  useEffect(() => {
    api.get("/apollo/status").then((res) => setStatus(res.data)).catch(() => setStatus(null));
    loadList();
  }, []);

  useEffect(() => {
    const state = location.state;
    if (!state) return;
    if (state.mode) setMode(state.mode);
    if (state.name) setName(state.name);
    if (state.prefilled) {
      if (state.mode === "people") {
        setPeopleFilters((prev) => ({ ...prev, ...state.prefilled }));
      } else {
        setOrgFilters((prev) => ({ ...prev, ...state.prefilled }));
      }
    }
    navigate(location.pathname, { replace: true, state: null });
  }, [location, navigate]);

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

  const setFilter = (key, value) => {
    if (mode === "organizations") {
      setOrgFilters((prev) => ({ ...prev, [key]: value }));
    } else {
      setPeopleFilters((prev) => ({ ...prev, [key]: value }));
    }
  };

  const run = async (e) => {
    e?.preventDefault();
    if (!name.trim()) {
      toast.info("Give your research a name first.");
      return;
    }
    const creditNote =
      mode === "organizations"
        ? "Company searches use Apollo credits."
        : "People API Search does not consume credits, but results are stored locally.";
    if (!confirm(`Run this search and capture up to ${maxRecords} records? ${creditNote}`)) return;

    setRunning(true);
    try {
      const fields = mode === "organizations" ? ORG_FILTER_FIELDS : PEOPLE_FILTER_FIELDS;
      const filters = mode === "organizations" ? orgFilters : peopleFilters;
      const { data } = await api.post("/research/searches", {
        name: name.trim(),
        query_type: mode,
        criteria: buildCriteria(filters, fields),
        max_records: Number(maxRecords),
      });
      toast.success(
        `Captured ${data.result_count} records${data.total_available ? ` (of ${data.total_available} available)` : ""}.`
      );
      setName("");
      setOrgFilters(emptyFilters(ORG_FILTER_FIELDS));
      setPeopleFilters(emptyFilters(PEOPLE_FILTER_FIELDS));
      loadList();
      navigate(`/research/${data.id}`);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setRunning(false);
    }
  };

  const createDataset = async (e) => {
    e?.preventDefault();
    if (!datasetName.trim()) {
      toast.info("Give your dataset a name first.");
      return;
    }
    setCreatingDataset(true);
    try {
      const { data } = await api.post("/research/datasets", { name: datasetName.trim() });
      toast.success("Empty company dataset created.");
      setDatasetName("");
      loadList();
      navigate(`/research/${data.id}`);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setCreatingDataset(false);
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
          Search Apollo or build your own company list (manual entry / import), then enrich and find contacts.
        </p>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-ink-200 bg-white px-4 py-3 text-sm text-ink-600">
        <Icon.Sparkles width={18} height={18} className="mt-0.5 text-brand-500" />
        <p>
          Company search uses{" "}
          <code className="rounded bg-ink-50 px-1 text-xs">/mixed_companies/search</code> and consumes credits.
          People search uses{" "}
          <code className="rounded bg-ink-50 px-1 text-xs">/mixed_people/api_search</code> (no credits). Saved data
          stays separate from your CRM.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={createMode === "apollo" ? "btn-primary" : "btn-secondary"}
          onClick={() => setCreateMode("apollo")}
        >
          <Icon.Search width={18} height={18} /> Apollo search
        </button>
        <button
          type="button"
          className={createMode === "dataset" ? "btn-primary" : "btn-secondary"}
          onClick={() => setCreateMode("dataset")}
        >
          <Icon.Plus width={18} height={18} /> Own company list
        </button>
      </div>

      {createMode === "dataset" ? (
        <form onSubmit={createDataset} className="card p-5 space-y-4">
          <p className="text-sm text-ink-600">
            Create an empty company dataset. Add companies manually or import a CSV/Excel file (column{" "}
            <code className="rounded bg-ink-50 px-1 text-xs">customer_name</code> required, optional{" "}
            <code className="rounded bg-ink-50 px-1 text-xs">domain</code>, <code className="rounded bg-ink-50 px-1 text-xs">country</code>).
            Then enrich via Apollo and search contacts with filters — same as Apollo research.
          </p>
          <div className="flex flex-wrap items-end gap-4">
            <div className="min-w-[220px] flex-1">
              <Field label="Dataset name *">
                <input
                  className="input"
                  placeholder="e.g. Target accounts Q3"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                />
              </Field>
            </div>
            <button type="submit" className="btn-primary" disabled={creatingDataset}>
              {creatingDataset ? (
                <Spinner className="h-4 w-4 border-white/40 border-t-white" />
              ) : (
                <Icon.Plus width={18} height={18} />
              )}
              Create dataset
            </button>
          </div>
        </form>
      ) : (
      <>
      {disabled && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          The Apollo integration is {status?.configured ? "disabled" : "not configured"}. Go to{" "}
          <a href="/settings" className="font-medium underline">
            Settings
          </a>{" "}
          to enable it.
        </div>
      )}

      <form onSubmit={run} className="card p-5">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            className={mode === "organizations" ? "btn-primary" : "btn-secondary"}
            onClick={() => setMode("organizations")}
          >
            <Icon.Building width={18} height={18} /> Companies
          </button>
          <button
            type="button"
            className={mode === "people" ? "btn-primary" : "btn-secondary"}
            onClick={() => setMode("people")}
          >
            <Icon.Users width={18} height={18} /> People
          </button>
        </div>

        <ApolloFilterForm fields={activeFields} values={activeFilters} onChange={setFilter} />

        <div className="mt-4 flex flex-wrap items-end gap-4 border-t border-ink-100 pt-4">
          <div className="min-w-[220px] flex-1">
            <Field label="Research name *">
              <input
                className="input"
                placeholder="e.g. Dutch fintech VPs Q3"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
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
      </>
      )}

      <div className="card">
        <div className="border-b border-ink-100 px-5 py-4">
          <h2 className="text-sm font-semibold text-ink-900">Saved research</h2>
        </div>
        {loadingList ? (
          <div className="flex justify-center py-10">
            <Spinner className="h-6 w-6" />
          </div>
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
                      <Link to={`/research/${s.id}`} className="font-medium text-ink-900 hover:text-brand-600">
                        {s.name}
                      </Link>
                    </td>
                    <td className="table-td">
                      {s.criteria?._dataset_source === "manual" ? (
                        <span className="badge bg-violet-50 text-violet-700">Manual list</span>
                      ) : (
                        <span className="capitalize">{s.query_type === "people" ? "People" : "Companies"}</span>
                      )}
                    </td>
                    <td className="table-td">
                      {s.result_count}
                      {s.total_available ? <span className="text-ink-400"> / {s.total_available}</span> : null}
                    </td>
                    <td className="table-td text-ink-500">{new Date(s.created_at).toLocaleString()}</td>
                    <td className="table-td">
                      <div className="flex items-center justify-end gap-1">
                        <Link to={`/research/${s.id}`} className="btn-ghost px-2 py-1 text-sm">
                          View
                        </Link>
                        <button className="btn-ghost px-2 py-1 text-sm" onClick={() => exportSearch(s, "csv")}>
                          <Icon.Download width={15} height={15} /> CSV
                        </button>
                        <button className="btn-ghost px-2 py-1 text-sm" onClick={() => exportSearch(s, "xlsx")}>
                          <Icon.Download width={15} height={15} /> Excel
                        </button>
                        <button className="btn-ghost px-2 py-1 text-red-500" onClick={() => remove(s)}>
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
    </div>
  );
}
