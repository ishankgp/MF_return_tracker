import os
import shutil
import tempfile
from datetime import datetime, timedelta
import pytest

os.environ["FLASK_ENV"] = "testing"

from app import create_app
from config import TestingConfig
from mf_tracker.services.history_store import HistoryStore
import fetch_mf_returns


@pytest.fixture
def app():
    """Create and configure a Flask application for testing."""
    test_app = create_app(TestingConfig)
    test_app.config["TESTING"] = True
    test_app.config["LOGIN_DISABLED"] = True
    yield test_app


@pytest.fixture
def client(app):
    """A test client for the Flask app."""
    return app.test_client()


@pytest.fixture
def temp_db():
    """Provide an isolated HistoryStore in a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_history.db")
        store = HistoryStore(db_path)
        yield store


@pytest.fixture
def isolated_funds_dir():
    """Provide isolated funds.json and research_funds.json in a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        orig_funds = fetch_mf_returns.FUNDS_FILE
        orig_research = fetch_mf_returns.RESEARCH_FUNDS_FILE
        orig_funds_lock = fetch_mf_returns.FUNDS_LOCK_FILE
        orig_research_lock = fetch_mf_returns.RESEARCH_LOCK_FILE

        funds_file = os.path.join(tmp_dir, "funds.json")
        research_file = os.path.join(tmp_dir, "research_funds.json")
        fetch_mf_returns.FUNDS_FILE = funds_file
        fetch_mf_returns.RESEARCH_FUNDS_FILE = research_file
        fetch_mf_returns.FUNDS_LOCK_FILE = funds_file + ".lock"
        fetch_mf_returns.RESEARCH_LOCK_FILE = research_file + ".lock"

        yield tmp_dir

        fetch_mf_returns.FUNDS_FILE = orig_funds
        fetch_mf_returns.RESEARCH_FUNDS_FILE = orig_research
        fetch_mf_returns.FUNDS_LOCK_FILE = orig_funds_lock
        fetch_mf_returns.RESEARCH_LOCK_FILE = orig_research_lock


@pytest.fixture
def realistic_nav_data():
    """
    Generate 5 years of realistic trading NAV data (from 2021-01-01 to 2026-06-01).
    Excludes weekends (Saturday & Sunday).
    Starting NAV = 100.0 on 2021-01-01, compounding smoothly to ~250.0 on 2026-06-01.
    Returns (parsed_navs, dates, raw_api_list).
    """
    start_date = datetime(2021, 1, 1)
    end_date = datetime(2026, 6, 1)
    total_days = (end_date - start_date).days

    parsed_navs = []
    dates = []
    raw_api_list = []

    current_nav = 100.0
    daily_factor = (250.0 / 100.0) ** (1.0 / total_days)

    curr_dt = start_date
    while curr_dt <= end_date:
        if curr_dt.weekday() < 5:  # Monday to Friday
            date_str = curr_dt.strftime("%d-%m-%Y")
            nav_val = round(current_nav, 4)
            parsed_navs.append((curr_dt, nav_val, date_str))
            dates.append(curr_dt)
            raw_api_list.append({"date": date_str, "nav": str(nav_val)})
        current_nav *= daily_factor
        curr_dt += timedelta(days=1)

    return {
        "parsed_navs": parsed_navs,
        "dates": dates,
        "raw_api_list": raw_api_list,
        "as_of_date": end_date,
    }
