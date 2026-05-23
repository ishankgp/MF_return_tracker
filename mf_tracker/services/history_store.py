import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional


class HistoryStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS fund_master (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    is_portfolio INTEGER NOT NULL DEFAULT 0,
                    last_seen_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS refresh_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    fund_count INTEGER DEFAULT 0,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS nav_daily (
                    code TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    nav REAL,
                    source_date TEXT,
                    is_stale INTEGER NOT NULL DEFAULT 0,
                    run_id INTEGER,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (code, as_of_date),
                    FOREIGN KEY(code) REFERENCES fund_master(code)
                );

                CREATE TABLE IF NOT EXISTS metric_daily (
                    code TEXT NOT NULL,
                    as_of_date TEXT NOT NULL,
                    returns_json TEXT NOT NULL,
                    consistency_score REAL,
                    data_completeness REAL NOT NULL DEFAULT 0,
                    score_components_json TEXT,
                    run_id INTEGER,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (code, as_of_date),
                    FOREIGN KEY(code) REFERENCES fund_master(code)
                );
                """
            )

    def start_refresh_run(self, trigger_type: str) -> int:
        started_at = datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO refresh_runs (started_at, status, trigger_type)
                VALUES (?, 'running', ?)
                """,
                (started_at, trigger_type),
            )
            return int(cur.lastrowid)

    def finish_refresh_run(
        self,
        run_id: int,
        status: str,
        fund_count: int = 0,
        error: Optional[str] = None,
    ) -> None:
        finished_at = datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE refresh_runs
                SET finished_at = ?, status = ?, fund_count = ?, error = ?
                WHERE id = ?
                """,
                (finished_at, status, fund_count, error, run_id),
            )

    def save_snapshot(
        self,
        run_id: int,
        funds: List[Dict[str, object]],
    ) -> None:
        created_at = datetime.utcnow().isoformat()
        with self._lock, self._connect() as conn:
            for fund in funds:
                code = str(fund.get("code", ""))
                if not code:
                    continue

                conn.execute(
                    """
                    INSERT INTO fund_master (code, name, is_portfolio, last_seen_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(code) DO UPDATE SET
                        name = excluded.name,
                        is_portfolio = excluded.is_portfolio,
                        last_seen_at = excluded.last_seen_at
                    """,
                    (
                        code,
                        str(fund.get("name", "")),
                        1 if bool(fund.get("is_portfolio", False)) else 0,
                        created_at,
                    ),
                )

                as_of_date = fund.get("as_of_date") or fund.get("current_date")
                if not as_of_date:
                    continue

                conn.execute(
                    """
                    INSERT INTO nav_daily (code, as_of_date, nav, source_date, is_stale, run_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(code, as_of_date) DO UPDATE SET
                        nav = excluded.nav,
                        source_date = excluded.source_date,
                        is_stale = excluded.is_stale,
                        run_id = excluded.run_id,
                        created_at = excluded.created_at
                    """,
                    (
                        code,
                        str(as_of_date),
                        fund.get("current_nav"),
                        fund.get("current_date"),
                        1 if bool(fund.get("is_stale", False)) else 0,
                        run_id,
                        created_at,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO metric_daily (
                        code, as_of_date, returns_json, consistency_score, data_completeness,
                        score_components_json, run_id, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(code, as_of_date) DO UPDATE SET
                        returns_json = excluded.returns_json,
                        consistency_score = excluded.consistency_score,
                        data_completeness = excluded.data_completeness,
                        score_components_json = excluded.score_components_json,
                        run_id = excluded.run_id,
                        created_at = excluded.created_at
                    """,
                    (
                        code,
                        str(as_of_date),
                        json.dumps(fund.get("returns", {})),
                        fund.get("consistency_score"),
                        float(fund.get("data_completeness", 0) or 0),
                        json.dumps(fund.get("score_components", {})),
                        run_id,
                        created_at,
                    ),
                )

    def get_last_successful_refresh(self) -> Optional[Dict[str, object]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, started_at, finished_at, fund_count, trigger_type
                FROM refresh_runs
                WHERE status = 'success'
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
            return dict(row) if row else None

    def get_fund_history(self, code: str, range_key: str) -> List[Dict[str, object]]:
        range_days = {"1y": 365, "3y": 1095, "5y": 1825}.get(range_key, 365)
        min_date = (datetime.utcnow() - timedelta(days=range_days)).date().isoformat()

        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    n.code,
                    n.as_of_date,
                    n.nav,
                    n.source_date,
                    n.is_stale,
                    m.consistency_score,
                    m.data_completeness,
                    m.returns_json
                FROM nav_daily n
                LEFT JOIN metric_daily m
                    ON m.code = n.code AND m.as_of_date = n.as_of_date
                WHERE n.code = ? AND n.as_of_date >= ?
                ORDER BY n.as_of_date ASC
                """,
                (str(code), min_date),
            ).fetchall()

        history: List[Dict[str, object]] = []
        for row in rows:
            item = dict(row)
            item["returns"] = json.loads(item.pop("returns_json", "{}") or "{}")
            item["is_stale"] = bool(item.get("is_stale", 0))
            history.append(item)
        return history

