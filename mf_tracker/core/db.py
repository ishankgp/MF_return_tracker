import os
from mf_tracker.services.history_store import HistoryStore

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.getenv("DATA_DIR", BASE_DIR)
history_store = HistoryStore(os.path.join(DATA_DIR, "mf_history.db"))
