import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import login_required

from mf_tracker.services.note_service import load_notes, save_notes

logger = logging.getLogger(__name__)
notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")

@notes_bp.route("", methods=["GET"])
@login_required
def get_notes_api():
    return jsonify(load_notes())

@notes_bp.route("", methods=["POST"])
@login_required
def add_note_api():
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

@notes_bp.route("/<int:index>", methods=["DELETE"])
@login_required
def delete_note_api(index):
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
