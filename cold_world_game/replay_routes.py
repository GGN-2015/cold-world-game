"""HTTP routes shared by the live game and the arena."""

import hmac
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile, ZipFile

from flask import jsonify, render_template, request, send_file

from .replays import MAX_UPLOAD, read_manifest, read_segment


def register_replay_routes(app, library, password, *, arena=False, allowed_origins=()):
    def authorized():
        origin = request.headers.get("Origin")
        if origin and urlsplit(origin).netloc != request.host and origin not in allowed_origins:
            return jsonify(error="invalid_origin"), 403
        if password is not None:
            encoded = request.headers.get("X-Replay-Password-Encoded")
            supplied = unquote(encoded) if encoded is not None else request.headers.get("X-Replay-Password", "")
            if not hmac.compare_digest(supplied.encode("utf-8"), password.encode("utf-8")):
                return jsonify(error="unauthorized"), 403
        return None

    @app.after_request
    def replay_no_cache(response):
        if request.path == "/api/replays" or request.path.startswith("/api/replays/"):
            response.cache_control.private = True
            response.cache_control.no_store = True
        return response

    @app.get("/replay/")
    def replay():
        return render_template("replay.html", arena=arena, password_required=password is not None)

    @app.get("/api/replays")
    def replay_list():
        failure = authorized()
        if failure:
            return failure
        fields = ("id", "title", "source", "location", "duration", "status", "created_at", "result")
        return jsonify(records=[
            {**{field: entry.get(field) for field in fields},
             "configuration": {key: entry.get("configuration", {}).get(key) for key in ("weapon", "batch")}}
            for entry in library.list()
        ])

    @app.get("/api/replays/<identifier>")
    def replay_info(identifier):
        failure = authorized()
        if failure:
            return failure
        try:
            return jsonify(library.metadata(library.path(identifier)))
        except FileNotFoundError:
            return jsonify(error="arena_history_missing"), 404
        except (OSError, ValueError, KeyError, BadZipFile):
            return jsonify(error="replay_file"), 422

    @app.get("/api/replays/<identifier>/segments/<int:number>")
    def replay_segment(identifier, number):
        failure = authorized()
        if failure:
            return failure
        try:
            with ZipFile(library.path(identifier)) as archive:
                meta = read_manifest(archive)
                if number >= len(meta["segments"]):
                    return jsonify(error="arena_history_range"), 404
                return jsonify(read_segment(archive, meta["segments"][number]))
        except FileNotFoundError:
            return jsonify(error="arena_history_missing"), 404
        except (OSError, ValueError, KeyError, BadZipFile):
            return jsonify(error="replay_file"), 422

    @app.get("/api/replays/<identifier>/download")
    def replay_download(identifier):
        failure = authorized()
        if failure:
            return failure
        try:
            return send_file(library.path(identifier), as_attachment=True, mimetype="application/zip")
        except FileNotFoundError:
            return jsonify(error="arena_history_missing"), 404

    @app.post("/api/replays/upload")
    def replay_upload():
        failure = authorized()
        if failure:
            return failure
        request.max_content_length = MAX_UPLOAD
        file = request.files.get("file")
        if file is None:
            return jsonify(error="replay_file"), 400
        try:
            return jsonify(library.upload(file.stream, file.filename or "Recording")), 201
        except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError, EOFError, BadZipFile, RecursionError, OverflowError, NotImplementedError, RuntimeError):
            return jsonify(error="replay_file"), 422
