// Same company, different ATS-posting spelling -- backend/jobfinder/
// featured.py lists every real variant separately for is_featured()'s exact
// match; this table exists for the same underlying reason, so the company
// tracker doesn't double-list "HPE" and "Hewlett Packard Enterprise" as if
// they were two different companies. Deliberately conservative -- only
// unambiguous pure renames, not cases like Google/Alphabet or TikTok/
// ByteDance where the posting entity might genuinely be a distinct
// division worth seeing separately.
const COMPANY_ALIASES: Record<string, string> = {
  "hewlett packard (hp)": "HP",
  hpe: "HP",
  "hewlett packard enterprise": "HP",
  "motorola solutions": "Motorola",
  "micron technology": "Micron",
};

export function canonicalCompanyName(company: string): string {
  return COMPANY_ALIASES[company.trim().toLowerCase()] ?? company;
}
