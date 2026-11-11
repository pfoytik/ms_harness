"""
Tool-agnostic SQLite interface for the MS Harness samples database.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str) -> None:
    schema = Path(__file__).parent.parent / "db" / "schema.sql"
    conn = _connect(db_path)
    conn.executescript(schema.read_text())
    conn.commit()
    conn.close()


# ── Sweeps ────────────────────────────────────────────────────────────────────

def create_sweep(db_path: str, sweep_type: str, n_planned: int, notes: str = None) -> int:
    conn = _connect(db_path)
    cur = conn.execute(
        "INSERT INTO sweeps (sweep_type, n_planned, status, notes, created_at) VALUES (?,?,?,?,?)",
        (sweep_type, n_planned, "running", notes, _now()),
    )
    sweep_id = cur.lastrowid
    conn.commit()
    conn.close()
    return sweep_id


def complete_sweep(db_path: str, sweep_id: int, n_complete: int) -> None:
    conn = _connect(db_path)
    conn.execute(
        "UPDATE sweeps SET status=?, n_complete=?, completed_at=? WHERE sweep_id=?",
        ("complete", n_complete, _now(), sweep_id),
    )
    conn.commit()
    conn.close()


def list_sweeps(db_path: str) -> list[dict]:
    conn = _connect(db_path)
    rows = conn.execute("SELECT * FROM sweeps ORDER BY sweep_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Scenarios ─────────────────────────────────────────────────────────────────

def create_scenario(db_path: str, sweep_id: int) -> int:
    conn = _connect(db_path)
    cur = conn.execute(
        "INSERT INTO scenarios (sweep_id, status, created_at) VALUES (?,?,?)",
        (sweep_id, "pending", _now()),
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid


def write_scenario_result(db_path: str, scenario_id: int,
                          inputs: dict, outputs: dict) -> None:
    conn = _connect(db_path)
    conn.executemany(
        "INSERT INTO inputs (scenario_id, parameter, value) VALUES (?,?,?)",
        [(scenario_id, k, float(v)) for k, v in inputs.items()],
    )
    conn.executemany(
        "INSERT INTO outputs (scenario_id, metric, value) VALUES (?,?,?)",
        [(scenario_id, k, float(v)) for k, v in outputs.items()],
    )
    conn.execute(
        "UPDATE scenarios SET status=?, completed_at=? WHERE scenario_id=?",
        ("complete", _now(), scenario_id),
    )
    conn.commit()
    conn.close()


def load_sweep_data(db_path: str, sweep_id: int) -> tuple[list[dict], list[dict]]:
    """Return (inputs_rows, outputs_rows) for all complete scenarios in sweep."""
    conn = _connect(db_path)
    scenario_ids = [
        r[0] for r in conn.execute(
            "SELECT scenario_id FROM scenarios WHERE sweep_id=? AND status='complete'",
            (sweep_id,),
        ).fetchall()
    ]
    if not scenario_ids:
        conn.close()
        return [], []

    ph = ",".join("?" * len(scenario_ids))
    inputs = conn.execute(
        f"SELECT scenario_id, parameter, value FROM inputs WHERE scenario_id IN ({ph})",
        scenario_ids,
    ).fetchall()
    outputs = conn.execute(
        f"SELECT scenario_id, metric, value FROM outputs WHERE scenario_id IN ({ph})",
        scenario_ids,
    ).fetchall()
    conn.close()
    return [dict(r) for r in inputs], [dict(r) for r in outputs]


def load_all_data(db_path: str) -> tuple[list[dict], list[dict]]:
    """Return all complete scenario inputs and outputs across all sweeps."""
    conn = _connect(db_path)
    inputs = conn.execute(
        "SELECT i.scenario_id, i.parameter, i.value FROM inputs i "
        "JOIN scenarios s USING (scenario_id) WHERE s.status='complete'"
    ).fetchall()
    outputs = conn.execute(
        "SELECT o.scenario_id, o.metric, o.value FROM outputs o "
        "JOIN scenarios s USING (scenario_id) WHERE s.status='complete'"
    ).fetchall()
    conn.close()
    return [dict(r) for r in inputs], [dict(r) for r in outputs]


# ── Findings ──────────────────────────────────────────────────────────────────

def save_finding(db_path: str, sweep_id: int, report: dict) -> int:
    conn = _connect(db_path)
    cur = conn.execute(
        "INSERT INTO findings (sweep_id, report_json, created_at) VALUES (?,?,?)",
        (sweep_id, json.dumps(report), _now()),
    )
    fid = cur.lastrowid
    conn.commit()
    conn.close()
    return fid


def load_latest_finding(db_path: str) -> dict | None:
    conn = _connect(db_path)
    row = conn.execute(
        "SELECT report_json FROM findings ORDER BY finding_id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def db_summary(db_path: str) -> dict:
    conn = _connect(db_path)
    n_sweeps   = conn.execute("SELECT COUNT(*) FROM sweeps").fetchone()[0]
    n_complete = conn.execute("SELECT COUNT(*) FROM scenarios WHERE status='complete'").fetchone()[0]
    n_pending  = conn.execute("SELECT COUNT(*) FROM scenarios WHERE status='pending'").fetchone()[0]
    n_findings = conn.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    conn.close()
    return {
        "sweeps": n_sweeps,
        "scenarios_complete": n_complete,
        "scenarios_pending": n_pending,
        "findings": n_findings,
    }
