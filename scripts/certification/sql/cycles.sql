-- One row per scoped machine/hour; no ERP quantities multiplied per cycle.
-- TimescaleDB dialect. Half-open UTC range; invalid cycles excluded in ON so
-- machines without valid cycles remain visible (COUNT(c.time)=0).
SELECT m.site_id, m.id AS machine_id,
       time_bucket('1 hour', c.time) AS hour_utc,
       count(c.time) AS cycle_count, avg(c.cycle_time_s) AS avg_cycle_time_s
FROM machines m
LEFT JOIN machine_cycles c ON c.machine_id = m.id
 AND c.time >= %(from_utc)s AND c.time < %(to_utc)s
 AND c.data_quality_status = 'valid'
WHERE m.site_id = %(site_id)s
GROUP BY m.site_id, m.id, time_bucket('1 hour', c.time)
ORDER BY m.id, hour_utc
LIMIT %(limit)s
