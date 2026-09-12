import aiohttp
import asyncio
import bisect
import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from asyncio_throttle import Throttler
from cachetools import TTLCache
from filelock import FileLock

from mf_tracker.services.models import FundMetrics

logger = logging.getLogger(__name__)

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", SOURCE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)

FUNDS_FILE = os.path.join(DATA_DIR, "funds.json")
RESEARCH_FUNDS_FILE = os.path.join(DATA_DIR, "research_funds.json")
RESEARCH_FUNDS_SOURCE = os.path.join(SOURCE_DIR, "research_funds.json")

FUNDS_LOCK_FILE = FUNDS_FILE + ".lock"
RESEARCH_LOCK_FILE = RESEARCH_FUNDS_FILE + ".lock"
LOCK_TIMEOUT_SECONDS = int(os.getenv("FILE_LOCK_TIMEOUT_SECONDS", "10"))

PERIODS = {
    "1day": 1,
    "1week": 7,
    "1month": 30,
    "3month": 90,
    "6month": 180,
    "1year": 365,
    "2year": 730,
    "3year": 1095,
    "5year": 1825,
}

SCORE_WEIGHTS = {"1year": 0.2, "2year": 0.3, "3year": 0.5}
SCORE_METHOD_VERSION = "v2_reweighted_missing"

STALE_THRESHOLD_DAYS = int(os.getenv("STALE_THRESHOLD_DAYS", "3"))
COMPARISON_COVERAGE_THRESHOLD = float(os.getenv("COMPARISON_COVERAGE_THRESHOLD", "0.8"))
API_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT", "60"))
API_RETRY_ATTEMPTS = max(1, int(os.getenv("API_RETRY_ATTEMPTS", "3")))
API_RETRY_BACKOFF_SECONDS = float(os.getenv("API_RETRY_BACKOFF_SECONDS", "1.5"))
API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "3"))
API_RATE_PERIOD = float(os.getenv("API_RATE_PERIOD", "1"))
MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
CONNECTION_POOL_SIZE = int(os.getenv("CONNECTION_POOL_SIZE", "5"))

API_CACHE_TTL = int(os.getenv("API_CACHE_TTL", os.getenv("REDIS_TTL", "600")))
API_CACHE_MAXSIZE = int(os.getenv("API_CACHE_MAXSIZE", "500"))
api_cache = TTLCache(maxsize=API_CACHE_MAXSIZE, ttl=API_CACHE_TTL)

DEFAULT_FUNDS = [
    {"name": "Motilal Oswal Midcap Fund", "code": "127042"},
    {"name": "Quant Small Cap Fund", "code": "120828"},
    {"name": "Bandhan Small Cap Fund", "code": "147946"},
    {"name": "Edelweiss Mid Cap Fund", "code": "140228"},
    {"name": "Parag Parikh Flexi Cap Fund", "code": "122639"},
    {"name": "Quant ELSS Tax Saver Fund", "code": "120847"},
    {"name": "Nippon India Small Cap Fund", "code": "118778"},
    {"name": "Invesco India Smallcap Fund", "code": "145137"},
    {"name": "Tata Small Cap Fund", "code": "145206"},
    {"name": "HDFC Mid-Cap Opportunities Fund", "code": "118989"},
]


def clear_data_caches() -> None:
    api_cache.clear()


def _atomic_write_json(path: str, payload: List[Dict[str, str]]) -> None:
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=4)
    os.replace(temp_path, path)


