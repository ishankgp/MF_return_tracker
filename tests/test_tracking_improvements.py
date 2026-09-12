import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

os.environ["FLASK_ENV"] = "testing"

import app as app_module  # noqa: E402
from fetch_mf_returns import _compute_metrics_for_fund, _compute_score, api_cache, clear_data_caches  # noqa: E402
from mf_tracker.services.history_store import HistoryStore  # noqa: E402


class TestTrackingImprovements(unittest.TestCase):
    def test_cache_invalidation_clears_fetch_and_app_cache(self):
        api_cache["fund_raw_123"] = {"value": 1}
        app_module.memory_cache["funds_cache:all:latest"] = {"value": 2}

        clear_data_caches()
        app_module.clear_response_caches()

        self.assertNotIn("fund_raw_123", api_cache)
        self.assertNotIn("funds_cache:all:latest", app_module.memory_cache)

    def test_sparse_history_returns_none_not_zero(self):
        as_of = datetime(2026, 5, 20)
        parsed = []
        for offset in range(0, 15):
            dt = as_of - timedelta(days=offset)
            parsed.append((dt, 100.0 + offset, dt.strftime("%d-%m-%Y")))
        parsed.sort(key=lambda row: row[0])
        dates = [row[0] for row in parsed]

        raw = {
            "name": "Test Fund",
            "code": "999999",
            "parsed_navs": parsed,
            "parsed_dates": dates,
            "is_portfolio": True,
        }

        metrics = _compute_metrics_for_fund(raw, requested_as_of=as_of)
        self.assertIsNotNone(metrics["returns"]["1day"])
        self.assertIsNone(metrics["returns"]["5year"])

    def test_score_reweighting_works_with_missing_periods(self):
        returns = {"1year": None, "2year": 20.0, "3year": 10.0}
        score, components = _compute_score(returns)

        self.assertAlmostEqual(score, 13.75, places=2)
        self.assertIn("2year", components["normalized_weights"])
        self.assertIn("3year", components["normalized_weights"])
        self.assertNotIn("1year", components["normalized_weights"])
        self.assertAlmostEqual(components["normalized_weights"]["2year"], 0.375, places=3)
        self.assertAlmostEqual(components["normalized_weights"]["3year"], 0.625, places=3)

    def test_api_schema_includes_new_metadata_fields(self):
        app_module.app.config["LOGIN_DISABLED"] = True
        client = app_module.app.test_client()

        mock_payload = {
            "funds": [
                {
                    "name": "Test Fund",
                    "code": "111111",
                    "current_nav": 123.45,
                    "returns": {
                        "1day": None,
                        "1week": 1.0,
                        "1month": 2.0,
                        "3month": 3.0,
                        "6month": 4.0,
                        "1year": 5.0,
                        "2year": 6.0,
                        "3year": 7.0,
                        "5year": None,
                    },
                    "dates": {"1day": None},
                    "period_source_dates": {"1day": None},
                    "current_date": "21-05-2026",
                    "as_of_date": "21-05-2026",
                    "year_breakdown": {},
                    "consistency_score": 6.2,
                    "is_portfolio": True,
                    "data_completeness": 0.7,
                    "is_stale": False,
                    "score_components": {"coverage": 1.0},
                    "score_method_version": "v2_reweighted_missing",
                }
            ],
            "timestamp": "2026-05-23T10:00:00",
            "count": 1,
            "comparison_anchor_date": "21-05-2026",
            "comparison_header_dates": {"1day": "20-05-2026"},
            "scope": "portfolio",
        }

        with patch("app.get_cached_data", return_value=mock_payload):
            response = client.get("/api/funds?scope=portfolio")
        self.assertEqual(response.status_code, 200)

        body = response.get_json()
        self.assertIn("comparison_anchor_date", body)
        self.assertIn("comparison_header_dates", body)
        self.assertEqual(body["scope"], "portfolio")
        self.assertEqual(body["funds"][0]["as_of_date"], "21-05-2026")
        self.assertIn("data_completeness", body["funds"][0])
        self.assertIn("is_stale", body["funds"][0])
        self.assertIn("score_components", body["funds"][0])
        self.assertIn("score_method_version", body["funds"][0])
        self.assertIsNone(body["funds"][0]["returns1d"])

    def test_history_store_snapshot_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "history.db")
            store = HistoryStore(db_path)
            run_id = store.start_refresh_run(trigger_type="test")
            store.save_snapshot(
                run_id,
                [
                    {
                        "code": "123456",
                        "name": "Alpha Fund",
                        "is_portfolio": True,
                        "as_of_date": "2026-05-20",
                        "current_date": "2026-05-20",
                        "current_nav": 100.0,
                        "is_stale": False,
                        "returns": {"1year": 12.5},
                        "consistency_score": 9.2,
                        "data_completeness": 1.0,
                        "score_components": {"coverage": 1.0},
                    }
                ],
            )
            store.finish_refresh_run(run_id, status="success", fund_count=1)

            last_success = store.get_last_successful_refresh()
            history = store.get_fund_history("123456", "1y")

            self.assertIsNotNone(last_success)
            self.assertEqual(last_success["fund_count"], 1)
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["code"], "123456")

    def test_refresh_quality_rejects_zero_portfolio_payload(self):
        payload = {
            "scope": "all",
            "funds": [{"name": "Research Fund", "is_portfolio": False}],
            "expected_count": 80,
            "failed_count": 79,
            "expected_portfolio_count": 11,
            "fetched_portfolio_count": 0,
        }

        error = app_module._refresh_quality_error(payload)

        self.assertIsNotNone(error)
        self.assertIn("zero portfolio funds", error)

    def test_refresh_rejects_partial_payload_and_keeps_cached_dashboard(self):
        cache_key = app_module._cache_key("all", None)
        previous_payload = {
            "funds": [{"name": "Portfolio Fund", "is_portfolio": True}],
            "timestamp": "2026-08-10T19:00:23",
            "count": 1,
        }
        partial_payload = {
            "funds": [{"name": "Research Fund", "is_portfolio": False}],
            "timestamp": "2026-08-10T21:59:23",
            "count": 1,
            "scope": "all",
            "expected_count": 80,
            "failed_count": 79,
            "expected_portfolio_count": 11,
            "fetched_portfolio_count": 0,
        }

        app_module.memory_cache.clear()
        app_module.memory_cache[cache_key] = previous_payload

        with (
            patch("app.redis_client", None),
            patch("app.clear_data_caches"),
            patch("app.get_cached_data", return_value=partial_payload),
            patch.object(app_module.history_store, "start_refresh_run", return_value=123),
            patch.object(app_module.history_store, "finish_refresh_run") as finish_refresh,
            patch.object(app_module.history_store, "save_snapshot") as save_snapshot,
        ):
            response = app_module.refresh_and_persist(trigger_type="manual_post", scope="all")

        self.assertIn("error", response)
        self.assertEqual(response["funds"], previous_payload["funds"])
        self.assertEqual(app_module.memory_cache[cache_key], previous_payload)
        save_snapshot.assert_not_called()
        finish_refresh.assert_called_once()

    def test_compose_all_payload_blends_and_ranks(self):
        portfolio = {
            "funds": [{"name": "Fund P", "code": "101", "consistency_score": 50.0, "is_portfolio": True}],
            "comparison_anchor_date": "2026-09-01",
            "comparison_header_dates": {"1day": "2026-08-31"},
            "expected_count": 1,
            "failed_count": 0,
            "expected_portfolio_count": 1,
            "fetched_portfolio_count": 1,
        }
        research = {
            "funds": [{"name": "Fund R", "code": "201", "consistency_score": 80.0, "is_portfolio": False}],
            "comparison_anchor_date": "2026-08-01",
            "comparison_header_dates": {"1day": "2026-07-31"},
            "expected_count": 1,
            "failed_count": 0,
            "expected_portfolio_count": 0,
            "fetched_portfolio_count": 0,
        }

        composed = app_module._compose_all_payload(portfolio, research)
        self.assertEqual(composed["count"], 2)
        self.assertEqual(composed["scope"], "all")
        self.assertEqual(composed["funds"][0]["code"], "201")
        self.assertFalse(composed["funds"][0]["is_portfolio"])
        self.assertEqual(composed["funds"][1]["code"], "101")
        self.assertTrue(composed["funds"][1]["is_portfolio"])
        self.assertEqual(composed["comparison_anchor_date"], "2026-09-01")

    def test_invalidate_scope_cache_preserves_research_on_portfolio_refresh(self):
        app_module.memory_cache.clear()
        app_module.research_memory_cache.clear()

        app_module.memory_cache["funds_cache:portfolio:latest"] = {"scope": "portfolio"}
        app_module.memory_cache["funds_cache:all:latest"] = {"scope": "all"}
        app_module.research_memory_cache["funds_cache:research:latest"] = {"scope": "research"}

        app_module.invalidate_scope_cache("portfolio")

        self.assertNotIn("funds_cache:portfolio:latest", app_module.memory_cache)
        self.assertNotIn("funds_cache:all:latest", app_module.memory_cache)
        self.assertIn("funds_cache:research:latest", app_module.research_memory_cache)

    def test_refresh_endpoint_accepts_scope_param(self):
        app_module.app.config["LOGIN_DISABLED"] = True
        client = app_module.app.test_client()

        with patch("app.refresh_and_persist", return_value={"funds": [], "timestamp": "2026-09-01", "expected_count": 0, "failed_count": 0, "expected_portfolio_count": 0, "fetched_portfolio_count": 0}) as mock_refresh:
            response = client.post("/api/refresh?scope=portfolio")
            self.assertEqual(response.status_code, 200)
            mock_refresh.assert_called_once_with(trigger_type="manual_post", scope="portfolio")


if __name__ == "__main__":
    unittest.main()
