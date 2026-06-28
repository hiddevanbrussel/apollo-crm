import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api, { apiError, isUnauthorized } from "../api/client";
import { Icon } from "../components/icons";
import { CompanyLogo, Field, Modal, PageLoader, SourceBadge, Spinner, StatusBadge } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";

function Detail({ label, value, href, icon: IconCmp }) {
  return (
    <div className="py-2.5">
      <dt className="flex items-center gap-1.5 text-xs font-medium text-ink-400">
        {IconCmp && <IconCmp width={13} height={13} />} {label}
      </dt>
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

const EDIT_FIELDS = [
  "first_name",
  "last_name",
  "full_name",
  "title",
  "title_ai",
  "email",
  "phone",
  "linkedin_url",
  "city",
  "country",
  "seniority",
  "department",
  "company_id",
];

export default function ContactDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { isAdmin } = useAuth();
  const [contact, setContact] = useState(null);
  const [enriching, setEnriching] = useState(false);
  const [enrichingProspeo, setEnrichingProspeo] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [apolloReady, setApolloReady] = useState(false);
  const [prospeoReady, setProspeoReady] = useState(false);
  const [groqReady, setGroqReady] = useState(false);
  const [normalizingTitle, setNormalizingTitle] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [companies, setCompanies] = useState([]);
  const [savingEdit, setSavingEdit] = useState(false);

  useEffect(() => {
    api
      .get("/settings/status")
      .then((res) => {
        setApolloReady(res.data.apollo?.enabled && res.data.apollo?.configured);
        setProspeoReady(res.data.prospeo?.enabled && res.data.prospeo?.configured);
        setGroqReady(res.data.groq?.enabled && res.data.groq?.configured);
      })
      .catch(() => {
        setApolloReady(false);
        setProspeoReady(false);
      });
  }, []);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/contacts/${id}`);
      setContact(data);
    } catch (err) {
      if (!isUnauthorized(err)) {
        toast.error(apiError(err));
      }
      navigate("/contacts");
    }
  }, [id, navigate, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const enrich = async () => {
    setEnriching(true);
    try {
      const { data } = await api.post(`/contacts/${id}/enrich`);
      setContact(data);
      const provider = data.source === "prospeo" ? "Prospeo" : "Apollo";
      toast.success(
        data.enrichment_status === "pending"
          ? "Contact matched. Waterfall email enrichment is in progress — results arrive in a few minutes."
          : `Contact enriched via ${provider}.`,
      );
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setEnriching(false);
    }
  };

  const enrichProspeo = async () => {
    setEnrichingProspeo(true);
    try {
      const { data } = await api.post(`/contacts/${id}/enrich-prospeo`);
      setContact(data);
      toast.success("Contact enriched via Prospeo.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setEnrichingProspeo(false);
    }
  };

  const completeInfo = async () => {
    setCompleting(true);
    try {
      const { data } = await api.post(`/contacts/${id}/complete`);
      setContact(data);
      toast.success("Fetched complete info via Apollo.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setCompleting(false);
    }
  };

  const normalizeTitle = async () => {
    setNormalizingTitle(true);
    try {
      const { data } = await api.post(`/contacts/${id}/normalize-title`);
      setContact(data);
      toast.success(data.title_ai ? `Title AI: ${data.title_ai}` : "Title normalized.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setNormalizingTitle(false);
    }
  };

  const openEdit = async () => {
    const initial = {};
    EDIT_FIELDS.forEach((f) => {
      if (f === "company_id") {
        initial[f] = contact.company_id ? String(contact.company_id) : "";
      } else {
        initial[f] = contact[f] ?? "";
      }
    });
    setEditForm(initial);
    setShowEdit(true);
    try {
      const { data } = await api.get("/companies", { params: { page_size: 200 } });
      const list = data.items || [];
      if (contact.company && !list.some((c) => c.id === contact.company.id)) {
        list.unshift({ id: contact.company.id, name: contact.company.name });
      }
      setCompanies(list);
    } catch {
      setCompanies(contact.company ? [{ id: contact.company.id, name: contact.company.name }] : []);
    }
  };

  const saveEdit = async (e) => {
    e?.preventDefault();
    setSavingEdit(true);
    try {
      const payload = {};
      EDIT_FIELDS.forEach((f) => {
        if (f === "company_id") {
          payload.company_id = editForm.company_id ? Number(editForm.company_id) : null;
        } else {
          payload[f] = editForm[f] === "" ? null : editForm[f];
        }
      });
      const { data } = await api.put(`/contacts/${id}`, payload);
      setContact(data);
      setShowEdit(false);
      toast.success("Contact updated.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSavingEdit(false);
    }
  };

  if (!contact) return <PageLoader />;

  const name = contact.full_name || `${contact.first_name || ""} ${contact.last_name || ""}`.trim() || "Unknown";
  const initials = name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  const canMatch =
    Boolean(contact.apollo_id) ||
    Boolean(contact.prospeo_id) ||
    Boolean(contact.email?.trim()) ||
    Boolean(contact.linkedin_url?.trim()) ||
    Boolean(contact.full_name?.trim()) ||
    Boolean(contact.first_name?.trim() && contact.last_name?.trim());
  const enrichReady = apolloReady || prospeoReady;
  const employment = Array.isArray(contact.apollo_data?.employment_history)
    ? contact.apollo_data.employment_history
    : [];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link to="/contacts" className="btn-secondary px-2 py-2">
            <Icon.ChevronLeft width={18} height={18} />
          </Link>
          {contact.photo_url ? (
            <img src={contact.photo_url} alt="" className="h-12 w-12 rounded-full object-cover" />
          ) : (
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-sm font-semibold text-brand-600">
              {initials}
            </div>
          )}
          <div>
            <h1 className="text-xl font-semibold text-ink-900">{name}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span className="text-sm text-ink-500">{contact.title || "—"}</span>
              {contact.title_ai && contact.title_ai !== contact.title && (
                <span className="text-sm text-brand-600" title="AI-normalized title">
                  → {contact.title_ai}
                </span>
              )}
              <StatusBadge status={contact.enrichment_status} />
              <SourceBadge source={contact.source} />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={openEdit}>
            <Icon.Edit width={18} height={18} /> Edit
          </button>
          {isAdmin && contact.apollo_id && (
            <button
              className="btn-secondary"
              onClick={completeInfo}
              disabled={completing || !apolloReady}
              title={
                apolloReady
                  ? "Full profile via GET /people/{id} — requires an Apollo ID from Match or Find people"
                  : "Apollo is off — enable it in Settings"
              }
            >
              {completing ? <Spinner className="h-4 w-4" /> : <Icon.Sparkles width={18} height={18} />}
              {contact.enrichment_status === "enriched" ? "Refresh profile" : "Full profile"}
            </button>
          )}
          {isAdmin && (
          <button
            className="btn-secondary"
            onClick={enrichProspeo}
            disabled={enrichingProspeo || !prospeoReady || !canMatch}
            title={
              !prospeoReady
                ? "Prospeo is off — enable it in Settings"
                : !canMatch
                  ? "Add an email, name + company, or LinkedIn URL to enrich via Prospeo"
                  : "Enrich via Prospeo enrich-person"
            }
          >
            {enrichingProspeo ? <Spinner className="h-4 w-4" /> : <Icon.Sparkles width={18} height={18} />}
            Match via Prospeo
          </button>
          )}
          {isAdmin && (
          <button
            className="btn-secondary"
            onClick={normalizeTitle}
            disabled={normalizingTitle || !groqReady || !contact.title?.trim()}
            title={
              !groqReady
                ? "Groq is off — enable it in Settings"
                : !contact.title?.trim()
                  ? "Contact has no title to normalize"
                  : "Generate a uniform title via Groq AI (keeps original title)"
            }
          >
            {normalizingTitle ? <Spinner className="h-4 w-4" /> : <Icon.Bolt width={18} height={18} />}
            Title AI
          </button>
          )}
          {isAdmin && (
          <button
            className="btn-primary"
            onClick={enrich}
            disabled={enriching || !enrichReady || !canMatch}
            title={
              !enrichReady
                ? "Enable Apollo or Prospeo in Settings"
                : !canMatch
                  ? "Add an email, name, or LinkedIn URL to match"
                  : "Try Apollo first, then Prospeo if no match is found"
            }
          >
            {enriching ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : <Icon.Sparkles width={18} height={18} />}
            Match contact
          </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="card p-5 lg:col-span-2">
          <h2 className="mb-2 text-sm font-semibold text-ink-900">Details</h2>
          <dl className="grid grid-cols-1 gap-x-8 sm:grid-cols-2">
            <Detail label="Title (original)" value={contact.title} />
            <Detail label="Title AI" value={contact.title_ai} />
            <Detail label="Email" value={contact.email} href={contact.email ? `mailto:${contact.email}` : null} icon={Icon.Mail} />
            <Detail label="Email status" value={contact.email_status} />
            <Detail label="Phone" value={contact.phone} href={contact.phone ? `tel:${contact.phone}` : null} icon={Icon.Phone} />
            <Detail label="LinkedIn" value={contact.linkedin_url} href={contact.linkedin_url} />
            <Detail label="Seniority" value={contact.seniority} />
            <Detail label="Department" value={contact.department} />
            <Detail label="City" value={contact.city} />
            <Detail label="Country" value={contact.country} />
            <Detail label="Apollo ID" value={contact.apollo_id} />
            <Detail label="Prospeo ID" value={contact.prospeo_id} />
            <div className="sm:col-span-2">
              <Detail label="Headline" value={contact.headline} />
            </div>
          </dl>

          {employment.length > 0 && (
            <div className="mt-5 border-t border-ink-100 pt-4">
              <h3 className="mb-2 text-sm font-semibold text-ink-900">Employment history</h3>
              <ul className="space-y-2">
                {employment.map((job, i) => (
                  <li key={job.id || job._id || i} className="flex items-start justify-between gap-3 text-sm">
                    <div>
                      <p className="font-medium text-ink-800">{job.title || "—"}</p>
                      <p className="text-ink-500">{job.organization_name || "—"}</p>
                    </div>
                    <span className="whitespace-nowrap text-xs text-ink-400">
                      {(job.start_date || "").slice(0, 4) || "?"}
                      {" – "}
                      {job.current ? "Present" : (job.end_date || "").slice(0, 4) || "?"}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {contact.apollo_data && Object.keys(contact.apollo_data).length > 0 && (
            <details className="mt-5 border-t border-ink-100 pt-4">
              <summary className="cursor-pointer text-sm font-semibold text-ink-700">
                {contact.source === "import" ? "Import extra data" : "Raw Apollo data"}
              </summary>
              {contact.apollo_data.raw && (
                <div className="mt-3">
                  <p className="mb-1 text-xs font-medium text-ink-500">Search / match API responses</p>
                  <pre className="max-h-96 overflow-auto rounded-lg bg-ink-900 p-4 text-xs text-ink-100">
{JSON.stringify(contact.apollo_data.raw, null, 2)}
                  </pre>
                </div>
              )}
              <pre className="mt-3 max-h-96 overflow-auto rounded-lg bg-ink-900 p-4 text-xs text-ink-100">
{JSON.stringify(
  contact.source === "import"
    ? contact.apollo_data.import_extra || contact.apollo_data
    : Object.fromEntries(
        Object.entries(contact.apollo_data).filter(([key]) => !["raw"].includes(key)),
      ),
  null,
  2,
)}
              </pre>
            </details>
          )}

          {contact.prospeo_data && Object.keys(contact.prospeo_data).length > 0 && (
            <details className="mt-5 border-t border-ink-100 pt-4">
              <summary className="cursor-pointer text-sm font-semibold text-ink-700">Raw Prospeo data</summary>
              {contact.prospeo_data.raw && (
                <div className="mt-3">
                  <p className="mb-1 text-xs font-medium text-ink-500">Search / enrich API responses</p>
                  <pre className="max-h-96 overflow-auto rounded-lg bg-ink-900 p-4 text-xs text-ink-100">
{JSON.stringify(contact.prospeo_data.raw, null, 2)}
                  </pre>
                </div>
              )}
              <pre className="mt-3 max-h-96 overflow-auto rounded-lg bg-ink-900 p-4 text-xs text-ink-100">
{JSON.stringify(
  Object.fromEntries(Object.entries(contact.prospeo_data).filter(([key]) => key !== "raw")),
  null,
  2,
)}
              </pre>
            </details>
          )}
        </div>

        <div className="card p-5">
          <h2 className="mb-2 text-sm font-semibold text-ink-900">Company</h2>
          {contact.company ? (
            <Link
              to={`/companies/${contact.company.id}`}
              className="flex items-center gap-3 rounded-lg border border-ink-100 p-3 hover:bg-ink-50"
            >
              <CompanyLogo domain={contact.company.domain} name={contact.company.name} size={40} />
              <div>
                <p className="text-sm font-medium text-ink-900">{contact.company.name}</p>
                <p className="text-xs text-ink-400">{contact.company.domain || "—"}</p>
              </div>
            </Link>
          ) : (
            <p className="text-sm text-ink-400">Not linked to a company.</p>
          )}
        </div>
      </div>

      <Modal
        open={showEdit}
        onClose={() => setShowEdit(false)}
        title="Edit contact"
        wide
        footer={
          <>
            <button className="btn-secondary" type="button" onClick={() => setShowEdit(false)}>
              Cancel
            </button>
            <button className="btn-primary" onClick={saveEdit} disabled={savingEdit}>
              {savingEdit && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
            </button>
          </>
        }
      >
        <form onSubmit={saveEdit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="First name">
            <input
              className="input"
              value={editForm.first_name || ""}
              onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
            />
          </Field>
          <Field label="Last name">
            <input
              className="input"
              value={editForm.last_name || ""}
              onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Full name">
              <input
                className="input"
                value={editForm.full_name || ""}
                onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                placeholder="Optional if first and last name are set"
              />
            </Field>
          </div>
          <Field label="Title">
            <input
              className="input"
              value={editForm.title || ""}
              onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
            />
          </Field>
          <Field label="Title AI">
            <input
              className="input"
              value={editForm.title_ai || ""}
              onChange={(e) => setEditForm({ ...editForm, title_ai: e.target.value })}
              placeholder="Normalized title (optional)"
            />
          </Field>
          <Field label="Email">
            <input
              className="input"
              type="email"
              value={editForm.email || ""}
              onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
            />
          </Field>
          <Field label="Phone">
            <input
              className="input"
              value={editForm.phone || ""}
              onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
            />
          </Field>
          <Field label="LinkedIn">
            <input
              className="input"
              value={editForm.linkedin_url || ""}
              onChange={(e) => setEditForm({ ...editForm, linkedin_url: e.target.value })}
            />
          </Field>
          <Field label="City">
            <input
              className="input"
              value={editForm.city || ""}
              onChange={(e) => setEditForm({ ...editForm, city: e.target.value })}
            />
          </Field>
          <Field label="Country">
            <input
              className="input"
              value={editForm.country || ""}
              onChange={(e) => setEditForm({ ...editForm, country: e.target.value })}
            />
          </Field>
          <Field label="Seniority">
            <input
              className="input"
              value={editForm.seniority || ""}
              onChange={(e) => setEditForm({ ...editForm, seniority: e.target.value })}
            />
          </Field>
          <Field label="Department">
            <input
              className="input"
              value={editForm.department || ""}
              onChange={(e) => setEditForm({ ...editForm, department: e.target.value })}
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Company">
              <select
                className="input"
                value={editForm.company_id || ""}
                onChange={(e) => setEditForm({ ...editForm, company_id: e.target.value })}
              >
                <option value="">No company</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        </form>
      </Modal>
    </div>
  );
}