def _read_json_file(path: str, default: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        return default or []
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_funds() -> List[Dict[str, str]]:
    lock = FileLock(FUNDS_LOCK_FILE, timeout=LOCK_TIMEOUT_SECONDS)
    with lock:
        if not os.path.exists(FUNDS_FILE):
            _atomic_write_json(FUNDS_FILE, DEFAULT_FUNDS)
            return list(DEFAULT_FUNDS)
        try:
            return _read_json_file(FUNDS_FILE, default=[])
        except Exception as exc:
            logger.error("Error loading funds: %s", exc)
            return []


def load_research_funds() -> List[Dict[str, str]]:
    lock = FileLock(RESEARCH_LOCK_FILE, timeout=LOCK_TIMEOUT_SECONDS)
    with lock:
        if not os.path.exists(RESEARCH_FUNDS_FILE) and os.path.exists(RESEARCH_FUNDS_SOURCE):
            shutil.copy2(RESEARCH_FUNDS_SOURCE, RESEARCH_FUNDS_FILE)
        if not os.path.exists(RESEARCH_FUNDS_FILE):
            return []
        try:
            return _read_json_file(RESEARCH_FUNDS_FILE, default=[])
        except Exception as exc:
            logger.error("Error loading research funds: %s", exc)
            return []


def save_funds(funds_list: List[Dict[str, str]]) -> bool:
    try:
        lock = FileLock(FUNDS_LOCK_FILE, timeout=LOCK_TIMEOUT_SECONDS)
        with lock:
            _atomic_write_json(FUNDS_FILE, funds_list)
        return True
    except Exception as exc:
        logger.error("Error saving funds: %s", exc)
        return False


def save_research_funds(funds_list: List[Dict[str, str]]) -> bool:
    try:
        lock = FileLock(RESEARCH_LOCK_FILE, timeout=LOCK_TIMEOUT_SECONDS)
        with lock:
            _atomic_write_json(RESEARCH_FUNDS_FILE, funds_list)
        return True
    except Exception as exc:
        logger.error("Error saving research funds: %s", exc)
        return False


def add_fund(name: str, code: str) -> bool:
    try:
        funds_list = load_funds()
        code_str = str(code)
        if any(str(item.get("code")) == code_str for item in funds_list):
            return False
        funds_list.append({"name": name, "code": code_str})
        return save_funds(funds_list)
    except Exception as exc:
        logger.error("Error in add_fund: %s", exc)
        return False


def remove_fund(code: str) -> bool:
    funds_list = load_funds()
    code_str = str(code)
    new_funds = [fund for fund in funds_list if str(fund.get("code")) != code_str]
    if len(new_funds) == len(funds_list):
        return False
    return save_funds(new_funds)


def add_research_fund(name: str, code: str) -> bool:
    try:
        funds_list = load_research_funds()
        code_str = str(code)
        if any(str(item.get("code")) == code_str for item in funds_list):
            return False
        funds_list.append({"name": name, "code": code_str})
        return save_research_funds(funds_list)
    except Exception as exc:
        logger.error("Error in add_research_fund: %s", exc)
        return False


def remove_research_fund(code: str) -> bool:
    funds_list = load_research_funds()
    code_str = str(code)
    new_funds = [fund for fund in funds_list if str(fund.get("code")) != code_str]
    if len(new_funds) == len(funds_list):
        return False
    return save_research_funds(new_funds)


def parse_nav_data(nav_data: List[Dict[str, str]]) -> Tuple[List[Tuple[datetime, float, str]], List[datetime]]:
    parsed: List[Tuple[datetime, float, str]] = []
    for item in nav_data:
        try:
            dt = datetime.strptime(item["date"], "%d-%m-%Y")
            nav = float(item["nav"])
            parsed.append((dt, nav, item["date"]))
        except (ValueError, KeyError, TypeError):
            continue
    parsed.sort(key=lambda value: value[0])
    dates = [value[0] for value in parsed]
    return parsed, dates


def _resolve_as_of(parsed_navs: List[Tuple[datetime, float, str]], dates: List[datetime], requested_as_of: Optional[datetime]) -> Tuple[Optional[float], Optional[str], Optional[datetime]]:
    if not dates:
        return None, None, None

    if requested_as_of is None:
        dt, nav, date_str = parsed_navs[-1]
        return nav, date_str, dt

    idx = bisect.bisect_right(dates, requested_as_of)
    if idx == 0:
        return None, None, None

    dt, nav, date_str = parsed_navs[idx - 1]
    return nav, date_str, dt


def find_closest_nav(parsed_navs: List[Tuple[datetime, float, str]], dates: List[datetime], target_date: datetime) -> Tuple[Optional[float], Optional[str]]:
    if not dates:
        return None, None
    idx = bisect.bisect_right(dates, target_date)
    if idx == 0:
        return None, None
    _, nav, date_str = parsed_navs[idx - 1]
    return nav, date_str


def _compute_score(returns: Dict[str, Optional[float]]) -> Tuple[Optional[float], Dict[str, object]]:
    available = {period: value for period, value in returns.items() if period in SCORE_WEIGHTS and value is not None}
    if not available:
        return None, {
            "raw_weights": SCORE_WEIGHTS,
            "normalized_weights": {},
            "used_periods": [],
            "coverage": 0.0,
        }

    weight_sum = sum(SCORE_WEIGHTS[period] for period in available)
    normalized = {period: SCORE_WEIGHTS[period] / weight_sum for period in available}
    score = sum(float(available[period]) * normalized[period] for period in available)

    return score, {
        "raw_weights": SCORE_WEIGHTS,
        "normalized_weights": normalized,
        "used_periods": sorted(available.keys()),
        "coverage": round(len(available) / len(SCORE_WEIGHTS), 4),
    }


def _compute_metrics_for_fund(raw: Dict[str, object], requested_as_of: Optional[datetime]) -> Dict[str, object]:
    parsed_navs: List[Tuple[datetime, float, str]] = raw.get("parsed_navs", [])
    parsed_dates: List[datetime] = raw.get("parsed_dates", [])

    current_nav, actual_as_of_str, actual_as_of_dt = _resolve_as_of(parsed_navs, parsed_dates, requested_as_of)

    returns: Dict[str, Optional[float]] = {}
    period_source_dates: Dict[str, Optional[str]] = {}

    if actual_as_of_dt is not None and current_nav is not None:
        for period, days in PERIODS.items():
            historical_nav, historical_date = find_closest_nav(parsed_navs, parsed_dates, actual_as_of_dt - timedelta(days=days))
            period_source_dates[period] = historical_date
            if historical_nav is None or historical_nav == 0:
                returns[period] = None
                continue

            absolute_return = ((current_nav - historical_nav) / historical_nav) * 100
            if period in {"2year", "3year", "5year"}:
                try:
                    years = days / 365.0
                    returns[period] = ((current_nav / historical_nav) ** (1 / years) - 1) * 100
                except Exception:
                    returns[period] = absolute_return
            else:
                returns[period] = absolute_return
    else:
        for period in PERIODS:
            period_source_dates[period] = None
            returns[period] = None

    year_breakdown: Dict[str, Dict[str, object]] = {}
    if actual_as_of_dt is not None and current_nav is not None:
        for period_years in [2, 3, 5]:
            period_key = f"{period_years}year"
            period_data: Dict[str, object] = {"year_dates": {}}

            for index in range(period_years):
                year_number = index + 1
                end_target = actual_as_of_dt - timedelta(days=365 * index)
                start_target = actual_as_of_dt - timedelta(days=365 * (index + 1))

                end_nav, end_date_str = find_closest_nav(parsed_navs, parsed_dates, end_target)
                start_nav, start_date_str = find_closest_nav(parsed_navs, parsed_dates, start_target)

                key = f"year{year_number}"
                period_data["year_dates"][f"{key}_start"] = start_date_str
                period_data["year_dates"][f"{key}_end"] = end_date_str

                if end_nav is None or start_nav is None or start_nav == 0:
                    period_data[key] = 0.0
                else:
                    period_data[key] = ((end_nav - start_nav) / start_nav) * 100

            historical_nav, _ = find_closest_nav(parsed_navs, parsed_dates, actual_as_of_dt - timedelta(days=365 * period_years))
            if historical_nav is None or historical_nav == 0:
                period_data["total_absolute"] = 0.0
            else:
                period_data["total_absolute"] = ((current_nav - historical_nav) / historical_nav) * 100

            year_breakdown[period_key] = period_data
    else:
        for period_years in [2, 3, 5]:
            year_breakdown[f"{period_years}year"] = {
                "year_dates": {},
                "total_absolute": 0.0,
            }

    consistency_score, score_components = _compute_score(returns)

    available_periods = sum(1 for value in returns.values() if value is not None)
    data_completeness = round(available_periods / len(PERIODS), 4)

    is_stale = True
    if actual_as_of_dt is not None:
        is_stale = (datetime.utcnow().date() - actual_as_of_dt.date()).days > STALE_THRESHOLD_DAYS

    requested_as_of_str = requested_as_of.strftime("%d-%m-%Y") if requested_as_of else actual_as_of_str

    metrics = FundMetrics(
        name=str(raw.get("name", "")),
        code=str(raw.get("code", "")),
        current_nav=current_nav,
        as_of_date=requested_as_of_str,
        current_date=actual_as_of_str,
        period_source_dates=period_source_dates,
        dates=period_source_dates,
        returns=returns,
        consistency_score=consistency_score,
        score_components=score_components,
        score_method_version=SCORE_METHOD_VERSION,
        year_breakdown=year_breakdown,
        data_completeness=data_completeness,
        is_stale=is_stale,
        is_portfolio=bool(raw.get("is_portfolio", False)),
    )
    return metrics.__dict__


async def _fetch_fund_nav_data_async(session: aiohttp.ClientSession, fund: Dict[str, object], throttler: Throttler) -> Optional[Dict[str, object]]:
    cache_key = f"fund_raw_{fund['code']}"
    if cache_key in api_cache:
        cached = dict(api_cache[cache_key])
        cached["is_portfolio"] = bool(fund.get("is_portfolio", False))
        cached["name"] = fund.get("name", cached.get("name"))
        return cached

    url = f"https://api.mfapi.in/mf/{fund['code']}"
    payload = None
    retryable_statuses = {429, 500, 502, 503, 504}

    for attempt in range(1, API_RETRY_ATTEMPTS + 1):
        try:
            async with throttler:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS)) as response:
                    if response.status == 200:
                        payload = await response.json()
                        break

                    if response.status not in retryable_statuses or attempt == API_RETRY_ATTEMPTS:
                        logger.error("HTTP %s for %s", response.status, fund.get("name"))
                        return None

                    logger.warning(
                        "HTTP %s for %s; retrying attempt %s/%s",
                        response.status,
                        fund.get("name"),
                        attempt + 1,
                        API_RETRY_ATTEMPTS,
                    )
        except asyncio.TimeoutError:
            if attempt == API_RETRY_ATTEMPTS:
                logger.error(
                    "Timeout while fetching data for %s after %s attempts",
                    fund.get("name"),
                    API_RETRY_ATTEMPTS,
                )
                return None
            logger.warning(
                "Timeout while fetching data for %s; retrying attempt %s/%s",
                fund.get("name"),
                attempt + 1,
                API_RETRY_ATTEMPTS,
            )
        except aiohttp.ClientError as exc:
            if attempt == API_RETRY_ATTEMPTS:
                logger.error("Network error fetching %s after %s attempts: %s", fund.get("name"), API_RETRY_ATTEMPTS, exc)
                return None
            logger.warning(
                "Network error fetching %s: %s; retrying attempt %s/%s",
                fund.get("name"),
                exc,
                attempt + 1,
                API_RETRY_ATTEMPTS,
            )
        except Exception as exc:
            logger.error("Error fetching %s: %s", fund.get("name"), exc)
            return None

        await asyncio.sleep(API_RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)))

    if payload is None:
        return None

    nav_data = payload.get("data")
    if not nav_data:
        logger.error("Empty NAV data for %s", fund.get("name"))
        return None

    parsed_navs, parsed_dates = parse_nav_data(nav_data)
    if not parsed_navs:
        logger.error("No parsable NAV data for %s", fund.get("name"))
        return None

    latest_dt, latest_nav, latest_str = parsed_navs[-1]
    raw = {
        "name": fund.get("name", ""),
        "code": str(fund.get("code", "")),
        "parsed_navs": parsed_navs,
        "parsed_dates": parsed_dates,
        "latest_date": latest_dt,
        "latest_nav": latest_nav,
        "latest_date_str": latest_str,
        "is_portfolio": bool(fund.get("is_portfolio", False)),
    }
    api_cache[cache_key] = raw
    return raw


