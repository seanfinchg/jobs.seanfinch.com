// ATS location fields have no shared schema across adapters -- Greenhouse,
// Ashby, Lever, SmartRecruiters, Workable, Workday, and Rippling all format
// multi-office, remote, and international postings differently, and the
// dictionaries below were built by pulling every distinct location string
// out of a real production export (~4,000 postings, ~860 distinct strings)
// and categorizing what actually showed up -- comma pairs ("Austin, TX"),
// reversed hyphen pairs ("California - Redwood City", "Argentina - Buenos
// Aires"), ATS-internal codes ("US-CA-Menlo Park", "Bengaluru - BLR1",
// "NYC-Privy"), bare city/state/country names with no delimiter at all,
// "Remote"/"Hybrid" qualifiers in half a dozen phrasings, and outright
// placeholders ("2 Locations", "N/A"). This is a best-effort normalizer
// tuned to that real distribution, not an exhaustive gazetteer.

export interface LocationSegment {
  raw: string;
  city: string | null;
  state: string | null; // two-letter USPS code when resolvable (US only)
  country: string | null;
  remote: boolean;
  hybrid: boolean;
}

export interface ParsedLocation {
  raw: string;
  segments: LocationSegment[];
  remote: boolean;
  hybrid: boolean;
  // Short, deduped labels suitable for a filter dropdown or column, e.g.
  // ["Remote"], ["New York, NY", "Seattle, WA"], ["United States"]. Empty
  // for strings that carry no resolvable location at all (garbage/
  // placeholder input) so they don't pollute the filter with junk tags --
  // the raw string still displays fine in the table regardless.
  labels: string[];
}

const US_STATE_NAMES: Record<string, string> = {
  alabama: "AL", alaska: "AK", arizona: "AZ", arkansas: "AR", california: "CA",
  colorado: "CO", connecticut: "CT", delaware: "DE", florida: "FL", georgia: "GA",
  hawaii: "HI", idaho: "ID", illinois: "IL", indiana: "IN", iowa: "IA",
  kansas: "KS", kentucky: "KY", louisiana: "LA", maine: "ME", maryland: "MD",
  massachusetts: "MA", michigan: "MI", minnesota: "MN", mississippi: "MS",
  missouri: "MO", montana: "MT", nebraska: "NE", nevada: "NV",
  "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
  "north carolina": "NC", "north dakota": "ND", ohio: "OH", oklahoma: "OK",
  oregon: "OR", pennsylvania: "PA", "rhode island": "RI", "south carolina": "SC",
  "south dakota": "SD", tennessee: "TN", texas: "TX", utah: "UT", vermont: "VT",
  virginia: "VA", washington: "WA", "west virginia": "WV", wisconsin: "WI",
  wyoming: "WY", "district of columbia": "DC",
};
const VALID_US_ABBR = new Set(Object.values(US_STATE_NAMES));
const US_STATE_FULL_NAME: Record<string, string> = Object.fromEntries(
  Object.entries(US_STATE_NAMES).map(([name, abbr]) => [
    abbr,
    name.replace(/\b\w/g, (c) => c.toUpperCase()),
  ]),
);

