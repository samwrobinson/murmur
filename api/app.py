from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
import os
import threading

from config import FLASK_HOST, FLASK_PORT, AUDIO_DIR, TRANSCRIBE_LOCALLY, get_persisted_setting, set_persisted_setting
from transcribe import transcribe_entry
from wifi import (
    get_wifi_status, scan_networks, get_saved_networks,
    connect_to_network, forget_network, add_network,
)
from db import (
    init_db, get_entries, get_entry, create_entry, update_entry, delete_entry,
    toggle_favorite, search_entries, get_on_this_day, add_tag, remove_tag,
    get_all_tags, create_milestone, get_milestones, get_stats, get_random_prompt,
    get_untranscribed_entries,
)

app = Flask(__name__)
CORS(app)  # Allow 11ty dev server to call API


def entry_to_dict(entry, tags=None):
    """Convert a sqlite3.Row to a JSON-safe dict."""
    d = dict(entry)
    if tags is not None:
        d["tags"] = tags
    return d


# --- Entry endpoints ---

@app.route("/api/entries")
def api_entries():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    favorites = request.args.get("favorites", "false") == "true"
    tag = request.args.get("tag", None)
    entries, total = get_entries(page=page, per_page=per_page, favorites_only=favorites, tag=tag)
    return jsonify({
        "entries": [entry_to_dict(e) for e in entries],
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@app.route("/api/entries/<int:entry_id>")
def api_entry_detail(entry_id):
    entry, tags = get_entry(entry_id)
    if not entry:
        return jsonify({"error": "Entry not found"}), 404
    return jsonify(entry_to_dict(entry, tags))


@app.route("/api/entries/untranscribed")
def api_untranscribed():
    entries = get_untranscribed_entries()
    return jsonify({"entries": [dict(e) for e in entries]})


@app.route("/api/entries", methods=["POST"])
def api_create_entry():
    # Handle audio file upload (multipart form)
    if request.content_type and "multipart/form-data" in request.content_type:
        audio = request.files.get("audio")
        notes = request.form.get("notes")
        source = request.form.get("source", "web-audio")
        duration = request.form.get("duration", type=float)
        tags_str = request.form.get("tags", "")

        audio_filename = None
        if audio:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            ext = os.path.splitext(audio.filename)[1] or ".webm"
            audio_filename = f"{timestamp}{ext}"
            audio.save(os.path.join(AUDIO_DIR, audio_filename))

        entry_id = create_entry(
            audio_filename=audio_filename,
            duration_seconds=duration,
            notes=notes,
            source=source,
        )

        # Add tags if provided
        if tags_str:
            for tag_name in tags_str.split(","):
                tag_name = tag_name.strip()
                if tag_name:
                    add_tag(entry_id, tag_name)

        # Kick off background transcription for audio entries
        if audio_filename and TRANSCRIBE_LOCALLY:
            audio_path = os.path.join(AUDIO_DIR, audio_filename)
            client_key = request.headers.get("X-OpenAI-Key")
            threading.Thread(
                target=transcribe_entry,
                args=(entry_id, audio_path),
                kwargs={"client_key": client_key},
                daemon=True,
            ).start()

        entry, tags = get_entry(entry_id)
        return jsonify(entry_to_dict(entry, tags)), 201

    # Handle JSON body (text-only entries)
    data = request.get_json() or {}
    entry_id = create_entry(
        notes=data.get("notes"),
        source=data.get("source", "web"),
    )

    # Add tags if provided
    tags_list = data.get("tags", [])
    for tag_name in tags_list:
        if tag_name.strip():
            add_tag(entry_id, tag_name.strip())

    entry, tags = get_entry(entry_id)
    return jsonify(entry_to_dict(entry, tags)), 201


@app.route("/api/entries/<int:entry_id>", methods=["PUT"])
def api_update_entry(entry_id):
    data = request.get_json() or {}
    update_entry(
        entry_id,
        notes=data.get("notes"),
        transcription=data.get("transcription"),
        transcription_status=data.get("transcription_status"),
    )
    entry, tags = get_entry(entry_id)
    return jsonify(entry_to_dict(entry, tags))


@app.route("/api/entries/<int:entry_id>", methods=["DELETE"])
def api_delete_entry(entry_id):
    delete_entry(entry_id)
    return jsonify({"success": True})


@app.route("/api/entries/<int:entry_id>/favorite", methods=["POST"])
def api_toggle_favorite(entry_id):
    toggle_favorite(entry_id)
    entry, tags = get_entry(entry_id)
    return jsonify(entry_to_dict(entry, tags))


@app.route("/api/entries/<int:entry_id>/tag", methods=["POST"])
def api_add_tag(entry_id):
    data = request.get_json() or {}
    tag_name = data.get("tag", "").strip()
    if tag_name:
        add_tag(entry_id, tag_name)
    entry, tags = get_entry(entry_id)
    return jsonify(entry_to_dict(entry, tags))


@app.route("/api/entries/<int:entry_id>/tag", methods=["DELETE"])
def api_remove_tag(entry_id):
    data = request.get_json() or {}
    tag_name = data.get("tag", "").strip()
    if tag_name:
        remove_tag(entry_id, tag_name)
    entry, tags = get_entry(entry_id)
    return jsonify(entry_to_dict(entry, tags))


# --- Search ---

@app.route("/api/search")
def api_search():
    query = request.args.get("q", "")
    if not query:
        return jsonify({"entries": [], "query": ""})
    entries = search_entries(query)
    return jsonify({
        "entries": [entry_to_dict(e) for e in entries],
        "query": query,
    })


# --- On This Day ---

@app.route("/api/on-this-day")
def api_on_this_day():
    entries = get_on_this_day()
    return jsonify({"entries": [entry_to_dict(e) for e in entries]})


# --- Tags ---

@app.route("/api/tags")
def api_tags():
    tags = get_all_tags()
    return jsonify({"tags": [dict(t) for t in tags]})


# --- Milestones ---

@app.route("/api/milestones")
def api_milestones_list():
    milestones = get_milestones()
    return jsonify({"milestones": [dict(m) for m in milestones]})


@app.route("/api/milestones", methods=["POST"])
def api_create_milestone():
    data = request.get_json() or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Title required"}), 400
    create_milestone(
        title=title,
        milestone_date=data.get("date"),
        entry_id=data.get("entry_id"),
    )
    return jsonify({"success": True}), 201


# --- Stats ---

@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())


# --- Prompt ---

@app.route("/api/prompt")
def api_prompt():
    prompt = get_random_prompt()
    return jsonify(dict(prompt) if prompt else {})


# --- WiFi ---

@app.route("/api/wifi/status")
def api_wifi_status():
    return jsonify(get_wifi_status())


@app.route("/api/wifi/scan")
def api_wifi_scan():
    return jsonify({"networks": scan_networks()})


@app.route("/api/wifi/saved")
def api_wifi_saved():
    return jsonify({"networks": get_saved_networks()})


@app.route("/api/wifi/connect", methods=["POST"])
def api_wifi_connect():
    data = request.get_json() or {}
    ssid = data.get("ssid", "").strip()
    password = data.get("password", "").strip() or None
    if not ssid:
        return jsonify({"success": False, "message": "SSID required"}), 400
    result = connect_to_network(ssid, password)
    status_code = 200 if result["success"] else 502
    return jsonify(result), status_code


@app.route("/api/wifi/add", methods=["POST"])
def api_wifi_add():
    data = request.get_json() or {}
    ssid = data.get("ssid", "").strip()
    password = data.get("password", "").strip() or None
    if not ssid:
        return jsonify({"success": False, "message": "Network name required"}), 400
    result = add_network(ssid, password)
    status_code = 200 if result["success"] else 502
    return jsonify(result), status_code


@app.route("/api/wifi/forget", methods=["POST"])
def api_wifi_forget():
    data = request.get_json() or {}
    ssid = data.get("ssid", "").strip()
    if not ssid:
        return jsonify({"success": False, "message": "SSID required"}), 400
    result = forget_network(ssid)
    status_code = 200 if result["success"] else 502
    return jsonify(result), status_code


# --- Settings (persisted on Pi) ---

@app.route("/api/settings/openai-key")
def api_get_openai_key():
    key = get_persisted_setting("openai_api_key") or ""
    if len(key) > 8:
        masked = key[:7] + "..." + key[-4:]
    elif key:
        masked = key[:3] + "..."
    else:
        masked = ""
    return jsonify({"masked_key": masked})


@app.route("/api/settings/openai-key", methods=["POST"])
def api_set_openai_key():
    data = request.get_json() or {}
    key = data.get("key", "").strip()
    if not key:
        return jsonify({"error": "Key is required"}), 400
    set_persisted_setting("openai_api_key", key)
    return jsonify({"success": True})


# --- Audio files ---

@app.route("/api/audio/<filename>")
def api_serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)


if __name__ == "__main__":
    init_db()
    print(f"\n  Murmur API running at http://localhost:{FLASK_PORT}\n")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=True)
