import bisect
from datetime import datetime, timedelta
import pytest

from fetch_mf_returns import (
    PERIODS,
    SCORE_WEIGHTS,
    _compute_common_anchor_date,
    _compute_metrics_for_fund,
    _compute_score,
    _resolve_as_of,
    find_closest_nav,
)


@pytest.mark.regression
@pytest.mark.unit
class TestRegressionMetrics:
    def test_period_returns_simple_vs_cagr_formula(self, realistic_nav_data):
        """
        Verify that 1d, 1w, 1m, 3m, 6m, 1y use absolute return,
        while 2y, 3y, 5y use annualized CAGR: ((current/past)**(1/years) - 1)*100.
        """
        raw = {
            "name": "Benchmark Growth Fund",
            "code": "100001",
            "parsed_navs": realistic_nav_data["parsed_navs"],
            "parsed_dates": realistic_nav_data["dates"],
            "is_portfolio": True,
        }
        as_of = realistic_nav_data["as_of_date"]
        metrics = _compute_metrics_for_fund(raw, requested_as_of=as_of)

        returns = metrics["returns"]
        current_nav = metrics["current_nav"]

        # Ensure all standard periods are populated
        for p in ["1day", "1week", "1month", "3month", "6month", "1year", "2year", "3year", "5year"]:
            assert returns[p] is not None, f"Expected return for {p} to be computed"
            assert returns[p] > 0, f"Expected positive return for {p}"

        # Verify 1-year simple return formula: (current - past) / past * 100
        hist_1y_nav, _ = find_closest_nav(
            realistic_nav_data["parsed_navs"],
            realistic_nav_data["dates"],
            as_of - timedelta(days=365),
        )
        expected_1y_return = ((current_nav - hist_1y_nav) / hist_1y_nav) * 100
        assert pytest.approx(returns["1year"], rel=1e-3) == expected_1y_return

        # Verify 3-year CAGR formula: ((current / past) ** (1/3) - 1) * 100
        hist_3y_nav, _ = find_closest_nav(
            realistic_nav_data["parsed_navs"],
            realistic_nav_data["dates"],
            as_of - timedelta(days=1095),
        )
        years = 1095 / 365.0
        expected_3y_cagr = ((current_nav / hist_3y_nav) ** (1.0 / years) - 1.0) * 100
        assert pytest.approx(returns["3year"], rel=1e-3) == expected_3y_cagr

    def test_score_reweighting_scenarios(self):
        """
        Exhaustively test _compute_score:
        1. All 1y, 2y, 3y present -> weights (0.2, 0.3, 0.5)
        2. Missing 1y -> weights (0.3/0.8 = 0.375, 0.5/0.8 = 0.625)
        3. Missing 2y -> weights (0.2/0.7 = 0.2857, 0.5/0.7 = 0.7143)
        4. Missing 3y -> weights (0.2/0.5 = 0.4, 0.3/0.5 = 0.6)
        5. Missing all -> None, coverage 0.0
        6. Negative returns
        """
        # 1. All present
        r_all = {"1year": 10.0, "2year": 20.0, "3year": 30.0}
        score, comp = _compute_score(r_all)
        expected = 10.0 * 0.2 + 20.0 * 0.3 + 30.0 * 0.5  # 2 + 6 + 15 = 23.0
        assert pytest.approx(score, abs=1e-4) == expected
        assert comp["coverage"] == 1.0
        assert pytest.approx(comp["normalized_weights"]["1year"]) == 0.2
        assert pytest.approx(comp["normalized_weights"]["2year"]) == 0.3
        assert pytest.approx(comp["normalized_weights"]["3year"]) == 0.5

        # 2. Missing 1y
        r_no_1y = {"1year": None, "2year": 20.0, "3year": 30.0}
        score, comp = _compute_score(r_no_1y)
        expected = 20.0 * (0.3 / 0.8) + 30.0 * (0.5 / 0.8)  # 7.5 + 18.75 = 26.25
        assert pytest.approx(score, abs=1e-4) == expected
        assert comp["coverage"] == round(2 / 3, 4)
        assert "1year" not in comp["normalized_weights"]

        # 3. Missing 2y
        r_no_2y = {"1year": 14.0, "2year": None, "3year": 21.0}
        score, comp = _compute_score(r_no_2y)
        w1 = 0.2 / 0.7
        w3 = 0.5 / 0.7
        expected = 14.0 * w1 + 21.0 * w3
        assert pytest.approx(score, abs=1e-4) == expected

        # 4. Missing 3y
        r_no_3y = {"1year": 10.0, "2year": 15.0, "3year": None}
        score, comp = _compute_score(r_no_3y)
        expected = 10.0 * 0.4 + 15.0 * 0.6  # 4 + 9 = 13.0
        assert pytest.approx(score, abs=1e-4) == expected

        # 5. Missing all
        r_empty = {"1year": None, "2year": None, "3year": None}
        score, comp = _compute_score(r_empty)
        assert score is None
        assert comp["coverage"] == 0.0
        assert comp["normalized_weights"] == {}

        # 6. Negative returns
        r_neg = {"1year": -10.0, "2year": -5.0, "3year": 10.0}
        score, _ = _compute_score(r_neg)
        expected = (-10.0 * 0.2) + (-5.0 * 0.3) + (10.0 * 0.5)  # -2 - 1.5 + 5 = 1.5
        assert pytest.approx(score, abs=1e-4) == expected

    def test_non_trading_day_weekend_and_holiday_resolution(self):
        """
        Verify that querying an exact Sunday resolves to Friday's NAV
        and dates prior to fund inception return None.
        """
        # Friday 2026-05-15, Monday 2026-05-18
        friday = datetime(2026, 5, 15)
        monday = datetime(2026, 5, 18)
        nav_list = [
            (friday, 100.0, "15-05-2026"),
            (monday, 102.5, "18-05-2026"),
        ]
        dates = [friday, monday]

        # Saturday
        saturday = datetime(2026, 5, 16)
        nav, d_str = find_closest_nav(nav_list, dates, saturday)
        assert nav == 100.0
        assert d_str == "15-05-2026"

        # Sunday
        sunday = datetime(2026, 5, 17)
        nav, d_str = find_closest_nav(nav_list, dates, sunday)
        assert nav == 100.0
        assert d_str == "15-05-2026"

        # Prior to inception
        thursday_before = datetime(2026, 5, 14)
        nav, d_str = find_closest_nav(nav_list, dates, thursday_before)
        assert nav is None
        assert d_str is None

    def test_stale_data_detection(self):
        """
        Verify that a fund whose latest NAV is older than STALE_THRESHOLD_DAYS
        is flagged with is_stale = True.
        """
        old_date = datetime.utcnow() - timedelta(days=10)
        recent_date = datetime.utcnow() - timedelta(days=1)

        raw_stale = {
            "name": "Stale Fund",
            "code": "888881",
            "parsed_navs": [(old_date, 50.0, old_date.strftime("%d-%m-%Y"))],
            "parsed_dates": [old_date],
            "is_portfolio": True,
        }
        metrics_stale = _compute_metrics_for_fund(raw_stale, requested_as_of=None)
        assert metrics_stale["is_stale"] is True

        raw_fresh = {
            "name": "Fresh Fund",
            "code": "888882",
            "parsed_navs": [(recent_date, 50.0, recent_date.strftime("%d-%m-%Y"))],
            "parsed_dates": [recent_date],
            "is_portfolio": True,
        }
        metrics_fresh = _compute_metrics_for_fund(raw_fresh, requested_as_of=None)
        assert metrics_fresh["is_stale"] is False

    def test_common_anchor_date_consensus(self):
        """
        Test that _compute_common_anchor_date selects the candidate date
        that achieves >= threshold coverage among funds.
        """
        d1 = datetime(2026, 5, 20)
        d2 = datetime(2026, 5, 21)
        d3 = datetime(2026, 5, 22)

        # 8 funds on d3, 2 funds on d2
        raw_funds = []
        for i in range(8):
            raw_funds.append({"parsed_dates": [d1, d2, d3], "latest_date": d3})
        for i in range(2):
            raw_funds.append({"parsed_dates": [d1, d2], "latest_date": d2})

        # At 80% coverage (threshold 0.8), 8/10 funds have d3 -> consensus should be d3
        anchor = _compute_common_anchor_date(raw_funds, threshold=0.8)
        assert anchor == d3

        # At 90% coverage, 8/10 is only 80%, so consensus falls back to d2 (100% coverage)
        anchor_strict = _compute_common_anchor_date(raw_funds, threshold=0.9)
        assert anchor_strict == d2


    def test_year_by_year_breakdown_structure(self, realistic_nav_data):
        """
        Verify that year_breakdown provides year1..year5 returns and start/end dates.
        """
        raw = {
            "name": "Multi-year Fund",
            "code": "100002",
            "parsed_navs": realistic_nav_data["parsed_navs"],
            "parsed_dates": realistic_nav_data["dates"],
            "is_portfolio": True,
        }
        as_of = realistic_nav_data["as_of_date"]
        metrics = _compute_metrics_for_fund(raw, requested_as_of=as_of)

        yb = metrics["year_breakdown"]
        assert "2year" in yb
        assert "3year" in yb
        assert "5year" in yb

        assert "year1" in yb["3year"]
        assert "year2" in yb["3year"]
        assert "year3" in yb["3year"]
        assert "year_dates" in yb["3year"]
        assert "year1_start" in yb["3year"]["year_dates"]
        assert "year1_end" in yb["3year"]["year_dates"]