def _build_header_dates(anchor_date: datetime) -> Dict[str, str]:
    header_dates = {}
    for period, days in PERIODS.items():
        header_dates[period] = (anchor_date - timedelta(days=days)).strftime("%d-%m-%Y")
    return header_dates


def _compute_common_anchor_date(raw_funds: List[Dict[str, object]], threshold: float) -> Optional[datetime]:
    latest_dates = [fund.get("latest_date") for fund in raw_funds if fund.get("latest_date") is not None]
    if not latest_dates:
        return None

    unique_candidates = sorted(set(latest_dates), reverse=True)
    total = len(latest_dates)

    for candidate in unique_candidates:
        coverage = sum(1 for value in latest_dates if value >= candidate) / total
        if coverage >= threshold:
            return candidate

    return min(latest_dates)


def _build_fund_universe(scope: str) -> List[Dict[str, object]]:
    portfolio_funds = load_funds()
    research_funds = load_research_funds()

    for fund in portfolio_funds:
        fund["is_portfolio"] = True

    portfolio_codes = {str(fund.get("code")) for fund in portfolio_funds}
    only_research = []
    for fund in research_funds:
        code = str(fund.get("code"))
        if code not in portfolio_codes:
            copied = dict(fund)
            copied["is_portfolio"] = False
            only_research.append(copied)

    if scope == "portfolio":
        return portfolio_funds
    if scope == "research":
        return only_research

    all_funds = list(portfolio_funds)
    all_funds.extend(only_research)
    return all_funds


