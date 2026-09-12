import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from mf_tracker.core.db import history_store
from mf_tracker.services.cache_service import (
    clear_response_caches,
    invalidate_scope_cache,
    read_response_cache,
    write_response_cache,
)
from fetch_mf_returns import clear_data_caches, fetch_funds_data

logger = logging.getLogger(__name__)

LAST_REFRESH_STATUS: Dict[str, Any] = {
    "timestamp": None,
    "status": "never",
    "error": None,
}

# The MIN_REFRESH_SUCCESS_RATIO should ideally be passed in or loaded from config
import os
MIN_REFRESH_SUCCESS_RATIO = float(os.getenv("MIN_REFRESH_SUCCESS_RATIO", "0.6"))

def _cache_key(scope: str, as_of: Optional[datetime]) -> str:
    as_of_key = as_of.strftime("%Y-%m-%d") if as_of else "latest"
    return f"funds_cache:{scope}:{as_of_key}"

def _parse_as_of(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError("Invalid as_of date. Use YYYY-MM-DD or DD-MM-YYYY")

def _refresh_metadata(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "expected_count": int(result.get("expected_count", len(result.get("funds", []))) or 0),
        "failed_count": int(result.get("failed_count", 0) or 0),
        "failed_funds": result.get("failed_funds", []),
        "expected_portfolio_count": int(result.get("expected_portfolio_count", 0) or 0),
        "fetched_portfolio_count": int(result.get("fetched_portfolio_count", 0) or 0),
    }

def _refresh_quality_error(payload: Dict[str, Any]) -> Optional[str]:
    funds = payload.get("funds", []) or []
    expected_count = int(payload.get("expected_count", len(funds)) or 0)
    fetched_count = len(funds)
    expected_portfolio_count = int(payload.get("expected_portfolio_count", 0) or 0)
    fetched_portfolio_count = int(
        payload.get("fetched_portfolio_count", sum(1 for fund in funds if fund.get("is_portfolio"))) or 0
    )
    scope = str(payload.get("scope", "all")).lower()

    if scope in {"all", "portfolio"} and expected_portfolio_count > 0 and fetched_portfolio_count == 0:
        return (
            "Refresh fetched zero portfolio funds. The external MF API likely timed out; "
            "kept the previous dashboard data instead."
        )

    if expected_count > 0 and fetched_count / expected_count < MIN_REFRESH_SUCCESS_RATIO:
        return (
            f"Refresh fetched only {fetched_count}/{expected_count} funds, below the "
            f"{MIN_REFRESH_SUCCESS_RATIO:.0%} safety threshold. Kept the previous dashboard data instead."
        )

    return None

def _compose_all_payload(portfolio_payload: Dict[str, Any], research_payload: Dict[str, Any]) -> Dict[str, Any]:
    portfolio_funds = list(portfolio_payload.get("funds", []) or [])
    research_funds = list(research_payload.get("funds", []) or [])

    for fund in portfolio_funds:
        fund["is_portfolio"] = True
    for fund in research_funds:
        fund["is_portfolio"] = False

    combined_funds = portfolio_funds + research_funds
    combined_funds.sort(
        key=lambda fund: (fund.get("consistency_score") is not None, fund.get("consistency_score") or float("-inf")),
        reverse=True,
    )

    anchor_date = portfolio_payload.get("comparison_anchor_date") or research_payload.get("comparison_anchor_date")
    header_dates = portfolio_payload.get("comparison_header_dates") or research_payload.get("comparison_header_dates", {})

    expected_count = int(portfolio_payload.get("expected_count", len(portfolio_funds))) + int(research_payload.get("expected_count", len(research_funds)))
    failed_count = int(portfolio_payload.get("failed_count", 0)) + int(research_payload.get("failed_count", 0))
    failed_funds = list(portfolio_payload.get("failed_funds", [])) + list(research_payload.get("failed_funds", []))
    expected_portfolio = int(portfolio_payload.get("expected_portfolio_count", len(portfolio_funds)))
    fetched_portfolio = int(portfolio_payload.get("fetched_portfolio_count", len(portfolio_funds)))

    return {
        "funds": combined_funds,
        "timestamp": portfolio_payload.get("timestamp") or datetime.utcnow().isoformat(),
        "count": len(combined_funds),
        "comparison_anchor_date": anchor_date,
        "comparison_header_dates": header_dates,
        "scope": "all",
        "expected_count": expected_count,
        "failed_count": failed_count,
        "failed_funds": failed_funds,
        "expected_portfolio_count": expected_portfolio,
        "fetched_portfolio_count": fetched_portfolio,
    }

def get_cached_data(
    scope: str = "all",
    as_of: Optional[datetime] = None,
    force_refresh: bool = False,
    store: bool = True,
) -> Dict[str, Any]:
    cache_key = _cache_key(scope, as_of)

    if not force_refresh:
        cached_payload = read_response_cache(cache_key)
        if cached_payload:
            return cached_payload

    if scope == "all":
        portfolio_payload = get_cached_data(scope="portfolio", as_of=as_of, force_refresh=force_refresh, store=store)
        research_payload = get_cached_data(scope="research", as_of=as_of, force_refresh=force_refresh, store=store)

        if portfolio_payload.get("error") and not portfolio_payload.get("funds"):
            return portfolio_payload

        composed = _compose_all_payload(portfolio_payload, research_payload)
        if store:
            write_response_cache(cache_key, composed)
        return composed

    result = asyncio.run(fetch_funds_data(as_of_date=as_of, scope=scope))
    funds = result.get("funds", [])
    metadata = _refresh_metadata(result)
    if not funds:
        payload = {
            "error": "No data available",
            "funds": [],
            "timestamp": datetime.utcnow().isoformat(),
            "count": 0,
            "comparison_anchor_date": result.get("comparison_anchor_date"),
            "comparison_header_dates": result.get("comparison_header_dates", {}),
            "scope": scope,
            **metadata,
        }
    else:
        payload = {
            "funds": funds,
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(funds),
            "comparison_anchor_date": result.get("comparison_anchor_date"),
            "comparison_header_dates": result.get("comparison_header_dates", {}),
            "scope": scope,
            **metadata,
        }

    if store:
        write_response_cache(cache_key, payload)
    return payload

def refresh_and_persist(trigger_type: str = "manual", scope: str = "all", as_of: Optional[datetime] = None) -> Dict[str, Any]:
    run_id = history_store.start_refresh_run(trigger_type)
    try:
        cache_key = _cache_key(scope, as_of)
        previous_payload = read_response_cache(cache_key)
        clear_data_caches()

        payload = get_cached_data(scope=scope, as_of=as_of, force_refresh=True, store=False)
        if payload.get("error") and not payload.get("funds"):
            history_store.finish_refresh_run(run_id, status="failed", error=payload.get("error"), fund_count=0)
            LAST_REFRESH_STATUS.update({"timestamp": datetime.utcnow().isoformat(), "status": "failed", "error": payload.get("error")})
            return payload

        quality_error = _refresh_quality_error(payload)
        if quality_error:
            fund_count = len(payload.get("funds", []))
            history_store.finish_refresh_run(run_id, status="failed", error=quality_error, fund_count=fund_count)
            LAST_REFRESH_STATUS.update({"timestamp": datetime.utcnow().isoformat(), "status": "failed", "error": quality_error})
            logger.warning(
                "%s fetched_count=%s expected_count=%s fetched_portfolio_count=%s expected_portfolio_count=%s",
                quality_error,
                fund_count,
                payload.get("expected_count"),
                payload.get("fetched_portfolio_count"),
                payload.get("expected_portfolio_count"),
            )
            response = {
                "error": quality_error,
                "funds": previous_payload.get("funds", []) if previous_payload else [],
                "partial_funds_count": fund_count,
                "expected_count": payload.get("expected_count"),
                "failed_count": payload.get("failed_count"),
                "fetched_portfolio_count": payload.get("fetched_portfolio_count"),
                "expected_portfolio_count": payload.get("expected_portfolio_count"),
            }
            return response

        invalidate_scope_cache(scope)
        write_response_cache(cache_key, payload)

        if scope in {"portfolio", "research"}:
            other_scope = "research" if scope == "portfolio" else "portfolio"
            other_payload = get_cached_data(scope=other_scope, as_of=as_of, force_refresh=False, store=True)
            if scope == "portfolio":
                all_payload = _compose_all_payload(payload, other_payload)
            else:
                all_payload = _compose_all_payload(other_payload, payload)
            write_response_cache(_cache_key("all", as_of), all_payload)

        history_store.save_snapshot(run_id, payload.get("funds", []))
        history_store.finish_refresh_run(run_id, status="success", fund_count=len(payload.get("funds", [])))
        LAST_REFRESH_STATUS.update({"timestamp": payload.get("timestamp"), "status": "success", "error": None})
        return payload
    except Exception as exc:
        logger.error("Refresh failed: %s", exc)
        logger.error(traceback.format_exc())
        history_store.finish_refresh_run(run_id, status="failed", error=str(exc), fund_count=0)
        LAST_REFRESH_STATUS.update({"timestamp": datetime.utcnow().isoformat(), "status": "failed", "error": str(exc)})
        return {"error": str(exc), "funds": []}

def process_fund_data(results: Dict[str, Any]):
    if not results or "funds" not in results:
        return []

    funds_data = []
    for result in results["funds"]:
        if not result:
            continue

        try:
            fund_info = {
                "name": result.get("name", ""),
                "code": result.get("code", ""),
                "current_nav": f"{result['current_nav']:.2f}" if result.get("current_nav") is not None else None,
                "current_date": result.get("current_date"),
                "as_of_date": result.get("as_of_date"),
                "period_source_dates": result.get("period_source_dates", {}),
                "dates": result.get("dates", {}),
                "returns": result.get("returns", {}),
                "year_breakdown": result.get("year_breakdown", {}),
                "consistency_score": result.get("consistency_score"),
                "score_components": result.get("score_components", {}),
                "score_method_version": result.get("score_method_version", "v2_reweighted_missing"),
                "data_completeness": result.get("data_completeness", 0),
                "is_stale": bool(result.get("is_stale", False)),
                "is_portfolio": bool(result.get("is_portfolio", False)),
            }
            funds_data.append(fund_info)
        except Exception as exc:
            logger.error("Error processing fund data %s: %s", result.get("name", "Unknown"), exc)

    return funds_data
