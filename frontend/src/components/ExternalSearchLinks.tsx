import { LEVEL_LABELS } from "@/types";

interface ExternalSearchLinksProps {
  roles: string[];
  levels: string[];
}

// LinkedIn and Indeed have no legitimate public API for job listings as of
// 2026 (LinkedIn: ToS-prohibited scraping; Indeed: Publisher API shut down
// in 2023, XML feeds being retired through 2026) -- real ingestion isn't an
// option for either. This is the honest ceiling: generated search links the
// user opens themselves, built from whatever Role/Level filters are
// already active above instead of a separate free-text box to fill in.
const FIELD_SEARCH_TERMS: Record<string, string> = {
  "software-engineering": '"software engineer"',
  "data-ml": '("data engineer" OR "machine learning engineer")',
  "devops-sre": '("devops engineer" OR "site reliability engineer")',
  qa: '("qa engineer" OR "test engineer")',
  mobile: '("mobile engineer" OR "ios engineer" OR "android engineer")',
  systems: '("systems engineer" OR "embedded engineer")',
  security: '"security engineer"',
};

const LEVEL_SEARCH_TERMS: Record<string, string> = {
  intern: '(intern OR internship OR "co-op")',
  "new-grad": '("new grad" OR "new graduate" OR "entry level" OR "early career")',
  mid: "",
  senior: "senior",
  staff: "staff",
  principal: "(principal OR distinguished)",
};

const DEFAULT_ROLE_TERM = '("software engineer" OR engineer)';
const DEFAULT_LEVELS = ["new-grad", "intern"];

function buildRoleTerm(roles: string[]): string {
  const terms = roles.map((r) => FIELD_SEARCH_TERMS[r]).filter(Boolean);
  if (terms.length === 0) return DEFAULT_ROLE_TERM;
  return terms.length === 1 ? (terms[0] ?? DEFAULT_ROLE_TERM) : `(${terms.join(" OR ")})`;
}

export default function ExternalSearchLinks({ roles, levels }: ExternalSearchLinksProps): React.JSX.Element {
  const activeLevels = levels.length > 0 ? levels : DEFAULT_LEVELS;
  const roleTerm = buildRoleTerm(roles);

  const rows = activeLevels.map((level) => {
    const levelTerm = LEVEL_SEARCH_TERMS[level] ?? "";
    const query = levelTerm ? `${roleTerm} ${levelTerm}` : roleTerm;
    return {
      level,
      linkedInUrl: `https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(query)}&sortBy=DD`,
      indeedUrl: `https://www.indeed.com/jobs?q=${encodeURIComponent(query)}`,
    };
  });

  return (
    <div className="rounded-lg border border-white/10 p-4">
      <p className="mb-3 text-sm text-ultra-light-mode/50">
        LinkedIn and Indeed can't be ingested directly (no public API, ToS-restricted). These search links are
        built from your Role/Level filters above{roles.length === 0 && levels.length === 0 ? " (none set -- showing defaults)" : ""}:
      </p>
      <div className="flex flex-col gap-2">
        {rows.map(({ level, linkedInUrl, indeedUrl }) => (
          <div key={level} className="flex flex-wrap items-center gap-3">
            <span className="w-24 shrink-0 text-sm text-ultra-light-mode/70">{LEVEL_LABELS[level] ?? level}</span>
            <a
              href={linkedInUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-accent hover:bg-white/5"
            >
              LinkedIn
            </a>
            <a
              href={indeedUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md border border-white/10 px-3 py-1.5 text-sm text-accent hover:bg-white/5"
            >
              Indeed
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
