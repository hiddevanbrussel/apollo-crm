import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api, { apiError } from "../api/client";
import { Icon } from "../components/icons";
import { CompanyLogo, EmptyState, PageLoader, Pagination } from "../components/ui";
import { slug } from "../constants/apolloSearchFields";
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
  { key: "seniority", label: "Seniority" },
  { key: "organization_name", label: "Company" },
  { key: "organization_domain", label: "Domain" },
  { key: "city", label: "City" },
  { key: "country", label: "Country" },
  { key: "linkedin_url", label: "LinkedIn" },
];

function CellValue({ column, row, isOrg }) {
  const value = row[column.key];
  if (value === null || value === undefined || value === "") return "—";

  if (column.key === "name" && isOrg) {
    return (
      <div className="flex items-center gap-3">
        <CompanyLogo domain={row.domain} name={value} size={32} />
        <span className="font-medium text-ink-900">{value}</span>
      </div>
    );
  }

  if (column.key === "website" || column.key === "linkedin_url") {
    const href = column.key === "website" && !String(value).startsWith("http") ? `https://${value}` : value;
    return (
      <a href={href} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">
        {String(value).replace(/^https?:\/\//, "")}
      </a>
    );
  }

  return String(value);
}

export default function ResearchDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 20;

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
  }, [id, page, toast]);

  useEffect(() => {
    load();
  }, [load]);

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
    if (!confirm(`Delete research "${data?.search?.name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/research/searches/${id}`);
      toast.success("Research deleted.");
      navigate("/research");
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const startPeopleSearch = async () => {
    try {
      const { data: res } = await api.get(`/research/searches/${id}/domains`);
      const domains = res.domains || [];
      if (!domains.length) {
        toast.info("No domains in this dataset to search people for.");
        return;
      }
      navigate("/research", {
        state: {
          mode: "people",
          prefilled: { organization_domains: domains.slice(0, 1000).join(", ") },
          name: `${data.search.name} — contacts`,
        },
      });
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const search = data?.search;
  const isOrg = search?.query_type === "organizations";
  const columns = isOrg ? ORG_COLUMNS : PEOPLE_COLUMNS;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/research" className="mb-2 inline-flex items-center gap-1 text-sm text-ink-500 hover:text-brand-600">
            <Icon.ChevronRight width={16} height={16} className="rotate-180" /> Back to Market Research
          </Link>
          <h1 className="text-xl font-semibold text-ink-900">{search?.name || "Research"}</h1>
          <p className="text-sm text-ink-500">
            {isOrg ? "Companies" : "People"} · {search?.result_count ?? 0} records captured
            {search?.total_available ? ` of ${search.total_available} available` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isOrg && (
            <button
              className="btn-secondary"
              onClick={startPeopleSearch}
              title="Start a people search using domains from this dataset"
            >
              <Icon.Users width={18} height={18} /> Find people
            </button>
          )}
          <button className="btn-secondary" onClick={() => exportSearch("csv")}>
            <Icon.Download width={18} height={18} /> CSV
          </button>
          <button className="btn-secondary" onClick={() => exportSearch("xlsx")}>
            <Icon.Download width={18} height={18} /> Excel
          </button>
          <button className="btn-secondary text-red-600 hover:border-red-200 hover:bg-red-50" onClick={remove}>
            <Icon.Trash width={18} height={18} /> Delete
          </button>
        </div>
      </div>

      <div className="card">
        {loading ? (
          <PageLoader />
        ) : !data?.items?.length ? (
          <EmptyState title="No records" description="This research dataset is empty." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b border-ink-100 bg-ink-50/50">
                  <tr>
                    {columns.map((col) => (
                      <th key={col.key} className="table-th">
                        {col.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {data.items.map((row, i) => (
                    <tr key={i} className="hover:bg-ink-50/60">
                      {columns.map((col) => (
                        <td key={col.key} className="table-td">
                          <CellValue column={col} row={row} isOrg={isOrg} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="border-t border-ink-100 px-4 py-3">
              <Pagination page={page} pageSize={pageSize} total={data.total} onPage={setPage} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
