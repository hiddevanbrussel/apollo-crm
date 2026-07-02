import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import api, { apiError, notifyApiError } from "../api/client";
import { Icon } from "./icons";
import { Spinner } from "./ui";
import { useToast } from "../context/ToastContext";

const SUGGESTIONS = [
  "How many companies do we have, and how many are enriched?",
  "Top 20 grootste energiemaatschappijen in Nederland - maak een recordset",
  "Zoek 50 fintech bedrijven in Belgie met 50+ medewerkers",
  "Contacts with a verified email",
];

const MD_COMPONENTS = {
  p: (p) => <p className="mb-2 last:mb-0" {...p} />,
  strong: (p) => <strong className="font-semibold text-ink-900" {...p} />,
  em: (p) => <em className="italic" {...p} />,
  a: (p) => <a className="text-brand-600 underline" target="_blank" rel="noreferrer" {...p} />,
  ul: (p) => <ul className="mb-2 list-disc space-y-1 pl-5 marker:text-ink-400 last:mb-0" {...p} />,
  ol: (p) => <ol className="mb-2 list-decimal space-y-1 pl-5 marker:text-ink-400 last:mb-0" {...p} />,
  li: (p) => <li className="leading-relaxed" {...p} />,
  h1: (p) => <h1 className="mb-2 mt-1 text-base font-semibold text-ink-900" {...p} />,
  h2: (p) => <h2 className="mb-2 mt-1 text-sm font-semibold text-ink-900" {...p} />,
  h3: (p) => <h3 className="mb-1 mt-1 text-sm font-semibold text-ink-900" {...p} />,
  blockquote: (p) => <blockquote className="mb-2 border-l-2 border-ink-200 pl-3 text-ink-500" {...p} />,
  hr: () => <hr className="my-3 border-ink-100" />,
  code: ({ className, children, ...props }) => {
    const isBlock = String(className || "").includes("language-");
    if (isBlock) {
      return (
        <code className={`font-mono ${className || ""}`} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-ink-200/60 px-1 py-0.5 font-mono text-[0.85em] text-ink-800" {...props}>
        {children}
      </code>
    );
  },
  pre: (p) => <pre className="mb-2 overflow-x-auto rounded-lg bg-ink-900 p-3 text-xs text-ink-100 last:mb-0" {...p} />,
  table: (p) => (
    <div className="mb-2 overflow-x-auto last:mb-0">
      <table className="w-full border-collapse text-xs" {...p} />
    </div>
  ),
  th: (p) => <th className="border border-ink-200 bg-ink-50 px-2 py-1 text-left font-semibold text-ink-700" {...p} />,
  td: (p) => <td className="border border-ink-200 px-2 py-1 text-ink-700" {...p} />,
};

function Markdown({ children }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
      {children}
    </ReactMarkdown>
  );
}

