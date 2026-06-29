import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api, { apiError } from "../api/client";
import ApolloFilterForm from "../components/ApolloFilterForm";
import { Icon } from "../components/icons";
import { CompanyLogo, EmptyState, Field, Modal, PageLoader, SourceBadge, Spinner, StatusBadge } from "../components/ui";
import {
  PEOPLE_CONTACT_FIELDS,
  buildCriteria,
  emptyFilters,
} from "../constants/apolloSearchFields";
import { useToast } from "../context/ToastContext";

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

export default function ResearchCompanyDetail() {
  const { searchId, resultId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [company, setCompany] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [tab, setTab] = useState("overview");
  const [apolloReady, setApolloReady] = useState(false);
  const [enriching, setEnriching] = useState(false);

  const [showContacts, setShowContacts] = useState(false);
  const [contactName, setContactName] = useState("");
  const [contactMaxRecords, setContactMaxRecords] = useState(500);
  const [contactFilters, setContactFilters] = useState(() => emptyFilters(PEOPLE_CONTACT_FIELDS));
  const [runningContacts, setRunningContacts] = useState(false);

  const load = useCallback(async () => {
    try {
      const [{ data }, contactsRes] = await Promise.all([
        api.get(`/research/searches/${searchId}/results/${resultId}`),
        api.get(`/research/searches/${searchId}/results/${resultId}/contacts`),
      ]);
      setCompany(data);
      setContacts(contactsRes.data.items || []);
    } catch (err) {
      toast.error(apiError(err));
      navigate(`/research/${searchId}`);
    }
  }, [searchId, resultId, navigate, toast]);

  const loadContacts = useCallback(async () => {
    setContactsLoading(true);
    try {
      const { data } = await api.get(`/research/searches/${searchId}/results/${resultId}/contacts`);
      setContacts(data.items || []);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setContactsLoading(false);
    }
  }, [searchId, resultId, toast]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (tab === "contacts") {
      loadContacts();
    }
  }, [tab, loadContacts]);

  useEffect(() => {
    api
      .get("/apollo/status")
      .then((res) => setApolloReady(res.data.enabled && res.data.configured))
      .catch(() => setApolloReady(false));
  }, []);

  const enrich = async () => {
    if (!confirm("Fetch complete company profile from Apollo? This may consume credits.")) return;
    setEnriching(true);
    try {
      await api.post(`/research/searches/${searchId}/results/${resultId}/enrich`);
      await load();
      toast.success("Company enriched.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setEnriching(false);
    }
  };

  const openContactsModal = () => {
    if (!company?.fields?.domain) {
      toast.info("This company has no domain to search contacts for.");
      return;
    }
    setContactName(`${company.fields.name || company.name || "Company"} — contacts`);
    setContactFilters(emptyFilters(PEOPLE_CONTACT_FIELDS));
    setShowContacts(true);
  };

  const runContactSearch = async (e) => {
    e?.preventDefault();
    if (!contactName.trim()) {
      toast.info("Give this contact search a name first.");
      return;
    }
    if (
      !confirm(
        `Search contacts at ${company.fields.domain} and save up to ${contactMaxRecords} records? People API Search does not consume credits.`
      )
    ) {
      return;
    }

    setRunningContacts(true);
    try {
      const { data: created } = await api.post(`/research/searches/${searchId}/results/${resultId}/people`, {
        name: contactName.trim(),
        criteria: buildCriteria(contactFilters, PEOPLE_CONTACT_FIELDS),
        max_records: Number(contactMaxRecords),
      });
      toast.success(
        `Captured ${created.result_count} contacts${created.total_available ? ` (of ${created.total_available} available)` : ""}.`
      );
      setShowContacts(false);
      await loadContacts();
      setTab("contacts");
      toast.success(
        `Captured ${created.result_count} contacts${created.total_available ? ` (of ${created.total_available} available)` : ""}. View them in the Contacts tab, or open the full research dataset.`,
      );
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setRunningContacts(false);
    }
  };

  if (!company) return <PageLoader />;

  const fields = company.fields || {};
  const website = fields.website || (fields.domain ? `https://${fields.domain}` : null);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link to={`/research/${searchId}`} className="btn-secondary px-2 py-2">
            <Icon.ChevronLeft width={18} height={18} />
          </Link>
          <CompanyLogo domain={fields.domain} name={fields.name || company.name} size={48} rounded="rounded-xl" />
          <div>
            <h1 className="text-xl font-semibold text-ink-900">{fields.name || company.name}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <StatusBadge status={company.enriched ? "enriched" : "none"} />
              <span className="text-xs text-ink-400">Market research · {company.search_name}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            className="btn-secondary"
            onClick={openContactsModal}
            disabled={!fields.domain || !apolloReady}
            title={fields.domain ? "Find contacts at this company" : "No domain available"}
          >
            <Icon.Users width={18} height={18} /> Find contacts
          </button>
          <button
            className="btn-primary"
            onClick={enrich}
            disabled={enriching || !apolloReady}
            title={apolloReady ? "Enrich via Apollo complete organization info" : "Enable Apollo in Settings"}
          >
            {enriching ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : <Icon.Sparkles width={18} height={18} />}
            Enrich via Apollo
          </button>
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
              <Detail label="Domain" value={fields.domain} href={fields.domain ? `https://${fields.domain}` : null} />
              <Detail label="Website" value={website} href={website} />
              <Detail label="LinkedIn" value={fields.linkedin_url} href={fields.linkedin_url} />
              <Detail label="Industry" value={fields.industry} />
              <Detail label="Employees" value={fields.employee_count?.toLocaleString?.() || fields.employee_count} />
              <Detail label="Revenue" value={fields.revenue ? `$${Number(fields.revenue).toLocaleString()}` : null} />
              <Detail label="Country" value={fields.country} />
              <Detail label="City" value={fields.city} />
              <Detail label="Phone" value={fields.phone} />
              <Detail label="Apollo ID" value={fields.apollo_id || company.apollo_id} />
            </dl>
          )}

          {tab === "contacts" && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-ink-500">
                  {contactsLoading
                    ? "Loading contacts…"
                    : contacts.length
                      ? `${contacts.length} contact(s) from prior research and CRM records at ${fields.domain || "this domain"}`
                      : fields.domain
                        ? `No contacts found yet for ${fields.domain}. Use “Find contacts” to search Apollo.`
                        : "No domain on this company — contacts cannot be matched."}
                </p>
                <button
                  className="btn-secondary"
                  onClick={openContactsModal}
                  disabled={!fields.domain || !apolloReady}
                  title={fields.domain ? "Find more contacts at this company" : "No domain available"}
                >
                  <Icon.Users width={18} height={18} /> Find contacts
                </button>
              </div>

              {contactsLoading ? (
                <div className="flex justify-center py-12">
                  <Spinner className="h-6 w-6" />
                </div>
              ) : contacts.length === 0 ? (
                <EmptyState
                  title="No contacts yet"
                  description={
                    fields.domain
                      ? "Run a contact search or check if matching CRM records exist for this domain."
                      : "Enrich this company first to get a domain, then search for contacts."
                  }
                  action={
                    fields.domain && apolloReady ? (
                      <button className="btn-primary" onClick={openContactsModal}>
                        <Icon.Search width={18} height={18} /> Find contacts
                      </button>
                    ) : null
                  }
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="border-b border-ink-100">
                      <tr>
                        <th className="table-th">Name</th>
                        <th className="table-th">Title</th>
                        <th className="table-th">Email</th>
                        <th className="table-th">Source</th>
                        <th className="table-th">Status</th>
                        <th className="table-th"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-100">
                      {contacts.map((ct) => (
                        <tr key={`${ct.source}-${ct.id}`} className="hover:bg-ink-50/60">
                          <td className="table-td font-medium text-ink-900">{ct.name || "—"}</td>
                          <td className="table-td">{ct.title || "—"}</td>
                          <td className="table-td">{ct.email || "—"}</td>
                          <td className="table-td">
                            {ct.source === "crm" ? (
                              <SourceBadge source={ct.contact_source || "manual"} />
                            ) : (
                              <span className="badge-mono border border-brand-200 bg-brand-50 text-brand-600">
                                RESEARCH
                              </span>
                            )}
                          </td>
                          <td className="table-td">
                            <StatusBadge
                              status={
                                ct.source === "crm"
                                  ? ct.enrichment_status || "none"
                                  : ct.enriched
                                    ? "enriched"
                                    : "none"
                              }
                            />
                          </td>
                          <td className="table-td text-right">
                            {ct.source === "crm" ? (
                              <Link to={`/contacts/${ct.id}`} className="btn-ghost px-2 py-1 text-sm">
                                Open
                              </Link>
                            ) : (
                              <Link
                                to={`/research/${ct.research_search_id}`}
                                className="btn-ghost px-2 py-1 text-sm"
                                title={ct.research_search_name || "People research"}
                              >
                                Open research
                              </Link>
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
            <pre className="max-h-[32rem] overflow-auto rounded-lg bg-ink-50 p-4 text-xs text-ink-700">
              {JSON.stringify(company.raw_data, null, 2)}
            </pre>
          )}
        </div>
      </div>

      {!fields.domain && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          No domain on this record — enrich via Apollo first, or contact search is not available.
        </div>
      )}

      <Modal
        open={showContacts}
        onClose={() => !runningContacts && setShowContacts(false)}
        title={`Find contacts at ${fields.name || company.name}`}
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
            Searches contacts only at <strong>{fields.domain}</strong>. Add filters to narrow by title, seniority,
            location, and more. Results are saved as a new people research dataset.
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
    </div>
  );
}