// Full names only, keyed by their normalized (lowercased) form -- every
// entry here is safe to match against a *whole* bare segment or the tail of
// a comma list without colliding with a US state abbreviation. Short 2/3-
// letter country codes that collide with US state codes (CA/DE/IN/IL for
// Canada/Germany/India/Israel) are deliberately left out of this table and
// handled contextually instead (see HYPHEN_COUNTRY_CODES), since e.g. "IN"
// means Indiana in "Crane, IN" but India in "IN-Bangalore-MSO".
const COUNTRY_ALIASES: Record<string, string> = {
  us: "United States", usa: "United States", "u.s": "United States",
  "u.s.a": "United States", "united states": "United States",
  "united states of america": "United States", america: "United States",
  uk: "United Kingdom", "u.k": "United Kingdom", gb: "United Kingdom",
  "united kingdom": "United Kingdom", england: "United Kingdom",
  scotland: "United Kingdom", wales: "United Kingdom",
  britain: "United Kingdom", "great britain": "United Kingdom",
  canada: "Canada", can: "Canada",
  ireland: "Ireland", ie: "Ireland", irl: "Ireland", "republic of ireland": "Ireland",
  india: "India", ind: "India",
  poland: "Poland", pl: "Poland", pol: "Poland",
  israel: "Israel", isr: "Israel",
  germany: "Germany", deu: "Germany",
  uae: "United Arab Emirates", "united arab emirates": "United Arab Emirates",
  australia: "Australia", "new zealand": "New Zealand",
  singapore: "Singapore", china: "China", japan: "Japan",
  "south korea": "South Korea", taiwan: "Taiwan", "hong kong": "Hong Kong",
  netherlands: "Netherlands", "the netherlands": "Netherlands",
  france: "France", spain: "Spain", italy: "Italy", germany2: "Germany",
  switzerland: "Switzerland", austria: "Austria", belgium: "Belgium",
  denmark: "Denmark", norway: "Norway", sweden: "Sweden", finland: "Finland",
  iceland: "Iceland", portugal: "Portugal", greece: "Greece",
  romania: "Romania", hungary: "Hungary", czechia: "Czech Republic",
  "czech republic": "Czech Republic", slovenia: "Slovenia", slovakia: "Slovakia",
  serbia: "Serbia", croatia: "Croatia", cyprus: "Cyprus", armenia: "Armenia",
  estonia: "Estonia", latvia: "Latvia", lithuania: "Lithuania",
  ukraine: "Ukraine", russia: "Russia", turkey: "Turkey", qatar: "Qatar",
  "saudi arabia": "Saudi Arabia", egypt: "Egypt", "south africa": "South Africa",
  nigeria: "Nigeria", kenya: "Kenya", brazil: "Brazil", mexico: "Mexico",
  argentina: "Argentina", chile: "Chile", colombia: "Colombia", peru: "Peru",
  uruguay: "Uruguay", "costa rica": "Costa Rica", panama: "Panama",
  vietnam: "Vietnam", thailand: "Thailand", indonesia: "Indonesia",
  malaysia: "Malaysia", philippines: "Philippines",
  // Broad regions -- not countries, but the source data uses them exactly
  // like one ("Europe", "AMER" as a corporate region code for the
  // Americas), so they're useful as their own filter tag rather than
  // dropped entirely.
  europe: "Europe", "north america": "North America", amer: "Americas",
};
delete COUNTRY_ALIASES.germany2;

// 2-letter ATS location codes that only mean a country in the specific
// hyphen-prefix context ("XX-City...") -- everywhere else (a trailing
// comma token, a bare word) the same letters mean a US state, since that's
// what they mean far more often in this data ("Wilmington, DE", "Crane,
// IN", "Deerfield, IL" are all real US postings).
const HYPHEN_COUNTRY_CODES: Record<string, string> = {
  CA: "Canada", DE: "Germany", IN: "India", PL: "Poland", UK: "United Kingdom",
  GB: "United Kingdom", FR: "France", MX: "Mexico", IE: "Ireland", CN: "China",
};

const CANADA_PROVINCES = new Set([
  "alberta", "british columbia", "manitoba", "new brunswick",
  "newfoundland and labrador", "nova scotia", "ontario",
  "prince edward island", "quebec", "saskatchewan",
  "northwest territories", "nunavut", "yukon",
]);
// Trailing 2-letter province code with no "Canada" spelled out anywhere
// ("Toronto, ON") is still an unambiguous Canada signal -- none of these
// collide with a US state abbreviation.
const CANADA_PROVINCE_ABBR = new Set([
  "on", "qc", "bc", "ab", "mb", "sk", "ns", "nb", "pe", "nl", "yt", "nt", "nu",
]);

interface CityAlias {
  city: string;
  state?: string;
  country?: string;
}

