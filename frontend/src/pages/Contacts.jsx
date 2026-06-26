import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { apiError } from "../api/client";
import { Icon } from "../components/icons";
import { EmptyState, Field, Modal, Pagination, PageLoader, SourceBadge, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../context/ToastContext";

const EMPTY = { first_name: "", last_name: "", title: "", email: "", phone: "", linkedin_url: "", city: "", country: "", seniority: "", department: "", company_id: "" };

export default function Contacts() {
  const toast = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [companies, setCompanies] = useState([]);
  const [saving, setSaving] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);
  const pageSize = 20;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/contacts", {
        params: {
          search: search || undefined,
          enrichment_status: status || undefined,
          source: sourceFilter || undefined,
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
  }, [search, status, sourceFilter, page, toast]);

  useEffect(() => {
    load();
  }, [load]);

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
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setDeletingAll(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">Contacts</h1>
          <p className="text-sm text-ink-500">Manage all contacts in your CRM.</p>
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
          <button className="btn-primary" onClick={openCreate}>
            <Icon.Plus width={18} height={18} /> New contact
          </button>
        </div>
      </div>

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
          <select className="input w-auto" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            <option value="enriched">Enriched</option>
            <option value="none">Not enriched</option>
            <option value="failed">Failed</option>
          </select>
          <select className="input w-auto" value={sourceFilter} onChange={(e) => { setSourceFilter(e.target.value); setPage(1); }}>
            <option value="">All sources</option>
            <option value="import">Imported</option>
            <option value="apollo">Apollo</option>
            <option value="manual">Manual</option>
          </select>
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
                  <tr key={ct.id} className="hover:bg-ink-50/60">
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
