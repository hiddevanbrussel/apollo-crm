import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import AiAssistantWidget from "./AiAssistantWidget";
import { Icon } from "./icons";

const NAV_MAIN = [
  { to: "/", label: "Dashboard", icon: Icon.Dashboard, end: true },
  { to: "/apollo", label: "Apollo Search", icon: Icon.Search },
  { to: "/research", label: "Market Research", icon: Icon.Compass },
];

const NAV_RECORDS = [
  { to: "/companies", label: "Companies", icon: Icon.Building },
  { to: "/contacts", label: "Contacts", icon: Icon.Users },
];

const NAV_FOOTER = [
  { to: "/users", label: "Users", icon: Icon.Users, adminOnly: true },
  { to: "/settings", label: "Settings", icon: Icon.Settings, adminOnly: true },
];

function NavGroup({ items, isAdmin }) {
  const visible = items.filter((item) => !item.adminOnly || isAdmin);
  if (!visible.length) return null;
  return (
    <div className="space-y-0.5">
      {visible.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : "nav-item-idle"}`}
        >
          <item.icon width={18} height={18} />
          {item.label}
        </NavLink>
      ))}
    </div>
  );
}

export default function Layout() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  const onSearch = (e) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/companies?search=${encodeURIComponent(query.trim())}`);
    }
  };

  const initials =
    user?.name
      ?.split(" ")
      .map((p) => p[0])
      .slice(0, 2)
      .join("")
      .toUpperCase() || "U";

  return (
    <div className="h-full bg-canvas">
      <div className="flex h-full w-full overflow-hidden bg-white">
        {/* Sidebar */}
        <aside className="flex w-64 flex-shrink-0 flex-col border-r border-ink-200 bg-ink-50">
          <div className="flex items-center gap-2.5 px-5 py-5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent-400 to-accent-600 text-white shadow-sm">
              <Icon.Sparkles width={18} height={18} />
            </div>
            <span className="text-[15px] font-semibold tracking-tight text-ink-900">Apollo CRM</span>
          </div>

          <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-2">
            <NavGroup items={NAV_MAIN} />
            <div>
              <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                Records
              </p>
              <NavGroup items={NAV_RECORDS} />
            </div>
          </nav>

          <div className="space-y-3 px-3 pb-3">
            <NavGroup items={NAV_FOOTER} isAdmin={isAdmin} />

            <div className="rounded-xl border border-ink-200 bg-white p-3">
              <div className="mb-2 flex items-center justify-between text-xs text-ink-500">
                <span>{isAdmin ? "Administrator" : "User"}</span>
                <span className="badge bg-green-50 text-green-700">Active</span>
              </div>
              <p className="text-[11px] leading-relaxed text-ink-400">
                Your data lives in your own database. Apollo is only used on request.
              </p>
            </div>

            <div className="flex items-center gap-3 rounded-xl border border-ink-200 bg-white px-2.5 py-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">
                {initials}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink-900">{user?.name}</p>
                <p className="truncate text-xs text-ink-400">{user?.email}</p>
              </div>
              <button className="btn-ghost px-2 py-1.5" onClick={logout} title="Log out">
                <Icon.Logout width={18} height={18} />
              </button>
            </div>
          </div>
        </aside>

        {/* Main */}
        <div className="flex min-w-0 flex-1 flex-col bg-white">
          <header className="flex h-16 flex-shrink-0 items-center gap-4 border-b border-ink-200 px-6">
            <form onSubmit={onSearch} className="relative w-full max-w-sm">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400">
                <Icon.Search width={18} height={18} />
              </span>
              <input
                className="input bg-ink-50 pl-10"
                placeholder="Search companies…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </form>
            <div className="ml-auto flex items-center gap-3 text-sm text-ink-500">
              <span className="hidden sm:inline">Welcome,</span>
              <span className="font-medium text-ink-800">{user?.name?.split(" ")[0]}</span>
            </div>
          </header>

          <main className="flex-1 overflow-y-auto px-6 py-6">
            <Outlet />
          </main>
        </div>
      </div>

      <AiAssistantWidget />
    </div>
  );
}