// Bare or near-bare city names the source data actually uses without a
// state/country attached (harvested from the real export, not guessed) --
// plus the handful of ATS-specific abbreviations (NYC, SF, LA, "NYC-
// Privy") that show up as their own tokens.
const CITY_ALIASES: Record<string, CityAlias> = {
  "new york city": { city: "New York", state: "NY" },
  "new york": { city: "New York", state: "NY" },
  nyc: { city: "New York", state: "NY" },
  "washington dc": { city: "Washington", state: "DC" },
  "san francisco": { city: "San Francisco", state: "CA" },
  sf: { city: "San Francisco", state: "CA" },
  "south sf": { city: "South San Francisco", state: "CA" },
  "south san francisco": { city: "South San Francisco", state: "CA" },
  "san francisco bay area": { city: "San Francisco Bay Area", state: "CA" },
  seattle: { city: "Seattle", state: "WA" },
  "san jose": { city: "San Jose", state: "CA" },
  washington: { city: "Washington", state: "DC" },
  dc: { city: "Washington", state: "DC" },
  "los angeles": { city: "Los Angeles", state: "CA" },
  "los angeles area": { city: "Los Angeles", state: "CA" },
  la: { city: "Los Angeles", state: "CA" },
  boston: { city: "Boston", state: "MA" },
  chicago: { city: "Chicago", state: "IL" },
  austin: { city: "Austin", state: "TX" },
  denver: { city: "Denver", state: "CO" },
  atlanta: { city: "Atlanta", state: "GA" },
  redmond: { city: "Redmond", state: "WA" },
  mclean: { city: "McLean", state: "VA" },
  arlington: { city: "Arlington", state: "VA" },
  rosslyn: { city: "Arlington", state: "VA" },
  sea: { city: "Seattle", state: "WA" },
  tor: { city: "Toronto", country: "Canada" },
  baltimore: { city: "Baltimore", state: "MD" },
  charlotte: { city: "Charlotte", state: "NC" },
  columbus: { city: "Columbus", state: "OH" },
  dallas: { city: "Dallas", state: "TX" },
  miami: { city: "Miami", state: "FL" },
  nashville: { city: "Nashville", state: "TN" },
  philadelphia: { city: "Philadelphia", state: "PA" },
  pittsburgh: { city: "Pittsburgh", state: "PA" },
  princeton: { city: "Princeton", state: "NJ" },
  raleigh: { city: "Raleigh", state: "NC" },
  tysons: { city: "Tysons", state: "VA" },
  "mountain view": { city: "Mountain View", state: "CA" },
  toronto: { city: "Toronto", country: "Canada" },
  montreal: { city: "Montreal", country: "Canada" },
  vancouver: { city: "Vancouver", country: "Canada" },
  london: { city: "London", country: "United Kingdom" },
  dublin: { city: "Dublin", country: "Ireland" },
  cork: { city: "Cork", country: "Ireland" },
  bangalore: { city: "Bangalore", country: "India" },
  bengaluru: { city: "Bengaluru", country: "India" },
  chennai: { city: "Chennai", country: "India" },
  gurugram: { city: "Gurugram", country: "India" },
  hyderabad: { city: "Hyderabad", country: "India" },
  delhi: { city: "Delhi", country: "India" },
  pune: { city: "Pune", country: "India" },
  mohali: { city: "Mohali", country: "India" },
  singapore: { city: "Singapore", country: "Singapore" },
  sydney: { city: "Sydney", country: "Australia" },
  belgrade: { city: "Belgrade", country: "Serbia" },
  warsaw: { city: "Warsaw", country: "Poland" },
  barcelona: { city: "Barcelona", country: "Spain" },
  madrid: { city: "Madrid", country: "Spain" },
  lisbon: { city: "Lisbon", country: "Portugal" },
  aveiro: { city: "Aveiro", country: "Portugal" },
  paris: { city: "Paris", country: "France" },
  berlin: { city: "Berlin", country: "Germany" },
  munich: { city: "Munich", country: "Germany" },
  "tel aviv": { city: "Tel Aviv", country: "Israel" },
  "tel aviv-yafo": { city: "Tel Aviv", country: "Israel" },
  "sao paulo": { city: "Sao Paulo", country: "Brazil" },
  "são paulo": { city: "Sao Paulo", country: "Brazil" },
  "taipei city": { city: "Taipei", country: "Taiwan" },
  taipei: { city: "Taipei", country: "Taiwan" },
  reykjavík: { city: "Reykjavik", country: "Iceland" },
  reykjavik: { city: "Reykjavik", country: "Iceland" },
  milan: { city: "Milan", country: "Italy" },
  prague: { city: "Prague", country: "Czech Republic" },
  vienna: { city: "Vienna", country: "Austria" },
  zurich: { city: "Zurich", country: "Switzerland" },
  zürich: { city: "Zurich", country: "Switzerland" },
  wellington: { city: "Wellington", country: "New Zealand" },
};

