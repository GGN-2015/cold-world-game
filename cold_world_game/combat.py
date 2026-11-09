import math

from .constants import AXE, BODY_RADIUS, BULLET_BLOCKERS, DEMOLITION, FOODS, GUNS
from .geometry import distance, normalized, segment_box, segment_circle, tile
from .models import Item, Projectile, identifier


class Combat:
    def update_player_attack(self, player, controls, seconds):
        item = player.inventory[player.selected]
        if not controls.held or controls.ui or item is None:
            controls.stop_attack()
            return
        if item.kind in FOODS:
            self.eat(player, controls, item, seconds)
            return
        if player.temperature < 5:
            controls.stop_attack()
            return
        if item.kind in GUNS:
            if controls.pending_shot or item.kind == "rifle":
                self.fire_gun(player, controls, item)
            controls.pending_shot = False
        elif item.kind == "axe":
            self.swing_axe(player, controls, seconds)
        else:
            controls.stop_attack()

    def fire_gun(self, player, controls, item):
        if self.elapsed + 1e-9 < player.next_shot or player.last_shot_tick == self.tick_number:
            return
        direction_x, direction_y = normalized(controls.aim_x - player.x, controls.aim_y - player.y)
        if direction_x == direction_y == 0 or not item.ammo:
            return
        self.touch()
        settings = GUNS[item.kind]
        player.next_shot = self.elapsed + settings["interval"]
        player.last_shot_tick = self.tick_number
        item.ammo -= 1
        shot = identifier()
        self.shot_hits[shot] = set()
        angle = math.atan2(direction_y, direction_x)
        self.emit_event("shot", player.id, item.kind, player.x, player.y)
        offsets = (-12, -6, 0, 6, 12) if item.kind == "shotgun" else (0,)
        for offset in offsets:
            heading = angle + math.radians(offset)
            projectile = Projectile(player.x, player.y, math.cos(heading) * settings["speed"], math.sin(heading) * settings["speed"], settings["range"], settings["damage"], player.id, shot=shot)
            self.projectiles[projectile.id] = projectile
        if item.ammo == 0:
            player.inventory[player.selected] = None
            controls.stop_attack()

    def eat(self, player, controls, item, seconds):
        point = tile(controls.aim_x), tile(controls.aim_y)
        near_fire = any(fire.kind == "campfire" and fire.lit and 1 <= abs(tile(player.x) - fire.x) + abs(tile(player.y) - fire.y) <= 3 for fire in self.structures.values())
        if player.hunger > 10 or not near_fire or self.structure_at(*point):
            controls.target = None
            controls.progress = 0
            return
        target = f"food:{item.id}:{point}"
        self.progress(controls, target, seconds)
        if controls.progress + 1e-9 >= 0.5:
            self.touch()
            player.hunger += FOODS[item.kind]
            self.emit_event("eat", player.id, item.kind, player.x, player.y)
            player.inventory[player.selected] = None
            controls.stop_attack()

    @staticmethod
    def progress(controls, target, seconds):
        if controls.target != target:
            controls.target = target
            controls.progress = 0.0
        controls.progress += seconds

    def axe_monster_target(self, controls):
        monster = self.monsters.get(controls.aim_target)
        if monster is None and controls.aim_target is None:
            monster = next((candidate for candidate in self.monsters.values() if math.hypot(candidate.x - controls.aim_x, candidate.y - controls.aim_y) <= BODY_RADIUS), None)
        return monster

    def strike_axe(self, player, controls):
        monster = self.axe_monster_target(controls)
        controls.target = None
        controls.progress = 0.0
        if monster is None or distance(player, monster) > AXE["range"] or not self.visible(player.x, player.y, monster.x, monster.y) or self.elapsed + 1e-9 < player.next_axe_attack:
            return
        self.touch()
        player.next_axe_attack = self.elapsed + AXE["interval"]
        monster.hp -= AXE["damage"]
        if monster.hp <= 0:
            self.monsters.pop(monster.id, None)

    def swing_axe(self, player, controls, seconds):
        if self.axe_monster_target(controls) is not None:
            controls.target = None
            controls.progress = 0.0
            return
        structure = self.structures.get(controls.aim_target) if controls.aim_target else self.structure_at(tile(controls.aim_x), tile(controls.aim_y))
        if structure is None or distance(player, structure) > 3 or not self.visible(player.x, player.y, structure.x, structure.y, ignore=structure.id) or self.demolition_locked(structure.id) or (structure.kind in ("chest", "campfire") and not controls.shift) or (structure.kind == "chest" and any(structure.slots)):
            controls.target = None
            controls.progress = 0
            return
        self.progress(controls, "structure:" + structure.id, seconds)
        if controls.progress + 1e-9 >= DEMOLITION[structure.kind]:
            self.touch()
            if structure.kind == "tree":
                materials = [Item.create("wood") for count in range(self.random.randint(1, 3))]
            elif structure.kind == "fence":
                materials = [Item.create("fence")]
            elif structure.kind == "campfire":
                materials = [Item.create("wood") for count in range(structure.fuel)]
                if structure.igniter:
                    materials.append(structure.igniter)
            else:
                materials = [Item.create("wood")]
            for material in materials:
                self.drop_item(material, structure.x, structure.y)
            self.remove_structure(structure)
            controls.stop_attack()

    def hurt_player(self, player, amount):
        previous = player.temperature
        previous_hunger = player.hunger
        player.temperature = max(0.0, player.temperature - amount)
        player.hunger = max(0.0, player.hunger - amount)
        if player.temperature < previous or player.hunger < previous_hunger:
            self.emit_event("hurt", player.id, "player", player.x, player.y)
        controls = self.controls[player.id]
        if player.temperature < 5:
            controls.stop_attack()
            if previous >= 5:
                controls.ghost_monsters.update(monster.id for monster in self.monsters.values() if distance(player, monster) < BODY_RADIUS * 2)
        if player.temperature <= 0:
            for monster in self.monsters.values():
                if monster.target == player.id:
                    self.clear_target(monster)

    def update_projectiles(self, seconds):
        for projectile_id, projectile in list(self.projectiles.items()):
            speed = math.hypot(projectile.velocity_x, projectile.velocity_y)
            travel = min(projectile.remaining, speed * seconds)
            end_x = projectile.x + projectile.velocity_x * travel / speed
            end_y = projectile.y + projectile.velocity_y * travel / speed
            candidates = []
            for structure in self.nearby_structures(projectile.x, projectile.y, end_x, end_y):
                if structure.kind in BULLET_BLOCKERS:
                    fraction = segment_box(projectile.x, projectile.y, end_x, end_y, structure.x, structure.y)
                    if fraction is not None:
                        candidates.append((fraction, 0, "structure", structure))
            for player_id in self.online:
                player = self.players[player_id]
                if player.temperature <= 0 or (not projectile.hostile and player_id == projectile.owner):
                    continue
                fraction = segment_circle(projectile.x, projectile.y, end_x, end_y, player.x, player.y)
                if fraction is not None:
                    candidates.append((fraction, 1, "player", player))
            if not projectile.hostile:
                for monster in self.monsters.values():
                    fraction = segment_circle(projectile.x, projectile.y, end_x, end_y, monster.x, monster.y)
                    if fraction is not None:
                        candidates.append((fraction, 2, "monster", monster))
            if candidates:
                fraction, priority, kind, target = min(candidates, key=lambda candidate: (candidate[0], candidate[1]))
                if kind == "player":
                    hit_players = self.shot_hits.setdefault(projectile.shot, set())
                    if projectile.hostile or target.id not in hit_players:
                        self.hurt_player(target, 5 if projectile.hostile else 1)
                        hit_players.add(target.id)
                elif kind == "monster":
                    target.hp -= projectile.damage
                    if target.hp <= 0:
                        self.monsters.pop(target.id, None)
                del self.projectiles[projectile_id]
            else:
                projectile.x, projectile.y = end_x, end_y
                projectile.remaining -= travel
                if projectile.remaining <= 1e-9:
                    del self.projectiles[projectile_id]
        active_shots = {projectile.shot for projectile in self.projectiles.values()}
        self.shot_hits = {shot: players for shot, players in self.shot_hits.items() if shot in active_shots}
