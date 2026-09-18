import type { Job } from "@/types";

interface StatsBarProps {
  jobs: Job[];
}

interface Tile {
  label: string;
  value: string;
}

function relativeDay(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  return `${days}d ago`;
}

export default function StatsBar({ jobs }: StatsBarProps): React.JSX.Element {
  const companies = new Set(jobs.map((j) => j.company)).size;
  const lastSeen = jobs.reduce<string | null>(
    (latest, j) => (!latest || j.first_seen > latest ? j.first_seen : latest),
    null,
  );

  const tiles: Tile[] = [
    { label: "Open roles", value: String(jobs.length) },
    { label: "Companies", value: String(companies) },
    { label: "Newest match", value: lastSeen ? relativeDay(lastSeen) : "—" },
  ];

  return (
    <div className="grid grid-cols-3 gap-2 sm:gap-4">
      {tiles.map((tile) => (
        <div
          key={tile.label}
          className="rounded-lg border border-white/10 bg-dark-mode px-3 py-3 sm:px-5 sm:py-4"
        >
          <div className="font-jost text-xl font-semibold text-light-mode sm:text-3xl">{tile.value}</div>
          <div className="mt-1 text-xs text-ultra-light-mode/70 sm:text-sm">{tile.label}</div>
        </div>
      ))}
    </div>
  );
}