// Placeholder/junk values an ATS sometimes exports instead of a real
// location -- these produce no filterable label at all (the raw text still
// shows in the table), rather than becoming their own nonsense filter tag.
const GARBAGE_RE = /^(\*?job posting only\b.*|n\/?a|\d+\s+locations?)$/i;

// A short alphanumeric tail on a "City - CODE" pair is an ATS-internal
// office code ("Bengaluru - BLR1", "London - UK2", "San Francisco - SF9"),
// not a second place name -- recognized by shape (short, no vowspace,
// often ending in digits) plus not matching anything in the place tables.
function looksLikeOfficeCode(token: string): boolean {
  const key = normalizeKey(token);
  if (COUNTRY_ALIASES[key] || US_STATE_NAMES[key] || CITY_ALIASES[key]) return false;
  return /^[a-z]{2,6}\d{0,3}$/i.test(token.trim());
}

function stripPunctuation(token: string): string {
  return token.replace(/\./g, "").trim();
}

function normalizeKey(token: string): string {
  return stripPunctuation(token).toLowerCase().replace(/\s+/g, " ").trim();
}

function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

interface PlaceResult {
  city: string | null;
  state: string | null;
  country: string | null;
}

const EMPTY_PLACE: PlaceResult = { city: null, state: null, country: null };

function cleanupCityNoise(city: string): string {
  return city
    .replace(/\s+(regional )?municipality$/i, "")
    .replace(/\s+(office|hq|headquarters)$/i, "")
    .replace(/^[\s-]+|[\s-]+$/g, "")
    .trim();
}

// Resolves a single city-shaped candidate string (possibly with an
// ATS-code prefix like "NYC-Privy") against the alias table.
function resolveCity(rawCity: string): PlaceResult {
  const cleaned = cleanupCityNoise(rawCity);
  if (!cleaned) return EMPTY_PLACE;
  const key = normalizeKey(cleaned);
  let alias = CITY_ALIASES[key];
  if (!alias && cleaned.includes("-")) {
    alias = CITY_ALIASES[normalizeKey(cleaned.split("-")[0] ?? "")];
  }
  if (alias) return { city: alias.city, state: alias.state ?? null, country: alias.country ?? null };
  return { city: cleaned, state: null, country: null };
}

// Classifies a single bare word/phrase with no comma or hyphen structure
// left in it -- a country name, a US state name, a Canadian province, a
// known city, or (last resort) an opaque place name to display as-is.
function classifyBare(whole: string): PlaceResult {
  const cleaned = cleanupCityNoise(whole);
  if (!cleaned) return EMPTY_PLACE;
  if (GARBAGE_RE.test(cleaned)) return EMPTY_PLACE;

  const key = normalizeKey(cleaned);
  if (COUNTRY_ALIASES[key]) return { city: null, state: null, country: COUNTRY_ALIASES[key] };
  if (US_STATE_NAMES[key]) return { city: null, state: US_STATE_NAMES[key], country: null };
  if (VALID_US_ABBR.has(cleaned.toUpperCase()) && cleaned.length <= 2) {
    return { city: null, state: cleaned.toUpperCase(), country: null };
  }
  if (CANADA_PROVINCES.has(key)) return { city: titleCase(cleaned), state: null, country: "Canada" };
  if (CITY_ALIASES[key]) return resolveCity(cleaned);

  // Multi-word leftovers (e.g. "IN Remote India" with "Remote" already
  // stripped leaves "IN India") -- look for one unambiguous whole-word
  // match rather than matching substrings, so a stray "IN"/"CA" doesn't
  // silently turn into a country here.
  const words = cleaned.split(/\s+/);
  if (words.length > 1) {
    for (const w of words) {
      const wk = normalizeKey(w);
      if (COUNTRY_ALIASES[wk]) return { city: null, state: null, country: COUNTRY_ALIASES[wk] };
      if (CANADA_PROVINCES.has(wk)) return { city: titleCase(w), state: null, country: "Canada" };
    }
  }

  return resolveCity(cleaned);
}

