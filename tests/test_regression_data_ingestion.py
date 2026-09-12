import json
import os
from datetime import datetime
import pytest

from fetch_mf_returns import (
    _atomic_write_json,
    _build_fund_universe,
    _read_json_file,
    add_fund,
    add_research_fund,
    load_funds,
    load_research_funds,
    parse_nav_data,
    remove_fund,
    remove_research_fund,
    save_funds,
    save_research_funds,
)


@pytest.mark.regression
@pytest.mark.unit
class TestRegressionDataIngestion:
    def test_parse_nav_data_robustness(self):
        """
        Verify that parse_nav_data handles clean, dirty, malformed,
        missing keys, non-numeric values, and unsorted records safely.
        """
        raw_records = [
            {"date": "20-05-2026", "nav": "150.50"},
            {"date": "18-05-2026", "nav": "148.20"},  # Out of order
            {"date": "invalid-date", "nav": "150.00"},  # Bad date format
            {"date": "19-05-2026", "nav": "N/A"},  # Bad nav
            {"date": "19-05-2026"},  # Missing nav key
            {"nav": "150.00"},  # Missing date key
            None,  # Null entry
            {"date": "21-05-2026", "nav": "152.00"},
        ]

        parsed, dates = parse_nav_data([r for r in raw_records if isinstance(r, dict)])

        # Should only have 3 valid entries: 18th, 20th, 21st
        assert len(parsed) == 3
        assert len(dates) == 3

        # Must be strictly sorted chronologically
        assert dates[0] == datetime(2026, 5, 18)
        assert dates[1] == datetime(2026, 5, 20)
        assert dates[2] == datetime(2026, 5, 21)

        assert parsed[0][1] == 148.20
        assert parsed[1][1] == 150.50
        assert parsed[2][1] == 152.00

    def test_atomic_file_write_and_read(self, isolated_funds_dir):
        """
        Verify atomic JSON write prevents file corruption and guarantees integrity.
        """
        target_path = os.path.join(isolated_funds_dir, "test_atomic.json")
        payload = [{"name": "Fund 1", "code": "101"}, {"name": "Fund 2", "code": "102"}]

        _atomic_write_json(target_path, payload)
        assert os.path.exists(target_path)

        read_back = _read_json_file(target_path)
        assert read_back == payload

    def test_fund_management_lifecycle(self, isolated_funds_dir):
        """
        Test adding, checking duplicate prevention, saving, and removing funds.
        """
        # Save initial list
        initial = [{"name": "Fund A", "code": "1001"}]
        assert save_funds(initial) is True

        funds = load_funds()
        assert len(funds) == 1
        assert funds[0]["code"] == "1001"

        # Add new fund
        added = add_fund("Fund B", "1002")
        assert added is True
        assert len(load_funds()) == 2

        # Prevent duplicate fund code
        dup_add = add_fund("Fund B Duplicate", "1002")
        assert dup_add is False
        assert len(load_funds()) == 2

        # Remove existing fund
        removed = remove_fund("1001")
        assert removed is True
        funds_after_removal = load_funds()
        assert len(funds_after_removal) == 1
        assert funds_after_removal[0]["code"] == "1002"

        # Remove non-existent fund
        removed_missing = remove_fund("9999")
        assert removed_missing is False

    def test_research_fund_lifecycle(self, isolated_funds_dir):
        """
        Test research funds addition, removal, and duplicate prevention.
        """
        initial = [{"name": "Research Fund X", "code": "2001"}]
        assert save_research_funds(initial) is True

        loaded = load_research_funds()
        assert len(loaded) == 1

        # Add research fund
        assert add_research_fund("Research Fund Y", "2002") is True
        assert len(load_research_funds()) == 2

        # Duplicate research fund rejected
        assert add_research_fund("Research Fund Y Dup", "2002") is False

        # Remove research fund
        assert remove_research_fund("2001") is True
        assert len(load_research_funds()) == 1

    def test_build_fund_universe_scopes_and_deduplication(self, isolated_funds_dir):
        """
        Verify _build_fund_universe:
        - Portfolio funds always have is_portfolio=True
        - Research funds have is_portfolio=False
        - If a fund code is in both portfolio and research, portfolio takes precedence in 'all'
        """
        save_funds([
            {"name": "Shared Fund", "code": "9001"},
            {"name": "Portfolio Only", "code": "9002"},
        ])
        save_research_funds([
            {"name": "Shared Fund in Research", "code": "9001"},  # Overlaps
            {"name": "Research Only", "code": "9003"},
        ])

        # Scope = portfolio
        p_universe = _build_fund_universe("portfolio")
        assert len(p_universe) == 2
        assert all(f.get("is_portfolio") is True for f in p_universe)

        # Scope = research (shared fund is excluded because it's already in portfolio)
        r_universe = _build_fund_universe("research")
        assert len(r_universe) == 1
        assert r_universe[0]["code"] == "9003"
        assert r_universe[0]["is_portfolio"] is False

        # Scope = all
        all_universe = _build_fund_universe("all")
        assert len(all_universe) == 3
        codes = [f["code"] for f in all_universe]
        assert "9001" in codes
        assert "9002" in codes
        assert "9003" in codes
        # 9001 should retain is_portfolio = True
        fund_9001 = next(f for f in all_universe if f["code"] == "9001")
        assert fund_9001["is_portfolio"] is True