async def fetch_all_funds_async(as_of_date: Optional[datetime] = None, scope: str = "all") -> Dict[str, object]:
    throttler = Throttler(rate_limit=API_RATE_LIMIT, period=API_RATE_PERIOD)
    fund_universe = _build_fund_universe(scope)
    expected_count = len(fund_universe)
    expected_portfolio_count = sum(1 for fund in fund_universe if fund.get("is_portfolio"))

    if not fund_universe:
        return {
            "funds": [],
            "comparison_anchor_date": None,
            "comparison_header_dates": {},
            "scope": scope,
            "expected_count": 0,
            "failed_count": 0,
            "failed_funds": [],
            "expected_portfolio_count": 0,
            "fetched_portfolio_count": 0,
        }

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=max(API_TIMEOUT_SECONDS * API_RETRY_ATTEMPTS + 10, 30)),
        connector=aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS, limit_per_host=CONNECTION_POOL_SIZE),
    ) as session:
        tasks = [_fetch_fund_nav_data_async(session, fund, throttler) for fund in fund_universe]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    raw_funds: List[Dict[str, object]] = []
    failed_funds: List[Dict[str, object]] = []
    for index, item in enumerate(raw_results):
        source_fund = fund_universe[index]
        if isinstance(item, Exception):
            logger.error("Exception for fund %s: %s", source_fund.get("name"), item)
            failed_funds.append(
                {
                    "name": source_fund.get("name"),
                    "code": str(source_fund.get("code", "")),
                    "is_portfolio": bool(source_fund.get("is_portfolio")),
                }
            )
            continue
        if item is None:
            failed_funds.append(
                {
                    "name": source_fund.get("name"),
                    "code": str(source_fund.get("code", "")),
                    "is_portfolio": bool(source_fund.get("is_portfolio")),
                }
            )
            continue
        raw_funds.append(item)

    if not raw_funds:
        return {
            "funds": [],
            "comparison_anchor_date": None,
            "comparison_header_dates": {},
            "scope": scope,
            "expected_count": expected_count,
            "failed_count": len(failed_funds),
            "failed_funds": failed_funds,
            "expected_portfolio_count": expected_portfolio_count,
            "fetched_portfolio_count": 0,
        }

    anchor_date = as_of_date or _compute_common_anchor_date(raw_funds, COMPARISON_COVERAGE_THRESHOLD)
    metrics = [_compute_metrics_for_fund(raw, anchor_date) for raw in raw_funds]
    fetched_portfolio_count = sum(1 for fund in metrics if fund.get("is_portfolio"))

    metrics.sort(
        key=lambda fund: (fund.get("consistency_score") is not None, fund.get("consistency_score") or float("-inf")),
        reverse=True,
    )

    return {
        "funds": metrics,
        "comparison_anchor_date": anchor_date.strftime("%d-%m-%Y") if anchor_date else None,
        "comparison_header_dates": _build_header_dates(anchor_date) if anchor_date else {},
        "scope": scope,
        "expected_count": expected_count,
        "failed_count": len(failed_funds),
        "failed_funds": failed_funds,
        "expected_portfolio_count": expected_portfolio_count,
        "fetched_portfolio_count": fetched_portfolio_count,
    }


async def fetch_funds_data(as_of_date: Optional[datetime] = None, scope: str = "all") -> Dict[str, object]:
    return await fetch_all_funds_async(as_of_date=as_of_date, scope=scope)


def main() -> None:
    try:
        result = asyncio.run(fetch_funds_data())
        funds = result.get("funds", [])
        if not funds:
            logger.error("No fund data could be fetched")
            return

        print("\nMutual Fund Returns Summary:")
        print("=" * 120)
        for fund in funds:
            r = fund.get("returns", {})
            print(
                f"{fund['name']:<40} {fund['code']:<10} "
                f"NAV={fund.get('current_nav') if fund.get('current_nav') is not None else 'N/A':<10} "
                f"AsOf={fund.get('as_of_date'):<12} "
                f"1D={r.get('1day')} 1W={r.get('1week')} 1M={r.get('1month')} "
                f"3M={r.get('3month')} 1Y={r.get('1year')}"
            )
        print(f"\nTotal funds processed: {len(funds)}")
    except Exception as exc:
        logger.error("Error in main function: %s", exc)


if __name__ == "__main__":
    main()
