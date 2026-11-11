import hmac
import json
import logging
import socket
import time
from urllib.parse import urlsplit

from flask import Flask, jsonify, render_template, request
from flask_sock import Sock
from simple_websocket import ConnectionClosed

from .actions import GameError
from .server import GameServer, send


LOGGER = logging.getLogger(__name__)


def reject_constant(value):
    raise ValueError(f"Invalid JSON number: {value}")


def password_matches(supplied, expected):
    if not isinstance(supplied, str):
        return False
    try:
        return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))
    except UnicodeError:
        return False


def parse_message(raw):
    if not isinstance(raw, str) or len(raw) > 32768:
        raise GameError("invalid_message", "Messages must be JSON text, up to 32768 characters")
    try:
        message = json.loads(raw, parse_constant=reject_constant)
    except (ValueError, RecursionError) as error:
        raise GameError("invalid_json", "Invalid JSON message") from error
    if not isinstance(message, dict):
        raise GameError("invalid_message", "Messages must be JSON objects")
    sequence = message.get("seq")
    if sequence is not None and (isinstance(sequence, bool) or not isinstance(sequence, int) or not 0 <= sequence <= 2 ** 53 - 1):
        raise GameError("invalid_sequence", "seq must be a nonnegative safe integer")
    return message


def create_app(password=None, save_path=None, seed=None, start_engine=True, allowed_origins=()):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=32768, SOCK_SERVER_OPTIONS={"ping_interval": 25, "max_message_size": 32768})
    server = GameServer(password=password, save_path=save_path, seed=seed, start_engine=start_engine)
    app.extensions["cold_world_game"] = server
    sock = Sock(app)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/server")
    def server_info():
        return jsonify({"name": "cold-world-game", "version": "0.1.0", "websocket": "/ws", "info": "/api/info", "client": "/"})

    @app.get("/health")
    def health():
        with server.world.lock:
            healthy = server.world.fault is None and not server.stopping.is_set()
            return jsonify({"ok": healthy, "online": len(server.world.online), "paused": not server.world.online or not healthy, "tick": server.world.tick_number}), 200 if healthy else 503

    @app.get("/api/info")
    def info():
        return jsonify(server.world.catalog())

    @sock.route("/ws")
    def websocket_handler(websocket):
        player_id = None
        if not server.register(websocket):
            websocket.close()
            return
        try:
            origin = request.headers.get("Origin")
            if origin and urlsplit(origin).netloc != request.host and origin not in allowed_origins:
                raise GameError("invalid_origin", "This browser origin is not allowed")
            message = parse_message(websocket.receive(timeout=10))
            supplied_password = message.get("password")
            if message.get("type") != "join" or not password_matches(supplied_password, server.password):
                raise GameError("unauthorized", "The first message must join with the correct server password")
            candidate_id = message.get("player_id")
            state = server.world.join(candidate_id, client_movement=message.get("client_movement") is True)
            player_id = candidate_id
            quiet_inputs = message.get("quiet_inputs") is True
            wants_roster = message.get("player_roster") is True
            processed_sequence = 0
            state["command_sequence"] = processed_sequence
            welcome = {"type": "welcome", "player_id": player_id, "protocol": 1, "state": state}
            if wants_roster:
                welcome["roster"] = server.world.player_roster()
            send(websocket, welcome)
            next_state = time.monotonic() + 0.1
            next_roster = time.monotonic() + 1
            tokens, last_token = 120.0, time.monotonic()
            while not server.stopping.is_set():
                raw = websocket.receive(timeout=max(0, min(0.05, next_state - time.monotonic())))
                now = time.monotonic()
                if raw is not None:
                    tokens = min(120, tokens + (now - last_token) * 60)
                    last_token = now
                    tokens -= 1
                    if tokens < 0:
                        raise GameError("rate_limited", "Too many commands; the limit is 60 per second with a burst of 120")
                    sequence = None
                    try:
                        command = parse_message(raw)
                        sequence = command.get("seq")
                        result = server.world.execute(player_id, command)
                        if sequence is not None:
                            processed_sequence = max(processed_sequence, sequence)
                        if sequence is not None or not quiet_inputs or command.get("type") not in ("input", "stop"):
                            send(websocket, {"type": "ack", "seq": sequence, "result": result})
                    except GameError as error:
                        if sequence is not None:
                            processed_sequence = max(processed_sequence, sequence)
                        send(websocket, {"type": "error", "seq": sequence, "code": error.code, "message": str(error)})
                now = time.monotonic()
                if now >= next_state:
                    state = server.world.snapshot(player_id)
                    state["command_sequence"] = processed_sequence
                    send(websocket, {"type": "state", "state": state})
                    now = time.monotonic()
                    next_state += (int((now - next_state) / 0.1) + 1) * 0.1
                if wants_roster and now >= next_roster:
                    send(websocket, {"type": "roster", **server.world.player_roster()})
                    next_roster = time.monotonic() + 1
        except GameError as error:
            try:
                send(websocket, {"type": "error", "code": error.code, "message": str(error)})
                websocket.receive(timeout=1)
            except ConnectionClosed:
                pass
        except ConnectionClosed:
            pass
        except Exception:
            LOGGER.exception("WebSocket connection failed")
            try:
                send(websocket, {"type": "error", "code": "server_error", "message": "The server could not complete this request"})
            except Exception:
                pass
        finally:
            try:
                if player_id is not None:
                    server.world.leave(player_id)
            except Exception:
                LOGGER.exception("Could not persist disconnected player")
                with server.world.lock:
                    server.world.online.discard(player_id)
                    server.world.controls.pop(player_id, None)
            finally:
                server.unregister(websocket)
                try:
                    websocket.close()
                except ConnectionClosed:
                    pass
                if websocket.mode == "werkzeug":
                    websocket.thread.join(timeout=1)
                    try:
                        websocket.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

    return app
