from unittest.mock import patch
import pytest

from app import create_app
from config import TestingConfig


@pytest.mark.regression
@pytest.mark.api
class TestRegressionAPI:
    def test_api_funds_scope_validation(self, client):
        """
        Verify that /api/funds accepts all|portfolio|research and rejects any other scope.
        """
        mock_data = {
            "funds": [
                {
                    "name": "Sample Fund",
                    "code": "1001",
                    "current_nav": 100.0,
                    "returns": {"1day": 0.1},
                    "consistency_score": 10.0,
                    "is_portfolio": True,
                }
            ],
            "timestamp": "2026-05-20T12:00:00",
            "comparison_anchor_date": "20-05-2026",
            "comparison_header_dates": {},
        }

        with patch("mf_tracker.api.funds.get_cached_data", return_value=mock_data):
            for valid_scope in ["all", "portfolio", "research"]:
                res = client.get(f"/api/funds?scope={valid_scope}")
                assert res.status_code == 200
                data = res.get_json()
                assert data["scope"] == valid_scope
                assert len(data["funds"]) == 1

            # Invalid scope
            res_invalid = client.get("/api/funds?scope=crypto")
            assert res_invalid.status_code == 400
            assert "Invalid scope" in res_invalid.get_json()["error"]

    def test_api_funds_response_schema_contract(self, client):
        """
        Enforce complete JSON schema contract for /api/funds endpoint response.
        """
        mock_data = {
            "funds": [
                {
                    "name": "Tax Saver Fund",
                    "code": "120847",
                    "current_nav": 245.85,
                    "returns": {
                        "1day": 0.45,
                        "1week": 1.2,
                        "1month": 3.4,
                        "3month": 5.6,
                        "6month": 8.9,
                        "1year": 18.5,
                        "2year": 22.1,
                        "3year": 25.0,
                        "5year": 20.3,
                    },
                    "dates": {"1day": "19-05-2026"},
                    "period_source_dates": {"1day": "19-05-2026"},
                    "current_date": "20-05-2026",
                    "as_of_date": "20-05-2026",
                    "data_completeness": 1.0,
                    "is_stale": False,
                    "score_components": {"coverage": 1.0},
                    "score_method_version": "v2_reweighted_missing",
                    "year_breakdown": {},
                    "consistency_score": 22.4,
                    "is_portfolio": True,
                }
            ],
            "timestamp": "2026-05-20T12:00:00",
            "comparison_anchor_date": "20-05-2026",
            "comparison_header_dates": {"1day": "19-05-2026"},
            "expected_count": 1,
            "failed_count": 0,
            "expected_portfolio_count": 1,
            "fetched_portfolio_count": 1,
        }

        with patch("mf_tracker.api.funds.get_cached_data", return_value=mock_data):
            res = client.get("/api/funds?scope=all")
            assert res.status_code == 200
            body = res.get_json()

            # Verify root fields
            expected_root_keys = [
                "funds", "timestamp", "count", "scope",
                "comparison_anchor_date", "comparison_header_dates",
                "expected_count", "failed_count",
                "expected_portfolio_count", "fetched_portfolio_count",
            ]
            for key in expected_root_keys:
                assert key in body, f"Root field '{key}' missing from /api/funds response"

            fund = body["funds"][0]
            # Verify fund fields contract
            expected_fund_keys = [
                "id", "name", "code", "nav",
                "returns1d", "returns1w", "returns1m", "returns3m", "returns6m",
                "returns1y", "returns2y", "returns3y", "returns5y",
                "dates", "period_source_dates", "current_date", "as_of_date",
                "data_completeness", "is_stale", "score_components",
                "score_method_version", "year_breakdown", "consistency_score",
                "is_portfolio", "category", "risk",
            ]
            for key in expected_fund_keys:
                assert key in fund, f"Fund field '{key}' missing from /api/funds fund object"

    def test_api_refresh_endpoint_methods(self, client):
        """
        Verify POST /api/refresh and GET /api/refresh behavior.
        """
        mock_payload = {
            "funds": [{"name": "Fund 1", "code": "101"}],
            "timestamp": "2026-05-20T15:00:00",
            "expected_count": 1,
            "failed_count": 0,
            "expected_portfolio_count": 1,
            "fetched_portfolio_count": 1,
        }

        with patch("mf_tracker.api.funds.refresh_and_persist", return_value=mock_payload):
            # POST
            res_post = client.post("/api/refresh?scope=portfolio")
            assert res_post.status_code == 200
            assert res_post.get_json()["message"] == "Data refreshed successfully"
            assert "warning" not in res_post.get_json()

            # GET (deprecated but supported with warning)
            res_get = client.get("/api/refresh?scope=portfolio")
            assert res_get.status_code == 200
            assert "warning" in res_get.get_json()

            # Invalid scope
            res_bad = client.post("/api/refresh?scope=invalid")
            assert res_bad.status_code == 400

    def test_api_notes_crud(self, client):
        """
        Verify GET, POST, and DELETE /api/notes endpoints.
        """
        notes_store = []

        with (
            patch("mf_tracker.api.notes.load_notes", side_effect=lambda: list(notes_store)),
            patch("mf_tracker.api.notes.save_notes", side_effect=lambda notes: (notes_store.clear(), notes_store.extend(notes), True)[2]),
        ):
            # 1. GET initial empty notes
            res = client.get("/api/notes")
            assert res.status_code == 200
            assert res.get_json() == []

            # 2. POST invalid note
            res_bad = client.post("/api/notes", json={"text": "Missing date"})
            assert res_bad.status_code == 400

            # 3. POST valid note
            res_ok = client.post("/api/notes", json={"date": "2026-05-20", "text": "Rebalanced portfolio"})
            assert res_ok.status_code == 200
            assert len(notes_store) == 1

            # 4. DELETE out of range
            res_del_bad = client.delete("/api/notes/99")
            assert res_del_bad.status_code == 404

            # 5. DELETE valid index
            res_del_ok = client.delete("/api/notes/0")
            assert res_del_ok.status_code == 200
            assert len(notes_store) == 0

    def test_api_research_funds_crud(self, client):
        """
        Verify GET, POST, and DELETE /api/research-funds.
        """
        with (
            patch("mf_tracker.api.funds.load_research_funds", return_value=[{"name": "R1", "code": "301"}]),
            patch("mf_tracker.api.funds.add_research_fund", return_value=True),
            patch("mf_tracker.api.funds.remove_research_fund", return_value=True),
            patch("mf_tracker.api.funds.clear_response_caches"),
            patch("mf_tracker.api.funds.clear_data_caches"),
        ):
            # GET
            res_get = client.get("/api/research-funds")
            assert res_get.status_code == 200
            assert len(res_get.get_json()) == 1

            # POST missing fields
            res_post_bad = client.post("/api/research-funds", json={"name": "Only Name"})
            assert res_post_bad.status_code == 400

            # POST valid
            res_post_ok = client.post("/api/research-funds", json={"name": "R2", "code": "302"})
            assert res_post_ok.status_code == 200

            # DELETE valid
            res_del = client.delete("/api/research-funds/301")
            assert res_del.status_code == 200

    def test_auth_enforcement_when_login_enabled(self):
        """
        Verify that protected endpoints redirect to login when LOGIN_DISABLED is False.
        """
        auth_app = create_app(TestingConfig)
        auth_app.config["TESTING"] = True
        auth_app.config["LOGIN_DISABLED"] = False

        auth_client = auth_app.test_client()

        # Should redirect to login (302)
        res_funds = auth_client.get("/api/funds")
        assert res_funds.status_code == 302
        assert "/login" in res_funds.headers.get("Location", "")

        res_refresh = auth_client.post("/api/refresh")
        assert res_refresh.status_code == 302

        res_notes = auth_client.get("/api/notes")
        assert res_notes.status_code == 302
