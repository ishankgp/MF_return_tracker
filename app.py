from flask import Flask, render_template, send_from_directory, jsonify, request, redirect, url_for, flash, session
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import asyncio
import json
import logging
import os
import traceback

import pytz
import redis
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from authlib.integrations.flask_client import OAuth
from cachetools import TTLCache
from dotenv import load_dotenv
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from filelock import FileLock, Timeout as FileLockTimeout
try:
    from flask_session import Session
except Exception:  # pragma: no cover - optional dependency fallback for local/tests
    Session = None

from config import get_config
from fetch_mf_returns import (
    add_fund,
    add_research_fund,
    clear_data_caches,
    fetch_funds_data,
    load_research_funds,
    remove_fund,
    remove_research_fund,
)
from mf_tracker.services.history_store import HistoryStore


load_dotenv()

app = Flask(__name__)
app.config.from_object(get_config())
APP_START_TIME = datetime.now().strftime("%b %d, %H:%M:%S")

secret_key = app.config.get("SECRET_KEY")
if not secret_key and app.config.get("FLASK_ENV", "development") == "production":
    raise ValueError("SECRET_KEY must be set in production")
app.secret_key = secret_key or "dev-secret-key"

CORS(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=app.config.get("GOOGLE_CLIENT_ID"),
    client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

allowed_users_raw = app.config.get("ALLOWED_USERS", ["ishan.kgp@gmail.com"])
if isinstance(allowed_users_raw, str):
    allowed_users_raw = [allowed_users_raw]
ALLOWED_USERS = {value.strip().lower() for value in allowed_users_raw if value and value.strip()}

IS_VERCEL = os.environ.get("VERCEL") == "1"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", BASE_DIR)
logs_dir = os.path.join(DATA_DIR, "logs")
os.makedirs(logs_dir, exist_ok=True)

log_handlers = [logging.StreamHandler()]
if not IS_VERCEL:
    log_handlers.append(logging.FileHandler(os.path.join(logs_dir, "app.log"), encoding="utf-8"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=log_handlers,
)
logger = logging.getLogger(__name__)

REDIS_URL = app.config.get("REDIS_URL", "redis://localhost:6379")
redis_client = None
try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()
    logger.info("Redis connection established")
except Exception as exc:
    logger.warning("Redis not available: %s", exc)

if redis_client and Session is not None:
    app.config["SESSION_TYPE"] = "redis"
    app.config["SESSION_REDIS"] = redis_client
    app.config["SESSION_PERMANENT"] = True
    app.config["SESSION_USE_SIGNER"] = True
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
    Session(app)
    logger.info("Redis-based sessions enabled")
else:
    logger.info("Using default cookie-based sessions")

memory_cache = TTLCache(
    maxsize=app.config.get("MEMORY_CACHE_SIZE", 200),
    ttl=app.config.get("MEMORY_CACHE_TTL", 600),
)
redis_cache_ttl = int(app.config.get("REDIS_TTL", app.config.get("MEMORY_CACHE_TTL", 600)))

history_store = HistoryStore(os.path.join(DATA_DIR, "mf_history.db"))
scheduler_leader_lock = None

LAST_REFRESH_STATUS: Dict[str, Any] = {
    "timestamp": None,
    "status": "never",
    "error": None,
}


class User(UserMixin):
    def __init__(self, user_id: str, email: str, name: str):
        self.id = user_id
        self.email = email
        self.name = name


@login_manager.user_loader
def load_user(user_id: str):
    if "user_email" in session:
        return User(session.get("user_id"), session.get("user_email"), session.get("user_name", "User"))
    return None


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


def clear_response_caches() -> None:
    memory_cache.clear()
    if redis_client:
        for pattern in ("funds_cache:*", "get_cached_data:*"):
            for key in redis_client.scan_iter(pattern):
                redis_client.delete(key)


def get_cached_data(scope: str = "all", as_of: Optional[datetime] = None, force_refresh: bool = False) -> Dict[str, Any]:
    cache_key = _cache_key(scope, as_of)

    if not force_refresh:
        if redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as exc:
                logger.warning("Redis cache read error: %s", exc)

        if cache_key in memory_cache:
            return memory_cache[cache_key]

    result = asyncio.run(fetch_funds_data(as_of_date=as_of, scope=scope))
    funds = result.get("funds", [])
    if not funds:
        payload = {
            "error": "No data available",
            "funds": [],
            "timestamp": datetime.utcnow().isoformat(),
            "count": 0,
            "comparison_anchor_date": result.get("comparison_anchor_date"),
            "comparison_header_dates": result.get("comparison_header_dates", {}),
            "scope": scope,
        }
    else:
        payload = {
            "funds": funds,
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(funds),
            "comparison_anchor_date": result.get("comparison_anchor_date"),
            "comparison_header_dates": result.get("comparison_header_dates", {}),
            "scope": scope,
        }

    if redis_client:
        try:
            redis_client.setex(cache_key, redis_cache_ttl, json.dumps(payload))
        except Exception as exc:
            logger.warning("Redis cache set error: %s", exc)

    memory_cache[cache_key] = payload
    return payload


def refresh_and_persist(trigger_type: str = "manual", scope: str = "all", as_of: Optional[datetime] = None) -> Dict[str, Any]:
    run_id = history_store.start_refresh_run(trigger_type)
    try:
        clear_response_caches()
        clear_data_caches()

        payload = get_cached_data(scope=scope, as_of=as_of, force_refresh=True)
        if payload.get("error"):
            history_store.finish_refresh_run(run_id, status="failed", error=payload.get("error"), fund_count=0)
            LAST_REFRESH_STATUS.update({"timestamp": datetime.utcnow().isoformat(), "status": "failed", "error": payload.get("error")})
            return payload

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


@app.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/auth/login")
def auth_login():
    redirect_uri = url_for("auth_callback", _external=True)
    if "localhost" not in redirect_uri and "127.0.0.1" not in redirect_uri:
        redirect_uri = redirect_uri.replace("http://", "https://")
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/callback")
def auth_callback():
    try:
        token = google.authorize_access_token()
        user_info = token.get("userinfo")
        if not user_info:
            response = google.get("https://openidconnect.googleapis.com/v1/userinfo")
            user_info = response.json()

        email = str(user_info.get("email", "")).lower()
        if email not in ALLOWED_USERS:
            flash("Access denied: You are not authorized to view this application.", "error")
            return redirect(url_for("login"))

        user = User(str(user_info.get("sub", email)), email, user_info.get("name", "User"))
        login_user(user)

        session["user_id"] = user.id
        session["user_email"] = user.email
        session["user_name"] = user.name
        session.permanent = True
        return redirect(url_for("index"))
    except Exception as exc:
        logger.error("Auth failed: %s", exc)
        flash(f"Authentication failed: {exc}", "error")
        return redirect(url_for("login"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("login"))


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/")
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


@app.route("/api/funds")
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
            }
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.error("Error in /api/funds: %s", exc)
        logger.error(traceback.format_exc())
        return jsonify({"error": str(exc), "funds": []}), 500


@app.route("/api/funds/history/<code>")
@login_required
def api_fund_history(code: str):
    range_key = request.args.get("range", "1y").lower()
    if range_key not in {"1y", "3y", "5y"}:
        return jsonify({"error": "Invalid range. Use 1y|3y|5y"}), 400

    history = history_store.get_fund_history(str(code), range_key)
    return jsonify({"code": str(code), "range": range_key, "count": len(history), "history": history})


@app.route("/api/refresh", methods=["POST", "GET"])
@login_required
def refresh_data():
    trigger = "manual_get" if request.method == "GET" else "manual_post"
    payload = refresh_and_persist(trigger_type=trigger, scope="all")
    if payload.get("error"):
        return jsonify({"error": payload.get("error")}), 500

    response = {
        "message": "Data refreshed successfully",
        "timestamp": payload.get("timestamp"),
        "count": len(payload.get("funds", [])),
    }
    if request.method == "GET":
        response["warning"] = "GET /api/refresh is deprecated. Use POST /api/refresh."
    return jsonify(response)


@app.route("/api/funds/search")
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


@app.route("/api/funds", methods=["POST"])
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


@app.route("/api/funds/<code>", methods=["DELETE"])
@login_required
def api_remove_fund(code):
    if remove_fund(str(code)):
        clear_response_caches()
        clear_data_caches()
        return jsonify({"success": True, "message": "Fund removed successfully"})
    return jsonify({"error": "Fund not found or error removing"}), 400


@app.route("/api/research-funds", methods=["POST"])
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


@app.route("/api/research-funds/<code>", methods=["DELETE"])
@login_required
def api_remove_research_fund(code):
    if remove_research_fund(str(code)):
        clear_response_caches()
        clear_data_caches()
        return jsonify({"success": True, "message": "Fund removed from research"})
    return jsonify({"error": "Fund not found in research or error removing"}), 400


@app.route("/api/research-funds", methods=["GET"])
@login_required
def api_get_research_funds():
    return jsonify(load_research_funds())


NOTES_FILE = os.path.join(DATA_DIR, "notes.json")
memory_notes = []


def load_notes():
    if IS_VERCEL:
        return memory_notes
    if not os.path.exists(NOTES_FILE):
        return []
    try:
        with open(NOTES_FILE, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        logger.error("Error loading notes: %s", exc)
        return []


def save_notes(notes):
    if IS_VERCEL:
        global memory_notes
        memory_notes = notes
        return True
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as handle:
            json.dump(notes, handle, indent=2)
        return True
    except Exception as exc:
        logger.error("Error saving notes: %s", exc)
        return False


@app.route("/api/notes", methods=["GET"])
@login_required
def get_notes():
    return jsonify(load_notes())


@app.route("/api/notes", methods=["POST"])
@login_required
def add_note():
    try:
        data = request.json
        if not data or "text" not in data or "date" not in data:
            return jsonify({"error": "Invalid data"}), 400

        notes = load_notes()
        notes.append({"date": data["date"], "text": data["text"], "created_at": datetime.utcnow().isoformat()})
        if save_notes(notes):
            return jsonify({"message": "Note added successfully", "notes": notes})
        return jsonify({"error": "Failed to save note"}), 500
    except Exception as exc:
        logger.error("Error adding note: %s", exc)
        return jsonify({"error": str(exc)}), 500


@app.route("/api/notes/<int:index>", methods=["DELETE"])
@login_required
def delete_note(index):
    try:
        notes = load_notes()
        if 0 <= index < len(notes):
            notes.pop(index)
            if save_notes(notes):
                return jsonify({"message": "Note deleted successfully", "notes": notes})
            return jsonify({"error": "Failed to save changes"}), 500
        return jsonify({"error": "Note not found"}), 404
    except Exception as exc:
        logger.error("Error deleting note: %s", exc)
        return jsonify({"error": str(exc)}), 500


def scheduled_refresh():
    lock = None
    if redis_client:
        lock = redis_client.lock("refresh_lock", timeout=1800)
        if not lock.acquire(blocking=False):
            logger.info("Another worker is already running scheduled refresh. Skipping.")
            return

    try:
        logger.info("Starting scheduled refresh")
        payload = refresh_and_persist(trigger_type="scheduled", scope="all")
        if payload.get("error"):
            logger.error("Scheduled refresh failed: %s", payload.get("error"))
        else:
            logger.info("Scheduled refresh completed. funds=%s", len(payload.get("funds", [])))
    finally:
        if lock:
            try:
                lock.release()
            except Exception:
                pass


def _should_start_scheduler() -> bool:
    """
    Feature-flagged scheduler startup policy.
    - legacy (default): preserve existing behavior (scheduler in each worker)
    - single: only one process starts scheduler via file lock leader election
    - off: disable scheduler
    """
    global scheduler_leader_lock

    scheduler_mode = str(os.getenv("SCHEDULER_MODE", "legacy")).strip().lower()
    if scheduler_mode in {"off", "disabled", "none", "0", "false"}:
        logger.info("Scheduler disabled via SCHEDULER_MODE=%s", scheduler_mode)
        return False

    if scheduler_mode != "single":
        return True

    lock_file = os.path.join(DATA_DIR, "scheduler_leader.lock")
    lock_timeout = int(os.getenv("SCHEDULER_LEADER_LOCK_TIMEOUT", "0"))
    scheduler_leader_lock = FileLock(lock_file, timeout=lock_timeout)
    try:
        scheduler_leader_lock.acquire(timeout=lock_timeout)
        logger.info("Scheduler leader lock acquired (%s)", lock_file)
        return True
    except FileLockTimeout:
        logger.info("Scheduler leader lock not acquired; skipping scheduler in this worker")
        return False


if not app.config.get("TESTING") and (not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true"):
    if _should_start_scheduler():
        scheduler = BackgroundScheduler()
        scheduler.add_job(func=scheduled_refresh, trigger="cron", hour=0, minute=30, timezone=pytz.timezone("Asia/Kolkata"))
        scheduler.add_job(func=scheduled_refresh)
        scheduler.start()
        logger.info("Scheduler started (00:30 IST + startup warm refresh)")


@app.route("/health")
def health_check():
    last_success = history_store.get_last_successful_refresh()

    status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "redis_connected": redis_client is not None,
        "memory_cache_size": len(memory_cache),
        "last_refresh": LAST_REFRESH_STATUS,
        "last_successful_refresh": last_success,
    }

    if redis_client:
        try:
            redis_client.ping()
        except Exception as exc:
            status["status"] = "degraded"
            status["redis_error"] = str(exc)

    if LAST_REFRESH_STATUS.get("status") == "failed":
        status["status"] = "degraded"

    return jsonify(status)


@app.route("/health/deep")
def health_check_deep():
    try:
        results = get_cached_data(scope="all", force_refresh=False)
        health_status = {
            "status": "healthy" if not results.get("error") else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "redis_connected": redis_client is not None,
            "funds_count": len(results.get("funds", [])),
            "cache_size": len(memory_cache),
            "comparison_anchor_date": results.get("comparison_anchor_date"),
        }
        if results.get("error"):
            health_status["error"] = results.get("error")
        return jsonify(health_status)
    except Exception as exc:
        logger.error("Deep health check failed: %s", exc)
        return jsonify({"status": "unhealthy", "error": str(exc), "timestamp": datetime.utcnow().isoformat()}), 500


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", error_message="Page not found", details="The requested page does not exist"), 404


@app.errorhandler(500)
def internal_error(_error):
    return render_template("error.html", error_message="Internal server error", details="Something went wrong on our end"), 500


if __name__ == "__main__":
    flask_env = os.getenv("FLASK_ENV", "development")
    debug_mode = flask_env != "production"

    if debug_mode:
        logger.info("Starting Flask in DEVELOPMENT mode")
    else:
        logger.info("Starting Flask in PRODUCTION mode")

    app.run(debug=debug_mode, host="127.0.0.1", port=5000, use_reloader=debug_mode)
