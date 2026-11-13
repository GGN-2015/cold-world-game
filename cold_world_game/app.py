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
from .sync import state_delta
from .wire import CompactSync


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


def create_app(password=None, save_path=None, seed=None, start_engine=True, allowed_origins=(), admin=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=32768, SOCK_SERVER_OPTIONS={"ping_interval": 25, "max_message_size": 32768})
    server = GameServer(password=password, save_path=save_path, seed=seed, start_engine=start_engine, admin=admin)
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
            persistence = server.persistence.status() if server.persistence else {"mode": "synchronous"}
            return jsonify({"ok": healthy, "online": len(server.world.online), "paused": not server.world.online or not healthy, "tick": server.world.tick_number, "persistence": persistence}), 200 if healthy else 503

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
            wants_deltas = message.get("state_deltas") is True
            compact = CompactSync() if message.get("compact_state") == 1 and wants_deltas else None
            wants_terrain = message.get("procedural_terrain") == 1 and wants_deltas
            server.publisher.subscribe(player_id, wants_terrain)
            terrain_previous = {}
            if wants_terrain:
                with server.world.lock:
                    state = server.world.snapshot(player_id, procedural=True)
                    terrain_changes, terrain_previous = server.world.terrain_updates(player_id, terrain_previous)
            state_revision = 0
            state["command_sequence"] = 0
            last_capture = time.monotonic()
            if compact:
                state = compact.welcome(state)
            welcome = {"type": "welcome", "player_id": player_id, "protocol": 1, "state": state}
            welcome["navigation_config"] = server.world.navigation_bootstrap()
            if compact:
                welcome["wire_config"] = compact.encoder.config()
            if wants_terrain:
                welcome["terrain_config"] = server.world.terrain_bootstrap()
                welcome["terrain"] = terrain_changes
            if wants_deltas:
                welcome["state_revision"] = state_revision
            previous_state = state
            if wants_roster:
                welcome["roster"] = server.world.player_roster()
                if compact:
                    compact.reset_roster(welcome["roster"])
            send(websocket, welcome)
            next_state = time.monotonic() + 0.1
            next_roster = time.monotonic() + 1
            tokens, last_token = 120.0, time.monotonic()
            while not server.stopping.is_set():
                raw = websocket.receive(timeout=max(0, min(0.05, next_state - time.monotonic())))
                now = time.monotonic()
                batch_started = time.perf_counter()
                batch_count = 0
                while raw is not None and not server.stopping.is_set():
                    received = time.perf_counter()
                    server.observe("inbound_backlog", len(getattr(websocket, "input_buffer", ())))
                    now = time.monotonic()
                    tokens = min(120, tokens + (now - last_token) * 60)
                    last_token = now
                    tokens -= 1
                    if tokens < 0:
                        raise GameError("rate_limited", "Too many commands; the limit is 60 per second with a burst of 120")
                    sequence = None
                    try:
                        command = parse_message(raw)
                        sequence = command.get("seq")
                        result = server.execute(player_id, command)
                        if sequence is not None or not quiet_inputs or command.get("type") not in ("input", "stop"):
                            send(websocket, {"type": "ack", "seq": sequence, "result": result})
                    except GameError as error:
                        send(websocket, {"type": "error", "seq": sequence, "code": error.code, "message": str(error)})
                    finally:
                        server.observe("received_command_ms", (time.perf_counter() - received) * 1000)
                    batch_count += 1
                    if batch_count >= 32 or time.perf_counter() - batch_started >= .004:
                        break
                    raw = websocket.receive(timeout=0)
                now = time.monotonic()
                if now >= next_state:
                    state, terrain_changes, current_terrain, captured_at = server.snapshot(player_id, wants_terrain, terrain_previous)
                    if captured_at < last_capture or state["tick"] < previous_state["tick"] or state["command_sequence"] < previous_state["command_sequence"]:
                        next_state = time.monotonic() + .01
                        continue
                    last_capture = captured_at
                    terrain_previous = current_terrain
                    if wants_deltas:
                        update = compact.delta(state) if compact else state_delta(previous_state, state, state_revision)
                        if wants_terrain and (terrain_changes["add"] or terrain_changes["remove"]):
                            update["terrain"] = terrain_changes
                        if compact:
                            websocket.send(compact.encoder.encode(update))
                        else:
                            send(websocket, update)
                        state_revision += 1
                    else:
                        send(websocket, {"type": "state", "state": state})
                    previous_state = state
                    now = time.monotonic()
                    next_state += (int((now - next_state) / 0.1) + 1) * 0.1
                if wants_roster and now >= next_roster:
                    roster = server.roster()
                    if compact:
                        update = compact.roster_delta(roster)
                        if update:
                            websocket.send(compact.encoder.encode(update))
                    else:
                        send(websocket, {"type": "roster", **roster})
                    next_roster = time.monotonic() + 1
        except GameError as error:
            try:
                send(websocket, {"type": "error", "code": error.code, "message": str(error)})
                websocket.receive(timeout=1)
            except (ConnectionClosed, OSError):
                pass
        except ConnectionClosed:
            pass
        except Exception:
            if not server.stopping.is_set():
                LOGGER.exception("WebSocket connection failed")
                try:
                    send(websocket, {"type": "error", "code": "server_error", "message": "The server could not complete this request"})
                except Exception:
                    pass
        finally:
            try:
                if player_id is not None:
                    server.publisher.unsubscribe(player_id)
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
                except (ConnectionClosed, OSError):
                    pass
                if websocket.mode == "werkzeug":
                    websocket.thread.join(timeout=1)
                    try:
                        websocket.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

    return app
