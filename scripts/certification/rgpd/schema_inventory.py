"""Read tracked SQL declarations only; no DB access. Output is a source index, not effective DDL."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[3]


def inventory():
    sources = [ROOT / "db/init.sql", *sorted((ROOT / "db/migrations").glob("*.sql")), ROOT / "db/setup_db.py"]
    result = {"scope": "lexical declarations; migrations NOT executed", "sources": [], "tables": {}}
    for source in sources:
        content = source.read_text()
        relative = str(source.relative_to(ROOT))
        result["sources"].append({"path": relative, "sha256": hashlib.sha256(content.encode()).hexdigest()})
        for match in re.finditer(r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?([a-z_]+)\s*\(", content):
            result["tables"].setdefault(match[1], []).append({"path": relative, "line": content[:match.start()].count("\n") + 1})
    return result


if __name__ == "__main__":
    print(json.dumps(inventory(), indent=2, sort_keys=True))
