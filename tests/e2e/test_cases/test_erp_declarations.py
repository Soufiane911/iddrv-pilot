"""Use the existing guarded E2E harness; all workbook values are synthetic."""
from datetime import datetime, timezone
from openpyxl import Workbook

from ingest.erp_reader import read_trs_declarations
from ingest.erp_repository import persist_declarations


def test_real_reader_keeps_two_team_declarations_and_revisions(db_conn, tmp_path):
    book = Workbook()
    sheet = book.active
    sheet.append(['Début Equipe', 'Num Equipe', 'Réf. Machine', 'Réf OF', 'Qté Pieces Bonnes', 'Total Rebuts'])
    sheet.append([datetime(2026, 9, 5, 5), 1, '606', '000012', 760, 40])
    sheet.append([datetime(2026, 9, 5, 13), 2, '606', '000012', 944, 16])
    path = tmp_path / 'synthetic-teams.xlsx'
    book.save(path)
    declarations = read_trs_declarations(path, source_timezone='Europe/Paris').declarations
    with db_conn.cursor() as cur:
        cur.execute("INSERT INTO machines(site_id,erp_ref) VALUES (1,'606') ON CONFLICT DO NOTHING")
        cur.execute("INSERT INTO import_passports(site_id,file_name) VALUES (1,'synthetic-teams.xlsx') RETURNING id")
        passport = cur.fetchone()[0]
    def persist():
        return persist_declarations(db_conn, site_id=1, passport_id=passport, declarations=declarations, recorded_at=datetime.now(timezone.utc))
    assert persist().created == 2
    assert persist().unchanged == 2
    declarations[0].good_parts = 752
    declarations[0].scrap_parts = 48
    assert persist().revised == 1
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM erp_declarations WHERE site_id=1 AND production_order_id='000012'")
        assert cur.fetchone()[0] == 2
        cur.execute('SELECT COUNT(*) FROM erp_declaration_revisions WHERE site_id=1')
        assert cur.fetchone()[0] == 3
