-- Spark SQL on the authorized view certification_cycles (see spark.py).
-- SQL parameters require Spark >=3.4. No path or value interpolated into SQL.
SELECT site_id, machine_id, date_trunc('HOUR', time) AS hour_utc,
       count(*) AS cycle_count, avg(cycle_time_s) AS avg_cycle_time_s
FROM certification_cycles
WHERE site_id = :site_id AND data_quality_status = 'valid'
 AND time >= CAST(:from_utc AS TIMESTAMP)
 AND time < CAST(:to_utc AS TIMESTAMP)
GROUP BY site_id, machine_id, date_trunc('HOUR', time)
ORDER BY machine_id, hour_utc LIMIT :row_limit
