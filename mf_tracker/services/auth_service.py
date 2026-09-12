from flask_login import UserMixin
from flask import session
from mf_tracker.core.extensions import login_manager
from flask import current_app

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

def get_allowed_users():
    allowed_users_raw = current_app.config.get("ALLOWED_USERS", ["ishan.kgp@gmail.com"])
    if isinstance(allowed_users_raw, str):
        allowed_users_raw = [allowed_users_raw]
    return {value.strip().lower() for value in allowed_users_raw if value and value.strip()}
