// A raw ISO timestamp ("2026-08-24T21:14:34-04:00") is precise but not
// scannable in a table of a few hundred rows -- relative phrasing reads
// faster, with the exact timestamp still available on hover for anyone who
// needs it.
export interface RelativeDate {
  label: string;
  title: string;
}

export function relativeDate(iso: string): RelativeDate {
  const date = new Date(iso);
  const title = Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

  if (Number.isNaN(date.getTime())) return { label: iso, title };

  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const diffDays = Math.round((startOfDay(new Date()) - startOfDay(date)) / 86_400_000);

  let label: string;
  if (diffDays < 0) label = title;
  else if (diffDays === 0) label = "Today";
  else if (diffDays === 1) label = "Yesterday";
  else if (diffDays < 7) label = `${diffDays} days ago`;
  else if (diffDays < 30) {
    const weeks = Math.floor(diffDays / 7);
    label = `${weeks} week${weeks > 1 ? "s" : ""} ago`;
  } else if (diffDays < 365) {
    const months = Math.floor(diffDays / 30);
    label = `${months} month${months > 1 ? "s" : ""} ago`;
  } else {
    const years = Math.floor(diffDays / 365);
    label = `${years} year${years > 1 ? "s" : ""} ago`;
  }

  return { label, title };
}
