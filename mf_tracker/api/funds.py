import logging
import traceback
import requests
from flask import Blueprint, jsonify, request
from flask_login import login_required

from mf_tracker.services.fund_service import (
    get_cached_data,
    refresh_and_persist,
    _parse_as_of,
)
from mf_tracker.services.cache_service import clear_response_caches
from mf_tracker.core.db import history_store
from fetch_mf_returns import (
    add_fund,
    add_research_fund,
    remove_fund,
    remove_research_fund,
    clear_data_caches,
    load_research_funds
)

logger = logging.getLogger(__name__)
funds_bp = Blueprint("funds", __name__, url_prefix="/api/funds")
research_bp = Blueprint("research_funds", __name__, url_prefix="/api/research-funds")
refresh_bp = Blueprint("refresh", __name__, url_prefix="/api/refresh")

@funds_bp.route("")
@login_required
def api_funds():
    try:
        scope = request.args.get("scope", "all").strip().lower()
        if scope not in {"all", "portfolio", "research"}:
            return jsonify({"error": "Invalid scope. Use all|portfolio|research"}), 400

        as_of_param = request.args.get("as_of")
        as_of_dt = _parse_as_of(as_of_param)

        results = get_cached_data(scope=scope, as_of=as_of_dt)
        if results.get("error"):
            return jsonify({"error": results["error"], "funds": []}), 500

        funds_data = []
        for idx, result in enumerate(results.get("funds", []), 1):
            fund = {
                "id": str(idx),
                "name": result.get("name"),
                "code": result.get("code", ""),
                "nav": result.get("current_nav"),
                "returns1d": result.get("returns", {}).get("1day"),
                "returns1w": result.get("returns", {}).get("1week"),
                "returns1m": result.get("returns", {}).get("1month"),
                "returns3m": result.get("returns", {}).get("3month"),
                "returns6m": result.get("returns", {}).get("6month"),
                "returns1y": result.get("returns", {}).get("1year"),
                "returns2y": result.get("returns", {}).get("2year"),
                "returns3y": result.get("returns", {}).get("3year"),
                "returns5y": result.get("returns", {}).get("5year"),
                "dates": result.get("dates", {}),
                "period_source_dates": result.get("period_source_dates", {}),
                "current_date": result.get("current_date"),
                "as_of_date": result.get("as_of_date"),
                "data_completeness": result.get("data_completeness", 0),
                "is_stale": bool(result.get("is_stale", False)),
                "score_components": result.get("score_components", {}),
                "score_method_version": result.get("score_method_version", "v2_reweighted_missing"),
                "year_breakdown": result.get("year_breakdown", {}),
                "consistency_score": result.get("consistency_score"),
                "is_portfolio": bool(result.get("is_portfolio", False)),
                "category": "Other",
                "risk": "Medium",
            }
            funds_data.append(fund)

        return jsonify(
            {
                "funds": funds_data,
                "timestamp": results.get("timestamp"),
                "count": len(funds_data),
                "scope": scope,
                "comparison_anchor_date": results.get("comparison_anchor_date"),
                "comparison_header_dates": results.get("comparison_header_dates", {}),
                "expected_count": results.get("expected_count"),
                "failed_count": results.get("failed_count"),
                "expected_portfolio_count": results.get("expected_portfolio_count"),
                "fetched_portfolio_count": results.get("fetched_portfolio_count"),
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.error("Error in /api/funds: %s", exc)
        logger.error(traceback.format_exc())
        return jsonify({"error": str(exc), "funds": []}), 500


@funds_bp.route("/history/<code>")
@login_required
def api_fund_history(code: str):
    range_key = request.args.get("range", "1y").lower()
    if range_key not in {"1y", "3y", "5y"}:
        return jsonify({"error": "Invalid range. Use 1y|3y|5y"}), 400

    history = history_store.get_fund_history(str(code), range_key)
    return jsonify({"code": str(code), "range": range_key, "count": len(history), "history": history})


@funds_bp.route("/search")
@login_required
def search_funds():
    query = request.args.get("q", "")
    if not query or len(query) < 3:
        return jsonify([])
    try:
        response = requests.get(f"https://api.mfapi.in/mf/search?q={query}", timeout=5)
        if response.status_code == 200:
            return jsonify(response.json())
        return jsonify([])
    except Exception as exc:
        logger.error("Error searching funds: %s", exc)
        return jsonify([]), 500


@funds_bp.route("", methods=["POST"])
@login_required
def api_add_fund():
    data = request.json or {}
    name = data.get("name")
    code = data.get("code")
    if not name or not code:
        return jsonify({"error": "Name and code required"}), 400

    if add_fund(name, str(code)):
        clear_response_caches()
        clear_data_caches()
        return jsonify({"success": True, "message": "Fund added successfully"})
    return jsonify({"error": "Fund already exists or error adding"}), 400


@funds_bp.route("/<code>", methods=["DELETE"])
@login_required
def api_remove_fund(code):
    if remove_fund(str(code)):
        clear_response_caches()
        clear_data_caches()
        return jsonify({"success": True, "message": "Fund removed successfully"})
    return jsonify({"error": "Fund not found or error removing"}), 400


@research_bp.route("", methods=["POST"])
@login_required
def api_add_research_fund():
    data = request.json or {}
    name = data.get("name")
    code = data.get("code")
    if not name or not code:
        return jsonify({"error": "Name and code required"}), 400

    if add_research_fund(name, str(code)):
        clear_response_caches()
        clear_data_caches()
        return jsonify({"success": True, "message": "Fund added to research"})
    return jsonify({"error": "Fund already in research or error adding"}), 400


@research_bp.route("/<code>", methods=["DELETE"])
@login_required
def api_remove_research_fund(code):
    if remove_research_fund(str(code)):
        clear_response_caches()
        clear_data_caches()
        return jsonify({"success": True, "message": "Fund removed from research"})
    return jsonify({"error": "Fund not found in research or error removing"}), 400


@research_bp.route("", methods=["GET"])
@login_required
def api_get_research_funds():
    return jsonify(load_research_funds())


@refresh_bp.route("", methods=["POST", "GET"])
@login_required
def refresh_data():
    scope = request.args.get("scope")
    if not scope and request.is_json and request.json:
        scope = request.json.get("scope")
    if not scope:
        scope = "all"
    scope = scope.strip().lower()
    if scope not in {"all", "portfolio", "research"}:
        return jsonify({"error": "Invalid scope. Use all|portfolio|research"}), 400

    trigger = "manual_get" if request.method == "GET" else "manual_post"
    payload = refresh_and_persist(trigger_type=trigger, scope=scope)
    if payload.get("error"):
        return jsonify(
            {
                "error": payload.get("error"),
                "partial_funds_count": payload.get("partial_funds_count"),
                "expected_count": payload.get("expected_count"),
                "failed_count": payload.get("failed_count"),
                "expected_portfolio_count": payload.get("expected_portfolio_count"),
                "fetched_portfolio_count": payload.get("fetched_portfolio_count"),
            }
        ), 500

    response = {
        "message": "Data refreshed successfully",
        "timestamp": payload.get("timestamp"),
        "count": len(payload.get("funds", [])),
        "expected_count": payload.get("expected_count"),
        "failed_count": payload.get("failed_count"),
        "expected_portfolio_count": payload.get("expected_portfolio_count"),
        "fetched_portfolio_count": payload.get("fetched_portfolio_count"),
        "scope": scope,
    }
    if request.method == "GET":
        response["warning"] = "GET /api/refresh is deprecated. Use POST /api/refresh."
    return jsonify(response)
