import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api, { apiError } from "../api/client";
import { Icon } from "../components/icons";
import { CompanyLogo, DomainTags, Field, Modal, PageLoader, SourceBadge, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";

const EDIT_FIELDS = [
  "name",
  "domain",
  "website",
  "linkedin_url",
  "industry",
  "employee_count",
  "revenue",
  "country",
  "city",
  "phone",
  "description",
  "tier",
  "revenue_2025",
  "sector_confidence",
  "partner_status",
];

function Detail({ label, value, href }) {
  return (
    <div className="py-2.5">
      <dt className="text-xs font-medium text-ink-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-ink-800">
        {href && value ? (
          <a href={href} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-600 hover:underline">
            {value} <Icon.External width={13} height={13} />
          </a>
        ) : (
          value || "—"
        )}
      </dd>
    </div>
  );
}

function canMatchContact(contact) {
  return (
    Boolean(contact.apollo_id) ||
    Boolean(contact.prospeo_id) ||
    Boolean(contact.email?.trim()) ||
    Boolean(contact.linkedin_url?.trim()) ||
    Boolean(contact.full_name?.trim()) ||
    Boolean(contact.first_name?.trim() && contact.last_name?.trim())
  );
}

export default function CompanyDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { isAdmin } = useAuth();
  const [company, setCompany] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [tab, setTab] = useState("overview");
  const [enriching, setEnriching] = useState(false);
  const [apolloReady, setApolloReady] = useState(false);
  const [prospeoReady, setProspeoReady] = useState(false);
  const [lushaReady, setLushaReady] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [savingEdit, setSavingEdit] = useState(false);
  const [groqReady, setGroqReady] = useState(false);
  const [findingDomain, setFindingDomain] = useState(false);
  const [findingPeople, setFindingPeople] = useState(false);
  const [completingId, setCompletingId] = useState(null);
  const [matchingId, setMatchingId] = useState(null);
  const [matchingAll, setMatchingAll] = useState(false);

  useEffect(() => {
    api
      .get("/settings/status")
      .then((res) => {
        const apollo = res.data.apollo?.enabled && res.data.apollo?.configured;
        const prospeo = res.data.prospeo?.enabled && res.data.prospeo?.configured;
        const lusha = res.data.lusha?.enabled && res.data.lusha?.configured;
        setApolloReady(apollo);
        setProspeoReady(prospeo);
        setLushaReady(lusha);
        setGroqReady(res.data.groq?.enabled && res.data.groq?.configured);
      })
      .catch(() => {
        setApolloReady(false);
        setProspeoReady(false);
        setGroqReady(false);
      });
  }, []);

  const load = useCallback(async () => {
    try {
      const [{ data: c }, { data: ct }] = await Promise.all([
        api.get(`/companies/${id}`),
        api.get(`/contacts`, { params: { company_id: id, page_size: 100 } }),
      ]);
      setCompany(c);
      setContacts(ct.items);
    } catch (err) {
      toast.error(apiError(err));
      navigate("/companies");
    }
  }, [id, navigate, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const enrich = async () => {
    setEnriching(true);
    try {
      const { data } = await api.post(`/companies/${id}/enrich`);
      setCompany(data);
      toast.success("Company enriched via Apollo.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setEnriching(false);
    }
  };

  const findDomain = async () => {
    const overwrite = company.domain
      ? confirm("This company already has a domain. Do you want to search again and overwrite it?")
      : false;
    setFindingDomain(true);
    try {
      const { data } = await api.post(
        `/companies/${id}/find-domain${overwrite ? "?overwrite=true" : ""}`
      );
      if (data.company) setCompany(data.company);
      if (data.applied) {
        toast.success(`Domain found: ${data.domain}`);
      } else if (data.found) {
        toast.info(`Suggestion: ${data.domain || "—"} — ${data.message || ""}`);
      } else {
        toast.error(data.message || "No domain found.");
      }
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setFindingDomain(false);
    }
  };

  const findPeople = async () => {
    setFindingPeople(true);
    try {
      const { data } = await api.post(`/companies/${id}/find-people`);
      toast.success(`Found ${data.total} people · ${data.created} new, ${data.updated} updated.`);
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setFindingPeople(false);
    }
  };

  const completePerson = async (contactId) => {
    setCompletingId(contactId);
    try {
      const { data } = await api.post(`/contacts/${contactId}/complete`);
      setContacts((prev) => prev.map((c) => (c.id === contactId ? data : c)));
      toast.success(`Fetched complete info for ${data.full_name || "this contact"}.`);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setCompletingId(null);
    }
  };

  const matchContact = async (contactId) => {
    setMatchingId(contactId);
    try {
      const { data } = await api.post(`/contacts/${contactId}/enrich`);
      setContacts((prev) => prev.map((c) => (c.id === contactId ? data : c)));
      toast.success(
        data.enrichment_status === "pending"
          ? "Contact matched. Waterfall email may arrive in a few minutes."
          : `Contact enriched via ${data.source === "prospeo" ? "Prospeo" : data.source === "lusha" ? "Lusha" : "Apollo"}.`,
      );
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setMatchingId(null);
    }
  };

  const matchAllContacts = async () => {
    if (!contacts.length) return;
    if (
      !confirm(
        `Match all ${contacts.length} contact(s) at this company? Apollo is tried first, then Prospeo. Credits apply per provider.`
      )
    ) {
      return;
    }
    setMatchingAll(true);
    try {
      const { data: res } = await api.post(`/companies/${id}/enrich-contacts`);
      const parts = [];
      if (res.enriched) parts.push(`${res.enriched} enriched`);
      if (res.pending) parts.push(`${res.pending} pending`);
      if (res.failed) parts.push(`${res.failed} failed`);
      toast.success(parts.length ? parts.join(", ") : "Bulk match completed.");
      if (res.errors?.length) {
        toast.info(res.errors.slice(0, 3).join(" · "));
      }
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setMatchingAll(false);
    }
  };

  const openEdit = () => {
    const initial = {};
    EDIT_FIELDS.forEach((f) => {
      initial[f] = company[f] ?? "";
    });
    setEditForm(initial);
    setShowEdit(true);
  };

  const saveEdit = async (e) => {
    e?.preventDefault();
    setSavingEdit(true);
    try {
      const payload = {};
      EDIT_FIELDS.forEach((f) => {
        let value = editForm[f];
        if (f === "employee_count" || f === "revenue" || f === "revenue_2025") {
          value = value === "" || value === null ? null : Number(value);
        } else {
          value = value === "" ? null : value;
        }
        payload[f] = value;
      });
      const { data } = await api.put(`/companies/${id}`, payload);
      setCompany(data);
      setShowEdit(false);
      toast.success("Company updated.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSavingEdit(false);
    }
  };

  if (!company) return <PageLoader />;

  const website = company.website || (company.domain ? `https://${company.domain}` : null);
  const enrichReady = apolloReady || prospeoReady || lushaReady;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link to="/companies" className="btn-secondary px-2 py-2">
            <Icon.ChevronLeft width={18} height={18} />
          </Link>
          <CompanyLogo domain={company.domain} name={company.name} size={48} rounded="rounded-xl" />
          <div>
            <h1 className="text-xl font-semibold text-ink-900">{company.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <StatusBadge status={company.enrichment_status} />
              <SourceBadge source={company.source} />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={openEdit}>
            <Icon.Edit width={18} height={18} /> Edit
          </button>
          <button
            className="btn-secondary"
            onClick={findDomain}
            disabled={findingDomain || !groqReady}
            title={groqReady ? "Find the domain via Groq (AI web search)" : "Groq is off — enable it in Settings"}
          >
            {findingDomain ? <Spinner className="h-4 w-4" /> : <Icon.Wand width={18} height={18} />}
            Find domain
          </button>
          {isAdmin && (
          <button
            className="btn-primary"
            onClick={enrich}
            disabled={enriching || !apolloReady}
            title={apolloReady ? "Enrich this company via Apollo (uses credits)" : "Apollo is off — enable it in Settings"}
          >
            {enriching ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : <Icon.Sparkles width={18} height={18} />}
            Enrich via Apollo
          </button>
          )}
        </div>
      </div>

      <div className="card">
        <div className="flex gap-1 border-b border-ink-100 px-4">
          {[
            ["overview", "Overview"],
            ["contacts", `Contacts (${contacts.length})`],
            ["apollo", "Apollo data"],
          ].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`-mb-px border-b-2 px-4 py-3 text-sm font-medium ${
                tab === key ? "border-brand-600 text-brand-700" : "border-transparent text-ink-500 hover:text-ink-800"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="p-5">
          {tab === "overview" && (
            <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2 lg:grid-cols-3">
              <div className="py-2.5 sm:col-span-2 lg:col-span-3">
                <dt className="text-xs font-medium text-ink-400">Domains</dt>
                <dd className="mt-1.5">
                  <DomainTags domains={company.domains} primary={company.domain} />
                </dd>
              </div>
              <Detail label="Website" value={website} href={website} />
              <Detail label="LinkedIn" value={company.linkedin_url} href={company.linkedin_url} />
              <Detail label="Industry" value={company.industry} />
              <Detail label="Employees" value={company.employee_count?.toLocaleString()} />
              <Detail label="Revenue" value={company.revenue ? `$${company.revenue.toLocaleString()}` : null} />
              <Detail label="Country" value={company.country} />
              <Detail label="City" value={company.city} />
              <Detail label="Tier" value={company.tier} />
              <Detail
                label="Revenue 2025"
                value={company.revenue_2025 != null ? company.revenue_2025.toLocaleString() : null}
              />
              <Detail label="Sector confidence" value={company.sector_confidence} />
              <Detail label="Partner status" value={company.partner_status} />
              <Detail label="Phone" value={company.phone} />
              <div className="sm:col-span-2 lg:col-span-3">
                <Detail label="Description" value={company.description} />
              </div>
            </dl>
          )}

          {tab === "contacts" && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-ink-500">{contacts.length} contact(s) linked</p>
                {isAdmin && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    className="btn-secondary"
                    onClick={matchAllContacts}
                    disabled={matchingAll || !enrichReady || contacts.length === 0}
                    title={
                      !contacts.length
                        ? "No contacts to enrich"
                        : enrichReady
                          ? "Match all linked contacts (Apollo, then Prospeo)"
                          : "Enable Apollo or Prospeo in Settings"
                    }
                  >
                    {matchingAll ? <Spinner className="h-4 w-4" /> : <Icon.Sparkles width={18} height={18} />}
                    Match all contacts
                  </button>
                  <button
                    className="btn-secondary"
                    onClick={findPeople}
                    disabled={findingPeople || !apolloReady || !company.domain}
                    title={
                      !company.domain
                        ? "Add a domain first to find people"
                        : apolloReady
                          ? "Find new people at this company via Apollo (uses credits)"
                          : "Apollo is off — enable it in Settings"
                    }
                  >
                    {findingPeople ? <Spinner className="h-4 w-4" /> : <Icon.Users width={18} height={18} />}
                    Find people via Apollo
                  </button>
                </div>
                )}
              </div>
              {contacts.length === 0 ? (
                <p className="py-8 text-center text-sm text-ink-400">
                  No contacts linked yet. Use “Find people via Apollo” to discover them.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="border-b border-ink-100">
                      <tr>
                        <th className="table-th">Name</th>
                        <th className="table-th">Title</th>
                        <th className="table-th">Email</th>
                        <th className="table-th">Status</th>
                        <th className="table-th"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-100">
                      {contacts.map((ct) => (
                        <tr key={ct.id} className="hover:bg-ink-50/60">
                          <td className="table-td">
                            <div className="flex items-center gap-3">
                              {ct.photo_url ? (
                                <img src={ct.photo_url} alt="" className="h-8 w-8 rounded-full object-cover" />
                              ) : (
                                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-600">
                                  {(ct.first_name || ct.full_name || "?").charAt(0).toUpperCase()}
                                </div>
                              )}
                              <Link to={`/contacts/${ct.id}`} className="font-medium text-ink-900 hover:text-brand-600">
                                {ct.full_name || `${ct.first_name || ""} ${ct.last_name || ""}`.trim() || "—"}
                              </Link>
                            </div>
                          </td>
                          <td className="table-td">{ct.title || "—"}</td>
                          <td className="table-td">{ct.email || "—"}</td>
                          <td className="table-td"><StatusBadge status={ct.enrichment_status} /></td>
                          <td className="table-td text-right">
                            {isAdmin && (
                              <div className="flex items-center justify-end gap-1">
                                <button
                                  className="btn-ghost px-2 py-1 text-sm"
                                  onClick={() => matchContact(ct.id)}
                                  disabled={matchingId === ct.id || !enrichReady || !canMatchContact(ct)}
                                  title={
                                    !enrichReady
                                      ? "Enable Apollo or Prospeo in Settings"
                                      : !canMatchContact(ct)
                                        ? "Add email, name, or LinkedIn to match"
                                        : "Match via Apollo people/match"
                                  }
                                >
                                  {matchingId === ct.id ? (
                                    <Spinner className="h-4 w-4" />
                                  ) : (
                                    <Icon.Sparkles width={16} height={16} />
                                  )}
                                  Match
                                </button>
                                {ct.apollo_id && (
                                  <button
                                    className="btn-ghost px-2 py-1 text-sm"
                                    onClick={() => completePerson(ct.id)}
                                    disabled={completingId === ct.id || !apolloReady}
                                    title={apolloReady ? "Fetch full profile via Apollo" : "Apollo is off"}
                                  >
                                    {completingId === ct.id ? (
                                      <Spinner className="h-4 w-4" />
                                    ) : (
                                      <Icon.Sparkles width={16} height={16} />
                                    )}
                                    Full profile
                                  </button>
                                )}
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {tab === "apollo" && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm text-ink-600">
                <span className="text-ink-400">Apollo ID:</span>
                <code className="rounded bg-ink-100 px-2 py-0.5 text-xs">{company.apollo_id || "Not linked"}</code>
              </div>
              <div className="rounded-lg border border-ink-100 bg-ink-50/50 p-4">
                <p className="text-sm text-ink-600">
                  {company.apollo_id
                    ? "This company is linked to Apollo. Use 'Enrich via Apollo' to refresh its data."
                    : "This company hasn't been enriched via Apollo yet. Click 'Enrich via Apollo' to fetch additional data based on its domain or name."}
                </p>
              </div>
              <pre className="max-h-80 overflow-auto rounded-lg bg-ink-900 p-4 text-xs text-ink-100">
{JSON.stringify(
  {
    apollo_id: company.apollo_id,
    domain: company.domain,
    industry: company.industry,
    employee_count: company.employee_count,
    revenue: company.revenue,
    enrichment_status: company.enrichment_status,
  },
  null,
  2
)}
              </pre>
            </div>
          )}
        </div>
      </div>

      <Modal
        open={showEdit}
        onClose={() => setShowEdit(false)}
        title="Edit company"
        wide
        footer={
          <>
            <button className="btn-secondary" onClick={() => setShowEdit(false)}>Cancel</button>
            <button className="btn-primary" onClick={saveEdit} disabled={savingEdit}>
              {savingEdit && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
            </button>
          </>
        }
      >
        <form onSubmit={saveEdit} className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <Field label="Name *">
              <input className="input" required value={editForm.name || ""} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
            </Field>
          </div>
          <Field label="Domain"><input className="input" value={editForm.domain || ""} onChange={(e) => setEditForm({ ...editForm, domain: e.target.value })} /></Field>
          <Field label="Website"><input className="input" value={editForm.website || ""} onChange={(e) => setEditForm({ ...editForm, website: e.target.value })} /></Field>
          <Field label="LinkedIn"><input className="input" value={editForm.linkedin_url || ""} onChange={(e) => setEditForm({ ...editForm, linkedin_url: e.target.value })} /></Field>
          <Field label="Industry"><input className="input" value={editForm.industry || ""} onChange={(e) => setEditForm({ ...editForm, industry: e.target.value })} /></Field>
          <Field label="Employees"><input className="input" type="number" value={editForm.employee_count ?? ""} onChange={(e) => setEditForm({ ...editForm, employee_count: e.target.value })} /></Field>
          <Field label="Revenue"><input className="input" type="number" value={editForm.revenue ?? ""} onChange={(e) => setEditForm({ ...editForm, revenue: e.target.value })} /></Field>
          <Field label="Country"><input className="input" value={editForm.country || ""} onChange={(e) => setEditForm({ ...editForm, country: e.target.value })} /></Field>
          <Field label="City"><input className="input" value={editForm.city || ""} onChange={(e) => setEditForm({ ...editForm, city: e.target.value })} /></Field>
          <Field label="Phone"><input className="input" value={editForm.phone || ""} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} /></Field>
          <div className="col-span-2">
            <Field label="Description"><textarea className="input" rows={3} value={editForm.description || ""} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} /></Field>
          </div>
        </form>
      </Modal>
    </div>
  );
}
