import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import api, { apiError } from "../api/client";
import { Icon } from "../components/icons";
import { Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";

function MicrosoftIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 21 21" aria-hidden="true">
      <rect x="1" y="1" width="9" height="9" fill="#f25022" />
      <rect x="11" y="1" width="9" height="9" fill="#7fba00" />
      <rect x="1" y="11" width="9" height="9" fill="#00a4ef" />
      <rect x="11" y="11" width="9" height="9" fill="#ffb900" />
    </svg>
  );
}

export default function Login() {
  const { user, login } = useAuth();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [azure, setAzure] = useState({ enabled: false, configured: false });

  useEffect(() => {
    api
      .get("/auth/azure/config")
      .then(({ data }) => setAzure(data))
      .catch(() => setAzure({ enabled: false, configured: false }));
  }, []);

  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(form.email, form.password);
    } catch (err) {
      setError(apiError(err, "Sign in failed."));
    } finally {
      setLoading(false);
    }
  };

  const signInWithMicrosoft = () => {
    window.location.href = "/auth/azure/login";
  };

  return (
    <div className="flex min-h-full items-center justify-center bg-canvas px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent-400 to-accent-600 text-white shadow-sm">
            <Icon.Sparkles width={22} height={22} />
          </div>
          <span className="text-xl font-semibold tracking-tight text-ink-900">Apollo CRM</span>
        </div>

        <div className="card p-7">
          <h1 className="text-lg font-semibold text-ink-900">Sign in</h1>
          <p className="mt-1 text-sm text-ink-500">Sign in to manage your CRM.</p>

          {error && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {azure.enabled && (
            <>
              <button
                type="button"
                className="btn-secondary mt-5 flex w-full items-center justify-center gap-2"
                onClick={signInWithMicrosoft}
              >
                <MicrosoftIcon />
                Sign in with Microsoft
              </button>
              <div className="my-5 flex items-center gap-3">
                <div className="h-px flex-1 bg-ink-200" />
                <span className="text-xs text-ink-400">or use email</span>
                <div className="h-px flex-1 bg-ink-200" />
              </div>
            </>
          )}

          <form onSubmit={submit} className={azure.enabled ? "space-y-4" : "mt-5 space-y-4"}>
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                className="input"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="label">Password</label>
              <input
                type="password"
                className="input"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
              />
            </div>
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : null}
              Sign in
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-ink-400">
          {azure.enabled
            ? "Microsoft sign-in is available for approved email domains."
            : "Contact an administrator if you need an account."}
        </p>
      </div>
    </div>
  );
}
