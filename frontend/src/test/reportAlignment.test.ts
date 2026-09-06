import { describe, expect, it } from 'vitest';
import { instantForLocalDateTime, localDateTimeForTimezone } from '../lib/timezone';

describe('planning site timezone', () => {
  it('converts a site-local datetime without using the browser timezone', () => {
    expect(instantForLocalDateTime('2026-09-07T08:00', 'Europe/Paris')).toBe('2026-09-07T06:00:00.000Z');
    expect(localDateTimeForTimezone('2026-09-07T06:00:00.000Z', 'Europe/Paris')).toBe('2026-09-07T08:00');
  });

  it('handles the site daylight-saving offset', () => {
    expect(instantForLocalDateTime('2026-01-12T08:00', 'America/Montreal')).toBe('2026-01-12T13:00:00.000Z');
  });
});