// "XX-City" / "XX-Province-City" / "US-ST-City" ATS location codes, and
// "Country - City" / "State - City" reversed pairs, and "City - CODE"
// pairs where the tail is an office code, not a second place.
function classifyHyphenated(whole: string): PlaceResult {
  const parts = whole.split("-").map((p) => p.trim()).filter(Boolean);
  if (parts.length === 0) return EMPTY_PLACE;

  if (parts.length >= 3) {
    const p0 = parts[0] ?? "";
    const p1 = parts[1] ?? "";
    const p2 = parts[2] ?? "";
    if (p0.toUpperCase() === "US" && VALID_US_ABBR.has(p1.toUpperCase())) {
      return { city: cleanupCityNoise(parts.slice(2).join("-")), state: p1.toUpperCase(), country: null };
    }
    const country = HYPHEN_COUNTRY_CODES[p0.toUpperCase()];
    if (country) {
      // "CA-Ontario-Toronto": second part is a province, not the city --
      // the city is more specific and comes third. Every other 3-part
      // code seen in the data ("PL-Warsaw-Lixa C", "IN-Bangalore-MSO")
      // puts the city second and an office/building nickname third.
      if (CANADA_PROVINCES.has(normalizeKey(p1))) {
        return { city: cleanupCityNoise(p2 || p1), state: null, country };
      }
      return { city: cleanupCityNoise(p1), state: null, country };
    }
  }

  if (parts.length >= 2) {
    const p0 = parts[0] ?? "";
    const rest = cleanupCityNoise(parts.slice(1).join("-"));
    // A "country code - country name" pair ("PL-Poland-Remote", once the
    // trailing "Remote" is gone, leaves "PL-Poland") is a redundant
    // spelled-out country, not a city -- don't report it as one.
    const restIsCountry = COUNTRY_ALIASES[normalizeKey(rest)] !== undefined;
    const p0Key = normalizeKey(p0);
    if (US_STATE_NAMES[p0Key]) {
      return { city: restIsCountry ? null : rest, state: US_STATE_NAMES[p0Key], country: null };
    }
    if (COUNTRY_ALIASES[p0Key]) {
      return { city: restIsCountry ? null : rest, state: null, country: COUNTRY_ALIASES[p0Key] };
    }
    const hyphenCountry = p0.toUpperCase() !== "US" ? (HYPHEN_COUNTRY_CODES[p0.toUpperCase()] ?? null) : null;
    if (hyphenCountry) {
      return { city: restIsCountry ? null : rest, state: null, country: hyphenCountry };
    }
    if (looksLikeOfficeCode(rest)) return classifyBare(p0);
    return resolveCity(p0);
  }

  return classifyBare(parts[0] ?? "");
}

// A comma-separated location where every recognizable state/country marker
// has already been stripped off the end still left 4+ bare leftover
// tokens -- almost always an ATS using "," instead of ";" to join what are
// really several independent offices ("San Francisco, CA, New York City,
// NY, Seattle, WA"). Classifying each token on its own beats gluing them
// into one unreadable city string.
function classifyCommaGlob(tokens: string[]): PlaceResult[] {
  return tokens.map(classifyBare);
}

function classifyCommaTokens(tokens: string[]): PlaceResult[] {
  if (tokens.length >= 4) return classifyCommaGlob(tokens);

  let remaining = tokens;
  let country: string | null = null;

  const last = remaining[remaining.length - 1];
  if (last !== undefined) {
    const key = normalizeKey(last);
    if (COUNTRY_ALIASES[key]) {
      country = COUNTRY_ALIASES[key];
      remaining = remaining.slice(0, -1);
    } else if (CANADA_PROVINCE_ABBR.has(key)) {
      country = "Canada";
      remaining = remaining.slice(0, -1);
    }
  }

  // No country marker anchored this list at all and there are still 3+
  // leftover tokens ("NYC, SEA, San Francisco") -- almost certainly
  // several offices joined with "," instead of ";", not one place with
  // three comma-separated qualifiers. Classify each on its own rather
  // than gluing them into one unreadable city string.
  if (!country && remaining.length >= 3) {
    const hasState = remaining.some((t) => {
      const key = normalizeKey(t);
      return US_STATE_NAMES[key] !== undefined || VALID_US_ABBR.has(stripPunctuation(t).toUpperCase());
    });
    if (!hasState) return classifyCommaGlob(tokens);
  }

  if (country && country !== "United States") {
    // Non-US: don't try to interpret a leftover province/region token as a
    // US state (that's the "Perth, WA, Australia" trap -- WA there is
    // Western Australia, not Washington). The most specific leftover
    // token is the city; middle tokens (province, "Metropolitan City of
    // X") are dropped rather than guessed at.
    const cityToken = remaining[0];
    if (!cityToken) return [{ city: null, state: null, country }];
    const resolved = resolveCity(cityToken);
    return [{ city: resolved.city, state: null, country: resolved.country ?? country }];
  }

  let state: string | null = null;
  const nextLast = remaining[remaining.length - 1];
  if (nextLast !== undefined) {
    const key = normalizeKey(nextLast);
    const upper = stripPunctuation(nextLast).toUpperCase();
    if (US_STATE_NAMES[key]) {
      state = US_STATE_NAMES[key];
      remaining = remaining.slice(0, -1);
    } else if (VALID_US_ABBR.has(upper)) {
      state = upper;
      remaining = remaining.slice(0, -1);
    }
  }

  const cityToken = remaining.length > 0 ? remaining.join(", ") : null;
  if (!cityToken) return [{ city: null, state, country }];
  const resolved = resolveCity(cityToken);
  return [{ city: resolved.city, state: state ?? resolved.state, country: country ?? resolved.country }];
}

