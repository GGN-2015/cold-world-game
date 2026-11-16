"""Runtime hazards, crossing devices, and field tools for the first barrier."""

import math
from collections import deque
from itertools import chain

from .actions import GameError
from .biome_layout import BIOME_RING
from .constants import CHAIN_CHARM_CHANCE, CHUNK_SIZE, EXPLOSIVE_WEAPONS, FOG_CAMPFIRE_RADIUS, FOG_LANTERN_RADIUS, FOG_STREET_LAMP_RADIUS, FOG_VIEW_RADIUS, GUNS, MELEE_WEAPONS, MONSTER_PROJECTILE_SPEED
from .constants import HARVEST_CHAIN_LIMIT, HARVEST_CHAIN_RADIUS
from .geometry import chunk, distance, normalized, tile
from .inventory import consume_use, take_item
from .models import Item, Monster, Projectile, Structure
from .wildlife import BIOME_GUARDS, MONSTER_TYPES


SCROLLS = ("fireball_scroll", "freeze_scroll")
BIOME_DEVICES = frozenset({"cable_station", "street_lamp", "bridge_pier"})
LAKE_COOLING = .20
FOG_RADII = {"player": FOG_VIEW_RADIUS, "lantern": FOG_LANTERN_RADIUS, "campfire": FOG_CAMPFIRE_RADIUS, "street_lamp": FOG_STREET_LAMP_RADIUS}


def line_points(start, end):
    dx, dy = end[0] - start[0], end[1] - start[1]
    steps = max(1, math.ceil(max(abs(dx), abs(dy))))
    return tuple(dict.fromkeys((tile(start[0] + dx * i / steps), tile(start[1] + dy * i / steps))
                               for i in range(steps + 1)))


