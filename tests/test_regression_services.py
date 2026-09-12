from datetime import datetime
import pytest

from mf_tracker.services.fund_service import (
    _compose_all_payload,
    _parse_as_of,
    _refresh_metadata,
    _refresh_quality_error,
    process_fund_data,
)


@pytest.mark.regression
@pytest.mark.unit
class TestRegressionServices:
    def test_compose_all_payload_ranking_and_flags(self):
        """
        Verify that _compose_all_payload correctly marks is_portfolio,
        blends both lists, and sorts descending by consistency_score with None at bottom.
        """
        port_funds = [
            {"name": "P1", "code": "101", "consistency_score": 15.0},
            {"name": "P2", "code": "102", "consistency_score": None},  # No score
        ]
        res_funds = [
            {"name": "R1", "code": "201", "consistency_score": 25.0},  # Highest score
            {"name": "R2", "code": "202", "consistency_score": 10.0},
        ]

        port_payload = {
            "funds": port_funds,
            "comparison_anchor_date": "20-05-2026",
            "comparison_header_dates": {"1d": "19-05-2026"},
            "expected_count": 2,
            "failed_count": 0,
            "expected_portfolio_count": 2,
            "fetched_portfolio_count": 2,
        }
        res_payload = {
            "funds": res_funds,
            "comparison_anchor_date": "18-05-2026",
            "comparison_header_dates": {"1d": "17-05-2026"},
            "expected_count": 2,
            "failed_count": 0,
            "expected_portfolio_count": 0,
            "fetched_portfolio_count": 0,
        }

        composed = _compose_all_payload(port_payload, res_payload)

        funds = composed["funds"]
        assert len(funds) == 4

        # Verify ordering: R1 (25.0), P1 (15.0), R2 (10.0), P2 (None)
        assert funds[0]["name"] == "R1"
        assert funds[0]["is_portfolio"] is False
        assert funds[1]["name"] == "P1"
        assert funds[1]["is_portfolio"] is True
        assert funds[2]["name"] == "R2"
        assert funds[2]["is_portfolio"] is False
        assert funds[3]["name"] == "P2"
        assert funds[3]["is_portfolio"] is True

        # Total counts
        assert composed["count"] == 4
        assert composed["expected_count"] == 4
        assert composed["fetched_portfolio_count"] == 2

    def test_refresh_quality_guardrails(self):
        """
        Test that _refresh_quality_error catches:
        1. Zero portfolio funds when expected > 0
        2. Success ratio dropping below MIN_REFRESH_SUCCESS_RATIO (0.6 default)
        3. Returns None for healthy refresh
        """
        # 1. Zero portfolio funds fetched
        zero_port = {
            "scope": "all",
            "funds": [{"name": "Research Only", "is_portfolio": False}],
            "expected_count": 10,
            "expected_portfolio_count": 5,
            "fetched_portfolio_count": 0,
        }
        err = _refresh_quality_error(zero_port)
        assert err is not None
        assert "zero portfolio funds" in err

        # 2. Too many failed funds (below 60% ratio)
        too_few = {
            "scope": "all",
            "funds": [
                {"name": "Fund 1", "is_portfolio": True},
                {"name": "Fund 2", "is_portfolio": True},
            ],
            "expected_count": 10,
            "expected_portfolio_count": 2,
            "fetched_portfolio_count": 2,
        }
        err_ratio = _refresh_quality_error(too_few)
        assert err_ratio is not None
        assert "safety threshold" in err_ratio

        # 3. Healthy refresh
        healthy = {
            "scope": "all",
            "funds": [
                {"name": "Fund 1", "is_portfolio": True},
                {"name": "Fund 2", "is_portfolio": True},
                {"name": "Fund 3", "is_portfolio": True},
                {"name": "Fund 4", "is_portfolio": False},
            ],
            "expected_count": 5,
            "expected_portfolio_count": 3,
            "fetched_portfolio_count": 3,
        }
        assert _refresh_quality_error(healthy) is None

    def test_parse_as_of_formats(self):
        """
        Verify _parse_as_of parses YYYY-MM-DD and DD-MM-YYYY,
        and raises ValueError for invalid inputs.
        """
        dt_iso = _parse_as_of("2026-05-20")
        assert dt_iso == datetime(2026, 5, 20)

        dt_dmy = _parse_as_of("20-05-2026")
        assert dt_dmy == datetime(2026, 5, 20)

        assert _parse_as_of(None) is None
        assert _parse_as_of("") is None

        with pytest.raises(ValueError, match="Invalid as_of date"):
            _parse_as_of("2026/05/20")

    def test_process_fund_data_formatting(self):
        """
        Verify process_fund_data properly handles NAV formatting and default dictionaries.
        """
        raw_results = {
            "funds": [
                {
                    "name": "Format Fund",
                    "code": "5001",
                    "current_nav": 123.4567,
                    "current_date": "20-05-2026",
                    "returns": {"1y": 15.2},
                    "consistency_score": 12.0,
                    "is_portfolio": True,
                },
                None,  # Handles None gracefully
            ]
        }
        processed = process_fund_data(raw_results)
        assert len(processed) == 1
        assert processed[0]["current_nav"] == "123.46"
        assert processed[0]["name"] == "Format Fund"
        assert processed[0]["is_portfolio"] is True