const REMOTE_RE = /\bremote\b/i;
const HYBRID_RE = /\bhybrid\b/i;

// A single office/remote option within one ATS location string, e.g. one
// side of "San Francisco, CA | Washington, DC". Usually resolves to one
// place, occasionally several (see classifyCommaGlob).
function parseSegment(rawSegment: string): LocationSegment[] {
  const raw = rawSegment.trim();
  const remote = REMOTE_RE.test(raw);
  const hybrid = HYBRID_RE.test(raw);

  let working = raw
    .replace(/\([^)]*\)/g, " ") // balanced parentheticals, e.g. "(Travel-Required)"
    .replace(/[()]/g, " ") // any left dangling by a mid-parenthetical split (e.g. "X | Y)" from "(X | Y)")
    .replace(/remote[-\s]friendly,?/gi, " ")
    .replace(/\bremote\b/gi, " ")
    .replace(/\bhybrid\b/gi, " ")
    .replace(/:\s*(all|select)\s+locations?$/i, "")
    .trim();

  if (!working) return [{ raw, city: null, state: null, country: null, remote, hybrid }];

  // Stripping "Remote"/"Hybrid" out of e.g. "France, Remote" or "Toronto,
  // Ontario, CAN - Remote" can leave a stray trailing comma or dash on the
  // final token ("France," / "CAN -") -- trimmed per-token here rather
  // than just on the whole string, since a single leftover token still
  // needs to reach classifyBare/classifyHyphenated clean.
  const tokens = working
    .split(",")
    .map((t) => t.replace(/^[\s-]+|[\s-]+$/g, "").trim())
    .filter(Boolean);

  let places: PlaceResult[];
  if (tokens.length > 1) {
    places = classifyCommaTokens(tokens);
  } else {
    const single = tokens[0] ?? working;
    places = [!single.includes(",") && single.includes("-") ? classifyHyphenated(single) : classifyBare(single)];
  }

  return places.map((p) => ({ raw, city: p.city, state: p.state, country: p.country, remote, hybrid }));
}

function segmentLabel(segment: LocationSegment): string | null {
  if (segment.city && segment.state) return `${segment.city}, ${segment.state}`;
  if (segment.city && segment.country) return `${segment.city}, ${segment.country}`;
  if (segment.city) return segment.city;
  if (segment.state) return US_STATE_FULL_NAME[segment.state] ?? segment.state;
  if (segment.country) return segment.country;
  return null;
}

const cache = new Map<string, ParsedLocation>();

// ATS location strings repeat heavily across postings from the same
// company (a job board of a few thousand roles might only have a few
// hundred distinct location strings), so this is cached by raw string
// rather than re-parsed per job on every render.
export function parseLocation(raw: string): ParsedLocation {
  const cached = cache.get(raw);
  if (cached) return cached;

  const rawSegments = raw
    .replace(/\s+or\s+(?=[A-Z])/g, ";")
    .split(/[;|•]/)
    .map((s) => s.trim())
    .filter(Boolean);
  const segments = (rawSegments.length > 0 ? rawSegments : [raw]).flatMap(parseSegment);
  const remote = REMOTE_RE.test(raw) || segments.some((s) => s.remote);
  const hybrid = HYBRID_RE.test(raw) || segments.some((s) => s.hybrid);

  const labels = [...new Set(segments.map(segmentLabel).filter((l): l is string => l !== null))];
  if (remote && !labels.includes("Remote")) labels.push("Remote");

  const parsed: ParsedLocation = { raw, segments, remote, hybrid, labels };
  cache.set(raw, parsed);
  return parsed;
}

