/** Small, locale-aware formatters for things the interface shows often. */

const UNITS = ['bytes', 'KB', 'MB', 'GB'] as const;

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return '';
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = unit === 0 || value >= 10 ? 0 : 1;
  return `${value.toFixed(digits)} ${UNITS[unit]}`;
}

/** "1 page", "3 pages". Pass the plural when it is not just an added "s". */
export function pluralise(count: number, singular: string, plural = `${singular}s`): string {
  return `${count.toLocaleString()} ${count === 1 ? singular : plural}`;
}

const DAY_MS = 24 * 60 * 60 * 1000;

/** "Today", "Yesterday", "3 days ago", or a date for anything older than a week. */
export function formatRelativeDay(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';
  const startOfDay = (date: Date): number =>
    new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const days = Math.round((startOfDay(now) - startOfDay(then)) / DAY_MS);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return then.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}
