import heapq
import math
import time
from collections import deque
from functools import lru_cache

from .constants import BODY_RADIUS, CHUNK_SIZE, KNOCKBACK, MONSTER_DEMOLITION, MONSTER_LIMIT, MONSTER_PROJECTILE_SPEED, MONSTER_SPAWN_CHANCES, NIGHT_MONSTER_HOURS, SOLID
from .geometry import DIRECTIONS, distance, normalized, tile
from .models import Monster, Projectile


PATH_STEPS = tuple((offset_x, offset_y, math.hypot(offset_x, offset_y)) for offset_x, offset_y in DIRECTIONS)
PATH_PLANS_PER_TICK = 8
PATH_TIME_BUDGET = 0.008


class Monsters:
    @staticmethod
    def allows_player_overlap(monster, player_id):
        return player_id is not None and not monster.big and monster.target == player_id and monster.overlap_player == player_id

    def demolition_locked(self, structure_id):
        return any(monster.demolition == structure_id for monster in self.monsters.values())

    @staticmethod
    def clear_target(monster):
        monster.target = None
        monster.overlap_player = None
        monster.path = []
        monster.demolition = None
        monster.demolition_progress = 0.0
        monster.next_demolition_feedback = 0.0
        monster.next_plan = 0.0

    def monster_spawn_chances(self):
        hour = self.environment()["hour"]
        start, end = NIGHT_MONSTER_HOURS
        return MONSTER_SPAWN_CHANCES["night" if hour >= start or hour < end else "day"]

    def spawn_monster(self):
        if len(self.monsters) >= MONSTER_LIMIT:
            return
        player = self.players[self.random.choice(sorted(self.online))]
        angle = self.random.uniform(0, math.tau)
        radius = math.sqrt(self.random.uniform(20 ** 2, 120 ** 2))
        position_x = player.x + math.cos(angle) * radius
        position_y = player.y + math.sin(angle) * radius
        if not self.generated(position_x, position_y) or self.structure_at(tile(position_x), tile(position_y)):
            return
        if any(math.hypot(position_x - self.players[player_id].x, position_y - self.players[player_id].y) < 20 for player_id in self.online):
            return
        if not self.can_stand(position_x, position_y, monster_id="spawning"):
            return
        chances = self.monster_spawn_chances()
        roll = self.random.random()
        big = roll < chances["big"]
        fast = not big and roll < chances["big"] + chances["fast"]
        monster = Monster(position_x, position_y, big=big, fast=fast, hp=50 if big else 10)
        self.monsters[monster.id] = monster

    def update_monsters(self, seconds):
        deadline = time.perf_counter() + PATH_TIME_BUDGET
        self.advance_paths(deadline)
        standing_players = {player_id: self.players[player_id] for player_id in self.online if self.players[player_id].temperature >= 5}
        identifiers = list(self.monsters)
        cursor = getattr(self, "_path_cursor", None)
        if cursor in self.monsters:
            pivot = identifiers.index(cursor) + 1
            identifiers = identifiers[pivot:] + identifiers[:pivot]
        due = [identifier for identifier in identifiers if identifier not in self._path_jobs and self.monsters[identifier].next_plan <= self.elapsed and (self.monsters[identifier].target in standing_players or any(distance(self.monsters[identifier], player) <= 32 for player in standing_players.values()))]
        planning = set(due[:PATH_PLANS_PER_TICK])
        if planning:
            self._path_cursor = due[min(len(due), PATH_PLANS_PER_TICK) - 1]
        for monster_id, monster in list(self.monsters.items()):
            if all(distance(monster, self.players[player_id]) > 120 for player_id in self.online):
                del self.monsters[monster_id]
                continue
            target = standing_players.get(monster.target)
            if target is None or target.temperature < 5 or distance(monster, target) > 40:
                self.clear_target(monster)
                target = None
            can_see = target is not None and self.visible(monster.x, monster.y, target.x, target.y)
            if can_see:
                monster.seen_x, monster.seen_y = target.x, target.y
                monster.last_seen = self.elapsed
            elif target is not None and self.elapsed - monster.last_seen >= 8:
                self.clear_target(monster)
                target = None
            if target is None:
                candidates = [player for player in standing_players.values() if player.temperature >= 5 and distance(monster, player) <= 32 and self.visible(monster.x, monster.y, player.x, player.y)]
                if candidates:
                    target = min(candidates, key=lambda player: (distance(monster, player), player.id))
                    monster.target = target.id
                    monster.seen_x, monster.seen_y = target.x, target.y
                    monster.last_seen = self.elapsed
                    can_see = True
            if target is None:
                self.wander(monster, seconds)
                continue
            if monster.big or monster.overlap_player != target.id or distance(monster, target) > 1 + KNOCKBACK["monster_melee"] + 1e-9:
                monster.overlap_player = None
            if monster.demolition:
                structure = self.structures.get(monster.demolition)
                if structure and distance(monster, structure) <= 1 + 1e-9:
                    self.demolish(monster, structure, seconds)
                    continue
                monster.demolition = None
                monster.demolition_progress = 0.0
                monster.next_plan = 0
            separation = distance(monster, target)
            if can_see and separation <= 1:
                if self.elapsed + 1e-9 >= monster.next_attack:
                    previous_x, previous_y = target.x, target.y
                    self.emit_event("melee", monster.id, "monster_big" if monster.big else "monster_fast" if monster.fast else "monster", monster.x, monster.y, target=target.id, target_x=target.x, target_y=target.y)
                    self.hurt_player(target, 2 if monster.big else 1, source=monster.id, direction=(target.x - monster.x, target.y - monster.y), knockback=KNOCKBACK["monster_big_melee" if monster.big else "monster_melee"])
                    monster.next_attack = self.elapsed + (1.5 if monster.big else 1)
                    if not monster.big and target.temperature >= 5:
                        displacement = math.hypot(target.x - previous_x, target.y - previous_y)
                        if displacement + 1e-6 < KNOCKBACK["monster_melee"]:
                            monster.overlap_player = target.id
                        elif distance(monster, target) >= BODY_RADIUS * 2:
                            monster.overlap_player = None
                if target.temperature < 5 or not self.allows_player_overlap(monster, target.id):
                    continue
            if monster.big and can_see and 1 < separation <= 12 and self.elapsed + 1e-9 >= monster.next_attack:
                direction_x, direction_y = normalized(target.x - monster.x, target.y - monster.y)
                projectile = Projectile(monster.x, monster.y, direction_x * MONSTER_PROJECTILE_SPEED, direction_y * MONSTER_PROJECTILE_SPEED, 0, 5, monster.id, hostile=True, origin_x=monster.x, origin_y=monster.y, spawned_at=self.elapsed, range_player=target.id)
                projectile.remaining = self.projectile_range(projectile)
                self.projectiles[projectile.id] = projectile
                self.emit_event("shot", monster.id, "monster", monster.x, monster.y, direction=[direction_x, direction_y])
                monster.next_attack = self.elapsed + 2
            if self.elapsed >= monster.next_plan and monster.id in planning:
                revision = getattr(self, "_terrain_revision", 0), len(self.chunks)
                self._path_jobs[monster.id] = monster, monster.target, (tile(monster.x), tile(monster.y)), revision, self.search_monster_path(monster)
                self._path_queue.append(monster.id)
                self.advance_paths(deadline)
            self.follow_path(monster, seconds)

    def search_monster_path(self, monster):
        path, reached = yield from self.search_path(monster, False)
        if monster.big and not reached:
            path, reached = yield from self.search_path(monster, True)
        return path

    def advance_paths(self, deadline):
        while self._path_queue and time.perf_counter() < deadline:
            identifier = self._path_queue.popleft()
            job = self._path_jobs.get(identifier)
            if job is None:
                continue
            monster, target_id, start, revision, search = job
            target = self.players.get(target_id)
            if self.monsters.get(identifier) is not monster or monster.demolition is not None or monster.target != target_id or target_id not in self.online or target is None or target.temperature < 5 or start != (tile(monster.x), tile(monster.y)) or revision != (getattr(self, "_terrain_revision", 0), len(self.chunks)):
                self._path_jobs.pop(identifier, None)
                continue
            try:
                next(search)
            except StopIteration as completed:
                monster.path = completed.value
                monster.next_plan = self.elapsed + 0.5
                self._path_jobs.pop(identifier, None)
            else:
                self._path_queue.append(identifier)

    def demolish(self, monster, structure, seconds):
        if monster.demolition != structure.id:
            monster.demolition = structure.id
            monster.demolition_progress = 0.0
            monster.next_demolition_feedback = 0.0
        for controls in self.controls.values():
            if controls.target == "structure:" + structure.id:
                controls.target = None
                controls.progress = 0.0
        monster.demolition_progress += seconds
        if self.elapsed + 1e-9 >= monster.next_demolition_feedback:
            self.emit_event("chop", monster.id, "monster", monster.x, monster.y, target=structure.id, target_x=structure.x, target_y=structure.y)
            monster.next_demolition_feedback = self.elapsed + 0.3
        if monster.demolition_progress + 1e-9 >= MONSTER_DEMOLITION[structure.kind]:
            self.touch()
            self.emit_event("break", monster.id, structure.kind, structure.x, structure.y, target=structure.id)
            self.remove_structure(structure)
            monster.demolition = None
            monster.demolition_progress = 0.0
            monster.path = []
            monster.next_plan = 0

    def follow_path(self, monster, seconds):
        remaining = monster.speed * seconds
        while remaining > 1e-9:
            while monster.path and math.hypot(monster.path[0][0] - monster.x, monster.path[0][1] - monster.y) < 1e-9:
                monster.path.pop(0)
            closing = not monster.big and (tile(monster.x), tile(monster.y)) == (tile(monster.seen_x), tile(monster.seen_y))
            if closing:
                point_x, point_y = monster.seen_x, monster.seen_y
            elif monster.path:
                point_x, point_y = monster.path[0]
            else:
                return
            structure = self.structure_at(tile(point_x), tile(point_y))
            blocked = structure is not None and structure.kind in SOLID
            separation = math.hypot(point_x - monster.x, point_y - monster.y)
            if blocked:
                if monster.big and structure.kind in MONSTER_DEMOLITION:
                    if separation <= 1 + 1e-9:
                        self.demolish(monster, structure, remaining / monster.speed)
                        return
                    travel = min(remaining, max(0, separation - 0.95))
                else:
                    monster.next_plan = 0
                    return
            else:
                travel = min(remaining, max(0, separation - 0.05) if closing else separation)
            if travel <= 1e-9:
                return
            direction_x, direction_y = normalized(point_x - monster.x, point_y - monster.y)
            previous_x, previous_y = monster.x, monster.y
            if not self.move_body(monster, direction_x * travel, direction_y * travel, monster_id=monster.id):
                monster.next_plan = 0
                return
            remaining -= travel
            if closing or blocked or math.hypot(monster.x - previous_x - direction_x * travel, monster.y - previous_y - direction_y * travel) > 1e-9:
                return

    def find_path(self, monster, allow_demolition):
        search = self.search_path(monster, allow_demolition)
        while True:
            try:
                next(search)
            except StopIteration as completed:
                return completed.value

    def search_path(self, monster, allow_demolition):
        start = tile(monster.x), tile(monster.y)
        goal_x, goal_y = monster.seen_x, monster.seen_y
        occupied = set()
        bodies = [other for other in self.monsters.values() if other.id != monster.id]
        bodies.extend(self.players[player_id] for player_id in self.online if self.players[player_id].temperature >= 5 and (monster.big or player_id != monster.target) and monster.id not in self.controls[player_id].ghost_monsters)
        for body in bodies:
            for point_x in range(tile(body.x) - 1, tile(body.x) + 2):
                for point_y in range(tile(body.y) - 1, tile(body.y) + 2):
                    if math.hypot(point_x - body.x, point_y - body.y) < BODY_RADIUS * 2:
                        occupied.add((point_x, point_y))
        occupied.discard(start)

        @lru_cache(maxsize=None)
        def cell_cost(point, breakable):
            point_chunk = (point[0] + CHUNK_SIZE // 2) // CHUNK_SIZE, (point[1] + CHUNK_SIZE // 2) // CHUNK_SIZE
            if abs(point[0] - start[0]) > 48 or abs(point[1] - start[1]) > 48 or point in occupied or point_chunk not in self.chunks:
                return None
            structure = self.structure_at(*point)
            if structure and structure.kind in SOLID:
                return MONSTER_DEMOLITION[structure.kind] if breakable and structure.kind in MONSTER_DEMOLITION else None
            return 0.0

        def neighbors(current):
            for offset_x, offset_y, movement_cost in PATH_STEPS:
                neighbor = current[0] + offset_x, current[1] + offset_y
                extra = cell_cost(neighbor, allow_demolition)
                if extra is None:
                    continue
                if offset_x and offset_y and (cell_cost((current[0] + offset_x, current[1]), False) is None or cell_cost((current[0], current[1] + offset_y), False) is None):
                    continue
                yield neighbor, movement_cost / monster.speed + extra

        goals = set()
        goal_cells = [(point_x, point_y) for point_x in range(tile(goal_x) - 1, tile(goal_x) + 2) for point_y in range(tile(goal_y) - 1, tile(goal_y) + 2)] if monster.big else [(tile(goal_x), tile(goal_y))]
        for point_x, point_y in goal_cells:
            structure = self.structure_at(point_x, point_y)
            ignored = structure.id if allow_demolition and structure and structure.kind in MONSTER_DEMOLITION else None
            if math.hypot(point_x - goal_x, point_y - goal_y) <= 1 + 1e-9 and cell_cost((point_x, point_y), allow_demolition) is not None and self.visible(point_x, point_y, goal_x, goal_y, ignore=ignored):
                goals.add((point_x, point_y))
        if start in goals:
            return [], True
        if not any(neighbors(start)):
            return [], False

        def travel_distance(point, goal):
            horizontal, vertical = abs(point[0] - goal[0]), abs(point[1] - goal[1])
            return horizontal + vertical + (math.sqrt(2) - 2) * min(horizontal, vertical)

        shortest = min((travel_distance(start, goal) for goal in goals), default=math.inf)
        for goal in sorted(goals):
            if travel_distance(start, goal) > shortest + 1e-9:
                continue
            current = start
            direct = []
            while current != goal:
                offset_x = (goal[0] > current[0]) - (goal[0] < current[0])
                offset_y = (goal[1] > current[1]) - (goal[1] < current[1])
                neighbor = current[0] + offset_x, current[1] + offset_y
                if cell_cost(neighbor, allow_demolition) != 0 or (offset_x and offset_y and (cell_cost((current[0] + offset_x, current[1]), False) is None or cell_cost((current[0], current[1] + offset_y), False) is None)):
                    break
                direct.append(neighbor)
                current = neighbor
            else:
                return direct, True
        fallback = False
        if not allow_demolition:
            region, frontier = set(goals), deque(goals)
            examined = 0
            while frontier and len(region) <= 256 and start not in region:
                examined += 1
                if examined % 32 == 0:
                    yield
                current = frontier.popleft()
                for neighbor, cost in neighbors(current):
                    if neighbor not in region:
                        region.add(neighbor)
                        frontier.append(neighbor)
            if not frontier and start not in region:
                fallback = True
                candidates = []
                examined = 0
                for radius in range(1, 49):
                    for offset_x in range(-radius, radius + 1):
                        for offset_y in range(-radius, radius + 1):
                            examined += 1
                            if examined % 128 == 0:
                                yield
                            if max(abs(offset_x), abs(offset_y)) != radius:
                                continue
                            point = tile(goal_x) + offset_x, tile(goal_y) + offset_y
                            if point not in region and cell_cost(point, allow_demolition) is not None:
                                candidates.append(point)
                    if candidates:
                        closest_radius = min(math.hypot(point[0] - goal_x, point[1] - goal_y) for point in candidates)
                        goals = {point for point in candidates if math.hypot(point[0] - goal_x, point[1] - goal_y) <= closest_radius + 1e-9}
                        break
        if not goals:
            return [], False
        goal_radius = max(math.hypot(point[0] - goal_x, point[1] - goal_y) for point in goals)

        def heuristic(point):
            return min(travel_distance(point, goal) for goal in goals) / monster.speed

        def remaining_distance(point):
            return max(0, math.hypot(point[0] - goal_x, point[1] - goal_y) - goal_radius) / monster.speed

        pending = [(heuristic(start), 0, start)]
        costs, parents = {start: 0.0}, {}
        closest, closest_distance = start, remaining_distance(start)
        visited = set()
        reached = False
        while pending and len(visited) < 4096:
            if len(visited) % 32 == 0:
                yield
            estimate, order, current = heapq.heappop(pending)
            if current in visited:
                continue
            visited.add(current)
            remaining = remaining_distance(current)
            if remaining < closest_distance:
                closest, closest_distance = current, remaining
            if current in goals:
                closest, reached = current, not fallback
                break
            for neighbor, movement_cost in neighbors(current):
                candidate = costs[current] + movement_cost
                if candidate < costs.get(neighbor, math.inf):
                    costs[neighbor] = candidate
                    parents[neighbor] = current
                    heapq.heappush(pending, (candidate + heuristic(neighbor), len(parents), neighbor))
        path = []
        while closest != start:
            path.append(closest)
            closest = parents[closest]
        path.reverse()
        return path, reached

    def wander(self, monster, seconds):
        selected = False
        if self.elapsed >= monster.next_wander:
            self.choose_wander(monster, seconds)
            selected = True
        if not (monster.wander_x or monster.wander_y):
            return
        moved = self.move_body(monster, monster.wander_x * monster.speed * seconds, monster.wander_y * monster.speed * seconds, monster_id=monster.id)
        if not moved and not selected:
            self.choose_wander(monster, seconds)
            self.move_body(monster, monster.wander_x * monster.speed * seconds, monster.wander_y * monster.speed * seconds, monster_id=monster.id)

    def choose_wander(self, monster, seconds):
        candidates, weights = [], []
        players = [self.players[player_id] for player_id in sorted(self.online) if self.players[player_id].temperature >= 5]
        nearest = min(players, key=lambda player: distance(monster, player)) if players else None
        step = min(0.3, monster.speed * seconds)
        for offset_x, offset_y in DIRECTIONS:
            direction_x, direction_y = normalized(offset_x, offset_y)
            if self.can_stand(monster.x + direction_x * step, monster.y + direction_y * step, monster_id=monster.id):
                candidates.append((direction_x, direction_y))
                toward = nearest is not None and direction_x * (nearest.x - monster.x) + direction_y * (nearest.y - monster.y) > 0
                weights.append(1.2 if toward else 1.0)
        monster.wander_x, monster.wander_y = self.random.choices(candidates, weights)[0] if candidates else (0.0, 0.0)
        monster.next_wander = self.elapsed + 2
