import math

import msgpack

from .sync import ENTITY_COLLECTIONS, changed_fields, state_delta


FIELDS = tuple(dict.fromkeys("""
id x y velocity_x velocity_y fields add update remove type base revision state objects entities
tick elapsed event_sequence you players monsters projectiles ground events environment movement
structure_states chunks interaction container terrain inventory backpack slots slot_changes kind
owner actor source target target_id shot attack_id range_player overlap_player seat_id occupant
temperature hunger money downed selected move_speed hp max_hp big fast species frozen_until
burning_until impaled sleeping rising demolition teleport_epoch mode epoch seated seat_direction
origin_x origin_y spawned_at remaining hostile range_x range_y range_radius weapon_kind
target_x target_y detonates_at trajectory flight_at time direction knockback damage target_type radius
range arc_degrees predicted weapon uses ammo item dropped_by immune_until lit monster_demolition
fuel igniter burn_remaining balance progress ui_open is_admin tile offset ambient_temperature
excitement_remaining year season day hour paused fault command_sequence unset online last_login_at
server_time roster_delta entries version hash patch reset count view_width view_height
""".split()))
FIELD_CODES = {name: index for index, name in enumerate(FIELDS)}
REFERENCES = frozenset("id owner actor source target target_id shot attack_id range_player overlap_player seat_id occupant demolition monster_demolition dropped_by remove order".split())
SCALES = {name: 256 for name in "x y velocity_x velocity_y origin_x origin_y range_x range_y target_x target_y offset knockback".split()}
SCALES.update({name: 1000 for name in "elapsed time spawned_at flight_at frozen_until burning_until detonates_at burn_remaining excitement_remaining immune_until".split()})
SCALES["direction"] = 4096
COLLECTIONS = (*ENTITY_COLLECTIONS, "structure_states")
PROJECTILE_FIELDS = frozenset("id x y velocity_x velocity_y owner hostile origin_x origin_y spawned_at range_player range_x range_y range_radius kind target_x target_y detonates_at target_id weapon_kind view_width view_height".split())


class WireEncoder:
    def __init__(self):
        self.references = {}

    def config(self):
        return {"version": 1, "fields": FIELDS, "references": sorted(REFERENCES), "scales": SCALES}

    def encode(self, message):
        reset = len(self.references) >= 16384
        if reset:
            self.references.clear()
        added = []

        def pack(value, field=None, precise=False):
            precise = precise or field == "you"
            value_type = type(value)
            if value_type is dict:
                return {FIELD_CODES.get(key, key): pack(entry, key, precise) for key, entry in value.items()}
            if value_type is list or value_type is tuple:
                return [pack(entry, field, precise) for entry in value]
            if value_type is str and field in REFERENCES:
                if value not in self.references:
                    self.references[value] = len(self.references)
                    added.append(value)
                return -self.references[value] - 1
            if (value_type is int or value_type is float) and field in SCALES:
                scaled = value * SCALES[field]
                if precise and field in ("x", "y"):
                    return scaled
                return round(scaled) if abs(scaled) <= 2 ** 53 - 1 else scaled
            return value

        payload = pack(message)
        return msgpack.packb([1, reset, added, payload], use_bin_type=True)


class CompactSync:
    def __init__(self):
        self.encoder = WireEncoder()
        self.previous = None
        self.revision = 0
        self.event_sequence = 0
        self.flights = {}
        self.roster = {}
        self.roster_revision = 0

    def project(self, state):
        view = {**state, "you": {key: value for key, value in state["you"].items() if key not in ("next_shot", "next_axe_attack", "last_shot_tick", "offline_since", "last_login_at", "tile", "offset")}}
        view["you"]["ambient_temperature"] = round(view["you"]["ambient_temperature"], 1)
        view["environment"] = {**state["environment"], "hour": math.floor(state["environment"]["hour"] * 60) / 60, "ambient_temperature": round(state["environment"]["ambient_temperature"], 1)}
        for name in ("players", "monsters"):
            view[name] = [{**entity, **{key: round(entity[key] * 256) / 256 for key in ("x", "y", "velocity_x", "velocity_y", "move_speed")}} for entity in state[name]]
        for player in view["players"]:
            player["temperature"] = math.floor(player["temperature"] * 10) / 10
            player.pop("hunger", None)
        flights = {}
        projectiles = []
        for projectile in state["projectiles"]:
            if projectile["kind"] in ("bullet", "durian_peel"):
                flight = self.flights.get(projectile["id"])
                if flight is None:
                    flight = {key: value for key, value in projectile.items() if key in PROJECTILE_FIELDS}
                    flight.update(x=projectile["x"], y=projectile["y"], flight_at=state["elapsed"], trajectory=True)
                if projectile["kind"] == "durian_peel":
                    flight = {**flight, "view_width": projectile["view_width"], "view_height": projectile["view_height"]}
                flights[projectile["id"]] = flight
                projectiles.append(flight)
            else:
                projectiles.append({key: value for key, value in projectile.items() if key in PROJECTILE_FIELDS})
        self.flights = flights
        view["projectiles"] = projectiles
        view["events"] = []
        view.setdefault("structure_states", [])
        return view

    def welcome(self, state):
        self.previous = self.project(state)
        self.event_sequence = state["event_sequence"]
        return self.previous

    def delta(self, state):
        view = self.project(state)
        message = state_delta(self.previous, view, self.revision, slot_deltas=True, collections=COLLECTIONS)
        message["state"]["events"] = [event for event in state["events"] if event["id"] > self.event_sequence]
        self.event_sequence = state["event_sequence"]
        self.previous = view
        self.revision += 1
        return message

    def reset_roster(self, roster):
        self.roster = {player["id"]: player for player in roster["players"]}
        return roster

    def roster_delta(self, roster):
        current = {player["id"]: player for player in roster["players"]}
        entries = []
        for identifier, player in current.items():
            if identifier not in self.roster:
                entries.append({"id": identifier, "fields": player})
            elif self.roster[identifier] != player:
                entries.append({"id": identifier, **changed_fields(self.roster[identifier], player)})
        removed = sorted(self.roster.keys() - current.keys())
        reordered = list(self.roster) != list(current)
        self.roster = current
        if not entries and not removed and not reordered:
            return None
        self.roster_revision += 1
        return {"type": "roster_delta", "base": self.roster_revision - 1, "revision": self.roster_revision, "server_time": roster["server_time"], "entries": entries, "remove": removed, **({"order": list(current)} if reordered else {})}