class Biomes:
    def biomes_at(self, x, y):
        return self.chunk_biomes((chunk(x), chunk(y)))

    def supports_lake_fire(self, surface):
        return bool(surface and (surface.kind in {"floor", "bridge_deck"} or surface.on_floor))

    def frozen_lake(self, x, y):
        return any(effect["kind"] == "ice" and self.elapsed < effect["until"]
                   and math.hypot(x - effect["x"], y - effect["y"]) <= effect["radius"]
                   for effect in self.biome_effects)

    def exposed_lake(self, x, y):
        return ("lake" in self.biomes_at(x, y)
                and not self.supports_lake_fire(self.structure_at(tile(x), tile(y)))
                and not self.frozen_lake(x, y))

    def biome_speed_scale(self, player):
        lake = self.exposed_lake(player.x, player.y)
        chilled = self.elapsed < player.chilled_until
        return .5 if lake or chilled else 1

    def biome_view(self, player, controls):
        y_radius, x_radius = min(32, controls.view_height / 2), min(37, controls.view_width / 2)
        visited = [(cx, cy, self.chunk_biomes((cx, cy)))
                   for cx in range(chunk(player.x - x_radius), chunk(player.x + x_radius) + 1)
                   for cy in range(chunk(player.y - y_radius), chunk(player.y + y_radius) + 1)]
        zones = self.biomes_at(player.x, player.y)
        fog = any("fog" in kinds for _, _, kinds in visited)
        lake = [[cx * CHUNK_SIZE, cy * CHUNK_SIZE] for cx, cy, kinds in visited if "lake" in kinds]
        effects = [entry for entry in self.biome_effects if entry["until"] > self.elapsed and
                   abs(entry["x"] - player.x) < x_radius + entry["radius"] and
                   abs(entry["y"] - player.y) < y_radius + entry["radius"]]
        view = {"zones": list(zones), "fog": fog, "lake": lake, "effects": effects}
        if fog:
            view["light_radii"] = FOG_RADII
            view["lantern"] = player.holds("lantern")
            view["other_lanterns"] = [
                {"id": other.id, "x": other.x, "y": other.y}
                for player_id in sorted(self.online)
                if player_id != player.id and (other := self.players[player_id])
                and abs(other.x - player.x) <= x_radius + FOG_LANTERN_RADIUS
                and abs(other.y - player.y) <= y_radius + FOG_LANTERN_RADIUS
                and other.holds("lantern")
            ]
        return view

    def add_biome_effect(self, kind, x, y, radius, duration):
        if len(self.biome_effects) >= 160:
            self.biome_effects.pop(0)
        self.biome_effects.append({"kind": kind, "x": x, "y": y, "radius": radius, "until": self.elapsed + duration})

    def trees_in_radius(self, x, y, radius):
        for tx in range(math.ceil(x - radius), math.floor(x + radius) + 1):
            for ty in range(math.ceil(y - radius), math.floor(y + radius) + 1):
                tree = self.structure_at(tx, ty)
                if tree and tree.kind == "tree" and math.hypot(x - tx, y - ty) <= radius:
                    yield tree

    def resolve_biome_explosion(self, projectile, settings):
        x, y = projectile.target_x, projectile.target_y
        if projectile.kind in {"freeze_scroll", "frost_bomb"}:
            self.add_biome_effect("ice", x, y, settings["radius"], 15 if projectile.kind == "freeze_scroll" else 25)
        elif projectile.kind in {"fireball_scroll", "fire_bottle"}:
            if projectile.kind == "fireball_scroll":
                points = line_points((projectile.origin_x, projectile.origin_y), (x, y))
                for light_x, light_y in points[::2]:
                    self.add_biome_effect("light", light_x, light_y, 3, 4)
            self.ignite_trees(x, y, settings["radius"], projectile.owner)
        elif projectile.kind == "flare_bomb":
            self.add_biome_effect("light", x, y, 3, 6)
        else:
            radius = settings["radius"]
            for tree in self.trees_in_radius(x, y, radius):
                if "forest" in self.biomes_at(tree.x, tree.y):
                    self.remove_structure(tree)
                    self.emit_event("break", projectile.owner, "tree", tree.x, tree.y, target=tree.id)

    def ignite_trees(self, x, y, radius, owner, *, trees=None):
        nearby = sorted(self.trees_in_radius(x, y, radius) if trees is None else trees,
                        key=lambda tree: (math.hypot(tree.x - x, tree.y - y), tree.x, tree.y))
        if not nearby:
            return
        scheduled = {entry["tree"] for entry in self.biome_fires}
        queue = deque((tree, 0) for tree in nearby)
        planned = 0
        while queue and planned < 20 and len(self.biome_fires) < 160:
            tree, depth = queue.popleft()
            if tree.id in scheduled or math.hypot(tree.x - x, tree.y - y) > radius + 3:
                continue
            planned += 1
            scheduled.add(tree.id)
            self.biome_fires.append({"tree": tree.id, "owner": owner, "at": self.elapsed + .25 * (depth + 1)})
            if depth < 3:
                for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    other = self.structure_at(tree.x + dx, tree.y + dy)
                    if other and other.kind == "tree" and other.id not in scheduled:
                        queue.append((other, depth + 1))

    def update_biome_effects(self):
        self.biome_effects = [entry for entry in self.biome_effects if entry["until"] > self.elapsed]
        due = [entry for entry in self.biome_fires if entry["at"] <= self.elapsed][:12]
        if not due:
            return
        self.touch()
        ids = {entry["tree"] for entry in due}
        self.biome_fires = [entry for entry in self.biome_fires if entry["tree"] not in ids]
        for entry in due:
            if tree := self.structures.get(entry["tree"]):
                self.remove_structure(tree)
                self.emit_event("break", entry["owner"], "tree", tree.x, tree.y, target=tree.id)

    def harvest_tree(self, tree, player, tool):
        if tool != "chain_chainsaw" and (tool != "axe" or not player.carries("chain_charm")):
            return [tree]
        stream = self.event_random("harvest-chain", tree.id)
        if tool == "axe" and stream.random() >= CHAIN_CHARM_CHANCE:
            return [tree]
        nearby = [target for target in self.trees_in_radius(tree.x, tree.y, HARVEST_CHAIN_RADIUS) if target.id != tree.id]
        return [tree, *stream.sample(nearby, min(len(nearby), HARVEST_CHAIN_LIMIT - 1))]

    def copy_scroll(self, player, controls, kind):
        if not isinstance(kind, str) or kind not in SCROLLS:
            raise GameError("invalid_item", "Select a scroll to copy")
        storages = (player.inventory, player.backpack)
        quill = next(((storage, index) for storage in storages for index, entry in enumerate(storage)
                      if entry and entry.kind == "quill" and entry.uses), None)
        paper = next(((storage, index) for storage in reversed(storages) for index, entry in enumerate(storage)
                      if entry and entry.kind == "papyrus"), None)
        if not quill or not paper or not player.carries(kind):
            raise GameError("scroll_materials", "Copying requires a quill, papyrus, and an original scroll")
        quill_storage, quill_index = quill
        paper_storage, paper_index = paper
        pen = quill_storage[quill_index]
        destination = next(((storage, index) for storage in storages for index, entry in enumerate(storage)
                            if entry is None
                            or (storage is quill_storage and index == quill_index and pen.uses == 1)
                            or (storage is paper_storage and index == paper_index and entry.count == 1)), None)
        if destination is None:
            raise GameError("inventory_full", "No room for the copied scroll")
        self.touch()
        consume_use(quill_storage, quill_index, pen)
        take_item(paper_storage, paper_index)
        storage, index = destination
        storage[index] = Item.create(kind)
        for changed_storage, changed_index in (quill, paper, destination):
            if changed_storage is player.inventory:
                self.cancel_selected(player, controls, changed_index)
        return {"output": kind}

    def linked_device(self, position, kind):
        cx, cy = chunk(position[0]), chunk(position[1])
        for x in range(cx * CHUNK_SIZE - CHUNK_SIZE // 2, cx * CHUNK_SIZE + CHUNK_SIZE // 2 + 1):
            for y in range(cy * CHUNK_SIZE - CHUNK_SIZE // 2, cy * CHUNK_SIZE + CHUNK_SIZE // 2 + 1):
                device = self.structure_at(x, y)
                if device and device.kind == kind and device.biome_anchor == position:
                    return device
        return None

    def use_cable(self, player, device):
        if player.temperature < 5 or distance(player, device) > 2 or not self.visible(player.x, player.y, device.x, device.y):
            raise GameError("out_of_range", "Stand within two tiles of the cable station")
        target = self.linked_device(device.biome_link, "cable_station")
        if not target or not target.repaired:
            raise GameError("crossing_unavailable", "The other end of this cable is unavailable")
        destination = self.return_destination(target.x, target.y)
        self.teleport_player(player, destination, "cable_station")
        return {"crossed": True}

    def crossing_endpoint(self, device):
        if device.kind in {"cable_station", "bridge_pier"}:
            self.ensure_terrain(*device.biome_link)
            other = self.linked_device(device.biome_link, device.kind)
            if not other and device.kind == "cable_station":
                raise GameError("crossing_unavailable", "The other end of this cable is unavailable")
            return other
        return None

    def finish_crossing_repair(self, device, other):
        if device.kind == "cable_station":
            self.record_structure(other.id)
            other.repaired = True
            self.invalidate_chunk(other)
        elif device.kind == "bridge_pier":
            endpoint = (other.x, other.y) if other else device.biome_link
            for x, y in line_points((device.x, device.y), endpoint):
                if not self.structure_at(x, y):
                    self.add_structure(Structure("bridge_deck", x, y))
        self.invalidate_chunk(device)

    def reveal_guards(self, player):
        previous = self.controls[player.id].next_biome_scan
        if self.elapsed < previous:
            return
        self.controls[player.id].next_biome_scan = self.elapsed + .35
        px, py = tile(player.x), tile(player.y)
        guards_enabled = "guard" in BIOME_RING["kinds"]
        if not any("forest" in kinds or (guards_enabled and "guard" in kinds)
                   for cx in range(chunk(px - 17), chunk(px + 17) + 1)
                   for cy in range(chunk(py - 17), chunk(py + 17) + 1)
                   if (kinds := self.chunk_biomes((cx, cy)))):
            return
        for x in range(px - 17, px + 18):
            for y in range(py - 17, py + 18):
                structure = self.structure_at(x, y)
                if not structure or not structure.biome_guard:
                    continue
                species = structure.biome_guard
                if species != "tree_spirit" and not guards_enabled:
                    continue
                if distance(player, structure) > (3 if species == "tree_spirit" else 17):
                    continue
                self.touch()
                self.remove_structure(structure)
                identifier = "biome:" + structure.id
                self.monsters[identifier] = Monster(x, y, id=identifier, species=species, hp=MONSTER_TYPES[species]["hp"])

    def near_guard_light(self, monster, players):
        if any(distance(monster, player) <= 6 and player.holds("lantern") for player in players):
            return True
        if any(effect["kind"] == "light" and self.elapsed < effect["until"] and
               math.hypot(monster.x - effect["x"], monster.y - effect["y"]) <= effect["radius"]
               for effect in self.biome_effects):
            return True
        x, y = tile(monster.x), tile(monster.y)
        for tx in range(x - 10, x + 11):
            for ty in range(y - 10, y + 11):
                source = self.structure_at(tx, ty)
                if source and ((source.kind == "street_lamp" and source.repaired and distance(monster, source) <= 10)
                               or (source.lit and distance(monster, source) <= 3.5)):
                    return True
        return False

    def update_biome_guards(self):
        players = [self.players[player_id] for player_id in sorted(self.online) if self.players[player_id].temperature >= 5]
        for player in players:
            self.reveal_guards(player)
            self.spawn_fog_monster(player)
        for monster in self.monsters.values():
            if monster.kind not in BIOME_GUARDS:
                continue
            target = min((player for player in players if distance(monster, player) <= 13
                          and self.visible(monster.x, monster.y, player.x, player.y)),
                         key=lambda player: distance(monster, player), default=None)
            if not target:
                continue
            if monster.kind == "frost_guard" and self.elapsed >= monster.next_light_daze:
                dazed = self.near_guard_light(monster, players)
                monster.next_light_daze = self.elapsed + (7 if dazed else .5)
                if dazed:
                    monster.dazed_until = self.elapsed + 2.5
                    self.emit_event("hit", target.id, "lantern", monster.x, monster.y, target=monster.id, target_type="monster")
            if self.elapsed < max(monster.next_attack, monster.dazed_until, monster.frozen_until):
                continue
            dx, dy = normalized(target.x - monster.x, target.y - monster.y)
            weapon = BIOME_GUARDS[monster.kind]
            shot = Projectile(monster.x, monster.y, dx * MONSTER_PROJECTILE_SPEED, dy * MONSTER_PROJECTILE_SPEED,
                              0, MONSTER_TYPES[monster.kind]["damage"], monster.id, hostile=True, weapon_kind=weapon,
                              origin_x=monster.x, origin_y=monster.y, spawned_at=self.elapsed, range_player=target.id)
            shot.remaining = self.projectile_range(shot)
            self.projectiles[shot.id] = shot
            self.emit_event("shot", monster.id, weapon, monster.x, monster.y, direction=[dx, dy])
            monster.next_attack = self.elapsed + MONSTER_TYPES[monster.kind]["interval"]

    def spawn_fog_monster(self, player):
        controls = self.controls[player.id]
        if self.elapsed < controls.next_fog_spawn or "fog" not in self.biomes_at(player.x, player.y):
            return
        controls.next_fog_spawn = self.elapsed + 3
        if sum(monster.id.startswith("fog:") and distance(monster, player) < 20 for monster in self.monsters.values()) >= 4:
            return
        stream = self.event_random("fog-mob", player.id)
        for _ in range(4):
            angle, radius = stream.uniform(0, math.tau), stream.uniform(8, 15)
            x, y = player.x + math.cos(angle) * radius, player.y + math.sin(angle) * radius
            if "fog" in self.biomes_at(x, y) and self.can_stand(x, y, monster_id="spawning"):
                identifier = f"fog:{player.id}:{self.tick_number}"
                self.monsters[identifier] = Monster(x, y, id=identifier, species="stalker", hp=MONSTER_TYPES["stalker"]["hp"])
                return

    def biome_guard_damage(self, monster, kind, amount):
        if monster.kind not in BIOME_GUARDS:
            return amount
        settings = MELEE_WEAPONS.get(kind) or EXPLOSIVE_WEAPONS.get(kind) or GUNS.get(kind) or {}
        if ((monster.kind == "frost_guard" and (kind == "burn" or "burn_duration" in settings))
                or (monster.kind == "ember_guard" and "freeze_duration" in settings)):
            return amount * 2
        return amount

    def biome_projectile_hit(self, target, projectile):
        if projectile.weapon_kind == "ice_beam":
            insulated = target.carries("heat_patch") or target.carries("down_coat") or target.carries("wool_scarf")
            target.chilled_until = max(target.chilled_until, self.elapsed + (1 if insulated else 3))
        elif projectile.weapon_kind == "ember_shot":
            if self.elapsed >= target.scorched_until:
                target.next_scorch = self.elapsed + 1
            target.scorched_until = self.elapsed + 4
