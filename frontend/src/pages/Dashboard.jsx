import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { apiError, isUnauthorized } from "../api/client";
import { Icon } from "../components/icons";
import { CompanyLogo, PageLoader } from "../components/ui";
import { useAuth } from "../context/AuthContext";

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

function StatCard({ icon: IconCmp, label, value, sub, accent }) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2">
        <IconCmp width={15} height={15} className={accent} />
        <span className="text-xs font-medium text-ink-500">{label}</span>
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-ink-900">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-ink-400">{sub}</p>}
    </div>
  );
}

function Meter({ label, value, total, color }) {
  const pct = total ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-ink-600">{label}</span>
        <span className="font-medium text-ink-900">
          {value}
          <span className="text-ink-400">/{total}</span>
          <span className="ml-1.5 text-xs text-ink-400">{pct}%</span>
        </span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-ink-100">
        <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function BarList({ items, color }) {
  if (!items?.length) return <p className="py-6 text-center text-sm text-ink-400">No data yet.</p>;
  const max = Math.max(1, ...items.map((i) => i.count));
  return (
    <ul className="space-y-3">
      {items.map((it) => (
        <li key={it.name}>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="truncate pr-2 text-ink-700">{it.name}</span>
            <span className="font-medium text-ink-900">{it.count}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-ink-100">
            <div className={`h-full rounded-full ${color}`} style={{ width: `${(it.count / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function IntegrationRow({ icon: IconCmp, name, enabled, configured }) {
  const ok = enabled && configured;
  const label = ok ? "Active" : configured ? "Disabled" : "Not set up";
  const dot = ok ? "bg-green-500" : configured ? "bg-amber-400" : "bg-ink-300";
  const pill = ok ? "bg-green-50 text-green-700" : configured ? "bg-amber-50 text-amber-700" : "bg-ink-100 text-ink-500";
  return (
    <div className="flex items-center justify-between py-2.5">
      <div className="flex items-center gap-2.5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink-50 text-ink-500">
          <IconCmp width={16} height={16} />
        </div>
        <span className="text-sm font-medium text-ink-800">{name}</span>
      </div>
      <span className={`badge inline-flex items-center gap-1.5 ${pill}`}>
        <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
        {label}
      </span>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .get("/dashboard")
      .then((res) => setData(res.data))
      .catch((err) => {
        if (!isUnauthorized(err)) setError(apiError(err));
      });
  }, []);

  if (error) return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>;
  if (!data) return <PageLoader />;

  const firstName = user?.name?.split(" ")[0] || "there";

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="relative -mx-6 -mt-6 min-h-[220px] overflow-hidden px-6 py-8 sm:min-h-[260px] sm:px-8 sm:py-10">
        <img
          src="/images/dashboard-banner.png"
          alt=""
          aria-hidden="true"
          className="absolute inset-0 h-full w-full object-cover object-right"
        />
        <div className="pointer-events-none absolute inset-y-0 left-0 w-3/5 bg-gradient-to-r from-white/70 to-transparent" />
        <div className="relative z-10 max-w-xl">
          <p className="text-sm font-medium text-ink-500 [text-shadow:0_1px_12px_rgba(255,255,255,0.95)]">{greeting()},</p>
          <h1 className="mt-0.5 text-2xl font-semibold tracking-tight text-ink-900 [text-shadow:0_1px_12px_rgba(255,255,255,0.95)] sm:text-3xl">
            {firstName} 👋
          </h1>
          <p className="mt-2 text-sm leading-relaxed text-ink-600 [text-shadow:0_1px_10px_rgba(255,255,255,0.9)]">
            Here's what's happening across your CRM. All data lives in your own database — Apollo and
            Groq are only used when you ask.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link
              to="/companies"
              className="btn-primary inline-flex items-center gap-1.5 px-3.5 py-2 text-sm"
            >
              <Icon.Building width={16} height={16} /> View companies
            </Link>
            <Link
              to="/apollo"
              className="btn-secondary inline-flex items-center gap-1.5 px-3.5 py-2 text-sm"
            >
              <Icon.Search width={16} height={16} /> Apollo Search
            </Link>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Icon.Building}
          label="Companies"
          value={data.total_companies.toLocaleString()}
          sub={`${data.companies_with_domain.toLocaleString()} with a domain`}
          accent="text-brand-500"
        />
        <StatCard
          icon={Icon.Users}
          label="Contacts"
          value={data.total_contacts.toLocaleString()}
          sub={`${data.contacts_with_email.toLocaleString()} with an email`}
          accent="text-sky-500"
        />
        <StatCard
          icon={Icon.Sparkles}
          label="Enriched companies"
          value={data.enriched_companies.toLocaleString()}
          sub={`${data.total_companies ? Math.round((data.enriched_companies / data.total_companies) * 100) : 0}% of all companies`}
          accent="text-amber-500"
        />
        <StatCard
          icon={Icon.Sparkles}
          label="Enriched contacts"
          value={data.enriched_contacts.toLocaleString()}
          sub={`${data.total_contacts ? Math.round((data.enriched_contacts / data.total_contacts) * 100) : 0}% of all contacts`}
          accent="text-purple-500"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column */}
        <div className="space-y-6 lg:col-span-2">
          <div className="card p-5">
            <h2 className="text-sm font-semibold text-ink-900">Data quality</h2>
            <p className="mt-0.5 text-xs text-ink-400">Coverage across your records.</p>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Meter label="Companies enriched" value={data.enriched_companies} total={data.total_companies} color="bg-brand-500" />
              <Meter label="Contacts enriched" value={data.enriched_contacts} total={data.total_contacts} color="bg-purple-500" />
              <Meter label="Companies with domain" value={data.companies_with_domain} total={data.total_companies} color="bg-emerald-500" />
              <Meter label="Contacts with email" value={data.contacts_with_email} total={data.total_contacts} color="bg-sky-500" />
            </div>
          </div>

          <div className="card p-5">
            <h2 className="text-sm font-semibold text-ink-900">Top industries</h2>
            <div className="mt-4">
              <BarList items={data.top_industries} color="bg-brand-400" />
            </div>
          </div>

          <div className="card">
            <div className="flex items-center justify-between border-b border-ink-100 px-5 py-4">
              <h2 className="text-sm font-semibold text-ink-900">Recently enriched companies</h2>
              <Link to="/companies" className="text-sm font-medium text-brand-600 hover:underline">
                View all
              </Link>
            </div>
            {data.recent_enriched_companies.length === 0 ? (
              <p className="px-5 py-10 text-center text-sm text-ink-400">No enriched companies yet.</p>
            ) : (
              <ul className="divide-y divide-ink-100">
                {data.recent_enriched_companies.map((c) => (
                  <li key={c.id}>
                    <Link to={`/companies/${c.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-ink-50">
                      <CompanyLogo domain={c.domain} name={c.name} size={36} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-ink-900">{c.name}</p>
                        <p className="truncate text-xs text-ink-400">{c.domain || c.industry || "—"}</p>
                      </div>
                      <span className="whitespace-nowrap text-xs text-ink-400">{[c.city, c.country].filter(Boolean).join(", ")}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          <div className="card p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink-900">Integrations</h2>
              <Link to="/settings" className="text-sm font-medium text-brand-600 hover:underline">
                Manage
              </Link>
            </div>
            <div className="mt-2 divide-y divide-ink-100">
              <IntegrationRow icon={Icon.Bolt} name="Apollo" enabled={data.apollo_enabled} configured={data.apollo_configured} />
              <IntegrationRow icon={Icon.Wand} name="Groq AI" enabled={data.groq_enabled} configured={data.groq_configured} />
              <IntegrationRow icon={Icon.Image} name="Logokit" enabled={data.logokit_enabled} configured={data.logokit_configured} />
            </div>
          </div>

          <div className="card p-5">
            <h2 className="text-sm font-semibold text-ink-900">Top countries</h2>
            <div className="mt-4">
              <BarList items={data.top_countries} color="bg-emerald-400" />
            </div>
          </div>

          <div className="card">
            <div className="border-b border-ink-100 px-5 py-4">
              <h2 className="text-sm font-semibold text-ink-900">Recent searches</h2>
            </div>
            {data.recent_searches.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-ink-400">No searches yet.</p>
            ) : (
              <ul className="divide-y divide-ink-100">
                {data.recent_searches.map((s) => (
                  <li key={s.id} className="flex items-center justify-between px-5 py-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink-50 text-ink-500">
                        {s.query_type === "people" ? <Icon.Users width={15} height={15} /> : <Icon.Building width={15} height={15} />}
                      </div>
                      <div>
                        <p className="text-sm capitalize text-ink-800">{s.query_type === "people" ? "People" : "Companies"}</p>
                        <p className="text-xs text-ink-400">{new Date(s.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                    <span className="badge bg-ink-100 text-ink-600">{s.result_count}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