function ResultTable({ columns, rows }) {
  if (!columns?.length || !rows?.length) return null;
  return (
    <div className="mt-3 overflow-x-auto rounded-lg border border-ink-100">
      <table className="w-full text-xs">
        <thead className="bg-ink-50/70">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-3 py-2 text-left font-semibold text-ink-600">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-100">
          {rows.slice(0, 20).map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-1.5 text-ink-700">
                  {cell === null || cell === undefined
                    ? "—"
                    : typeof cell === "object"
                    ? JSON.stringify(cell)
                    : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 20 && (
        <p className="px-3 py-2 text-[11px] text-ink-400">Showing 20 of {rows.length} rows.</p>
      )}
    </div>
  );
}

function ResearchPlanCard({ plan, creating, setCreating }) {
  const navigate = useNavigate();
  const toast = useToast();

  const review = () => {
    navigate("/research", {
      state: {
        mode: plan.query_type === "people" ? "people" : "organizations",
        name: plan.name,
        prefilled: plan.criteria,
        maxRecords: plan.max_records,
      },
    });
  };

  const create = async () => {
    const creditNote = plan.uses_apollo_credits
      ? "Company searches use Apollo credits."
      : "People search does not consume Apollo credits.";
    if (!confirm(`Recordset "${plan.name}" aanmaken met max ${plan.max_records} records? ${creditNote}`)) return;

    setCreating(true);
    try {
      const { data } = await api.post("/ai/research/create", {
        name: plan.name,
        query_type: plan.query_type,
        criteria: plan.criteria,
        max_records: plan.max_records,
        sort_by: plan.sort_by,
      });
      toast.success(`Recordset aangemaakt met ${data.result_count} records.`);
      navigate(`/research/${data.id}`);
    } catch (err) {
      notifyApiError(toast, err);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="mt-3 rounded-xl border border-brand-200 bg-brand-50/40 p-3 text-xs">
      <p className="font-semibold text-ink-900">{plan.name}</p>
      <p className="mt-1 text-ink-600">
        {plan.query_type === "people" ? "People" : "Companies"} · max {plan.max_records} records
        {plan.sort_by === "employee_count_desc" ? " · gesorteerd op medewerkers" : null}
        {plan.sort_by === "revenue_desc" ? " · gesorteerd op omzet" : null}
      </p>
      {plan.filter_preview?.length ? (
        <ul className="mt-2 space-y-1 text-ink-600">
          {plan.filter_preview.map((f) => (
            <li key={f.key}>
              <span className="text-ink-400">{f.label}:</span> {f.value}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className="btn-primary px-2.5 py-1 text-xs" onClick={create} disabled={creating}>
          {creating ? <Spinner className="h-3.5 w-3.5 border-white/40 border-t-white" /> : <Icon.Sparkles width={14} height={14} />}
          Maak recordset
        </button>
        <button type="button" className="btn-secondary px-2.5 py-1 text-xs" onClick={review} disabled={creating}>
          Bekijk filters
        </button>
      </div>
    </div>
  );
}

function AssistantMessage({ msg, creatingPlanId, setCreatingPlanId }) {
  const [showData, setShowData] = useState(false);
  const planKey = msg.research_plan ? `${msg.research_plan.name}-${msg.research_plan.max_records}` : null;
  const creating = creatingPlanId === planKey;

  return (
    <div className="flex gap-2.5">
      <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent-400 to-accent-600 text-white">
        <Icon.Sparkles width={14} height={14} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="rounded-2xl rounded-tl-sm bg-ink-50 px-3.5 py-2.5 text-sm leading-relaxed text-ink-800">
          <Markdown>{msg.content}</Markdown>
        </div>
        {msg.research_plan ? (
          <ResearchPlanCard
            plan={msg.research_plan}
            creating={creating}
            setCreating={(v) => setCreatingPlanId(v ? planKey : null)}
          />
        ) : null}
        {(msg.sql || msg.row_count > 0) && (
          <div className="mt-1.5">
            <button
              className="text-xs font-medium text-ink-400 hover:text-ink-600"
              onClick={() => setShowData((v) => !v)}
            >
              {showData ? "Hide" : "Show"} data{msg.row_count ? ` (${msg.row_count} rows)` : ""}
            </button>
            {showData && (
              <div className="mt-2">
                {msg.sql && (
                  <pre className="overflow-x-auto rounded-lg bg-ink-900 p-3 text-[11px] text-ink-100">{msg.sql}</pre>
                )}
                <ResultTable columns={msg.columns} rows={msg.rows} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AiChat() {
  const toast = useToast();
  const [status, setStatus] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [creatingPlanId, setCreatingPlanId] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    api
      .get("/ai/status")
      .then((res) => setStatus(res.data))
      .catch(() => setStatus({ enabled: false, configured: false, message: "Could not load status." }));
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const ready = status?.enabled && status?.configured;

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);
    try {
      const { data } = await api.post("/ai/ask", { question });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sql: data.sql,
          columns: data.columns,
          rows: data.rows,
          row_count: data.row_count,
          research_plan: data.research_plan,
        },
      ]);
    } catch (err) {
      const message = apiError(err, "Something went wrong.");
      if (message) {
        notifyApiError(toast, err);
        setMessages((prev) => [...prev, { role: "assistant", content: `Sorry — ${message}` }]);
      }
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    send();
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      {!ready && status && (
        <div className="m-3 mb-0 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {status.message || "The assistant needs the Groq integration."}{" "}
          <Link to="/settings" className="font-medium underline">
            Open Settings
          </Link>
        </div>
      )}

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="rounded-2xl border border-dashed border-ink-200 p-4 text-center">
            <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
              <Icon.Chat width={18} height={18} />
            </div>
            <p className="text-xs text-ink-500">
              Vraag iets over je CRM-data, of laat een Market Research recordset plannen (bijv. top 20 energiebedrijven).
            </p>
            <div className="mt-3 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => ready && send(s)}
                  disabled={!ready}
                  className="rounded-full border border-ink-200 bg-white px-2.5 py-1 text-[11px] text-ink-600 hover:border-brand-300 hover:text-brand-700 disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) =>
          msg.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-brand-600 px-3.5 py-2 text-sm text-white">
                {msg.content}
              </div>
            </div>
          ) : (
            <AssistantMessage key={i} msg={msg} creatingPlanId={creatingPlanId} setCreatingPlanId={setCreatingPlanId} />
          )
        )}

        {loading && (
          <div className="flex items-center gap-2.5 text-sm text-ink-400">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-accent-400 to-accent-600 text-white">
              <Icon.Sparkles width={14} height={14} />
            </div>
            <span className="flex items-center gap-2">
              <Spinner className="h-4 w-4" /> Thinking…
            </span>
          </div>
        )}
      </div>

      <form onSubmit={onSubmit} className="flex items-end gap-2 border-t border-ink-100 p-3">
        <textarea
          className="input min-h-[42px] flex-1 resize-none"
          rows={1}
          placeholder={ready ? "Vraag over CRM-data of beschrijf een recordset..." : "Enable Groq in Settings to chat"}
          value={input}
          disabled={!ready || loading}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button type="submit" className="btn-primary h-[42px] px-3" disabled={!ready || loading || !input.trim()} title="Send">
          {loading ? <Spinner className="h-4 w-4 border-white/40 border-t-white" /> : <Icon.Send width={18} height={18} />}
        </button>
      </form>
    </div>
  );
}
