"""Only starts/removes its own uniquely named disposable Timescale container."""
import argparse
import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path

from .database import SQL_DIR, extract


def command(*args):
    return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.DEVNULL).strip()


def run():
    import psycopg
    name = 'iddrv-c1c2-' + uuid.uuid4().hex[:12]
    image = 'timescale/timescaledb:2.28.2-pg16'
    command('image', 'inspect', image)  # No implicit download.
    try:
        command('run', '--pull=never', '-d', '--name', name,
                '--label', 'iddrv.certification.owner=' + name,
                '--memory=512m', '--cpus=1', '--pids-limit=128',
                '--tmpfs', '/var/lib/postgresql/data:rw,size=256m',
                '-e', 'POSTGRES_HOST_AUTH_METHOD=trust',
                '-p', '127.0.0.1::5432', image)
        port = int(command('port', name, '5432/tcp').rsplit(':', 1)[1])
        for _ in range(40):
            try:
                db = psycopg.connect(host='127.0.0.1', port=port, user='postgres', dbname='postgres', connect_timeout=2, autocommit=True)
                break
            except psycopg.OperationalError:
                time.sleep(.5)
        else:
            raise RuntimeError('sandbox_start_timeout')
        with db:
            db.execute((SQL_DIR / 'fixture.sql').read_text())
            result = extract(db, 1, '2026-09-01T00:00:00Z', '2026-09-01T01:00:00Z')
            assert [(r['machine_id'], r['cycle_count']) for r in result['rows']] == [(1, 2), (2, 0)]
            assert result['rows'][0]['avg_cycle_time_s'] == 15
            assert extract(db, 999, '2026-09-01T00:00:00Z', '2026-09-01T01:00:00Z')['count'] == 0
            try:
                extract(db, '1 OR 1=1', '2026-09-01T00:00:00Z', '2026-09-01T01:00:00Z')
            except ValueError:
                result['injection_rejected'] = True
            else:
                raise AssertionError('injection')
            result['server_version'] = db.execute('SHOW server_version').fetchone()[0]
            result['timescale_version'] = db.execute("SELECT extversion FROM pg_extension WHERE extname='timescaledb'").fetchone()[0]
            result['fixture_sha256'] = hashlib.sha256((SQL_DIR / 'fixture.sql').read_bytes()).hexdigest()
            return result
    finally:
        # docker run can create the container and then fail before returning.
        # Inspect even on failure; absence/inspection failure grants no ownership.
        try:
            owner = command('inspect', '--format', '{{ index .Config.Labels "iddrv.certification.owner" }}', name)
        except subprocess.CalledProcessError:
            owner = None
        if owner == name:
            command('rm', '-f', name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = run()
    content = json.dumps(result, default=str, sort_keys=True, indent=2) + '\n'
    (args.output / 'timescale.json').write_text(content)
    print(json.dumps({'count': result['count'], 'server_version': result['server_version'], 'timescale_version': result['timescale_version'], 'sha256': hashlib.sha256(content.encode()).hexdigest(), 'container_removed': True}))
