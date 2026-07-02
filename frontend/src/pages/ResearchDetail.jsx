import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api, { apiError } from "../api/client";
import ApolloFilterForm from "../components/ApolloFilterForm";
import { Icon } from "../components/icons";
import { CompanyLogo, ActionMenu, ActionMenuItem, EmptyState, Field, IconLink, Modal, PageLoader, Pagination, Spinner, StatusBadge, normalizeExternalHref } from "../components/ui";
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

  if (column.key === "website") {
    const href = normalizeExternalHref(value);
    return (
      <IconLink href={href} label={String(value)}>
        <Icon.Globe width={18} height={18} />
      </IconLink>
    );
  }

  if (column.key === "linkedin_url") {
    const href = normalizeExternalHref(value, "linkedin");
    return (
      <IconLink href={href} label={String(value)}>
        <Icon.LinkedIn width={18} height={18} />
      </IconLink>
    );
  }

  return String(value);
}

const PAGE_SIZE_OPTIONS = [20, 30, 40, 50, 100];

export default function ResearchDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

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
  const [editingCompanyId, setEditingCompanyId] = useState(null);
  const emptyCompanyForm = () => ({
    name: "",
    domain: "",
    country: "",
    industry: "",
    city: "",
    website: "",
    linkedin_url: "",
  });
  const [companyForm, setCompanyForm] = useState(emptyCompanyForm);
  const [savingCompany, setSavingCompany] = useState(false);
  const [importing, setImporting] = useState(false);
  const [childSearches, setChildSearches] = useState([]);
  const [loadingChildren, setLoadingChildren] = useState(false);

  const [showContactDataset, setShowContactDataset] = useState(false);
  const [contactDatasetName, setContactDatasetName] = useState("");
  const [creatingContactDataset, setCreatingContactDataset] = useState(false);

  const [companyOptions, setCompanyOptions] = useState([]);
  const [showAddContact, setShowAddContact] = useState(false);
  const [editingContactId, setEditingContactId] = useState(null);
  const emptyContactForm = () => ({
    name: "",
    company_result_id: "",
    title: "",
    email: "",
    phone: "",
    linkedin_url: "",
  });
  const [contactForm, setContactForm] = useState(emptyContactForm);
  const [savingContact, setSavingContact] = useState(false);

  const [showImportVault, setShowImportVault] = useState(false);
  const [importCompanyId, setImportCompanyId] = useState("");
  const [vaultContacts, setVaultContacts] = useState([]);
  const [loadingVaultContacts, setLoadingVaultContacts] = useState(false);
  const [selectedVault, setSelectedVault] = useState(new Set());
  const [importingVault, setImportingVault] = useState(false);

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
  }, [id, page, pageSize, toast]);

  const handlePageSize = (size) => {
    setPage(1);
    setPageSize(size);
  };

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!id) return;
    setLoadingChildren(true);
    api
      .get(`/research/searches/${id}/children`)
      .then((res) => setChildSearches(res.data.items || []))
      .catch(() => setChildSearches([]))
      .finally(() => setLoadingChildren(false));
  }, [id, data?.search?.updated_at]);

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
    const s = data?.search;
    const isContactList = s?.query_type === "people" && s?.criteria?._source_search_id;
    const msg = isContactList
      ? `Delete contact recordset "${s?.name}"? Contacts remain linked to their companies — only this list is removed.`
      : `Delete research "${s?.name}"? This cannot be undone.`;
    if (!confirm(msg)) return;
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
      setContactName("");
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
        `Captured ${created.result_count} contacts${created.total_available ? ` (of ${created.total_available} available)` : ""}${
          created.criteria?._already_at_company_count
            ? ` · ${created.criteria._already_at_company_count} already at company`
            : ""
        }.`
      );
      setShowContacts(false);
      load();
      api.get(`/research/searches/${id}/children`).then((res) => setChildSearches(res.data.items || []));
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

  const openAddCompany = () => {
    setEditingCompanyId(null);
    setCompanyForm(emptyCompanyForm());
    setShowAddCompany(true);
  };

  const openEditCompany = (row) => {
    setEditingCompanyId(row.id);
    setCompanyForm({
      name: row.name || "",
      domain: row.domain || "",
      country: row.country || "",
      industry: row.industry || "",
      city: row.city || "",
      website: row.website || "",
      linkedin_url: row.linkedin_url || "",
    });
    setShowAddCompany(true);
  };

  const closeCompanyModal = () => {
    if (savingCompany) return;
    setShowAddCompany(false);
    setEditingCompanyId(null);
    setCompanyForm(emptyCompanyForm());
  };

  const saveCompany = async (e) => {
    e?.preventDefault();
    if (!companyForm.name.trim()) {
      toast.info("Company name is required.");
      return;
    }
    setSavingCompany(true);
    try {
      const payload = {
        name: companyForm.name.trim(),
        domain: companyForm.domain || null,
        website: companyForm.website || null,
        industry: companyForm.industry || null,
        country: companyForm.country || null,
        city: companyForm.city || null,
        linkedin_url: companyForm.linkedin_url || null,
      };
      if (editingCompanyId) {
        await api.patch(`/research/searches/${id}/results/${editingCompanyId}`, payload);
        toast.success("Company updated.");
      } else {
        await api.post(`/research/searches/${id}/results`, payload);
        toast.success("Company added.");
        setPage(1);
      }
      setShowAddCompany(false);
      setEditingCompanyId(null);
      setCompanyForm(emptyCompanyForm());
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
    if (!confirm("Remove this record from the dataset? Contacts stay linked to the company.")) return;
    try {
      await api.delete(`/research/searches/${id}/results/${rowId}`);
      toast.success("Record removed.");
      load();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const createContactDataset = async (e) => {
    e?.preventDefault();
    if (!contactDatasetName.trim()) {
      toast.info("Give your contact recordset a name first.");
      return;
    }
    setCreatingContactDataset(true);
    try {
      const { data } = await api.post(`/research/searches/${id}/contact-datasets`, {
        name: contactDatasetName.trim(),
      });
      toast.success("Empty contact recordset created.");
      setShowContactDataset(false);
      setContactDatasetName("");
      api.get(`/research/searches/${id}/children`).then((res) => setChildSearches(res.data.items || []));
      navigate(`/research/${data.id}`);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setCreatingContactDataset(false);
    }
  };

  const loadCompanyOptions = async (parentSearchId) => {
    try {
      const { data } = await api.get(`/research/searches/${parentSearchId}/company-options`);
      setCompanyOptions(data.items || []);
    } catch {
      setCompanyOptions([]);
    }
  };

  const openAddContact = () => {
    setEditingContactId(null);
    setContactForm(emptyContactForm());
    if (sourceSearchId) loadCompanyOptions(sourceSearchId);
    setShowAddContact(true);
  };

  const openEditContact = (row) => {
    setEditingContactId(row.id);
    setContactForm({
      name: row.name || "",
      company_result_id: String(row.raw_data?._source_company_result_id || row.company_result_id || ""),
      title: row.title || "",
      email: row.email || "",
      phone: row.phone || "",
      linkedin_url: row.linkedin_url || "",
    });
    if (sourceSearchId) loadCompanyOptions(sourceSearchId);
    setShowAddContact(true);
  };

  const closeContactModal = () => {
    if (savingContact) return;
    setShowAddContact(false);
    setEditingContactId(null);
    setContactForm(emptyContactForm());
  };

  const saveContact = async (e) => {
    e?.preventDefault();
    if (!contactForm.name.trim()) {
      toast.info("Contact name is required.");
      return;
    }
    if (!contactForm.company_result_id) {
      toast.info("Select a company from the recordset.");
      return;
    }
    setSavingContact(true);
    try {
      const payload = {
        name: contactForm.name.trim(),
        company_result_id: Number(contactForm.company_result_id),
        title: contactForm.title || null,
        email: contactForm.email || null,
        phone: contactForm.phone || null,
        linkedin_url: contactForm.linkedin_url || null,
      };
      if (editingContactId) {
        await api.patch(`/research/searches/${id}/contacts/${editingContactId}`, payload);
        toast.success("Contact updated.");
      } else {
        await api.post(`/research/searches/${id}/contacts`, payload);
        toast.success("Contact added.");
        setPage(1);
      }
      setShowAddContact(false);
      setEditingContactId(null);
      setContactForm(emptyContactForm());
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setSavingContact(false);
    }
  };

  const openImportVault = () => {
    const parentId = data?.search?.criteria?._source_search_id;
    setImportCompanyId("");
    setVaultContacts([]);
    setSelectedVault(new Set());
    if (parentId) loadCompanyOptions(parentId);
    setShowImportVault(true);
  };

  const loadVaultContactsForCompany = async (companyId, parentId = data?.search?.criteria?._source_search_id) => {
    if (!companyId || !parentId) {
      setVaultContacts([]);
      return;
    }
    setLoadingVaultContacts(true);
    try {
      const { data: res } = await api.get(
        `/research/searches/${parentId}/results/${companyId}/contacts`
      );
      const items = (res.items || []).filter((ct) => ct.source === "research" && ct.vault_id);
      setVaultContacts(items);
      setSelectedVault(new Set());
    } catch (err) {
      toast.error(apiError(err));
      setVaultContacts([]);
    } finally {
      setLoadingVaultContacts(false);
    }
  };

  const toggleVaultContact = (vaultId) =>
    setSelectedVault((prev) => {
      const next = new Set(prev);
      next.has(vaultId) ? next.delete(vaultId) : next.add(vaultId);
      return next;
    });

  const importFromVault = async (e) => {
    e?.preventDefault();
    const vaultIds = [...selectedVault];
    if (!vaultIds.length) {
      toast.info("Select at least one contact.");
      return;
    }
    setImportingVault(true);
    try {
      const { data } = await api.post(`/research/searches/${id}/contacts/from-vault`, {
        vault_ids: vaultIds,
      });
      toast.success(`${data.added} added${data.skipped ? `, ${data.skipped} skipped` : ""}.`);
      setShowImportVault(false);
      setPage(1);
      load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setImportingVault(false);
    }
  };

  const search = data?.search;
  const isOrg = search?.query_type === "organizations";
  const isManualDataset = search?.criteria?._dataset_source === "manual";
  const sourceSearchId = search?.criteria?._source_search_id;
  const isGroqCompanyDataset = isOrg && search?.criteria?._dataset_source === "groq";
  const isManualContactDataset = !isOrg && isManualDataset && !!sourceSearchId;
  const isManualCompanyDataset = isOrg && (isManualDataset || isGroqCompanyDataset);
  const columns = isOrg ? ORG_COLUMNS : PEOPLE_COLUMNS;
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
            {isManualContactDataset
              ? "Manual contact list"
              : isManualCompanyDataset
                ? "Manual company list"
                : isOrg
                  ? "Companies"
                  : "People"}{" "}
            · {search?.result_count ?? 0} records captured
            {search?.total_available ? ` of ${search.total_available} available` : ""}
          </p>
          {sourceSearchId ? (
            <p className="mt-1 text-sm text-ink-500">
              {isManualContactDataset ? "Contact list from recordset" : "Contact search from recordset"}{" "}
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
          {isManualCompanyDataset && (
            <>
              <button className="btn-secondary" onClick={openAddCompany}>
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
            <button className="btn-secondary" onClick={() => setShowContactDataset(true)}>
              <Icon.Plus width={18} height={18} /> New contact list
            </button>
          )}
          {isManualContactDataset && (
            <>
              <button className="btn-primary" onClick={openAddContact}>
                <Icon.Plus width={18} height={18} /> Add contact
              </button>
              <button className="btn-secondary" onClick={openImportVault}>
                <Icon.Download width={18} height={18} /> Import from company
              </button>
            </>
          )}
          {isOrg ? (
            <ActionMenu
              trigger={
                <>
                  <Icon.Sparkles width={18} height={18} />
                  AI
                  <Icon.ChevronDown width={14} height={14} className="opacity-60" />
                </>
              }
            >
              <ActionMenuItem icon={<Icon.Users width={16} height={16} />} onClick={openContactsModal}>
                Find contacts
              </ActionMenuItem>
              <ActionMenuItem
                icon={enriching ? <Spinner className="h-4 w-4" /> : <Icon.Bolt width={16} height={16} />}
                disabled={enriching || !apolloReady}
                onClick={enrichAllUnenriched}
              >
                Enrich all
              </ActionMenuItem>
            </ActionMenu>
          ) : (
            <button
              className="btn-secondary"
              onClick={enrichAllUnenriched}
              disabled={enriching || !apolloReady}
              title={apolloReady ? undefined : "Enable Apollo in Settings to enrich."}
            >
              {enriching ? <Spinner className="h-4 w-4" /> : <Icon.Bolt width={18} height={18} />}
              Enrich all
            </button>
          )}
          <ActionMenu
            trigger={
              <>
                <Icon.Download width={18} height={18} />
                Export
                <Icon.ChevronDown width={14} height={14} className="opacity-60" />
              </>
            }
          >
            <ActionMenuItem icon={<Icon.Download width={16} height={16} />} onClick={() => exportSearch("csv")}>
              CSV
            </ActionMenuItem>
            <ActionMenuItem icon={<Icon.Download width={16} height={16} />} onClick={() => exportSearch("xlsx")}>
              Excel
            </ActionMenuItem>
          </ActionMenu>
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
              isManualContactDataset
                ? "Add contacts manually and link each one to a company from the parent recordset."
                : isManualCompanyDataset
                  ? "Add companies manually or import a CSV/Excel file to get started."
                  : "This research dataset is empty."
            }
            action={
              isManualContactDataset ? (
                <button className="btn-primary" onClick={openAddContact}>
                  <Icon.Plus width={18} height={18} /> Add contact
                </button>
              ) : isManualCompanyDataset ? (
                <div className="flex flex-wrap justify-center gap-2">
                  <button className="btn-primary" onClick={openAddCompany}>
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
                        <div className="flex flex-wrap items-center gap-1">
                          <StatusBadge status={row.enriched ? "enriched" : "none"} />
                          {!isOrg && row.already_at_company ? (
                            <span className="badge bg-amber-50 text-amber-700">Al bij bedrijf</span>
                          ) : null}
                        </div>
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
                          {isManualCompanyDataset && (
                            <button
                              className="btn-ghost px-2 py-1 text-sm"
                              onClick={() => openEditCompany(row)}
                              title="Edit company"
                            >
                              <Icon.Edit width={15} height={15} />
                            </button>
                          )}
                          {isManualContactDataset && (
                            <button
                              className="btn-ghost px-2 py-1 text-sm"
                              onClick={() => openEditContact(row)}
                              title="Edit contact"
                            >
                              <Icon.Edit width={15} height={15} />
                            </button>
                          )}
                          {(isManualCompanyDataset || isManualContactDataset) && (
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
              <Pagination
                page={page}
                pageSize={pageSize}
                total={data.total}
                onPage={setPage}
                pageSizeOptions={PAGE_SIZE_OPTIONS}
                onPageSize={handlePageSize}
              />
            </div>
          </>
        )}
      </div>

      {isOrg ? (
        <div className="card">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-ink-100 px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-ink-900">Contact recordsets</h2>
              <p className="mt-0.5 text-xs text-ink-500">
                Named contact lists linked to this company recordset. Deleting a list does not remove contacts from
                companies.
              </p>
            </div>
            <button className="btn-secondary text-sm" onClick={() => setShowContactDataset(true)}>
              <Icon.Plus width={16} height={16} /> New contact list
            </button>
          </div>
          {loadingChildren ? (
            <div className="flex justify-center py-8">
              <Spinner className="h-5 w-5" />
            </div>
          ) : childSearches.length === 0 ? (
            <div className="px-5 py-8 text-center text-sm text-ink-500">
              No contact lists yet. Create an empty list to add contacts manually, or use Find contacts for an Apollo
              search.
            </div>
          ) : (
            <div className="divide-y divide-ink-100">
              {childSearches.map((child) => (
                <div key={child.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                  <div className="min-w-0">
                    <Link to={`/research/${child.id}`} className="font-medium text-ink-900 hover:text-brand-600">
                      {child.name}
                    </Link>
                    <p className="text-xs text-ink-500">
                      {child.result_count} contacts · {new Date(child.created_at).toLocaleString()}
                      {child.criteria?._dataset_source === "manual" ? " · Manual" : ""}
                    </p>
                  </div>
                  <Link to={`/research/${child.id}`} className="btn-secondary text-sm">
                    <Icon.Users width={16} height={16} /> View contacts
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}

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
            Searches contacts at the <strong>{domainInfo?.domainCount ?? 0}</strong> domains from this company
            research ({domainInfo?.companyCount ?? 0} companies). Contacts are saved on each company; the recordset is
            a named view of those results.
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field
              label="Contact recordset name *"
              hint="This name appears in your saved research list under this company recordset."
            >
              <input
                className="input"
                required
                placeholder="e.g. Marketing directors Q3"
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
              />
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

          <ApolloFilterForm
            fields={PEOPLE_CONTACT_FIELDS}
            values={contactFilters}
            onChange={(key, value) => setContactFilters((prev) => ({ ...prev, [key]: value }))}
          />
        </form>
      </Modal>

      <Modal
        open={showAddCompany}
        onClose={closeCompanyModal}
        title={editingCompanyId ? "Edit company" : "Add company"}
        footer={
          <>
            <button className="btn-secondary" onClick={closeCompanyModal} disabled={savingCompany}>
              Cancel
            </button>
            <button className="btn-primary" onClick={saveCompany} disabled={savingCompany}>
              {savingCompany && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
            </button>
          </>
        }
      >
        <form onSubmit={saveCompany} className="grid grid-cols-2 gap-4">
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

      <Modal
        open={showContactDataset}
        onClose={() => !creatingContactDataset && setShowContactDataset(false)}
        title="New contact list"
        footer={
          <>
            <button className="btn-secondary" onClick={() => setShowContactDataset(false)} disabled={creatingContactDataset}>
              Cancel
            </button>
            <button className="btn-primary" onClick={createContactDataset} disabled={creatingContactDataset}>
              {creatingContactDataset ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : <Icon.Plus width={18} height={18} />}
              Create list
            </button>
          </>
        }
      >
        <form onSubmit={createContactDataset} className="space-y-4">
          <p className="text-sm text-ink-600">
            Create an empty contact recordset linked to this company list. Add contacts manually without running a new
            Apollo search each time.
          </p>
          <Field label="Contact list name *" hint="Shown under this company recordset in Market Research.">
            <input
              className="input"
              required
              placeholder="e.g. Decision makers — manual"
              value={contactDatasetName}
              onChange={(e) => setContactDatasetName(e.target.value)}
            />
          </Field>
        </form>
      </Modal>

      <Modal
        open={showAddContact}
        onClose={closeContactModal}
        title={editingContactId ? "Edit contact" : "Add contact"}
        footer={
          <>
            <button className="btn-secondary" onClick={closeContactModal} disabled={savingContact}>
              Cancel
            </button>
            <button className="btn-primary" onClick={saveContact} disabled={savingContact}>
              {savingContact ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : null}
              {editingContactId ? "Save changes" : "Add contact"}
            </button>
          </>
        }
      >
        <form onSubmit={saveContact} className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <Field label="Company from recordset *">
              <select
                className="input"
                required
                value={contactForm.company_result_id}
                onChange={(e) => setContactForm({ ...contactForm, company_result_id: e.target.value })}
              >
                <option value="">Select company…</option>
                {companyOptions.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.name}
                    {opt.domain ? ` (${opt.domain})` : ""}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div className="col-span-2">
            <Field label="Name *">
              <input
                className="input"
                required
                value={contactForm.name}
                onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
              />
            </Field>
          </div>
          <Field label="Title">
            <input
              className="input"
              value={contactForm.title}
              onChange={(e) => setContactForm({ ...contactForm, title: e.target.value })}
            />
          </Field>
          <Field label="Email">
            <input
              className="input"
              type="email"
              value={contactForm.email}
              onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
            />
          </Field>
          <Field label="Phone">
            <input
              className="input"
              value={contactForm.phone}
              onChange={(e) => setContactForm({ ...contactForm, phone: e.target.value })}
            />
          </Field>
          <Field label="LinkedIn">
            <input
              className="input"
              placeholder="https://linkedin.com/in/…"
              value={contactForm.linkedin_url}
              onChange={(e) => setContactForm({ ...contactForm, linkedin_url: e.target.value })}
            />
          </Field>
        </form>
      </Modal>

      <Modal
        open={showImportVault}
        onClose={() => !importingVault && setShowImportVault(false)}
        title="Import from company contacts"
        wide
        footer={
          <>
            <button className="btn-secondary" onClick={() => setShowImportVault(false)} disabled={importingVault}>
              Cancel
            </button>
            <button className="btn-primary" onClick={importFromVault} disabled={importingVault || selectedVault.size === 0}>
              {importingVault ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : null}
              Import {selectedVault.size || ""} contact{selectedVault.size === 1 ? "" : "s"}
            </button>
          </>
        }
      >
        <form onSubmit={importFromVault} className="space-y-4">
          <p className="text-sm text-ink-600">
            Pick contacts already saved on a company. Contact recordsets are views — the company keeps the master list.
          </p>
          <Field label="Company *">
            <select
              className="input"
              required
              value={importCompanyId}
              onChange={(e) => {
                setImportCompanyId(e.target.value);
                loadVaultContactsForCompany(e.target.value);
              }}
            >
              <option value="">Select company…</option>
              {companyOptions.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.name}
                  {opt.domain ? ` (${opt.domain})` : ""}
                </option>
              ))}
            </select>
          </Field>
          {loadingVaultContacts ? (
            <div className="flex justify-center py-8">
              <Spinner className="h-5 w-5" />
            </div>
          ) : importCompanyId && vaultContacts.length === 0 ? (
            <p className="text-sm text-ink-500">No saved contacts for this company yet. Run a contact search first.</p>
          ) : vaultContacts.length > 0 ? (
            <div className="max-h-80 overflow-y-auto rounded-lg border border-ink-200">
              <table className="w-full">
                <thead className="sticky top-0 border-b border-ink-100 bg-ink-50/90">
                  <tr>
                    <th className="table-th w-10"></th>
                    <th className="table-th">Name</th>
                    <th className="table-th">Title</th>
                    <th className="table-th">Email</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {vaultContacts.map((ct) => (
                    <tr key={ct.vault_id} className="hover:bg-ink-50/60">
                      <td className="table-td">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-ink-300 text-brand-600"
                          checked={selectedVault.has(ct.vault_id)}
                          onChange={() => toggleVaultContact(ct.vault_id)}
                        />
                      </td>
                      <td className="table-td font-medium">{ct.name || "—"}</td>
                      <td className="table-td">{ct.title || "—"}</td>
                      <td className="table-td">{ct.email || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </form>
      </Modal>
    </div>
  );
}
