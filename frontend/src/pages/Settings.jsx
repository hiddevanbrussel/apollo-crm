import { useEffect, useState } from "react";
import api, { apiError } from "../api/client";
import { resetLogokit } from "../api/logokit";
import { Icon } from "../components/icons";
import { Field, Modal, PageLoader, Spinner } from "../components/ui";
import { CompanyImportPanel, ContactImportPanel } from "../components/ImportPanel";
import { useToast } from "../context/ToastContext";

const SUB_TABS = [
  { id: "integrations", label: "Integrations" },
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

  // Logokit state
  const [logokit, setLogokit] = useState(null);
  const [logokitToken, setLogokitToken] = useState("");
  const [logokitUrl, setLogokitUrl] = useState("");
  const [logokitSaving, setLogokitSaving] = useState(false);
  const [logokitTesting, setLogokitTesting] = useState(false);
  const [logokitTest, setLogokitTest] = useState(null);
  const [apolloReady, setApolloReady] = useState(false);

  const load = async () => {
    try {
      const [{ data: a }, { data: g }, { data: l }] = await Promise.all([
        api.get("/settings/apollo"),
        api.get("/settings/groq"),
        api.get("/settings/logokit"),
      ]);
      setApollo(a);
      setApolloUrl(a.base_url);
      setGroq(g);
      setGroqUrl(g.base_url);
      setGroqModel(g.model);
      setLogokit(l);
      setLogokitUrl(l.base_url);
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

  if (!apollo || !groq || !logokit) return <PageLoader />;

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
              description="AI domain finder that searches the web for a company's official website using its name and country."
              configured={groq.configured}
              enabled={groq.enabled}
              onToggle={toggleGroq}
              onView={() => {
                setGroqTest(null);
                setDetail("groq");
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
          </div>
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
    </div>
  );
}
