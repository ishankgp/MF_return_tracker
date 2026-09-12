import json
from datetime import datetime, timedelta
import pytest

from mf_tracker.services.history_store import HistoryStore


@pytest.mark.regression
@pytest.mark.integration
class TestRegressionHistoryDB:
    def test_schema_initialization_and_tables(self, temp_db):
        """
        Verify that HistoryStore properly initializes the SQLite tables.
        """
        with temp_db._connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            )
            tables = [row["name"] for row in cursor.fetchall()]

        assert "fund_master" in tables
        assert "refresh_runs" in tables
        assert "nav_daily" in tables
        assert "metric_daily" in tables

    def test_refresh_run_lifecycle_transitions(self, temp_db):
        """
        Verify the complete lifecycle of a refresh run:
        - start_refresh_run creates a 'running' record with valid ID
        - finish_refresh_run updates status to 'success' or 'failed', records fund count & error
        """
        run_id = temp_db.start_refresh_run(trigger_type="manual_test")
        assert isinstance(run_id, int)
        assert run_id > 0

        with temp_db._connect() as conn:
            row = conn.execute("SELECT * FROM refresh_runs WHERE id = ?", (run_id,)).fetchone()
            assert row["status"] == "running"
            assert row["trigger_type"] == "manual_test"
            assert row["finished_at"] is None

        # Finish run with success
        temp_db.finish_refresh_run(run_id, status="success", fund_count=15)
        with temp_db._connect() as conn:
            row = conn.execute("SELECT * FROM refresh_runs WHERE id = ?", (run_id,)).fetchone()
            assert row["status"] == "success"
            assert row["fund_count"] == 15
            assert row["finished_at"] is not None
            assert row["error"] is None

        # Verify get_last_successful_refresh
        last_success = temp_db.get_last_successful_refresh()
        assert last_success is not None
        assert last_success["id"] == run_id
        assert last_success["fund_count"] == 15

    def test_save_snapshot_and_upsert_idempotency(self, temp_db):
        """
        Verify that save_snapshot properly records fund_master, nav_daily,
        and metric_daily, and can be called twice for the same date without failure.
        """
        run_id = temp_db.start_refresh_run("daily_cron")

        sample_fund = {
            "code": "100500",
            "name": "Kotak Emerging Equity",
            "is_portfolio": True,
            "as_of_date": "2026-05-20",
            "current_date": "2026-05-20",
            "current_nav": 85.50,
            "is_stale": False,
            "returns": {"1day": 0.5, "1year": 18.2},
            "consistency_score": 14.5,
            "data_completeness": 0.9,
            "score_components": {"coverage": 0.67},
        }

        # First snapshot save
        temp_db.save_snapshot(run_id, [sample_fund])

        # Verify fund_master
        with temp_db._connect() as conn:
            fm = conn.execute("SELECT * FROM fund_master WHERE code = ?", ("100500",)).fetchone()
            assert fm["name"] == "Kotak Emerging Equity"
            assert fm["is_portfolio"] == 1

            nav = conn.execute("SELECT * FROM nav_daily WHERE code = ?", ("100500",)).fetchone()
            assert nav["nav"] == 85.50
            assert nav["as_of_date"] == "2026-05-20"

            metric = conn.execute("SELECT * FROM metric_daily WHERE code = ?", ("100500",)).fetchone()
            assert metric["consistency_score"] == 14.5
            returns = json.loads(metric["returns_json"])
            assert returns["1year"] == 18.2

        # Second snapshot save (same date, updated NAV - should UPSERT without error)
        sample_fund_updated = dict(sample_fund)
        sample_fund_updated["current_nav"] = 86.20
        temp_db.save_snapshot(run_id, [sample_fund_updated])

        with temp_db._connect() as conn:
            count = conn.execute("SELECT count(*) as c FROM nav_daily WHERE code = ?", ("100500",)).fetchone()["c"]
            assert count == 1  # Should NOT duplicate row
            updated_nav = conn.execute("SELECT nav FROM nav_daily WHERE code = ?", ("100500",)).fetchone()["nav"]
            assert updated_nav == 86.20

    def test_get_fund_history_queries_and_ranges(self, temp_db):
        """
        Verify get_fund_history fetches and parses records across ranges (1y, 3y, 5y).
        """
        run_id = temp_db.start_refresh_run("seed")
        code = "100999"

        # Create 3 snapshots: today, 6 months ago, 2 years ago
        today = datetime.utcnow().date()
        date_today = today.isoformat()
        date_6m = (today - timedelta(days=180)).isoformat()
        date_2y = (today - timedelta(days=730)).isoformat()

        funds_snapshots = [
            {"code": code, "name": "Historical Fund", "as_of_date": date_today, "current_nav": 120.0, "returns": {"1m": 2.0}},
            {"code": code, "name": "Historical Fund", "as_of_date": date_6m, "current_nav": 110.0, "returns": {"1m": 1.0}},
            {"code": code, "name": "Historical Fund", "as_of_date": date_2y, "current_nav": 95.0, "returns": {"1m": 0.5}},
        ]

        temp_db.save_snapshot(run_id, funds_snapshots)

        # Query range '1y' (should return today and 6 months ago, but not 2 years ago)
        hist_1y = temp_db.get_fund_history(code, "1y")
        assert len(hist_1y) == 2
        dates_1y = [row["as_of_date"] for row in hist_1y]
        assert date_today in dates_1y
        assert date_6m in dates_1y
        assert date_2y not in dates_1y

        # Query range '3y' (should return all 3)
        hist_3y = temp_db.get_fund_history(code, "3y")
        assert len(hist_3y) == 3

        # Non-existent code returns empty list
        assert temp_db.get_fund_history("non_existent", "1y") == []
