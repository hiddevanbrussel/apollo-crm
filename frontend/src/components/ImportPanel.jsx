import { useRef, useState } from "react";
import api, { apiError } from "../api/client";
import { Icon } from "./icons";
import { Spinner } from "./ui";
import { useToast } from "../context/ToastContext";

function ImportResultSummary({ result, type }) {
  if (!result) return null;
  return (
    <div className="space-y-2 rounded-lg border border-ink-100 bg-white p-4">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        <span className="text-green-700">
          Created: <strong>{result.created}</strong>
        </span>
        {type === "companies" && (
          <span className="text-brand-700">
            Updated: <strong>{result.updated}</strong>
          </span>
        )}
        <span className="text-ink-500">
          {type === "contacts" ? "Skipped (existing)" : "Skipped"}:{" "}
          <strong>{result.skipped_duplicates}</strong>
        </span>
        {type === "companies" && result.enriched > 0 && (
          <span className="text-purple-700">
            Enriched: <strong>{result.enriched}</strong>
          </span>
        )}
        {type === "contacts" && result.domains_added > 0 && (
          <span className="text-teal-700">
            Domains added: <strong>{result.domains_added}</strong>
          </span>
        )}
        {type === "contacts" && result.skipped_apollo > 0 && (
          <span className="text-amber-700">
            Skipped (Apollo): <strong>{result.skipped_apollo}</strong>
          </span>
        )}
        <span className="text-ink-500">
          Total rows: <strong>{result.total_rows}</strong>
        </span>
      </div>
      {result.extra_columns?.length > 0 && (
        <p className="text-xs text-ink-400">Stored as extra data: {result.extra_columns.join(", ")}</p>
      )}
      {result.errors?.length > 0 && (
        <ul className="mt-2 max-h-32 list-disc overflow-y-auto pl-5 text-xs text-amber-700">
          {result.errors.map((err, i) => (
            <li key={i}>{err}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function CompanyImportPanel({ apolloReady = false }) {
  const toast = useToast();
  const fileInputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);
  const [enrichOnImport, setEnrichOnImport] = useState(false);

  const runImport = async () => {
    if (!file) {
      toast.info("Select a file first.");
      return;
    }
    setImporting(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("enrich", enrichOnImport ? "true" : "false");
      const { data } = await api.post("/companies/import", fd);
      setResult(data);
      toast.success(
        `${data.created} created, ${data.updated} updated${data.enriched ? `, ${data.enriched} enriched` : ""}.`
      );
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="card flex flex-col p-5">
      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-ink-200 bg-brand-50 text-brand-600">
          <Icon.Building width={18} height={18} />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-ink-900">Import companies</h3>
          <p className="mt-0.5 text-sm text-ink-500">Step 1 — upload your company spreadsheet.</p>
        </div>
      </div>

      <div className="mb-4 rounded-lg border border-ink-100 bg-ink-50/60 p-3 text-sm text-ink-600">
        Required: <code className="rounded bg-white px-1 text-xs">customer_name</code>. Also recognized:{" "}
        <code className="rounded bg-white px-1 text-xs">Country</code>,{" "}
        <code className="rounded bg-white px-1 text-xs">domain</code>,{" "}
        <code className="rounded bg-white px-1 text-xs">Tier</code>,{" "}
        <code className="rounded bg-white px-1 text-xs">Revenue 2025</code>,{" "}
        <code className="rounded bg-white px-1 text-xs">Sector_confidence</code>,{" "}
        <code className="rounded bg-white px-1 text-xs">Partner_status</code>.
        Countries are normalized on import (e.g. Brasil → Brazil, The Netherlands → Netherlands).
        Other columns are stored as extra data.
      </div>

      <div
        className="mb-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-ink-200 px-4 py-8 text-center hover:border-brand-300 hover:bg-brand-50/30"
        onClick={() => fileInputRef.current?.click()}
      >
        <Icon.Upload width={24} height={24} className="text-ink-400" />
        <p className="mt-2 text-sm font-medium text-ink-800">{file ? file.name : "Choose .xlsx or .csv"}</p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xlsm,.csv"
          className="hidden"
          onChange={(e) => {
            setFile(e.target.files?.[0] || null);
            setResult(null);
          }}
        />
      </div>

      {apolloReady && (
        <label className="mb-4 flex cursor-pointer items-start gap-3 rounded-lg border border-ink-100 p-3 hover:bg-ink-50/60">
          <input
            type="checkbox"
            className="mt-0.5 h-4 w-4 rounded border-ink-300"
            checked={enrichOnImport}
            onChange={(e) => setEnrichOnImport(e.target.checked)}
          />
          <span className="text-sm text-ink-700">
            Enrich via Apollo after import
            <span className="block text-xs text-ink-400">Uses Apollo credits per company with a domain.</span>
          </span>
        </label>
      )}

      <button className="btn-primary w-full" onClick={runImport} disabled={importing || !file}>
        {importing && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Import companies
      </button>

      {result && (
        <div className="mt-4">
          <ImportResultSummary result={result} type="companies" />
        </div>
      )}
    </div>
  );
}

export function ContactImportPanel() {
  const toast = useToast();
  const fileInputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);

  const runImport = async () => {
    if (!file) {
      toast.info("Select a file first.");
      return;
    }
    setImporting(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/contacts/import", fd);
      setResult(data);
      toast.success(
        `${data.created} created` +
          (data.skipped_duplicates ? `, ${data.skipped_duplicates} skipped (already exist)` : "") +
          (data.skipped_apollo ? `, ${data.skipped_apollo} skipped (Apollo)` : "") +
          "."
      );
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="card flex flex-col p-5">
      <div className="mb-4 flex items-start gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-ink-200 bg-green-50 text-green-700">
          <Icon.Users width={18} height={18} />
        </div>
        <div>
          <h3 className="text-sm font-semibold text-ink-900">Import contacts</h3>
          <p className="mt-0.5 text-sm text-ink-500">Step 2 — link people to imported companies.</p>
        </div>
      </div>

      <div className="mb-4 rounded-lg border border-ink-100 bg-ink-50/60 p-3 text-sm text-ink-600">
        Required: <code className="rounded bg-white px-1 text-xs">customer_name</code> (must match a company name)
        plus at least one of first_name, last_name, full_name or email. Email domains are added to the company
        automatically (multiple domains per company). Contacts get source <strong>IMPORT</strong>.
        Existing contacts are never overwritten — duplicates are skipped.
      </div>

      <div
        className="mb-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-ink-200 px-4 py-8 text-center hover:border-brand-300 hover:bg-brand-50/30"
        onClick={() => fileInputRef.current?.click()}
      >
        <Icon.Upload width={24} height={24} className="text-ink-400" />
        <p className="mt-2 text-sm font-medium text-ink-800">{file ? file.name : "Choose .xlsx or .csv"}</p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xlsm,.csv"
          className="hidden"
          onChange={(e) => {
            setFile(e.target.files?.[0] || null);
            setResult(null);
          }}
        />
      </div>

      <button className="btn-primary w-full" onClick={runImport} disabled={importing || !file}>
        {importing && <Spinner className="h-4 w-4 border-white/40 border-t-white" />} Import contacts
      </button>

      {result && (
        <div className="mt-4">
          <ImportResultSummary result={result} type="contacts" />
        </div>
      )}
    </div>
  );
}
