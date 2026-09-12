import json
import logging
import os
from flask import current_app

logger = logging.getLogger(__name__)
memory_notes = []

def get_notes_file():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    data_dir = os.getenv("DATA_DIR", base_dir)
    return os.path.join(data_dir, "notes.json")

def load_notes():
    is_vercel = os.environ.get("VERCEL") == "1"
    if is_vercel:
        return memory_notes
    notes_file = get_notes_file()
    if not os.path.exists(notes_file):
        return []
    try:
        with open(notes_file, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        logger.error("Error loading notes: %s", exc)
        return []

def save_notes(notes):
    is_vercel = os.environ.get("VERCEL") == "1"
    if is_vercel:
        global memory_notes
        memory_notes = notes
        return True
    try:
        notes_file = get_notes_file()
        with open(notes_file, "w", encoding="utf-8") as handle:
            json.dump(notes, handle, indent=2)
        return True
    except Exception as exc:
        logger.error("Error saving notes: %s", exc)
        return False
