#!/usr/bin/env python3
"""
traffic_cop.py -- SQLite concurrency lock for the 10-minute pipeline.

Ensures exactly one pipeline instance runs at a time across systemd-managed
processes. WAL mode for concurrent read/write.

Usage (import):
    from traffic_cop import PipelineLock
    lock = PipelineLock()
    if not lock.acquire():
        sys.exit(0)
    try:
        run_pipeline()
    finally:
        lock.release()

CLI test:  python3 traffic_cop.py
"""

import sqlite3
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

PROJECT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("GAZZETTA_DB_PATH", str(PROJECT / "data" / "gazzetta.db"))

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_state (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    state       TEXT NOT NULL DEFAULT 'IDLE'
                    CHECK (state IN ('IDLE', 'PROCESSING', 'ERROR')),
    started_at  TEXT,
    pid         INTEGER,
    hostname    TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
)
"""


class PipelineLock:
    """Acquire/release a singleton pipeline execution lock via SQLite state row.

    Only one process holds the lock at a time. acquire() returns False when
    another process is PROCESSING -- caller must sys.exit(0).
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.acquired = False
        self._conn = None

    # ── private ──────────────────────────────────────────────────
    def _ensure_table(self, conn):
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(CREATE_TABLE_SQL)
        conn.execute(
            "INSERT OR IGNORE INTO pipeline_state (id, state) VALUES (1, 'IDLE')"
        )
        conn.commit()

    def _ts(self):
        return datetime.now(timezone.utc).isoformat()

    # ── public ───────────────────────────────────────────────────
    def acquire(self):
        """Try to seize the lock. Returns True on success, False if busy."""
        self._conn = sqlite3.connect(self.db_path, timeout=10)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._ensure_table(self._conn)

        row = self._conn.execute(
            "SELECT state, started_at, pid FROM pipeline_state WHERE id=1"
        ).fetchone()

        if not row:
            print("traffic_cop: corrupt state row. Exiting.", file=sys.stderr)
            self._conn.close()
            sys.exit(1)

        state, started_at, pid = row

        if state == "PROCESSING":
            print(
                f"traffic_cop: locked by PID {pid} since {started_at}. Exiting."
            )
            self._conn.close()
            return False

        self._conn.execute(
            """UPDATE pipeline_state
               SET state='PROCESSING', started_at=?, pid=?, hostname=?, updated_at=?
               WHERE id=1 AND state='IDLE'""",
            (self._ts(), os.getpid(), os.uname().nodename, self._ts()),
        )
        self._conn.commit()
        self.acquired = True
        print(f"traffic_cop: lock acquired (PID {os.getpid()}).")
        return True

    def release(self):
        """Release the lock, resetting state to IDLE."""
        if not self._conn or not self.acquired:
            return
        try:
            self._conn.execute(
                "UPDATE pipeline_state SET state='IDLE', updated_at=? WHERE id=1",
                (self._ts(),),
            )
            self._conn.commit()
            print(f"traffic_cop: lock released (PID {os.getpid()}).")
        except sqlite3.Error as e:
            print(f"traffic_cop: release error: {e}", file=sys.stderr)
        finally:
            self._conn.close()
            self.acquired = False

    def set_error(self):
        """Non-blocking ERROR state -- next run can still acquire."""
        if not self._conn:
            return
        try:
            self._conn.execute(
                "UPDATE pipeline_state SET state='ERROR', updated_at=? WHERE id=1",
                (self._ts(),),
            )
            self._conn.commit()
        except sqlite3.Error:
            pass

    # ── context manager ──────────────────────────────────────────
    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, _tb):
        if exc_type is not None:
            self.set_error()
        self.release()
        return False


# ── CLI test (dummy sleep) ──────────────────────────────────────────
if __name__ == "__main__":
    import time
    print("traffic_cop: test mode")
    lock = PipelineLock()
    if not lock.acquire():
        sys.exit(0)
    try:
        print("  doing work (3 s)...")
        time.sleep(3)
        print("  work complete.")
    finally:
        lock.release()
    print("done.")
