import { useEffect, useRef, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { Icon } from "../components/icons";
import { PageLoader } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function LoginAzureCallback() {
  const { user, loading, completeSession } = useAuth();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState(null);
  const [finishing, setFinishing] = useState(false);
  const handledRef = useRef(false);

  useEffect(() => {
    if (handledRef.current) return;

    const err = searchParams.get("error");
    if (err) {
      handledRef.current = true;
      setError(err);
      return;
    }

    const token = searchParams.get("token");
    if (!token) {
      if (!loading) {
        handledRef.current = true;
        setError("No sign-in token received.");
      }
      return;
    }

    handledRef.current = true;
    setFinishing(true);
    completeSession(token).catch(() => {
      setFinishing(false);
      setError("Could not complete Microsoft sign-in.");
    });
  }, [searchParams, loading, completeSession]);

  if (user) return <Navigate to="/" replace />;
  if (finishing || (loading && !error)) return <PageLoader />;

  return (
    <div className="flex min-h-full items-center justify-center bg-canvas px-4 py-12">
      <div className="w-full max-w-md card p-7 text-center">
        <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent-400 to-accent-600 text-white">
          <Icon.Sparkles width={22} height={22} />
        </div>
        {error ? (
          <>
            <h1 className="text-lg font-semibold text-ink-900">Sign-in failed</h1>
            <p className="mt-2 text-sm text-red-700">{error}</p>
            <a href="/login" className="btn-primary mt-5 inline-flex">
              Back to sign in
            </a>
          </>
        ) : (
          <>
            <h1 className="text-lg font-semibold text-ink-900">Completing sign-in</h1>
            <p className="mt-2 text-sm text-ink-500">Please wait while we finish Microsoft sign-in.</p>
          </>
        )}
      </div>
    </div>
  );
}
