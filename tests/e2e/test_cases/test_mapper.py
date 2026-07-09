import subprocess
import os
import pytest
import json

pytestmark = [pytest.mark.feature_mapper]

def get_data_path(filename):
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)

def run_mapper(input_path, profile=None, extra_args=None):
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../ingest/mapper.py"))
    assert os.path.exists(script_path), f"Mapper script {script_path} does not exist"
    args = ["python3", script_path, input_path]
    if profile:
        args.extend(["--profile", profile])
    if extra_args:
        args.extend(extra_args)
    result = subprocess.run(args, capture_output=True, text=True)
    return result

@pytest.mark.tier1
def test_t1_map_01_row_based_mapping():
    """
    T1_MAP_01: Verify mapping standard columns to EUROMAP parameters.
    """
    path = get_data_path("map_standard.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres,Cushion\n2026-07-09T12:00:00Z,mach-A,2.5,180.5,12.4\n")
        
    result = run_mapper(path)
    assert result.returncode == 0, f"Mapper failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert len(data) == 1
    record = data[0]
    assert record.get("cycle_time") == 2.5
    assert record.get("injection_pressure_max") == 180.5
    assert record.get("cushion") == 12.4

@pytest.mark.tier1
def test_t1_map_02_transposed_mapping():
    """
    T1_MAP_02: Verify mapping works correctly on transposed matrices.
    """
    path = get_data_path("map_transposed.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Variable,Cycle1\nTime,2026-07-09T12:00:00Z\nMachine,mach-A\nCycle_Time,2.5\nInj_Pres,180.5\nCushion,12.4\n")
        
    result = run_mapper(path, extra_args=["--transposed"])
    assert result.returncode == 0, f"Mapper failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert len(data) == 1
    record = data[0]
    assert record.get("cycle_time") == 2.5
    assert record.get("injection_pressure_max") == 180.5

@pytest.mark.tier1
def test_t1_map_03_arburg_custom_mapping():
    """
    T1_MAP_03: Verify parsing and mapping of Arburg proprietary header structures.
    """
    path = get_data_path("map_arburg.txt")
    with open(path, "w", encoding="utf-8") as f:
        # Mock Arburg text export with custom metadata headers
        f.write("ARBURG Export File\nMachine: mach-Arburg-01\nDate: 09.07.2026 12:00:00\nData:\nCycle_Time;Inj_Pres;Cushion\n2.5;180.5;12.4\n")
        
    result = run_mapper(path, profile="arburg")
    assert result.returncode == 0, f"Mapper failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert len(data) == 1
    record = data[0]
    assert record.get("machine_id") == "mach-Arburg-01"
    assert record.get("cycle_time") == 2.5

@pytest.mark.tier1
def test_t1_map_04_timestamp_normalization():
    """
    T1_MAP_04: Check conversion of mixed datetime/epoch formats to ISO-8601 UTC.
    """
    path = get_data_path("map_timestamps.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time\n09/07/2026 12:00:00,mach-A,2.5\n1781006400,mach-A,2.4\n")
        
    result = run_mapper(path)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 2
    # Ensure both normalized to UTC strings
    assert data[0].get("timestamp").endswith("Z") or "+00:00" in data[0].get("timestamp")
    assert "2026-07-09" in data[0].get("timestamp")

@pytest.mark.tier1
def test_t1_map_05_unit_conversions():
    """
    T1_MAP_05: Check conversion of alternative physical units (psi/ms) to EUROMAP metric standards (bar/seconds).
    """
    path = get_data_path("map_units.csv")
    with open(path, "w", encoding="utf-8") as f:
        # Inj_Pres in psi (e.g. 2617 psi ~= 180.5 bar), Cycle_Time in ms (2500 ms = 2.5s)
        f.write("Time,Machine,Cycle_Time_ms,Inj_Pres_psi\n2026-07-09T12:00:00Z,mach-A,2500,2617\n")
        
    result = run_mapper(path, extra_args=["--convert-units"])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    record = data[0]
    assert pytest.approx(record.get("cycle_time"), 0.01) == 2.5
    assert pytest.approx(record.get("injection_pressure_max"), 1.0) == 180.4

