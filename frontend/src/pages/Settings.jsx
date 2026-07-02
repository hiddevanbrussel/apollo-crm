import { useEffect, useState } from "react";
import api, { apiError } from "../api/client";
import { resetLogokit } from "../api/logokit";
import { Icon } from "../components/icons";
import { Field, Modal, PageLoader, Spinner } from "../components/ui";
import { CompanyImportPanel, ContactImportPanel } from "../components/ImportPanel";
import { useToast } from "../context/ToastContext";

const SUB_TABS = [
  { id: "integrations", label: "Integrations" },
  { id: "activity", label: "Activity" },
  { id: "import", label: "Import" },
  { id: "about", label: "About" },
];

function Toggle({ checked, onChange, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation();
        onChange(!checked);
      }}
      className={`relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors duration-200 ${
        checked ? "bg-accent-500" : "bg-ink-300"
      } ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition-transform duration-200 ${
          checked ? "translate-x-4" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

function IntegrationTile({ icon, accent, title, description, configured, enabled, onToggle, onView }) {
  return (
    <div className="card flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className={`flex h-9 w-9 items-center justify-center rounded-lg border border-ink-200 ${accent}`}>
            {icon}
          </div>
          <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
        </div>
        <Toggle checked={enabled} onChange={onToggle} />
      </div>
      <p className="mt-3 flex-1 text-sm leading-relaxed text-ink-500">{description}</p>
      <div className="mt-4 flex items-center justify-between border-t border-ink-100 pt-3">
        <span className={`badge ${configured ? "bg-green-50 text-green-700" : "bg-ink-100 text-ink-500"}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${configured ? "bg-green-500" : "bg-ink-400"}`} />
          {configured ? "Configured" : "Not configured"}
        </span>
        <button className="btn-secondary" onClick={onView}>
          View integration
        </button>
      </div>
    </div>
  );
}

export default function Settings() {
  const toast = useToast();
  const [tab, setTab] = useState("integrations");
  const [detail, setDetail] = useState(null); // null | "apollo" | "groq"

  // Apollo state
  const [apollo, setApollo] = useState(null);
  const [apolloKey, setApolloKey] = useState("");
  const [apolloUrl, setApolloUrl] = useState("");
  const [apolloSaving, setApolloSaving] = useState(false);
  const [apolloTesting, setApolloTesting] = useState(false);
  const [apolloTest, setApolloTest] = useState(null);

  // Groq state
  const [groq, setGroq] = useState(null);
  const [groqKey, setGroqKey] = useState("");
  const [groqUrl, setGroqUrl] = useState("");
  const [groqModel, setGroqModel] = useState("");
  const [groqSaving, setGroqSaving] = useState(false);
  const [groqTesting, setGroqTesting] = useState(false);
  const [groqTest, setGroqTest] = useState(null);
  const [domainJob, setDomainJob] = useState(null);
  const [enrichJob, setEnrichJob] = useState(null);
  const [enrichJobs, setEnrichJobs] = useState([]);
  const [titleAiJob, setTitleAiJob] = useState(null);
  const [titleAiJobs, setTitleAiJobs] = useState([]);

  // Logokit state
  const [logokit, setLogokit] = useState(null);
  const [logokitToken, setLogokitToken] = useState("");
  const [logokitUrl, setLogokitUrl] = useState("");
  const [logokitSaving, setLogokitSaving] = useState(false);
  const [logokitTesting, setLogokitTesting] = useState(false);
  const [logokitTest, setLogokitTest] = useState(null);
  const [apolloReady, setApolloReady] = useState(false);

  // Prospeo state
  const [prospeo, setProspeo] = useState(null);
  const [prospeoKey, setProspeoKey] = useState("");
  const [prospeoUrl, setProspeoUrl] = useState("");
  const [prospeoSaving, setProspeoSaving] = useState(false);
  const [prospeoTesting, setProspeoTesting] = useState(false);
  const [prospeoTest, setProspeoTest] = useState(null);

  // Lusha state
  const [lusha, setLusha] = useState(null);
  const [lushaKey, setLushaKey] = useState("");
  const [lushaUrl, setLushaUrl] = useState("");
  const [lushaSaving, setLushaSaving] = useState(false);
  const [lushaTesting, setLushaTesting] = useState(false);
  const [lushaTest, setLushaTest] = useState(null);

  // Azure AD state
  const [azureAd, setAzureAd] = useState(null);
  const [azureClientId, setAzureClientId] = useState("");
  const [azureClientSecret, setAzureClientSecret] = useState("");
  const [azureAuthority, setAzureAuthority] = useState("");
  const [azureRedirectUri, setAzureRedirectUri] = useState("");
  const [azureDomainsText, setAzureDomainsText] = useState("");
  const [azureSaving, setAzureSaving] = useState(false);

  const load = async () => {
    try {
      const [{ data: a }, { data: g }, { data: l }, { data: p }, { data: lu }, { data: az }] = await Promise.all([
        api.get("/settings/apollo"),
        api.get("/settings/groq"),
        api.get("/settings/logokit"),
        api.get("/settings/prospeo"),
        api.get("/settings/lusha"),
        api.get("/settings/azure-ad"),
      ]);
      setApollo(a);
      setApolloUrl(a.base_url);
      setGroq(g);
      setGroqUrl(g.base_url);
      setGroqModel(g.model);
      setLogokit(l);
      setLogokitUrl(l.base_url);
      setProspeo(p);
      setProspeoUrl(p.base_url);
      setLusha(lu);
      setLushaUrl(lu.base_url);
      setAzureAd(az);
      setAzureClientId(az.client_id || "");
      setAzureAuthority(az.authority || "");
      setAzureRedirectUri(az.redirect_uri || "");
      setAzureDomainsText((az.allowed_domains || []).join("\n"));
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  useEffect(() => {
    load();
    api
      .get("/companies/find-domains/jobs/active")
      .then((r) => r.data && setDomainJob(r.data))
      .catch(() => {});
    api
      .get("/contacts/enrich/jobs/active")
      .then((r) => setEnrichJob(r.data || null))
      .catch(() => setEnrichJob(null));
    api
      .get("/contacts/enrich/jobs")
      .then((r) => setEnrichJobs(r.data || []))
      .catch(() => setEnrichJobs([]));
    api
      .get("/contacts/title-ai/jobs/active")
      .then((r) => setTitleAiJob(r.data || null))
      .catch(() => setTitleAiJob(null));
    api
      .get("/contacts/title-ai/jobs")
      .then((r) => setTitleAiJobs(r.data || []))
      .catch(() => setTitleAiJobs([]));
    api
      .get("/apollo/status")
      .then((res) => setApolloReady(res.data.enabled && res.data.configured))
      .catch(() => setApolloReady(false));
  }, []);

  // Poll a running domain job for progress.
  useEffect(() => {
    if (!domainJob || domainJob.status !== "running") return;
    const timer = setInterval(async () => {
      try {
        const { data } = await api.get(`/companies/find-domains/jobs/${domainJob.id}`);
        setDomainJob(data);
        if (data.status !== "running") {
          clearInterval(timer);
          if (data.status === "completed") {
            toast.success(`Done: ${data.applied} domains added (${data.found}/${data.total} found).`);
          } else if (data.status === "failed") {
            toast.error(`Domain lookup failed: ${data.error || "unknown error"}`);
          }
        }
      } catch {
        clearInterval(timer);
      }
    }, 1500);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domainJob?.id, domainJob?.status]);

  useEffect(() => {
    if (!enrichJob || !["queued", "running"].includes(enrichJob.status)) return;
    const timer = setInterval(async () => {
      try {
        const { data } = await api.get(`/contacts/enrich/jobs/${enrichJob.id}`);
        setEnrichJob(data);
        if (!["queued", "running"].includes(data.status)) {
          clearInterval(timer);
          const parts = [];
          if (data.enriched) parts.push(`${data.enriched} enriched`);
          if (data.pending) parts.push(`${data.pending} pending`);
          if (data.failed) parts.push(`${data.failed} failed`);
          toast.success(
            data.status === "completed"
              ? `Contact enrichment done${parts.length ? `: ${parts.join(", ")}` : "."}`
              : `Contact enrichment failed: ${data.error || "unknown error"}`
          );
          const { data: list } = await api.get("/contacts/enrich/jobs");
          setEnrichJobs(list || []);
        }
      } catch {
        clearInterval(timer);
      }
    }, 1500);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enrichJob?.id, enrichJob?.status]);

  useEffect(() => {
    if (!titleAiJob || !["queued", "running"].includes(titleAiJob.status)) return;
    const timer = setInterval(async () => {
      try {
        const { data } = await api.get(`/contacts/title-ai/jobs/${titleAiJob.id}`);
        setTitleAiJob(data);
        if (!["queued", "running"].includes(data.status)) {
          clearInterval(timer);
          const parts = [];
          if (data.normalized) parts.push(`${data.normalized} normalized`);
          if (data.skipped) parts.push(`${data.skipped} skipped`);
          if (data.failed) parts.push(`${data.failed} failed`);
          toast.success(
            data.status === "completed"
              ? `Title AI job done${parts.length ? `: ${parts.join(", ")}` : "."}`
              : `Title AI job failed: ${data.error || "unknown error"}`
          );
          const { data: list } = await api.get("/contacts/title-ai/jobs");
          setTitleAiJobs(list || []);
        }
      } catch {
        clearInterval(timer);
      }
    }, 1500);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [titleAiJob?.id, titleAiJob?.status]);

  // --- Apollo handlers ---
  const toggleApollo = async (value) => {
    try {
      const { data } = await api.put("/settings/apollo", { enabled: value });
      setApollo(data);
      toast.success(`Apollo ${value ? "enabled" : "disabled"}.`);
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const saveApollo = async () => {
    setApolloSaving(true);
    try {
      const payload = { base_url: apolloUrl };
      if (apolloKey.trim()) payload.api_key = apolloKey.trim();
      const { data } = await api.put("/settings/apollo", payload);
      setApollo(data);
      setApolloKey("");
      toast.success("Apollo settings saved.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setApolloSaving(false);
    }
  };

  const clearApolloKey = async () => {
    if (!confirm("Remove the Apollo API key?")) return;
    try {
      const { data } = await api.put("/settings/apollo", { clear_api_key: true });
      setApollo(data);
      toast.success("Apollo API key removed.");
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const testApollo = async () => {
    setApolloTesting(true);
    setApolloTest(null);
    try {
      const { data } = await api.post("/settings/apollo/test");
      setApolloTest(data);
      data.success ? toast.success(data.message) : toast.error(data.message);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setApolloTesting(false);
    }
  };

  // --- Groq handlers ---
  const toggleGroq = async (value) => {
    try {
      const { data } = await api.put("/settings/groq", { enabled: value });
      setGroq(data);
      toast.success(`Groq ${value ? "enabled" : "disabled"}.`);
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const toggleGroqAssistant = async (value) => {
    try {
      const { data } = await api.put("/settings/groq", { assistant_enabled: value });
      setGroq(data);
      toast.success(`AI assistant ${value ? "enabled" : "disabled"}.`);
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const saveGroq = async () => {
    setGroqSaving(true);
    try {
      const payload = { base_url: groqUrl, model: groqModel };
      if (groqKey.trim()) payload.api_key = groqKey.trim();
      const { data } = await api.put("/settings/groq", payload);
      setGroq(data);
      setGroqKey("");
      toast.success("Groq settings saved.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setGroqSaving(false);
    }
  };

  const clearGroqKey = async () => {
    if (!confirm("Remove the Groq API key?")) return;
    try {
      const { data } = await api.put("/settings/groq", { clear_api_key: true });
      setGroq(data);
      toast.success("Groq API key removed.");
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const testGroq = async () => {
    setGroqTesting(true);
    setGroqTest(null);
    try {
      const { data } = await api.post("/settings/groq/test");
      setGroqTest(data);
      data.success ? toast.success(data.message) : toast.error(data.message);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setGroqTesting(false);
    }
  };

  const findMissingDomains = async () => {
    if (!confirm("Find domains via Groq for ALL companies without a domain? This runs in the background and uses Groq tokens.")) return;
    try {
      const { data } = await api.post("/companies/find-domains/jobs");
      setDomainJob(data);
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  // --- Logokit handlers ---
  const toggleLogokit = async (value) => {
    try {
      const { data } = await api.put("/settings/logokit", { enabled: value });
      setLogokit(data);
      resetLogokit();
      toast.success(`Logokit ${value ? "enabled" : "disabled"}.`);
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const saveLogokit = async () => {
    setLogokitSaving(true);
    try {
      const payload = { base_url: logokitUrl };
      if (logokitToken.trim()) payload.token = logokitToken.trim();
      const { data } = await api.put("/settings/logokit", payload);
      setLogokit(data);
      setLogokitToken("");
      resetLogokit();
      toast.success("Logokit settings saved.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLogokitSaving(false);
    }
  };

  const clearLogokitToken = async () => {
    if (!confirm("Remove the Logokit token?")) return;
    try {
      const { data } = await api.put("/settings/logokit", { clear_token: true });
      setLogokit(data);
      resetLogokit();
      toast.success("Logokit token removed.");
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const testLogokit = async () => {
    setLogokitTesting(true);
    setLogokitTest(null);
    try {
      const body = logokitToken.trim() ? { token: logokitToken.trim() } : {};
      const { data } = await api.post("/settings/logokit/test", body);
      setLogokitTest(data);
      data.success ? toast.success(data.message) : toast.error(data.message);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLogokitTesting(false);
    }
  };

  // --- Prospeo handlers ---
  const toggleProspeo = async (value) => {
    try {
      const { data } = await api.put("/settings/prospeo", { enabled: value });
      setProspeo(data);
      toast.success(`Prospeo ${value ? "enabled" : "disabled"}.`);
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const saveProspeo = async () => {
    setProspeoSaving(true);
    try {
      const payload = { base_url: prospeoUrl };
      if (prospeoKey.trim()) payload.api_key = prospeoKey.trim();
      const { data } = await api.put("/settings/prospeo", payload);
      setProspeo(data);
      setProspeoKey("");
      toast.success("Prospeo settings saved.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setProspeoSaving(false);
    }
  };

  const clearProspeoKey = async () => {
    if (!confirm("Remove the Prospeo API key?")) return;
    try {
      const { data } = await api.put("/settings/prospeo", { clear_api_key: true });
      setProspeo(data);
      toast.success("Prospeo API key removed.");
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const testProspeo = async () => {
    setProspeoTesting(true);
    setProspeoTest(null);
    try {
      const { data } = await api.post("/settings/prospeo/test");
      setProspeoTest(data);
      data.success ? toast.success(data.message) : toast.error(data.message);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setProspeoTesting(false);
    }
  };

  const toggleLusha = async (value) => {
    try {
      const { data } = await api.put("/settings/lusha", { enabled: value });
      setLusha(data);
      toast.success(`Lusha ${value ? "enabled" : "disabled"}.`);
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const saveLusha = async () => {
    setLushaSaving(true);
    try {
      const payload = { base_url: lushaUrl };
      if (lushaKey.trim()) payload.api_key = lushaKey.trim();
      const { data } = await api.put("/settings/lusha", payload);
      setLusha(data);
      setLushaKey("");
      toast.success("Lusha settings saved.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLushaSaving(false);
    }
  };

  const clearLushaKey = async () => {
    if (!confirm("Remove the Lusha API key?")) return;
    try {
      const { data } = await api.put("/settings/lusha", { clear_api_key: true });
      setLusha(data);
      toast.success("Lusha API key removed.");
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const testLusha = async () => {
    setLushaTesting(true);
    setLushaTest(null);
    try {
      const { data } = await api.post("/settings/lusha/test");
      setLushaTest(data);
      data.success ? toast.success(data.message) : toast.error(data.message);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLushaTesting(false);
    }
  };

  const toggleAzureAd = async (value) => {
    try {
      const { data } = await api.put("/settings/azure-ad", { enabled: value });
      setAzureAd(data);
      toast.success(`Microsoft sign-in ${value ? "enabled" : "disabled"}.`);
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const saveAzureAd = async () => {
    setAzureSaving(true);
    try {
      const allowed_domains = azureDomainsText
        .split(/[\n,;]+/)
        .map((d) => d.trim())
        .filter(Boolean);
      const payload = {
        client_id: azureClientId.trim(),
        authority: azureAuthority.trim(),
        redirect_uri: azureRedirectUri.trim(),
        allowed_domains,
      };
      if (azureClientSecret.trim()) payload.client_secret = azureClientSecret.trim();
      const { data } = await api.put("/settings/azure-ad", payload);
      setAzureAd(data);
      setAzureClientId(data.client_id || "");
      setAzureClientSecret("");
      setAzureAuthority(data.authority || "");
      setAzureRedirectUri(data.redirect_uri || "");
      setAzureDomainsText((data.allowed_domains || []).join("\n"));
      toast.success("Azure AD settings saved.");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setAzureSaving(false);
    }
  };

  const clearAzureSecret = async () => {
    if (!confirm("Remove the Azure client secret?")) return;
    try {
      const { data } = await api.put("/settings/azure-ad", { clear_client_secret: true });
      setAzureAd(data);
      setAzureClientSecret("");
      toast.success("Azure client secret removed.");
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  if (!apollo || !groq || !logokit || !prospeo || !lusha || !azureAd) return <PageLoader />;

  const formatJobTime = (ts) => (ts ? new Date(ts * 1000).toLocaleString() : "—");

  const batchStatusClass = (status) => {
    if (status === "completed") return "bg-green-50 text-green-700";
    if (status === "running") return "bg-amber-50 text-amber-700";
    if (status === "failed") return "bg-red-50 text-red-700";
    return "bg-ink-100 text-ink-600";
  };

  const resultClass = (result) => {
    if (result === "enriched" || result === "normalized") return "bg-green-50 text-green-700";
    if (result === "pending") return "bg-amber-50 text-amber-700";
    if (result === "failed") return "bg-red-50 text-red-700";
    if (result === "skipped") return "bg-ink-100 text-ink-500";
    return "bg-ink-100 text-ink-600";
  };

  const TitleAiJobCard = ({ job, active = false }) => (
    <div className={`rounded-lg border p-4 ${active ? "border-brand-200 bg-brand-50/30" : "border-ink-100"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink-900">
            {job.source === "selected" ? "Selected contacts" : "Filtered contacts"}
            {active && <span className="ml-2 text-xs font-normal text-brand-600">Active</span>}
          </p>
          <p className="mt-0.5 text-xs text-ink-500">
            Started {formatJobTime(job.started_at)}
            {job.finished_at && ` · Finished ${formatJobTime(job.finished_at)}`}
          </p>
        </div>
        <span className={`badge capitalize ${batchStatusClass(job.status)}`}>{job.status}</span>
      </div>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-ink-100">
        <div
          className="h-full rounded-full bg-brand-500 transition-all duration-500"
          style={{
            width: `${
              job.total_contacts
                ? Math.round((job.processed_contacts / job.total_contacts) * 100)
                : job.status === "running"
                  ? 5
                  : 100
            }%`,
          }}
        />
      </div>
      <p className="mt-1.5 text-xs text-ink-500">
        {job.processed_contacts}/{job.total_contacts} contacts · {job.normalized} normalized · {job.skipped} skipped ·{" "}
        {job.failed} failed
        {job.current_contact && job.status === "running" && (
          <span className="block truncate text-ink-400">Current: {job.current_contact}</span>
        )}
      </p>
      {job.items?.length > 0 && (
        <div className="mt-3 max-h-64 overflow-y-auto overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-white">
              <tr className="border-b border-ink-100 text-left text-ink-400">
                <th className="pb-1.5 pr-3 font-medium">#</th>
                <th className="pb-1.5 pr-3 font-medium">Contact</th>
                <th className="pb-1.5 pr-3 font-medium">Status</th>
                <th className="pb-1.5 font-medium">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {job.items.map((item) => (
                <tr key={item.index} className={item.status === "running" ? "bg-amber-50/50" : ""}>
                  <td className="py-1.5 pr-3 font-medium text-ink-700">{item.index}</td>
                  <td className="py-1.5 pr-3 text-ink-700">{item.label || `#${item.contact_id}`}</td>
                  <td className="py-1.5 pr-3">
                    {item.result ? (
                      <span className={`badge capitalize ${resultClass(item.result)}`}>{item.result}</span>
                    ) : (
                      <span className={`badge capitalize ${batchStatusClass(item.status)}`}>{item.status}</span>
                    )}
                  </td>
                  <td className="py-1.5 text-ink-500">{item.error || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {job.log?.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-brand-600">Log ({job.log.length})</summary>
          <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-ink-900 p-3 text-[11px] text-ink-100">
            {job.log.map((entry) => `[${formatJobTime(entry.at)}] ${entry.message}`).join("\n")}
          </pre>
        </details>
      )}
    </div>
  );

  const JobCard = ({ job, active = false }) => (
    <div className={`rounded-lg border p-4 ${active ? "border-brand-200 bg-brand-50/30" : "border-ink-100"}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-ink-900">
            {job.source === "selected" ? "Selected contacts" : "Unenriched contacts"}
            {active && <span className="ml-2 text-xs font-normal text-brand-600">Active</span>}
          </p>
          <p className="mt-0.5 text-xs text-ink-500">
            Started {formatJobTime(job.started_at)}
            {job.finished_at && ` · Finished ${formatJobTime(job.finished_at)}`}
          </p>
        </div>
        <span className={`badge capitalize ${batchStatusClass(job.status)}`}>{job.status}</span>
      </div>

      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-ink-100">
        <div
          className="h-full rounded-full bg-brand-500 transition-all duration-500"
          style={{
            width: `${
              job.total_contacts
                ? Math.round((job.processed_contacts / job.total_contacts) * 100)
                : job.status === "running"
                  ? 5
                  : 100
            }%`,
          }}
        />
      </div>
      <p className="mt-1.5 text-xs text-ink-500">
        {job.processed_contacts}/{job.total_contacts} contacts · {job.enriched} enriched · {job.pending} pending ·{" "}
        {job.failed} failed
        {job.current_contact && job.status === "running" && (
          <span className="block truncate text-ink-400">Current: {job.current_contact}</span>
        )}
      </p>

      {job.items?.length > 0 && (
        <div className="mt-3 max-h-64 overflow-y-auto overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-white">
              <tr className="border-b border-ink-100 text-left text-ink-400">
                <th className="pb-1.5 pr-3 font-medium">#</th>
                <th className="pb-1.5 pr-3 font-medium">Contact</th>
                <th className="pb-1.5 pr-3 font-medium">Status</th>
                <th className="pb-1.5 font-medium">Detail</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {job.items.map((item) => (
                <tr key={item.index} className={item.status === "running" ? "bg-amber-50/50" : ""}>
                  <td className="py-1.5 pr-3 font-medium text-ink-700">{item.index}</td>
                  <td className="py-1.5 pr-3 text-ink-700">{item.label || `#${item.contact_id}`}</td>
                  <td className="py-1.5 pr-3">
                    {item.result ? (
                      <span className={`badge capitalize ${resultClass(item.result)}`}>{item.result}</span>
                    ) : (
                      <span className={`badge capitalize ${batchStatusClass(item.status)}`}>{item.status}</span>
                    )}
                  </td>
                  <td className="py-1.5 text-ink-500">
                    {item.error
                      ? item.error
                      : item.provider
                        ? `via ${item.provider}`
                        : item.status === "queued"
                          ? "Waiting"
                          : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {job.log?.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-ink-500">Log ({job.log.length})</summary>
          <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto rounded-lg bg-ink-900 p-3 font-mono text-[11px] text-ink-100">
            {job.log.map((entry, i) => (
              <li key={`${entry.at}-${i}`}>
                <span className="text-ink-400">{formatJobTime(entry.at)}</span> {entry.message}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );

  const TestResult = ({ result }) =>
    result ? (
      <div
        className={`rounded-lg border px-3 py-2 text-sm ${
          result.success ? "border-green-200 bg-green-50 text-green-700" : "border-red-200 bg-red-50 text-red-700"
        }`}
      >
        {result.message}
      </div>
    ) : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink-900">Settings</h1>
        <p className="text-sm text-ink-500">Manage your workspace and connected applications.</p>
      </div>

      {/* Horizontal submenu */}
      <div className="border-b border-ink-200">
        <div className="flex gap-1">
          {SUB_TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                tab === t.id
                  ? "border-accent-500 text-ink-900"
                  : "border-transparent text-ink-500 hover:text-ink-800"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {tab === "integrations" && (
        <div className="space-y-5">
          <div>
            <h2 className="text-base font-semibold text-ink-900">Integrations and connected apps</h2>
            <p className="text-sm text-ink-500">
              Supercharge your workflow and connect the tools you use every day.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
            <IntegrationTile
              icon={<Icon.Sparkles width={18} height={18} className="text-brand-600" />}
              accent="bg-white"
              title="Apollo API"
              description="Search and enrich companies and contacts via Apollo.io. Used on demand to fetch industry, headcount, revenue and more."
              configured={apollo.configured}
              enabled={apollo.enabled}
              onToggle={toggleApollo}
              onView={() => {
                setApolloTest(null);
                setDetail("apollo");
              }}
            />
            <IntegrationTile
              icon={<Icon.Bolt width={18} height={18} className="text-accent-600" />}
              accent="bg-accent-50"
              title="Groq API"
              description="AI domain finder, Title AI normalization, and the floating AI assistant chat widget."
              configured={groq.configured}
              enabled={groq.enabled}
              onToggle={toggleGroq}
              onView={() => {
                setGroqTest(null);
                setDetail("groq");
              }}
            />
            <IntegrationTile
              icon={<Icon.Users width={18} height={18} className="text-violet-600" />}
              accent="bg-violet-50"
              title="Prospeo API"
              description="Enrich contacts via Prospeo enrich-person — verified emails and B2B profile data as a fallback or alternative to Apollo."
              configured={prospeo.configured}
              enabled={prospeo.enabled}
              onToggle={toggleProspeo}
              onView={() => {
                setProspeoTest(null);
                setDetail("prospeo");
              }}
            />
            <IntegrationTile
              icon={<Icon.Phone width={18} height={18} className="text-emerald-600" />}
              accent="bg-emerald-50"
              title="Lusha API"
              description="Reveal phone numbers and emails for contacts via Lusha search-and-enrich."
              configured={lusha.configured}
              enabled={lusha.enabled}
              onToggle={toggleLusha}
              onView={() => {
                setLushaTest(null);
                setDetail("lusha");
              }}
            />
            <IntegrationTile
              icon={<Icon.Image width={18} height={18} className="text-brand-600" />}
              accent="bg-white"
              title="Logokit"
              description="Show company logos automatically based on their domain across the CRM."
              configured={logokit.configured}
              enabled={logokit.enabled}
              onToggle={toggleLogokit}
              onView={() => {
                setLogokitTest(null);
                setDetail("logokit");
              }}
            />
            <IntegrationTile
              icon={
                <svg width="18" height="18" viewBox="0 0 21 21" aria-hidden="true">
                  <rect x="1" y="1" width="9" height="9" fill="#0078d4" />
                  <rect x="11" y="1" width="9" height="9" fill="#0078d4" opacity="0.85" />
                  <rect x="1" y="11" width="9" height="9" fill="#0078d4" opacity="0.85" />
                  <rect x="11" y="11" width="9" height="9" fill="#0078d4" opacity="0.7" />
                </svg>
              }
              accent="bg-sky-50"
              title="Microsoft Entra ID"
              description="Sign in with Microsoft from any Azure AD tenant. Only users with approved email domains get access."
              configured={azureAd.configured}
              enabled={azureAd.enabled}
              onToggle={toggleAzureAd}
              onView={() => setDetail("azure-ad")}
            />
          </div>
        </div>
      )}

      {tab === "activity" && (
        <div className="space-y-5">
          <div>
            <h2 className="text-base font-semibold text-ink-900">Background jobs & logging</h2>
            <p className="text-sm text-ink-500">
              Track bulk contact enrichment batches and other background tasks.
            </p>
          </div>

          <div className="card p-5">
            <h3 className="text-sm font-semibold text-ink-900">Contact enrichment</h3>
            <p className="mt-1 text-xs text-ink-500">
              Start from Contacts via &quot;Match unenriched&quot; or &quot;Match selected&quot;. Contacts are matched
              one at a time so you can see exactly where a lookup fails.
            </p>
            {enrichJob && ["queued", "running"].includes(enrichJob.status) ? (
              <div className="mt-4">
                <JobCard job={enrichJob} active />
              </div>
            ) : enrichJobs.length === 0 ? (
              <p className="mt-4 text-sm text-ink-400">No enrichment jobs yet.</p>
            ) : (
              <div className="mt-4 space-y-3">
                <JobCard job={enrichJobs[0]} active={false} />
              </div>
            )}
            {enrichJobs.length > 1 && (
              <details className="mt-4">
                <summary className="cursor-pointer text-xs font-medium text-brand-600">
                  Previous jobs ({enrichJobs.length - 1})
                </summary>
                <div className="mt-3 space-y-3">
                  {enrichJobs.slice(1).map((job) => (
                    <JobCard key={job.id} job={job} />
                  ))}
                </div>
              </details>
            )}
          </div>

          <div className="card p-5">
            <h3 className="text-sm font-semibold text-ink-900">Title AI (Groq)</h3>
            <p className="mt-1 text-xs text-ink-500">
              Start from Contacts via &quot;Title AI&quot; or &quot;Title AI (filtered)&quot;. Original titles are kept;
              Title AI stores the normalized version.
            </p>
            {titleAiJob && ["queued", "running"].includes(titleAiJob.status) ? (
              <div className="mt-4">
                <TitleAiJobCard job={titleAiJob} active />
              </div>
            ) : titleAiJobs.length === 0 ? (
              <p className="mt-4 text-sm text-ink-400">No Title AI jobs yet.</p>
            ) : (
              <div className="mt-4 space-y-3">
                <TitleAiJobCard job={titleAiJobs[0]} active={false} />
              </div>
            )}
            {titleAiJobs.length > 1 && (
              <details className="mt-4">
                <summary className="cursor-pointer text-xs font-medium text-brand-600">
                  Previous jobs ({titleAiJobs.length - 1})
                </summary>
                <div className="mt-3 space-y-3">
                  {titleAiJobs.slice(1).map((job) => (
                    <TitleAiJobCard key={job.id} job={job} />
                  ))}
                </div>
              </details>
            )}
          </div>

          {domainJob && (
            <div className="card p-5">
              <h3 className="text-sm font-semibold text-ink-900">Domain lookup (Groq)</h3>
              <div className="mt-3 space-y-1.5">
                <div className="h-2 w-full overflow-hidden rounded-full bg-ink-100">
                  <div
                    className="h-full rounded-full bg-accent-500 transition-all duration-500"
                    style={{
                      width: `${domainJob.total ? Math.round((domainJob.processed / domainJob.total) * 100) : domainJob.status === "running" ? 5 : 100}%`,
                    }}
                  />
                </div>
                <p className="text-xs text-ink-500">
                  {domainJob.status === "running"
                    ? `Processing ${domainJob.processed}/${domainJob.total || "…"}`
                    : domainJob.status === "completed"
                      ? `Completed · ${domainJob.processed}/${domainJob.total} processed`
                      : `Failed · ${domainJob.error || "unknown error"}`}
                  {" · "}
                  {domainJob.applied} applied · {domainJob.found} found
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === "import" && (
        <div className="space-y-5">
          <div>
            <h2 className="text-base font-semibold text-ink-900">Data import</h2>
            <p className="text-sm text-ink-500">
              Import companies first, then contacts. Contact email domains are linked to their company automatically.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <CompanyImportPanel apolloReady={apolloReady} />
            <ContactImportPanel />
          </div>
        </div>
      )}

      {tab === "about" && (
        <div className="flex flex-col gap-6 lg:flex-row">
          <div className="min-w-0 flex-1 p-6">
            <div className="mb-3 flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-xl">
                🧇
              </div>
              <div>
                <h2 className="text-sm font-semibold text-ink-900">The Legend of Hidde van Brussel</h2>
                <p className="text-xs text-ink-400">Founding Father · Patron Saint of Lost Domains</p>
              </div>
            </div>
            <div className="space-y-3 text-sm leading-relaxed text-ink-600">
              <p>
                Long ago, in a damp Dutch office lit only by the glow of seventeen unclosed browser
                tabs, there lived a man named <span className="font-medium text-ink-800">Hidde van Brussel</span>.
                Hidde had a problem. Every morning he opened Apollo.io, and every morning Apollo.io
                gently whispered, <em>"that'll be a few more credits, please."</em> Hidde wept. Hidde's
                wallet wept harder.
              </p>
              <p>
                One fateful Tuesday, after his fourth stroopwafel and his ninth existential crisis,
                Hidde slammed his fist on the desk and declared: <span className="font-medium text-ink-800">
                "Why should my data live in someone else's castle, when I have a perfectly good
                basement?"</span> Thus, with nothing but caffeine, spite, and a suspicious amount of
                Tailwind classes, he forged this very CRM — a fortress where the data belonged to the
                people, and the people belonged to the data.
              </p>
              <p>
                Legend says he taught the application to find missing domains by sheer force of will
                (and a little Groq). They say he could enrich a company just by looking at it sternly.
                They say his bulk-select button still hums faintly at midnight, whispering
                <em>"select all… enrich all…"</em>
              </p>
              <p>
                Today, Hidde is remembered not as a developer, but as a movement. A vibe. A man who
                looked Big Sales Software in the eye and said: <span className="font-medium text-ink-800">
                "Nee."</span>
              </p>
              <p className="text-xs italic text-ink-400">
                This story is 12% true, 88% stroopwafel. No founding fathers were harmed in the
                making of this CRM.
              </p>
            </div>
          </div>

          <aside className="w-full shrink-0 lg:w-1/4">
            <div className="card p-6">
              <h2 className="text-sm font-semibold text-ink-900">Apollo CRM</h2>
              <p className="mt-1 text-sm text-ink-500">
                A self-hosted CRM. All your data lives in your own database. Apollo and Groq are only
                used on request as data sources — nothing is sent automatically.
              </p>
              <dl className="mt-4 space-y-4 text-sm">
                <div>
                  <dt className="text-xs font-medium text-ink-400">Deployment</dt>
                  <dd className="text-ink-800">Self-hosted (Docker)</dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-ink-400">Default login</dt>
                  <dd className="text-ink-800">admin@apollo-crm.com</dd>
                </div>
              </dl>
            </div>
          </aside>
        </div>
      )}

      {/* Apollo detail modal */}
      <Modal
        open={detail === "apollo"}
        onClose={() => setDetail(null)}
        title="Apollo API"
        footer={
          <>
            <button className="btn-secondary" onClick={testApollo} disabled={apolloTesting || !apollo.configured}>
              {apolloTesting ? <Spinner className="h-4 w-4" /> : <Icon.Globe width={18} height={18} />} Test connection
            </button>
            <button className="btn-primary" onClick={saveApollo} disabled={apolloSaving}>
              {apolloSaving && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-ink-100 bg-ink-50/60 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-ink-900">Integration status</p>
              <p className="text-xs text-ink-400">Enable to allow enrichment calls to Apollo.</p>
            </div>
            <Toggle checked={apollo.enabled} onChange={toggleApollo} />
          </div>
          <Field label="API key">
            <div className="flex gap-2">
              <input
                className="input"
                type="password"
                placeholder={apollo.configured ? apollo.api_key_masked || "••••••••" : "Enter your Apollo API key"}
                value={apolloKey}
                onChange={(e) => setApolloKey(e.target.value)}
              />
              {apollo.configured && (
                <button className="btn-danger whitespace-nowrap" onClick={clearApolloKey}>Remove</button>
              )}
            </div>
            <p className="mt-1 text-xs text-ink-400">Stored encrypted, never shown in full.</p>
          </Field>
          <Field label="Base URL">
            <input className="input" value={apolloUrl} onChange={(e) => setApolloUrl(e.target.value)} placeholder="https://api.apollo.io" />
          </Field>
          <TestResult result={apolloTest} />
        </div>
      </Modal>

      {/* Groq detail modal */}
      <Modal
        open={detail === "groq"}
        onClose={() => setDetail(null)}
        title="Groq API"
        footer={
          <>
            <button className="btn-secondary" onClick={testGroq} disabled={groqTesting || !groq.configured}>
              {groqTesting ? <Spinner className="h-4 w-4" /> : <Icon.Globe width={18} height={18} />} Test connection
            </button>
            <button className="btn-primary" onClick={saveGroq} disabled={groqSaving}>
              {groqSaving && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-ink-100 bg-ink-50/60 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-ink-900">Integration status</p>
              <p className="text-xs text-ink-400">Enable to allow AI domain lookups via Groq.</p>
            </div>
            <Toggle checked={groq.enabled} onChange={toggleGroq} />
          </div>
          <div className="flex items-center justify-between rounded-lg border border-ink-100 bg-ink-50/60 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-ink-900">AI assistant widget</p>
              <p className="text-xs text-ink-400">
                Show or hide the floating AI assistant button in the bottom-right corner of the app.
              </p>
            </div>
            <Toggle checked={groq?.assistant_enabled !== false} onChange={toggleGroqAssistant} />
          </div>
          <Field label="API key">
            <div className="flex gap-2">
              <input
                className="input"
                type="password"
                placeholder={groq.configured ? groq.api_key_masked || "••••••••" : "Enter your Groq API key"}
                value={groqKey}
                onChange={(e) => setGroqKey(e.target.value)}
              />
              {groq.configured && (
                <button className="btn-danger whitespace-nowrap" onClick={clearGroqKey}>Remove</button>
              )}
            </div>
            <p className="mt-1 text-xs text-ink-400">Stored encrypted, never shown in full.</p>
          </Field>
          <Field label="Model">
            <input className="input font-mono text-xs" value={groqModel} onChange={(e) => setGroqModel(e.target.value)} placeholder="groq/compound" />
            <p className="mt-1 text-xs text-ink-400">Use a model with web search, e.g. <code>groq/compound</code> or <code>groq/compound-mini</code>.</p>
          </Field>
          <Field label="Base URL">
            <input className="input" value={groqUrl} onChange={(e) => setGroqUrl(e.target.value)} placeholder="https://api.groq.com" />
          </Field>
          <div className="rounded-lg border border-ink-100 bg-ink-50/60 p-3 text-xs text-ink-500">
            Groq searches the web for a company's official domain based on its
            <strong> company name + country</strong>. You can also look it up per company with the
            “Find domain” button on a company's page.
          </div>
          <div className="space-y-3 rounded-lg border border-ink-100 px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-ink-900">Find missing domains</p>
                <p className="text-xs text-ink-400">
                  Look up domains for all companies without one. Runs in the background and uses Groq tokens.
                </p>
              </div>
              <button
                className="btn-secondary"
                onClick={findMissingDomains}
                disabled={domainJob?.status === "running" || !groq.enabled || !groq.configured}
                title={groq.enabled && groq.configured ? "" : "Enable Groq and add an API key first"}
              >
                {domainJob?.status === "running" ? <Spinner className="h-4 w-4" /> : <Icon.Wand width={18} height={18} />}
                {domainJob?.status === "running" ? "Running…" : "Run"}
              </button>
            </div>

            {domainJob && (
              <div className="space-y-1.5">
                <div className="h-2 w-full overflow-hidden rounded-full bg-ink-100">
                  <div
                    className="h-full rounded-full bg-accent-500 transition-all duration-500"
                    style={{
                      width: `${domainJob.total ? Math.round((domainJob.processed / domainJob.total) * 100) : (domainJob.status === "running" ? 5 : 100)}%`,
                    }}
                  />
                </div>
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-0.5 text-xs text-ink-500">
                  <span>
                    {domainJob.status === "running"
                      ? `Processing ${domainJob.processed}/${domainJob.total || "…"}`
                      : domainJob.status === "completed"
                        ? `Completed · ${domainJob.processed}/${domainJob.total} processed`
                        : `Failed · ${domainJob.error || "unknown error"}`}
                  </span>
                  <span>
                    {domainJob.applied} applied · {domainJob.found} found
                  </span>
                </div>
                {domainJob.status === "running" && domainJob.current && (
                  <p className="truncate text-xs text-ink-400">Current: {domainJob.current}</p>
                )}
              </div>
            )}
          </div>
          <TestResult result={groqTest} />
        </div>
      </Modal>

      {/* Logokit detail modal */}
      <Modal
        open={detail === "logokit"}
        onClose={() => setDetail(null)}
        title="Logokit"
        footer={
          <>
            <button className="btn-secondary" onClick={testLogokit} disabled={logokitTesting || !logokit.configured}>
              {logokitTesting ? <Spinner className="h-4 w-4" /> : <Icon.Globe width={18} height={18} />} Test connection
            </button>
            <button className="btn-primary" onClick={saveLogokit} disabled={logokitSaving}>
              {logokitSaving && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-ink-100 bg-ink-50/60 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-ink-900">Integration status</p>
              <p className="text-xs text-ink-400">Enable to show company logos by domain.</p>
            </div>
            <Toggle checked={logokit.enabled} onChange={toggleLogokit} />
          </div>
          <Field label="Publishable token">
            <div className="flex gap-2">
              <input
                className="input font-mono text-xs"
                placeholder={logokit.configured ? "Token set — enter a new one to replace" : "pk_..."}
                value={logokitToken}
                onChange={(e) => setLogokitToken(e.target.value)}
              />
              {logokit.configured && (
                <button className="btn-danger whitespace-nowrap" onClick={clearLogokitToken}>Remove</button>
              )}
            </div>
            <p className="mt-1 text-xs text-ink-400">
              Use your Logokit <strong>Logo API</strong> publishable token (<code>pk_…</code>) from{" "}
              <a
                href="https://logokit.com/account/api-tokens"
                target="_blank"
                rel="noreferrer"
                className="text-brand-600 hover:underline"
              >
                API Tokens → Logo API
              </a>
              . Not the Brand API secret token (<code>sk_…</code>).
            </p>
          </Field>
          <Field label="Image base URL">
            <input className="input" value={logokitUrl} onChange={(e) => setLogokitUrl(e.target.value)} placeholder="https://img.logokit.com" />
          </Field>
          <div className="rounded-lg border border-ink-100 bg-ink-50/60 p-3 text-xs text-ink-500">
            Logos load from{" "}
            <code>{(logokitUrl || "https://img.logokit.com")}/&#123;domain&#125;?token=pk_…</code>{" "}
            per the{" "}
            <a
              href="https://docs.logokit.com/authentication"
              target="_blank"
              rel="noreferrer"
              className="text-brand-600 hover:underline"
            >
              LogoKit authentication docs
            </a>
            . Save your token before testing. You can also test an unsaved token directly.
          </div>
          <TestResult result={logokitTest} />
        </div>
      </Modal>

      {/* Prospeo detail modal */}
      <Modal
        open={detail === "prospeo"}
        onClose={() => setDetail(null)}
        title="Prospeo API"
        footer={
          <>
            <button className="btn-secondary" onClick={testProspeo} disabled={prospeoTesting || !prospeo.configured}>
              {prospeoTesting ? <Spinner className="h-4 w-4" /> : <Icon.Globe width={18} height={18} />} Test connection
            </button>
            <button className="btn-primary" onClick={saveProspeo} disabled={prospeoSaving}>
              {prospeoSaving && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-ink-100 bg-ink-50/60 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-ink-900">Integration status</p>
              <p className="text-xs text-ink-400">Enable to enrich contacts via Prospeo enrich-person.</p>
            </div>
            <Toggle checked={prospeo.enabled} onChange={toggleProspeo} />
          </div>
          <Field label="API key">
            <div className="flex gap-2">
              <input
                className="input"
                type="password"
                placeholder={prospeo.configured ? prospeo.api_key_masked || "••••••••" : "Enter your Prospeo API key"}
                value={prospeoKey}
                onChange={(e) => setProspeoKey(e.target.value)}
              />
              {prospeo.configured && (
                <button className="btn-danger whitespace-nowrap" onClick={clearProspeoKey}>Remove</button>
              )}
            </div>
            <p className="mt-1 text-xs text-ink-400">
              Stored encrypted. Find your key in the{" "}
              <a href="https://prospeo.io/dashboard" target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">
                Prospeo dashboard
              </a>
              .
            </p>
          </Field>
          <Field label="Base URL">
            <input className="input" value={prospeoUrl} onChange={(e) => setProspeoUrl(e.target.value)} placeholder="https://api.prospeo.io" />
          </Field>
          <TestResult result={prospeoTest} />
        </div>
      </Modal>

      {/* Lusha detail modal */}
      <Modal
        open={detail === "lusha"}
        onClose={() => setDetail(null)}
        title="Lusha API"
        footer={
          <>
            <button className="btn-secondary" onClick={testLusha} disabled={lushaTesting || !lusha.configured}>
              {lushaTesting ? <Spinner className="h-4 w-4" /> : <Icon.Globe width={18} height={18} />} Test connection
            </button>
            <button className="btn-primary" onClick={saveLusha} disabled={lushaSaving}>
              {lushaSaving && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-ink-100 bg-ink-50/60 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-ink-900">Integration status</p>
              <p className="text-xs text-ink-400">Enable to reveal phones via Lusha search-and-enrich.</p>
            </div>
            <Toggle checked={lusha.enabled} onChange={toggleLusha} />
          </div>
          <Field label="API key">
            <div className="flex gap-2">
              <input
                className="input"
                type="password"
                placeholder={lusha.configured ? lusha.api_key_masked || "••••••••" : "Enter your Lusha API key"}
                value={lushaKey}
                onChange={(e) => setLushaKey(e.target.value)}
              />
              {lusha.configured && (
                <button className="btn-danger whitespace-nowrap" onClick={clearLushaKey}>Remove</button>
              )}
            </div>
            <p className="mt-1 text-xs text-ink-400">
              Stored encrypted. Generate a key in the{" "}
              <a href="https://dashboard.lusha.com/enrich/api" target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">
                Lusha API dashboard
              </a>
              .
            </p>
          </Field>
          <Field label="Base URL">
            <input className="input" value={lushaUrl} onChange={(e) => setLushaUrl(e.target.value)} placeholder="https://api.lusha.com" />
          </Field>
          <div className="rounded-lg border border-ink-100 bg-ink-50/60 p-3 text-xs text-ink-500">
            Uses <code className="rounded bg-white px-1">POST /v3/contacts/search-and-enrich</code> with{" "}
            <code className="rounded bg-white px-1">reveal: phones</code>. Each lookup charges Lusha credits (search + reveal).
          </div>
          <TestResult result={lushaTest} />
        </div>
      </Modal>

      <Modal
        open={detail === "azure-ad"}
        onClose={() => setDetail(null)}
        title="Microsoft Entra ID"
        footer={
          <button className="btn-primary" onClick={saveAzureAd} disabled={azureSaving}>
            {azureSaving && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Save
          </button>
        }
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-ink-100 bg-ink-50/60 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-ink-900">Microsoft sign-in</p>
              <p className="text-xs text-ink-400">Allow users to sign in via Azure AD from other tenants.</p>
            </div>
            <Toggle checked={azureAd.enabled} onChange={toggleAzureAd} />
          </div>

          <div className="rounded-lg border border-ink-100 bg-ink-50/40 px-4 py-3 text-xs text-ink-600">
            <p className="font-medium text-ink-800">Azure portal setup</p>
            <ul className="mt-2 list-disc space-y-1 pl-4">
              <li>Register a multi-tenant app (Accounts in any organizational directory).</li>
              <li>
                Redirect URI (Web):{" "}
                <code className="rounded bg-white px-1 py-0.5 text-ink-800">
                  {azureRedirectUri || azureAd.suggested_redirect_uri || "https://your-domain/api/auth/azure/callback"}
                </code>
              </li>
              <li>Copy the Application (client) ID and create a client secret below.</li>
            </ul>
          </div>

          <Field label="Client ID">
            <input
              className="input font-mono text-xs"
              value={azureClientId}
              onChange={(e) => setAzureClientId(e.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
            />
          </Field>

          <Field label="Client secret">
            <div className="flex gap-2">
              <input
                className="input font-mono text-xs"
                type="password"
                value={azureClientSecret}
                onChange={(e) => setAzureClientSecret(e.target.value)}
                placeholder={azureAd.configured ? azureAd.client_secret_masked || "••••••••" : "Enter client secret"}
              />
              {azureAd.configured && (
                <button className="btn-danger whitespace-nowrap" onClick={clearAzureSecret}>
                  Remove
                </button>
              )}
            </div>
            <p className="mt-1 text-xs text-ink-400">Stored encrypted. Leave empty to keep the current secret.</p>
          </Field>

          <Field label="Authority">
            <input
              className="input font-mono text-xs"
              value={azureAuthority}
              onChange={(e) => setAzureAuthority(e.target.value)}
              placeholder="https://login.microsoftonline.com/organizations"
            />
            <p className="mt-1 text-xs text-ink-400">
              Use <code className="text-xs">/organizations</code> for any Azure AD tenant (multi-tenant).
            </p>
          </Field>

          <Field label="Redirect URI">
            <input
              className="input font-mono text-xs"
              value={azureRedirectUri}
              onChange={(e) => setAzureRedirectUri(e.target.value)}
              placeholder={azureAd.suggested_redirect_uri || "https://your-domain/api/auth/azure/callback"}
            />
            <p className="mt-1 text-xs text-ink-400">
              Must match the redirect URI in Azure. Leave empty to use the suggested value above.
            </p>
          </Field>

          <Field label="Allowed email domains">
            <textarea
              className="input min-h-[120px] font-mono text-xs"
              value={azureDomainsText}
              onChange={(e) => setAzureDomainsText(e.target.value)}
              placeholder={"xential.nl\npartner.com"}
            />
            <p className="mt-1 text-xs text-ink-400">
              One domain per line (or comma-separated). Users from other Azure AD tenants can sign in, but only if
              their email domain is listed here.
            </p>
          </Field>

          {!azureAd.configured && (
            <p className="text-sm text-amber-700">
              Enter client ID and client secret, save, then enable Microsoft sign-in.
            </p>
          )}
        </div>
      </Modal>
    </div>
  );
}