// All the filter-tag keys a single raw location string should count toward,
// one per tree level it touches -- "San Francisco, CA" (via a "San
// Francisco, CA | Washington, DC" string) yields "country:United States",
// "state:California", and "city:San Francisco, CA". Used for both the tree
// filter's per-node counts and matching a selected tag against a job,
// since "does this job match the selected country" and "how many jobs does
// this country contain" are the same underlying question.
export function locationTagsFor(raw: string): string[] {
  const parsed = parseLocation(raw);
  const tags = new Set<string>();
  if (parsed.remote) tags.add("remote");
  for (const seg of parsed.segments) {
    if (seg.state) {
      tags.add(`state:${US_STATE_FULL_NAME[seg.state] ?? seg.state}`);
      tags.add("country:United States");
    } else if (seg.country) {
      tags.add(`country:${seg.country}`);
    } else if (seg.city) {
      // Resolved to a city but neither a US state nor a country -- an
      // unaliased place name (see CITY_ALIASES). Still worth surfacing in
      // the tree rather than silently dropping it.
      tags.add("country:Other");
    }
    const label = segmentLabel(seg);
    if (label && seg.city) tags.add(`city:${label}`);
  }
  return [...tags];
}

export interface LocationTreeNode {
  value: string; // "remote" | "country:<name>" | "state:<name>" | "city:<label>"
  label: string;
  children: LocationTreeNode[];
}

// Static Country -> State -> City shape built once from every distinct
// location string in the export (state only exists as a level for the US;
// everywhere else a country's cities nest directly under it). Independent
// of the active filters -- only the counts (see locationTagsFor) react to
// those, the same split JobTable already uses for Role/Level options vs.
// their counts.
export function buildLocationTree(rawLocations: Iterable<string>): LocationTreeNode[] {
  const countries = new Map<string, { states: Map<string, Set<string>>; cities: Set<string> }>();
  let hasRemote = false;

  function bucket(country: string) {
    let c = countries.get(country);
    if (!c) {
      c = { states: new Map(), cities: new Set() };
      countries.set(country, c);
    }
    return c;
  }

  for (const raw of rawLocations) {
    const parsed = parseLocation(raw);
    if (parsed.remote) hasRemote = true;
    for (const seg of parsed.segments) {
      const label = segmentLabel(seg);
      if (seg.state) {
        const c = bucket("United States");
        const stateName = US_STATE_FULL_NAME[seg.state] ?? seg.state;
        const cities = c.states.get(stateName) ?? new Set<string>();
        if (seg.city && label) cities.add(label);
        c.states.set(stateName, cities);
      } else if (seg.country) {
        const c = bucket(seg.country);
        if (seg.city && label) c.cities.add(label);
      } else if (seg.city && label) {
        bucket("Other").cities.add(label);
      }
    }
  }

  const countryNodes: LocationTreeNode[] = [...countries.entries()]
    .sort(([a], [b]) => (a === "Other" ? 1 : b === "Other" ? -1 : a.localeCompare(b)))
    .map(([country, { states, cities }]) => {
      const stateNodes: LocationTreeNode[] = [...states.entries()]
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([state, stateCities]) => ({
          value: `state:${state}`,
          label: state,
          children: [...stateCities].sort((a, b) => a.localeCompare(b)).map((label) => ({
            value: `city:${label}`,
            label,
            children: [],
          })),
        }));
      const cityNodes: LocationTreeNode[] = [...cities].sort((a, b) => a.localeCompare(b)).map((label) => ({
        value: `city:${label}`,
        label,
        children: [],
      }));
      return {
        value: `country:${country}`,
        label: country,
        children: [...stateNodes, ...cityNodes],
      };
    });

  return hasRemote
    ? [{ value: "remote", label: "Remote", children: [] }, ...countryNodes]
    : countryNodes;
}
