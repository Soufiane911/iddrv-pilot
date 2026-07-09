import subprocess
import os
import pytest
import json

pytestmark = [pytest.mark.feature_profiler]

def get_data_path(filename):
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, filename)

def run_profiler(filepath, extra_args=None):
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../ingest/profiler.py"))
    assert os.path.exists(script_path), f"Profiler script {script_path} does not exist"
    args = ["python3", script_path, filepath]
    if extra_args:
        args.extend(extra_args)
    result = subprocess.run(args, capture_output=True, text=True)
    return result

@pytest.mark.tier1
def test_t1_prof_01_comma_delimiter():
    """
    T1_PROF_01: Correctly profile a standard comma-delimited file.
    """
    path = get_data_path("test_comma.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("timestamp,machine_id,cycle_time,pressure\n2026-07-09T12:00:00Z,m1,2.5,180.5\n")
    
    result = run_profiler(path)
    assert result.returncode == 0, f"Profiler run failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert data.get("delimiter") == ","

@pytest.mark.tier1
def test_t1_prof_02_semicolon_delimiter():
    """
    T1_PROF_02: Correctly profile a semicolon-delimited file.
    """
    path = get_data_path("test_semicolon.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("timestamp;machine_id;cycle_time;pressure\n2026-07-09T12:00:00Z;m1;2.5;180.5\n")
        
    result = run_profiler(path)
    assert result.returncode == 0, f"Profiler run failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert data.get("delimiter") == ";"

@pytest.mark.tier1
def test_t1_prof_03_tab_delimiter():
    """
    T1_PROF_03: Correctly profile a tab-delimited file.
    """
    path = get_data_path("test_tab.tsv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("timestamp\tmachine_id\tcycle_time\tpressure\n2026-07-09T12:00:00Z\tm1\t2.5\t180.5\n")
        
    result = run_profiler(path)
    assert result.returncode == 0, f"Profiler run failed: {result.stderr}"
    data = json.loads(result.stdout)
    assert data.get("delimiter") == "\t"

@pytest.mark.tier1
def test_t1_prof_04_encoding_detection():
    """
    T1_PROF_04: Differentiate and identify utf-8 and iso-8859-1 (latin-1) encodings.
    """
    path_utf8 = get_data_path("test_utf8.csv")
    with open(path_utf8, "w", encoding="utf-8") as f:
        f.write("timestamp,machine,paramètres\n2026-07-09T12:00:00Z,m1,valeur_céleste\n")
        
    path_latin1 = get_data_path("test_latin1.csv")
    with open(path_latin1, "w", encoding="iso-8859-1") as f:
        f.write("timestamp,machine,paramètres\n2026-07-09T12:00:00Z,m1,valeur_céleste\n")
        
    res_utf8 = run_profiler(path_utf8)
    assert res_utf8.returncode == 0
    data_utf8 = json.loads(res_utf8.stdout)
    assert "utf-8" in data_utf8.get("encoding").lower()
    
    res_latin1 = run_profiler(path_latin1)
    assert res_latin1.returncode == 0
    data_latin1 = json.loads(res_latin1.stdout)
    assert "iso-8859-1" in data_latin1.get("encoding").lower() or "latin-1" in data_latin1.get("encoding").lower() or "windows-1252" in data_latin1.get("encoding").lower()

@pytest.mark.tier1
def test_t1_prof_05_transposition_flag():
    """
    T1_PROF_05: Detect transposed format where variables are listed in rows rather than columns.
    """
    path = get_data_path("test_transposed.csv")
    with open(path, "w", encoding="utf-8") as f:
        # Rows represent features, columns represent individual observation steps
        f.write("Variable,Cycle1,Cycle2,Cycle3\ntimestamp,2026-07-09T12:00:00Z,2026-07-09T12:00:01Z,2026-07-09T12:00:02Z\nmachine_id,m1,m1,m1\ncycle_time,2.5,2.4,2.6\n")
        
    result = run_profiler(path)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data.get("transposed") is True

@pytest.mark.tier2
def test_t2_prof_01_empty_file():
    """
    T2_PROF_01: Safely handle 0-byte or empty files without crashes.
    """
    path = get_data_path("test_empty.csv")
    with open(path, "w") as f:
        pass
        
    result = run_profiler(path)
    # The script can return error status or default config. It should NOT throw an unhandled python crash.
    assert "traceback" not in result.stderr.lower()
    if result.returncode == 0:
        data = json.loads(result.stdout)
        assert "error" in data or data.get("delimiter") is None

@pytest.mark.tier2
def test_t2_prof_02_mixed_delimiters_quoted():
    """
    T2_PROF_02: Delimiters inside quotes should not confuse detection.
    """
    path = get_data_path("test_mixed.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("id,comment,value\n1,\"This is a comment, with commas!\",9.8\n2,\"No comma here\",10.1\n")
        
    result = run_profiler(path)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    # comma should still be identified as delimiter
    assert data.get("delimiter") == ","

@pytest.mark.tier2
def test_t2_prof_03_binary_input():
    """
    T2_PROF_03: Script halts and exits with validation code if input is binary.
    """
    path = get_data_path("test_binary.png")
    # Write some binary garbage
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00")
        
    result = run_profiler(path)
    assert result.returncode != 0
    assert "binary" in result.stderr.lower() or "text" in result.stderr.lower() or "decode" in result.stderr.lower()

@pytest.mark.tier2
def test_t2_prof_04_unbalanced_rows():
    """
    T2_PROF_04: Profiler should log a warning or return error if row lengths vary wildly.
    """
    path = get_data_path("test_unbalanced.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("a,b,c\n1,2\n3,4,5,6\n7\n")
        
    result = run_profiler(path)
    # Should handle it gracefully, possibly warning that file is malformed
    assert result.returncode != 0 or "warning" in result.stderr.lower() or "malformed" in result.stderr.lower()

@pytest.mark.tier2
def test_t2_prof_05_oom_protection():
    """
    T2_PROF_05: Profiler operates on chunks to keep memory footprint low (<50MB) on large files.
    """
    path = get_data_path("test_large_dummy.csv")
    
    # We can construct a relatively large file for verification without taking gigabytes of disk.
    # A few megabytes is enough to test chunking behaviour if chunk size is small, or we simulate a stream.
    # Let's generate a 5MB file.
    with open(path, "w", encoding="utf-8") as f:
        f.write("timestamp,machine_id,cycle_time,pressure\n")
        for i in range(100000):
            f.write(f"2026-07-09T12:00:00Z,m1,2.5,{i}.0\n")
            
    import time
    start = time.time()
    result = run_profiler(path)
    elapsed = time.time() - start
    
    assert result.returncode == 0
    assert elapsed < 5.0  # Must finish fast, indicating it didn't do expensive loading
    # Clean up large file
    if os.path.exists(path):
        os.remove(path)
