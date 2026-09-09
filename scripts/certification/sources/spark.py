"""NON EXECUTE: Spark >=3.4 and authorized bounded Parquet partition required.
Operator-only library, no network/credentials discovery or automatic installation.
The supplied session owns cluster auth/config; caller must cancel timed-out jobs.
"""
from .database import SQL_DIR
from .window import validate_window


def extract(session, approved_partition, site_id, from_utc, to_utc, limit=1000):
    if type(site_id) is not int or site_id < 1 or type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError('scope')
    start, end = validate_window(from_utc, to_utc)
    # Isolate SQL configuration and temporary views, but share caller's context.
    # Never stop this session: SparkSession.stop also stops that shared context.
    session = session.newSession()
    # Path is an operator-approved single partition, never user/API input.
    session.conf.set('spark.sql.session.timeZone', 'UTC')
    view = 'certification_cycles'
    try:
        session.read.parquet(approved_partition).createOrReplaceTempView(view)
        frame = session.sql((SQL_DIR / 'spark_cycles.sql').read_text(), args={
            'site_id': site_id, 'from_utc': start.isoformat(), 'to_utc': end.isoformat(), 'row_limit': limit + 1})
        rows = [r.asDict() for r in frame.collect()]
        if len(rows) > limit:
            raise ValueError('row_limit')
        return rows
    finally:
        session.catalog.dropTempView(view)
