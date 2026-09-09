-- Synthetic projection of db/init.sql, NOT the complete application schema.
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE TABLE sites(id integer PRIMARY KEY, name text NOT NULL);
CREATE TABLE machines(id integer PRIMARY KEY, site_id integer REFERENCES sites(id), erp_ref text NOT NULL);
CREATE TABLE machine_cycles(time timestamptz NOT NULL, machine_id integer NOT NULL REFERENCES machines(id), cycle_time_s double precision, data_quality_status text NOT NULL);
SELECT create_hypertable('machine_cycles','time');
CREATE INDEX certification_cycles_machine_time ON machine_cycles(machine_id,time);
INSERT INTO sites VALUES (1,'Synthetic A'),(2,'Synthetic B');
INSERT INTO machines VALUES (1,1,'SYN-1'),(2,1,'SYN-2'),(3,2,'SYN-3');
INSERT INTO machine_cycles VALUES
 ('2026-09-01 00:00+00',1,10,'valid'),
 ('2026-09-01 00:30+00',1,20,'valid'),
 ('2026-09-01 00:40+00',1,999,'invalid'),
 ('2026-09-01 01:00+00',1,30,'valid'),
 ('2026-09-01 00:00+00',3,50,'valid');
ANALYZE;
