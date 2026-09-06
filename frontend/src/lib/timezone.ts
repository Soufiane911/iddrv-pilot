function partsAt(value: number, timeZone: string): Record<string, number> {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
  return Object.fromEntries(formatter.formatToParts(new Date(value))
    .filter((part) => part.type !== 'literal')
    .map((part) => [part.type, Number(part.value)]));
}

function offsetAt(value: number, timeZone: string): number {
  const parts = partsAt(value, timeZone);
  return Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second) - value;
}

/** Convert an instant returned by the API to the site's datetime-local wall time. */
export function localDateTimeForTimezone(value: string, timeZone: string): string {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return '';
  const parts = partsAt(timestamp, timeZone);
  return `${String(parts.year).padStart(4, '0')}-${String(parts.month).padStart(2, '0')}-${String(parts.day).padStart(2, '0')}T${String(parts.hour).padStart(2, '0')}:${String(parts.minute).padStart(2, '0')}`;
}

/** Convert a datetime-local wall time in the site's timezone to an API instant. */
export function instantForLocalDateTime(value: string, timeZone: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(value);
  if (!match) return value;
  const wall = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), Number(match[4]), Number(match[5]), Number(match[6] ?? 0));
  if (!Number.isFinite(wall)) return value;
  // Re-evaluate after the first correction so DST transitions use the offset
  // for the requested local wall time rather than the browser's timezone.
  let instant = wall - offsetAt(wall, timeZone);
  instant = wall - offsetAt(instant, timeZone);
  return new Date(instant).toISOString();
}

export function formatDateInTimezone(value: string | null | undefined, timeZone: string, withTime = true): string {
  if (!value) return 'N/D';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  try {
    return new Intl.DateTimeFormat('fr-FR', withTime
      ? { dateStyle: 'medium', timeStyle: 'short', timeZone }
      : { dateStyle: 'medium', timeZone }).format(date);
  } catch {
    return new Intl.DateTimeFormat('fr-FR', withTime ? { dateStyle: 'medium', timeStyle: 'short' } : { dateStyle: 'medium' }).format(date);
  }
}
