-- DuckDB: bounded local analytical projection, NOT a distributed-system proof.
SELECT site_id, machine_id, count(*) AS cycle_count, avg(cycle_time_s) AS avg_cycle_time_s
FROM read_json_auto(?)
WHERE site_id = ? AND data_quality_status = 'valid'
 AND CAST(time AS TIMESTAMPTZ) >= CAST(? AS TIMESTAMPTZ)
 AND CAST(time AS TIMESTAMPTZ) < CAST(? AS TIMESTAMPTZ)
GROUP BY site_id, machine_id ORDER BY machine_id LIMIT ?
