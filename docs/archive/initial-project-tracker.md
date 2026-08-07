# Archive — suivi initial du projet IDDRV

> Ce document reflète le cadrage de démarrage et n'est plus une source d'état.
> Pour l'avancement courant, consulter `docs/implementation-status.md` et
> `docs/orchestrated-implementation-plan.md`.

## Architecture
IDDRV reconciles macro-level factory ERP data (shifts, production runs/work orders) with micro-level machine sensor logs (individual injection molding cycle signals) using TimescaleDB for time-series storage and Redis as a message buffer.

- **Storage**:
  - PostgreSQL for relational metadata (machines, work orders/OFs, shifts/teams).
  - TimescaleDB hypertable `machine_cycles` for high-throughput time-series cycle records.
- **Ingestion**:
  - Standalone python scripts in `ingest/` handle:
    - File format profiling (delimiter, encoding, matrix transposition).
    - Mapping raw cycle data to standard EUROMAP 77/83 canonical profiles.
    - Staging and inserting into TimescaleDB.
- **Reconciliation**:
  - A temporal reconciliation engine correlates machine-level cycles with shift/order timelines from ERP databases based on timestamps, machine IDs, and status.

## Milestones

### Implementation Track
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Specs & Infra | Create technical spec doc and `docker-compose.yml` config | None | IN_PROGRESS (6a02500e-021a-4c41-baf8-1891a11f4ea7) |
| M2 | Database Schema Setup | Write SQL/Python initialization scripts for Postgres/TimescaleDB | M1 | PLANNED |
| M3 | Profiling & Ingestion | Implement file profiler, mapper to EUROMAP, and data insert scripts; create mock data generators | M2 | PLANNED |
| M4 | Temporal Reconciliation | Implement temporal reconciliation logic correlating ERP shifts/OFs and machine cycles | M3 | PLANNED |
| M5 | Final E2E Integration | Pass 100% of E2E tests (Tiers 1-4) and undergo adversarial hardening (Tier 5) | M4, E2E-3 | PLANNED |

### E2E Testing Track
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E-1 | Test Infra & Unit/Boundary Tests | Setup test runner/harness, write Tier 1 & 2 tests | None | IN_PROGRESS (edaeabb1-ce7c-487f-ba36-0e368f320b04) |
| E2E-2 | Integration & Workload Tests | Write Tier 3 & 4 tests | E2E-1 | PLANNED |
| E2E-3 | Publish Test Ready | Finalize tests and publish `TEST_READY.md` / `TEST_INFRA.md` | E2E-2 | PLANNED |

## Interface Contracts
### Ingestion API / CLI
- Entrypoint: Python scripts executed from the shell.
- Profiler output format: JSON dictionary containing:
  - `delimiter`: str (e.g., `,`, `;`, `\t`)
  - `encoding`: str (e.g., `utf-8`, `latin-1`)
  - `transposed`: bool
- Database input schemas conform strictly to EUROMAP 77/83 specifications.

## Code Layout
- `docs/superpowers/specs/industrial-ingestion-backend-db-design.md`: Technical specifications.
- `docker-compose.yml`: Local docker services (TimescaleDB, Redis).
- `db/`: SQL and python setup scripts.
  - `db/init.sql`: Table structure, hypertable creation, extension loading.
  - `db/setup_db.py`: Database setup runner.
- `ingest/`: Standalone ingestion package.
  - `ingest/generate_mock_data.py`: Mock data generator.
  - `ingest/profiler.py`: Formats/encoding detection.
  - `ingest/mapper.py`: Data ingestion/mapping.
  - `ingest/reconcile.py`: Temporal reconciliation.
- `tests/e2e/`: E2E test suite.
  - `tests/e2e/run_tests.py`: Main test runner.
  - `tests/e2e/test_cases/`: Tier 1, 2, 3, 4 test files and definitions.
