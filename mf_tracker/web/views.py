import logging
import traceback
import os
from datetime import datetime
from flask import Blueprint, render_template, current_app
from flask_login import login_required, current_user

from mf_tracker.services.fund_service import get_cached_data, process_fund_data

logger = logging.getLogger(__name__)
web_bp = Blueprint("web", __name__)

APP_START_TIME = datetime.now().strftime("%b %d, %H:%M:%S")

@web_bp.route("/login")
def login():
    if current_user.is_authenticated:
        from flask import redirect, url_for
        return redirect(url_for("web.index"))
    return render_template("login.html")

@web_bp.route("/")
@login_required
def index():
    try:
        results = get_cached_data(scope="all")
        funds_data = process_fund_data(results)
        if not funds_data:
            return render_template(
                "error.html",
                error_message="No fund data available",
                details=results.get("error", "Unable to fetch fund data from API"),
            ), 500

        timestamp = results.get("timestamp", datetime.utcnow().isoformat())
        try:
            dt = datetime.fromisoformat(timestamp)
            last_updated = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            last_updated = timestamp

        return render_template(
            "index.html",
            funds=funds_data,
            last_updated=last_updated,
            fund_count=len(funds_data),
            deploy_time=APP_START_TIME,
            comparison_anchor_date=results.get("comparison_anchor_date"),
            comparison_header_dates=results.get("comparison_header_dates", {}),
        )
    except Exception as exc:
        logger.error("Error rendering index: %s", exc)
        logger.error(traceback.format_exc())
        return render_template("error.html", error_message="Error loading fund data", details=str(exc)), 500
