"""Deterministic post-import incident detection.

This runtime module only reads committed PostgreSQL business rows. It never
reads scenario files or evaluation ground truth.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping

from ..db import get_connection


DETECTOR_VERSION = "scrap-window-v1"
MINIMUM_WINDOW_CYCLES = 30


@dataclass(frozen=True)
class ScrapWindow:
    machine_id: int
    production_order_id: str | None
    started_at: datetime
    ended_at: datetime
    data_cutoff: datetime
    baseline_rate: float
    incident_rate: float
    defect_type: str | None


def _scrap(row: Mapping) -> bool:
    return bool(row.get("scrap_flag")) or str(row.get("part_quality_status") or "").lower() == "scrap"


def detect_scrap_windows(rows: Iterable[Mapping], minimum: int = MINIMUM_WINDOW_CYCLES) -> list[ScrapWindow]:
    """Return the strongest adjacent baseline/event increase per machine and OF."""
    grouped: dict[tuple[int, str | None], list[Mapping]] = defaultdict(list)
    for row in rows:
        grouped[(int(row["machine_id"]), row.get("production_order_id"))].append(row)

    detected: list[ScrapWindow] = []
    for (machine_id, order_id), values in grouped.items():
        values.sort(key=lambda row: row["time"])
        if len(values) < minimum * 2:
            continue
        best = None
        for split in range(minimum, len(values) - minimum + 1):
            baseline = values[split - minimum:split]
            event = values[split:split + minimum]
            baseline_rate = sum(_scrap(row) for row in baseline) / minimum
            event_rate = sum(_scrap(row) for row in event) / minimum
            increase = event_rate - baseline_rate
            if event_rate < 0.15 or increase < 0.10:
                continue
            score = (increase, event_rate)
            if best is None or score > best[0]:
                best = (score, baseline_rate, event_rate, event)
        if best is None:
            continue
        _, baseline_rate, event_rate, event = best
        defects = Counter(
            str(row["defect_type"]) for row in event if row.get("defect_type")
        )
        detected.append(ScrapWindow(
            machine_id=machine_id,
            production_order_id=order_id,
            started_at=event[0]["time"],
            ended_at=event[-1]["time"],
            data_cutoff=values[-1]["time"],
            baseline_rate=baseline_rate,
            incident_rate=event_rate,
            defect_type=defects.most_common(1)[0][0] if defects else None,
        ))
    return detected


def _detection_key(site_id: int, window: ScrapWindow) -> str:
    payload = ":".join((
        DETECTOR_VERSION,
        str(site_id),
        str(window.machine_id),
        str(window.production_order_id or "none"),
        window.started_at.isoformat(),
        window.ended_at.isoformat(),
    ))
    return hashlib.sha256(payload.encode()).hexdigest()


def trigger_after_import(job, result) -> dict[str, int]:
    """Persist idempotent incidents after a committed machine-cycle import."""
    if not isinstance(result, Mapping) or result.get("transaction_committed") is not True:
        raise ValueError("detector_requires_committed_import")
    passport_id = result.get("passport_id") or getattr(job, "passport_id", None)
    site_id = result.get("site_id") or getattr(job, "site_id", None)
    if not passport_id or site_id is None:
        raise ValueError("detector_requires_passport_and_site")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """WITH affected AS (
                       SELECT machine_id,MAX(time) AS cutoff
                       FROM machine_cycles
                       WHERE passport_id=%s
                       GROUP BY machine_id
                   )
                   SELECT c.time,c.machine_id,c.production_order_id,c.scrap_flag,
                          c.part_quality_status,c.defect_type
                   FROM machine_cycles c
                   JOIN affected a ON a.machine_id=c.machine_id AND c.time<=a.cutoff
                   JOIN machines m ON m.id=c.machine_id
                   WHERE m.site_id=%s
                     AND COALESCE(c.data_quality_status,'valid')='valid'
                   ORDER BY c.machine_id,c.production_order_id,c.time""",
                (str(passport_id), int(site_id)),
            )
            names = [description[0] for description in cur.description]
            rows = [dict(zip(names, row)) for row in cur.fetchall()]
            windows = detect_scrap_windows(rows)
            inserted = 0
            for window in windows:
                severity = "critical" if window.incident_rate >= 0.30 else "high"
                defect = window.defect_type or "scrap"
                cur.execute(
                    """INSERT INTO incidents
                         (site_id,machine_id,production_order_id,order_site_id,status,
                          severity,symptom,defect_type,started_at,ended_at,data_cutoff,
                          confidence,detection_key)
                       VALUES (%s,%s,%s,%s,'open',%s,%s,%s,%s,%s,%s,'high',%s)
                       ON CONFLICT (detection_key) WHERE detection_key IS NOT NULL DO NOTHING""",
                    (
                        int(site_id), window.machine_id, window.production_order_id,
                        int(site_id) if window.production_order_id else None,
                        severity, f"{defect}_increase", window.defect_type,
                        window.started_at, window.ended_at, window.data_cutoff,
                        _detection_key(int(site_id), window),
                    ),
                )
                inserted += cur.rowcount
            conn.commit()
    return {"detected": len(windows), "inserted": inserted}
