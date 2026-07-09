import argparse
import sys
import os
import json
import time
import subprocess
import urllib.parse
from pathlib import Path
import pytest

# Add current directory and tests/e2e to python path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from env_manager import check_postgres_connection, check_redis_connection, check_docker_containers

class JsonReportPlugin:
    def __init__(self, output_path):
        self.output_path = output_path
        self.results = []
        self.start_time = None
        self.end_time = None

    def pytest_sessionstart(self, session):
        self.start_time = time.time()

    def pytest_runtest_logreport(self, report):
        # We only record the 'call' phase (the actual test execution)
        # or a failed/skipped 'setup' phase or a failed 'teardown' phase
        if report.when == "call" or (report.when == "setup" and (report.failed or report.skipped)) or (report.when == "teardown" and report.failed):
            outcome = report.outcome
            if report.failed:
                outcome = "failed"
            elif report.skipped:
                outcome = "skipped"
                
            self.results.append({
                "nodeid": report.nodeid,
                "outcome": outcome,
                "duration": report.duration,
                "error": str(report.longrepr) if report.failed else None
            })

    def pytest_sessionfinish(self, session, exitstatus):
        self.end_time = time.time()
        summary = {
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r["outcome"] == "passed"),
            "failed": sum(1 for r in self.results if r["outcome"] == "failed"),
            "skipped": sum(1 for r in self.results if r["outcome"] == "skipped"),
            "duration": self.end_time - self.start_time,
            "exitcode": int(exitstatus),
            "tests": self.results
        }
        
        # Write JSON report
        with open(self.output_path, "w") as f:
            json.dump(summary, f, indent=2)
            
        # Write TXT report
        txt_path = self.output_path.replace(".json", ".txt")
        with open(txt_path, "w") as f:
            f.write("=== E2E Test Execution Summary ===\n")
            f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Duration: {summary['duration']:.2f}s\n")
            f.write(f"Total Tests: {summary['total']}\n")
            f.write(f"Passed: {summary['passed']}\n")
            f.write(f"Failed: {summary['failed']}\n")
            f.write(f"Skipped: {summary['skipped']}\n")
            f.write(f"Exit Code: {summary['exitcode']}\n\n")
            f.write("=== Detail Report ===\n")
            for r in self.results:
                f.write(f"{r['nodeid']} - {r['outcome'].upper()} ({r['duration']:.4f}s)\n")
                if r['error']:
                    # Indent error details
                    indented = "\n".join("  " + line for line in r['error'].splitlines())
                    f.write(f"Error details:\n{indented}\n\n")

def main():
    parser = argparse.ArgumentParser(description="IDDRV E2E Test Suite Runner")
    parser.add_argument("-t", "--tier", type=str, default="1,2", help="Tiers of tests to run (comma-separated, e.g. '1' or '1,2')")
    parser.add_argument("-f", "--feature", type=str, default="all", help="Features to run (comma-separated or 'all')")
    parser.add_argument("--db-url", type=str, default="postgresql://iddrv_user:iddrv_secret_2024@localhost:5432/iddrv_test", help="TimescaleDB connection URL")
    parser.add_argument("--redis-url", type=str, default="redis://localhost:6379/1", help="Redis connection URL")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable detailed verbose output")
    parser.add_argument("--fail-fast", action="store_true", help="Stop execution immediately on first test failure")
    
    args = parser.parse_args()

    target_db = urllib.parse.urlparse(args.db_url).path.lstrip("/")
    if not target_db.endswith("_test"):
        parser.error("La suite E2E refuse une base qui ne se termine pas par '_test'.")

    setup_script = Path(__file__).resolve().parents[2] / "db" / "setup_db.py"
    print(f"Preparing isolated test database: {target_db}")
    setup_result = subprocess.run(
        [sys.executable, str(setup_script), "--db-url", args.db_url],
        text=True,
    )
    if setup_result.returncode != 0:
        print("Unable to prepare the E2E database.", file=sys.stderr)
        sys.exit(setup_result.returncode)
    
    print("====================================================")
    print("         IDDRV E2E PRE-FLIGHT CHECKS")
    print("====================================================")
    
    # Check docker containers
    docker_ok, docker_msg = check_docker_containers()
    print(f"Docker Daemon Status: {'RUNNING' if docker_ok else 'NOT RUNNING'}")
    if not docker_ok:
        print(f"  Warning details: {docker_msg}")
        
    # Check PostgreSQL/TimescaleDB
    db_ok = check_postgres_connection(args.db_url)
    print(f"PostgreSQL/TimescaleDB: {'CONNECTED' if db_ok else 'UNREACHABLE'}")
    if not db_ok:
        print(f"  Warning: Cannot connect to DB at {args.db_url}")
        
    # Check Redis
    redis_ok = check_redis_connection(args.redis_url)
    print(f"Redis:                  {'CONNECTED' if redis_ok else 'UNREACHABLE'}")
    if not redis_ok:
        print(f"  Warning: Cannot connect to Redis at {args.redis_url}")
        
    print("====================================================\n")
    
    # We will log status warning, but we still run pytest to discover and execute tests 
    # (even if they fail due to unreachable environment/missing scripts, we want a clean execution report).
    
    pytest_args = []
    
    # Set targets
    # Path to test cases folder
    test_cases_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_cases")
    pytest_args.append(test_cases_dir)
    
    # Verbosity
    if args.verbose:
        pytest_args.append("-vv")
        pytest_args.append("-s")
    else:
        pytest_args.append("-v")
        
    # Fail fast
    if args.fail_fast:
        pytest_args.append("-x")
        
    # Custom args for conftest
    pytest_args.append(f"--tier={args.tier}")
    pytest_args.append(f"--feature={args.feature}")
    pytest_args.append(f"--db-url={args.db_url}")
    pytest_args.append(f"--redis-url={args.redis_url}")
    
    # Run tests and generate reports
    report_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report.json")
    report_plugin = JsonReportPlugin(report_json_path)
    
    print(f"Starting pytest execution with args: {pytest_args}")
    exit_code = pytest.main(pytest_args, plugins=[report_plugin])
    
    print("\n====================================================")
    print(f"E2E execution completed with exit code: {exit_code}")
    print(f"Reports saved:")
    print(f"  - JSON Report: {report_json_path}")
    print(f"  - Text Report: {report_json_path.replace('.json', '.txt')}")
    print("====================================================")
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
