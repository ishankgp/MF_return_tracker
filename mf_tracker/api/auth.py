import logging
from flask import Blueprint, redirect, url_for, flash, session
from flask_login import login_required, login_user, logout_user
from mf_tracker.core.extensions import oauth
from mf_tracker.services.auth_service import User, get_allowed_users

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/login")
def auth_login():
    redirect_uri = url_for("auth.auth_callback", _external=True)
    if "localhost" not in redirect_uri and "127.0.0.1" not in redirect_uri:
        redirect_uri = redirect_uri.replace("http://", "https://")
    google = oauth.create_client("google")
    return google.authorize_redirect(redirect_uri)

@auth_bp.route("/callback")
def auth_callback():
    try:
        google = oauth.create_client("google")
        token = google.authorize_access_token()
        user_info = token.get("userinfo")
        if not user_info:
            response = google.get("https://openidconnect.googleapis.com/v1/userinfo")
            user_info = response.json()

        email = str(user_info.get("email", "")).lower()
        allowed_users = get_allowed_users()
        
        if email not in allowed_users:
            flash("Access denied: You are not authorized to view this application.", "error")
            return redirect(url_for("web.login"))

        user = User(str(user_info.get("sub", email)), email, user_info.get("name", "User"))
        login_user(user)

        session["user_id"] = user.id
        session["user_email"] = user.email
        session["user_name"] = user.name
        session.permanent = True
        return redirect(url_for("web.index"))
    except Exception as exc:
        logger.error("Auth failed: %s", exc)
        flash(f"Authentication failed: {exc}", "error")
        return redirect(url_for("web.login"))

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("web.login"))
