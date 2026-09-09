"""DuckDB local analytical adapter. No claim of a qualified big-data system."""
from pathlib import Path
from .database import SQL_DIR
from .window import validate_window


def extract(path, site_id, start, end, limit=1000):
    start, end = validate_window(start, end)
    import duckdb
    path = Path(path).resolve(strict=True)
    if path.suffix != '.jsonl' or path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError('file_limit')
    if type(site_id) is not int or site_id <= 0 or type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError('scope')
    query = (SQL_DIR / 'analytics.sql').read_text()
    with duckdb.connect(config={'memory_limit': '128MB', 'threads': 1, 'max_temp_directory_size': '0B', 'autoinstall_known_extensions': False, 'autoload_known_extensions': False}) as db:
        db.execute("SET TimeZone='UTC'")
        result = db.execute(query, [str(path), site_id, start, end, limit + 1])
        columns = [c[0] for c in result.description]
        rows = [dict(zip(columns, row)) for row in result.fetchall()]
        if len(rows) > limit:
            raise ValueError('row_limit')
        return {'engine': 'duckdb', 'version': duckdb.__version__, 'classification': 'local_analytical_not_distributed', 'rows': rows}