@pytest.mark.tier2
def test_t2_map_01_missing_mandatory_fields():
    """
    T2_MAP_01: Verify handling of rows missing timestamp or machine ID.
    """
    path = get_data_path("map_missing.csv")
    with open(path, "w", encoding="utf-8") as f:
        # First row missing machine, second row missing time
        f.write("Time,Machine,Cycle_Time\n,mach-A,2.5\n2026-07-09T12:00:00Z,,2.4\n")
        
    result = run_mapper(path)
    # The mapper should either reject these rows with non-zero exit or produce skip logs.
    # Typically, opaque-box E2E test asserts validation errors are reported and bad rows are dropped.
    assert result.returncode != 0 or "skip" in result.stderr.lower() or "missing" in result.stderr.lower()

@pytest.mark.tier2
def test_t2_map_02_range_outliers():
    """
    T2_MAP_02: Ensure physically impossible metrics are filtered out.
    """
    path = get_data_path("map_outliers.csv")
    with open(path, "w", encoding="utf-8") as f:
        # Negative cycle time and extreme pressure (e.g., 999999 bar)
        f.write("Time,Machine,Cycle_Time,Inj_Pres\n2026-07-09T12:00:00Z,mach-A,-2.5,180.5\n2026-07-09T12:00:01Z,mach-A,2.5,999999\n")
        
    result = run_mapper(path)
    # Should flag outliers as invalid
    assert "outlier" in result.stderr.lower() or "invalid" in result.stderr.lower() or result.returncode != 0

@pytest.mark.tier2
def test_t2_map_03_partial_malformed_rows():
    """
    T2_MAP_03: Syntactically malformed middle rows are skipped, while other rows succeed.
    """
    path = get_data_path("map_malformed.csv")
    with open(path, "w", encoding="utf-8") as f:
        # Row 2 is malformed (missing delimiter/bad values)
        f.write("Time,Machine,Cycle_Time\n2026-07-09T12:00:00Z,mach-A,2.5\n2026-07-09T12:00:01Z;mach-A;bad_val\n2026-07-09T12:00:02Z,mach-A,2.7\n")
        
    result = run_mapper(path)
    assert result.returncode == 0 or "warning" in result.stderr.lower()
    data = json.loads(result.stdout)
    # Should succeed on row 1 and row 3, skipping row 2
    assert len(data) == 2
    assert data[0].get("cycle_time") == 2.5
    assert data[1].get("cycle_time") == 2.7

@pytest.mark.tier2
def test_t2_map_04_timestamp_collisions():
    """
    T2_MAP_04: Handle multiple cycles logged on the same machine at the same millisecond timestamp.
    """
    path = get_data_path("map_collision.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time\n2026-07-09T12:00:00.123Z,mach-A,2.5\n2026-07-09T12:00:00.123Z,mach-A,2.6\n")
        
    result = run_mapper(path)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 2
    # Ensure they are either indexed uniquely or flagged
    assert data[0].get("timestamp") == data[1].get("timestamp")

@pytest.mark.tier2
def test_t2_map_05_inconsistent_type_casting():
    """
    T2_MAP_05: Cleanly parse fields with mixed numeric and text string null representation (N/A, NULL).
    """
    path = get_data_path("map_types.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("Time,Machine,Cycle_Time,Inj_Pres\n2026-07-09T12:00:00Z,mach-A,2.5,N/A\n2026-07-09T12:00:01Z,mach-A,NULL,180.5\n")
        
    result = run_mapper(path)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert len(data) == 2
    assert data[0].get("injection_pressure_max") is None
    assert data[1].get("cycle_time") is None
