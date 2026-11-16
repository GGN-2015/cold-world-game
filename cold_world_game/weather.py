from collections import deque

from .biomes import LAKE_COOLING
from .constants import DRINKS
from .expansion import carried_modifier
from .geometry import tile


HEAT_RADIUS = 9
ROOM_RADIUS = 12
ROOM_AREA = 81
FLOOR_TIER_SIZE = 20
SEALED_HEAT_ZONES = (
    (16, 12, 8), (20, 14, 9), (22, 16, 10), (25, 18, 11), (28, 20, 12), (30, 22, 13),
)
OUTDOOR_HEAT_NEAR = 12
OUTDOOR_HEAT_MIDDLE = 7
OUTDOOR_HEAT_EDGE_BONUS = 2
ROOM_WALLS = frozenset({"wall", "ring_wall", "door"})
CARDINAL_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class Weather:
    def room_at(self, point):
        revision = getattr(self, "_terrain_revision", 0)
        if self._heat_room_revision != revision or len(self._heat_rooms) >= 512:
            self._heat_rooms.clear()
            self._heat_room_revision = revision
        if point not in self._heat_rooms:
            self._heat_rooms[point] = self.scan_room(point)
        return self._heat_rooms[point]

    def scan_room(self, origin):
        distances = {origin: 0}
        pending = deque([origin])
        sealed = True
        while pending:
            x, y = pending.popleft()
            steps = distances[x, y]
            if not sealed and steps >= HEAT_RADIUS:
                continue
            for dx, dy in CARDINAL_STEPS:
                point = x + dx, y + dy
                if point in distances:
                    continue
                if not self.generated(*point):
                    sealed = False
                    continue
                wall = self.structure_at(*point)
                if wall and wall.kind in ROOM_WALLS and wall.solid:
                    continue
                distances[point] = steps + 1
                pending.append(point)
                if not sealed:
                    continue
                if len(distances) > ROOM_AREA or max(abs(point[0] - origin[0]), abs(point[1] - origin[1])) > ROOM_RADIUS:
                    sealed = False
        coverage = 0
        if sealed:
            floors = eligible = 0
            for point in distances:
                surface = self.structure_at(*point)
                if surface is None or surface.kind == "floor":
                    eligible += 1
                    if surface is not None:
                        floors += 1
            if eligible:
                coverage = 100 * floors // eligible
        return sealed, {point: steps for point, steps in distances.items() if steps <= HEAT_RADIUS}, coverage

    def heating_at(self, player):
        point = tile(player.x), tile(player.y)
        sealed, distances, coverage = self.room_at(point)
        floor_tier = coverage // FLOOR_TIER_SIZE
        insulation = floor_tier * FLOOR_TIER_SIZE / 100
        outdoor = self.environment()["ambient_temperature"]
        ambient = outdoor + (3 + 2 * insulation if sealed else 0)
        nearest = min((steps for position, steps in distances.items()
                       if (fire := self.structure_at(*position)) and fire.kind in {"campfire", "fixed_heater"} and fire.lit),
                      default=HEAT_RADIUS + 1)
        tier = max(0, nearest - 1) // 3
        if nearest <= HEAT_RADIUS:
            zones = SEALED_HEAT_ZONES[floor_tier] if sealed else (OUTDOOR_HEAT_NEAR, OUTDOOR_HEAT_MIDDLE, outdoor + OUTDOOR_HEAT_EDGE_BONUS)
            ambient = max(ambient, zones[tier])
        return ambient, sealed, coverage, nearest if nearest <= HEAT_RADIUS else None

    def update_player_temperature(self, player, seconds):
        excited_seconds = min(seconds, player.excitement_remaining)
        if excited_seconds:
            self.change_body_temperature(player, DRINKS["vodka"]["felt_temperature"], excited_seconds)
            player.excitement_remaining -= excited_seconds
        if seconds > excited_seconds:
            ambient = self.actual_temperature_at(player) + carried_modifier(player, "ambient_bonus", 0.0)
            self.change_body_temperature(player, ambient, seconds - excited_seconds)
        if self.exposed_lake(player.x, player.y):
            player.temperature = max(0, player.temperature - seconds * LAKE_COOLING)
