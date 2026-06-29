/** Apollo Organization Search (/mixed_companies/search) filter fields. */

export const ORG_FILTER_FIELDS = [
  { key: "q_organization_name", label: "Company name", type: "text", placeholder: "e.g. Apollo" },
  {
    key: "organization_domains",
    label: "Domains",
    type: "list",
    placeholder: "acme.com, foo.io",
    hint: "Comma-separated. Do not include www.",
  },
  {
    key: "organization_locations",
    label: "HQ locations",
    type: "list",
    placeholder: "Netherlands, Texas, Tokyo",
  },
  {
    key: "organization_not_locations",
    label: "Exclude HQ locations",
    type: "list",
    placeholder: "China, Russia",
  },
  {
    key: "organization_num_employees_ranges",
    label: "Employee ranges",
    type: "ranges",
    placeholder: "1,10 · 11,50 · 51,200",
    hint: "Use · or ; between ranges. Each range is min,max.",
  },
  {
    key: "organization_industries",
    label: "Keyword tags / industries",
    type: "list",
    placeholder: "software, fintech, consulting",
  },
  {
    key: "organization_ids",
    label: "Organization IDs",
    type: "list",
    placeholder: "Apollo organization IDs",
  },
  {
    key: "organization_latest_funding_stage_cd",
    label: "Funding stages",
    type: "list",
    placeholder: "seed, series_a, series_b",
  },
  {
    key: "currently_using_any_of_technology_uids",
    label: "Uses any technology",
    type: "list",
    placeholder: "salesforce, google_analytics",
    hint: "Use underscores instead of spaces.",
  },
  {
    key: "currently_using_all_of_technology_uids",
    label: "Uses all technologies",
    type: "list",
    placeholder: "salesforce, hubspot",
  },
  {
    key: "currently_not_using_any_of_technology_uids",
    label: "Does not use technology",
    type: "list",
    placeholder: "wordpress_org",
  },
  { key: "revenue_range_min", label: "Min revenue", type: "number", placeholder: "500000" },
  { key: "revenue_range_max", label: "Max revenue", type: "number", placeholder: "50000000" },
  {
    key: "organization_founded_year_range_min",
    label: "Founded after (year)",
    type: "number",
    placeholder: "2010",
  },
  {
    key: "organization_founded_year_range_max",
    label: "Founded before (year)",
    type: "number",
    placeholder: "2024",
  },
  {
    key: "q_organization_job_titles",
    label: "Active job titles",
    type: "list",
    placeholder: "sales manager, research analyst",
  },
  {
    key: "organization_job_locations",
    label: "Job locations",
    type: "list",
    placeholder: "Amsterdam, Japan",
  },
  { key: "organization_num_jobs_range_min", label: "Min active jobs", type: "number", placeholder: "5" },
  { key: "organization_num_jobs_range_max", label: "Max active jobs", type: "number", placeholder: "500" },
  {
    key: "organization_job_posted_at_range_min",
    label: "Jobs posted after",
    type: "date",
    placeholder: "2025-01-01",
  },
  {
    key: "organization_job_posted_at_range_max",
    label: "Jobs posted before",
    type: "date",
    placeholder: "2025-12-31",
  },
];

/** Apollo People API Search (/mixed_people/api_search) filter fields. */

export const PEOPLE_FILTER_FIELDS = [
  {
    key: "person_titles",
    label: "Job titles",
    type: "list",
    placeholder: "Head of Sales, CTO",
  },
  {
    key: "include_similar_titles",
    label: "Include similar titles",
    type: "boolean",
    placeholder: "true",
  },
  { key: "q_keywords", label: "Keywords", type: "text", placeholder: "AI, automation" },
  {
    key: "person_seniorities",
    label: "Seniorities",
    type: "list",
    placeholder: "vp, director, manager",
    hint: "owner, founder, c_suite, partner, vp, head, director, manager, senior, entry, intern",
  },
  {
    key: "person_locations",
    label: "Person locations",
    type: "list",
    placeholder: "Netherlands, California",
  },
  {
    key: "organization_locations",
    label: "Employer HQ locations",
    type: "list",
    placeholder: "Germany, Ireland",
  },
  {
    key: "organization_domains",
    label: "Employer domains",
    type: "list",
    placeholder: "acme.com, apollo.io",
  },
  { key: "q_organization_name", label: "Employer name", type: "text", placeholder: "Acme Corp" },
  {
    key: "contact_email_status",
    label: "Email status",
    type: "list",
    placeholder: "verified, likely to engage",
    hint: "verified, unverified, likely to engage, unavailable",
  },
  {
    key: "organization_ids",
    label: "Organization IDs",
    type: "list",
    placeholder: "Apollo organization IDs",
  },
  {
    key: "organization_num_employees_ranges",
    label: "Employer employee ranges",
    type: "ranges",
    placeholder: "1,10 · 11,50",
  },
  { key: "revenue_range_min", label: "Employer min revenue", type: "number", placeholder: "500000" },
  { key: "revenue_range_max", label: "Employer max revenue", type: "number", placeholder: "50000000" },
  {
    key: "currently_using_any_of_technology_uids",
    label: "Employer uses any technology",
    type: "list",
    placeholder: "salesforce, google_analytics",
  },
  {
    key: "currently_using_all_of_technology_uids",
    label: "Employer uses all technologies",
    type: "list",
    placeholder: "salesforce, hubspot",
  },
  {
    key: "currently_not_using_any_of_technology_uids",
    label: "Employer does not use technology",
    type: "list",
    placeholder: "wordpress_org",
  },
  {
    key: "q_organization_job_titles",
    label: "Employer active job titles",
    type: "list",
    placeholder: "sales manager",
  },
  {
    key: "organization_job_locations",
    label: "Employer job locations",
    type: "list",
    placeholder: "Atlanta, Japan",
  },
  { key: "organization_num_jobs_range_min", label: "Employer min active jobs", type: "number", placeholder: "5" },
  { key: "organization_num_jobs_range_max", label: "Employer max active jobs", type: "number", placeholder: "500" },
  {
    key: "organization_job_posted_at_range_min",
    label: "Employer jobs posted after",
    type: "date",
    placeholder: "2025-01-01",
  },
  {
    key: "organization_job_posted_at_range_max",
    label: "Employer jobs posted before",
    type: "date",
    placeholder: "2025-12-31",
  },
];

/** People filters when searching contacts within a saved company research (domains are automatic). */

export const PEOPLE_CONTACT_FIELDS = PEOPLE_FILTER_FIELDS.filter(
  (field) => !["organization_domains", "organization_ids"].includes(field.key)
);

export function emptyFilters(fields) {
  return Object.fromEntries(fields.map((f) => [f.key, f.type === "boolean" ? "" : ""]));
}

export function splitList(value) {
  return (value || "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

export function buildCriteria(filters, fields) {
  const out = {};
  for (const field of fields) {
    const value = filters[field.key];
    if (value === undefined || value === null || value === "") continue;

    if (field.type === "list") {
      const items = splitList(value);
      if (items.length) out[field.key] = items;
      continue;
    }

    if (field.type === "boolean") {
      const lowered = String(value).trim().toLowerCase();
      if (lowered === "true" || lowered === "false") {
        out[field.key] = lowered === "true";
      }
      continue;
    }

    if (field.type === "number") {
      const num = Number(value);
      if (!Number.isNaN(num)) out[field.key] = num;
      continue;
    }

    if (field.type === "ranges") {
      out[field.key] = value;
      continue;
    }

    out[field.key] = value;
  }
  return out;
}

export function slug(name) {
  return (name || "research").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "research";
}
