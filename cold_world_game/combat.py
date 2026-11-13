import math

from .constants import BODY_RADIUS, BULLET_BLOCKERS, DEMOLITION, DRINKS, EXPLOSIVE_WEAPONS, FLAME_STAFF, FOODS, GUNS, HARVEST_TOOLS, HEALING_ITEMS, KNOCKBACK, MELEE_WEAPONS, MONSTER_BULLET_BLOCKERS, MONSTER_COIN_DROPS, PANEL_DEMOLITION, PASSIVE_ITEMS, PROJECTILE_RANGE, READY_TO_EAT_FOODS, RETURN_ITEMS, REVIVAL_ITEMS, SMALL_MONSTER_FOOD_CHANCE, SMALL_MONSTER_FOOD_WEIGHTS
from .expansion import carried_modifier
from .geometry import distance, normalized, segment_box, segment_circle, tile
from .models import Item, Projectile, identifier
from .missiles import homing_position


class Combat:
    def update_player_attack(self, player, controls, seconds):
        seat = self.seated_structure(controls)
        if seat and seat.kind == "mounted_gun":
            self.fire_mounted_gun(player, controls, seat)
            return
        item = player.inventory[player.selected]
        if not controls.held or item is None or (item.uses is not None and item.uses <= 0):
            controls.stop_attack()
            return
        if controls.demolition_container:
            structure = self.structures.get(controls.demolition_container)
            if not controls.ui or controls.container != controls.demolition_container or structure is None or structure.kind not in PANEL_DEMOLITION or distance(player, structure) > 2 or player.temperature < 5 or item.kind not in HARVEST_TOOLS:
                controls.stop_attack()
                return
            self.dismantle_structure(player, controls, structure, seconds)
            return
        if controls.ui:
            controls.stop_attack()
            return
        if item.kind in REVIVAL_ITEMS:
            self.use_revival_item(player, controls, item, seconds)
            return
        if item.kind in HEALING_ITEMS:
            self.use_healing_item(player, controls, item, seconds)
            return
        if item.kind in DRINKS:
            self.use_drink(player, controls, item, seconds)
            return
        if item.kind in RETURN_ITEMS:
            self.use_return_item(player, controls, item, seconds)
            return
        if item.kind in FOODS:
            self.eat(player, controls, item, seconds)
            return
        if player.temperature < 5:
            controls.stop_attack()
            return
        if item.kind in EXPLOSIVE_WEAPONS:
            self.use_explosive(player, controls, item, seconds)
        elif item.kind in GUNS:
            if controls.pending_shot or item.kind == "rifle" or GUNS[item.kind].get("automatic", False):
                self.fire_gun(player, controls, item)
            controls.pending_shot = False
        elif item.kind in HARVEST_TOOLS:
            self.swing_axe(player, controls, seconds)
        elif item.kind in MELEE_WEAPONS:
            controls.target = None
            controls.progress = 0.0
        else:
            controls.stop_attack()

    def homing_targets(self, player):
        return self.monsters.values()

    def fire_gun(self, player, controls, item):
        if self.elapsed + 1e-9 < player.next_shot or player.last_shot_tick == self.tick_number:
            return
        direction_x, direction_y = normalized(controls.aim_x - player.x, controls.aim_y - player.y)
        target = None
        if item.kind == "homing_missile":
            target = min((monster for monster in self.homing_targets(player) if monster.hp > 0), key=lambda monster: ((monster.x - player.x) ** 2 + (monster.y - player.y) ** 2, monster.id), default=None)
            if target is None:
                return
            if direction_x == direction_y == 0:
                direction_x, direction_y = normalized(target.x - player.x, target.y - player.y)
                if direction_x == direction_y == 0:
                    direction_x = 1.0
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
        self.emit_event("shot", player.id, item.kind, player.x, player.y, direction=[direction_x, direction_y])
        pellets = settings.get("pellets", 5 if item.kind == "shotgun" else 1)
        spread = settings.get("spread", 12 if item.kind == "shotgun" else 0)
        offsets = tuple(-spread + 2 * spread * index / (pellets - 1) for index in range(pellets)) if pellets > 1 else (0,)
        for offset in offsets:
            heading = angle + math.radians(offset)
            projectile = Projectile(player.x, player.y, math.cos(heading) * settings["speed"], math.sin(heading) * settings["speed"], 0, settings["damage"], player.id, shot=shot, origin_x=player.x, origin_y=player.y, spawned_at=self.elapsed, range_player=player.id)
            projectile.weapon_kind = item.kind
            if target is not None:
                projectile.kind = "homing_missile"
                projectile.target_id = target.id
                projectile.target_x, projectile.target_y = target.x, target.y
                projectile.range_player = None
                projectile.detonates_at = self.elapsed + max(0.45, distance(player, target) / settings["speed"] + settings["launch_duration"])
            else:
                projectile.remaining = self.projectile_range(projectile)
            self.projectiles[projectile.id] = projectile
        if item.ammo == 0:
            if player.inventory[player.selected] is item:
                player.inventory[player.selected] = None
            controls.stop_attack()

    def eat(self, player, controls, item, seconds):
        point = tile(controls.aim_x), tile(controls.aim_y)
        fire_requirement_met = item.kind in READY_TO_EAT_FOODS or any(fire.lit and 1 <= abs(tile(player.x) - fire.x) + abs(tile(player.y) - fire.y) <= 3 for fire in self._campfires.values())
        if player.hunger > 10 or not fire_requirement_met or self.structure_at(*point):
            controls.target = None
            controls.progress = 0
            return
        target = f"food:{item.id}:{point}"
        self.progress(controls, target, seconds)
        if controls.progress + 1e-9 >= 0.5:
            self.touch()
            player.hunger += FOODS[item.kind]
            self.emit_event("eat", player.id, item.kind, player.x, player.y)
            player.inventory[player.selected] = Item.create("durian_peel") if item.kind == "durian" else None
            controls.stop_attack()

    def use_drink(self, player, controls, item, seconds):
        settings = DRINKS[item.kind]
        self.progress(controls, f"drink:{item.id}", seconds)
        if controls.progress + 1e-9 < settings["duration"]:
            return
        self.touch()
        player.excitement_remaining = settings["effect_duration"]
        player.inventory[player.selected] = None
        self.emit_event("eat", player.id, item.kind, player.x, player.y)
        controls.stop_attack()

    def use_explosive(self, player, controls, item, seconds):
        settings = EXPLOSIVE_WEAPONS[item.kind]
        if player.money < settings["coin_cost"]:
            controls.stop_attack()
            return
        if not self.generated(controls.aim_x, controls.aim_y) or math.hypot(controls.aim_x - player.x, controls.aim_y - player.y) > math.hypot(controls.view_width, controls.view_height) / 2 + 1e-9:
            controls.target = None
            controls.progress = 0.0
            return
        self.progress(controls, f"explosive:{item.id}", seconds)
        controls.progress = min(settings["duration"], controls.progress)
        if controls.progress + 1e-9 < settings["duration"] or self.elapsed + 1e-9 < player.next_shot or player.last_shot_tick == self.tick_number:
            return
        self.touch()
        player.money -= settings["coin_cost"]
        player.next_shot = self.elapsed + settings["interval"]
        player.last_shot_tick = self.tick_number
        projectile = Projectile(player.x, player.y, 0.0, 0.0, 0.0, settings["damage"], player.id, kind=item.kind, origin_x=player.x, origin_y=player.y, spawned_at=self.elapsed, target_x=controls.aim_x, target_y=controls.aim_y, detonates_at=self.elapsed + settings["flight_duration"])
        self.projectiles[projectile.id] = projectile
        self.emit_event("throw", player.id, item.kind, player.x, player.y, target_x=projectile.target_x, target_y=projectile.target_y)
        controls.progress = 0.0
        if settings["coin_cost"] == 0:
            player.inventory[player.selected] = None
            controls.stop_attack()

    def explode(self, projectile):
        settings = EXPLOSIVE_WEAPONS[projectile.kind]
        targets = [monster for monster in self.monsters.values() if (monster.x - projectile.target_x) ** 2 + (monster.y - projectile.target_y) ** 2 <= settings["radius"] ** 2 + 1e-9]
        self.touch()
        self.emit_event("explosion", projectile.owner, projectile.kind, projectile.target_x, projectile.target_y, radius=settings["radius"], damage=projectile.damage)
        for monster in targets:
            self.apply_weapon_status(monster, settings, projectile.owner)
            self.hurt_monster(monster, projectile.damage, projectile.owner, projectile.kind, (0.0, 0.0), knockback=False, feedback=False)
        self.projectiles.pop(projectile.id, None)

    def update_burning(self):
        for monster in list(self.monsters.values()):
            if monster.next_burn <= 0 or monster.next_burn > min(self.elapsed, monster.burning_until) + 1e-9:
                continue
            self.touch()
            while monster.id in self.monsters and monster.next_burn <= min(self.elapsed, monster.burning_until) + 1e-9:
                monster.next_burn += FLAME_STAFF["burn_interval"]
                self.hurt_monster(monster, FLAME_STAFF["burn_damage"], monster.burn_owner, "burn", (0.0, 0.0), knockback=False, feedback=False)
            if monster.next_burn > monster.burning_until + 1e-9:
                monster.next_burn = 0.0

    def restore_player(self, player, temperature=36.0, hunger=10.0):
        controls = self.controls.get(player.id)
        if controls:
            if player.temperature < 5:
                controls.movement_epoch += 1
            controls.stop_attack()
        player.temperature = temperature
        player.hunger = max(player.hunger, hunger)

    def use_revival_item(self, player, controls, item, seconds):
        settings = REVIVAL_ITEMS[item.kind]
        candidates = [self.players[other_id] for other_id in self.online if other_id != player.id and self.players[other_id].temperature < 5 and math.hypot(self.players[other_id].x - controls.aim_x, self.players[other_id].y - controls.aim_y) <= 0.75]
        target = next((other for other in candidates if other.id == controls.aim_target), None)
        if target is None and candidates:
            target = min(candidates, key=lambda other: (math.hypot(other.x - controls.aim_x, other.y - controls.aim_y), other.id))
        if target is None or distance(player, target) > settings["range"] or not self.visible(player.x, player.y, target.x, target.y):
            controls.target = None
            controls.progress = 0.0
            return
        self.progress(controls, f"revive:{item.id}:{target.id}", seconds)
        if controls.progress + 1e-9 < settings["duration"]:
            return
        self.touch()
        self.restore_player(target, settings["temperature"], settings["hunger"])
        player.inventory[player.selected] = None
        self.emit_event("heal", target.id, item.kind, target.x, target.y, source=player.id)
        controls.stop_attack()

    def use_healing_item(self, player, controls, item, seconds):
        settings = HEALING_ITEMS[item.kind]
        self.progress(controls, f"heal:{item.id}", seconds)
        if controls.progress + 1e-9 < settings["duration"]:
            return
        supplies = settings.get("supplies", {})
        if sum(storage.count(None) for storage in (player.backpack, player.inventory)) + 1 < sum(supplies.values()):
            controls.stop_attack()
            return
        self.touch()
        previous = player.temperature
        if "temperature" in settings:
            player.temperature = settings["temperature"]
        elif "temperature_delta" in settings:
            player.temperature = min(36.0, player.temperature + settings["temperature_delta"])
        if "hunger" in settings:
            player.hunger = max(player.hunger, settings["hunger"])
        elif "hunger_delta" in settings:
            player.hunger = max(player.hunger, min(10.0, player.hunger + settings["hunger_delta"]))
        if previous < 5 <= player.temperature:
            controls.movement_epoch += 1
        if item.uses is not None:
            item.uses -= 1
        if item.uses is None or item.uses <= 0:
            player.inventory[player.selected] = None
        for kind, count in supplies.items():
            for index in range(count):
                storage = player.backpack if None in player.backpack else player.inventory
                storage[storage.index(None)] = Item.create(kind)
        self.emit_event("unpack" if supplies else "heal", player.id, item.kind, player.x, player.y)
        controls.stop_attack()

    def use_return_item(self, player, controls, item, seconds):
        if not item.uses or item.uses < 0:
            controls.stop_attack()
            return
        self.progress(controls, f"return:{item.id}", seconds)
        if controls.progress + 1e-9 < RETURN_ITEMS[item.kind]["duration"]:
            return
        self.touch()
        destination = self.return_destination()
        item.uses -= 1
        if item.uses == 0:
            player.inventory[player.selected] = None
        self.teleport_player(player, destination, item.kind)

    def teleport_player(self, player, destination, kind):
        self.touch()
        departure_x, departure_y = player.x, player.y
        self.ensure_terrain(*destination)
        player.x, player.y = destination
        controls = self.controls[player.id]
        controls.movement_epoch += 1
        controls.teleport_epoch += 1
        controls.seat = None
        controls.move_x = controls.move_y = controls.velocity_x = controls.velocity_y = 0.0
        controls.ghost_monsters.clear()
        controls.aim_target = None
        controls.aim_x, controls.aim_y = player.x + 1, player.y
        controls.container = None
        controls.ui = False
        controls.stop_attack()
        for monster in self.monsters.values():
            if monster.target == player.id and not monster.big:
                self.clear_target(monster)
        self.emit_event("teleport_out", player.id, kind, departure_x, departure_y)
        self.emit_event("teleport_in", player.id, kind, player.x, player.y)

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

    def strike_melee(self, player, controls):
        item = player.inventory[player.selected]
        settings = MELEE_WEAPONS.get(item.kind) if item else None
        if settings is None or (item.uses is not None and item.uses <= 0):
            return
        controls.target = None
        controls.progress = 0.0
        structure = self.structures.get(controls.aim_target) if controls.aim_target else self.structure_at(tile(controls.aim_x), tile(controls.aim_y))
        if (structure is not None and self.axe_monster_target(controls) is None) or player.temperature < 5 or self.elapsed + 1e-9 < player.next_axe_attack:
            return
        direction_x, direction_y = normalized(controls.aim_x - player.x, controls.aim_y - player.y)
        if direction_x == direction_y == 0:
            return
        targets = []
        for monster in self.monsters.values():
            offset_x, offset_y = monster.x - player.x, monster.y - player.y
            if offset_x * offset_x + offset_y * offset_y <= settings["range"] ** 2 + 1e-9 and offset_x * direction_x + offset_y * direction_y >= math.hypot(offset_x, offset_y) * math.cos(math.radians(settings["arc_degrees"] / 2)) - 1e-9 and self.visible(player.x, player.y, monster.x, monster.y):
                targets.append((monster, offset_x, offset_y))
        self.touch()
        player.next_axe_attack = self.elapsed + settings["interval"]
        self.emit_event("melee", player.id, item.kind, player.x, player.y, direction=[direction_x, direction_y], range=settings["range"], arc_degrees=settings["arc_degrees"], targets=[monster.id for monster, offset_x, offset_y in targets], **({"attack_id": controls.attack_id} if controls.attack_id else {}))
        for monster, offset_x, offset_y in targets:
            self.apply_weapon_status(monster, settings, player.id)
            self.hurt_monster(monster, settings["damage"], player.id, item.kind, (offset_x, offset_y))
        if item.uses is not None and (targets or not settings.get("consume_on_hit", False)):
            item.uses -= 1
            if item.uses <= 0:
                player.inventory[player.selected] = None
                controls.stop_attack()
        return True

    def apply_weapon_status(self, monster, settings, owner):
        if "freeze_duration" not in settings and "burn_duration" not in settings:
            return
        self.touch()
        if "freeze_duration" in settings and not self.monster_inactive(monster):
            monster.frozen_until = max(monster.frozen_until, self.elapsed + settings["freeze_duration"])
        if "burn_duration" in settings:
            if monster.next_burn <= 0 or self.elapsed >= monster.burning_until:
                monster.next_burn = self.elapsed + settings["burn_interval"]
            monster.burning_until = max(monster.burning_until, self.elapsed + settings["burn_duration"])
            monster.burn_owner = owner

    def swing_axe(self, player, controls, seconds):
        if self.axe_monster_target(controls) is not None:
            controls.target = None
            controls.progress = 0.0
            return
        structure = self.structures.get(controls.aim_target) if controls.aim_target else self.structure_at(tile(controls.aim_x), tile(controls.aim_y))
        self.dismantle_structure(player, controls, structure, seconds)

    def dismantle_structure(self, player, controls, structure, seconds):
        item = player.inventory[player.selected]
        durations = HARVEST_TOOLS.get(item.kind, {}) if item else {}
        if item is None or (item.uses is not None and item.uses <= 0) or (structure is not None and structure.kind not in durations):
            controls.stop_attack()
            return
        if structure is None or distance(player, structure) > 3 or not self.visible(player.x, player.y, structure.x, structure.y, ignore=structure.id) or self.demolition_locked(structure.id) or (structure.kind in PANEL_DEMOLITION and (controls.demolition_container != structure.id or not structure.empty)):
            if controls.demolition_container:
                controls.stop_attack()
            else:
                controls.target = None
                controls.progress = 0
            return
        target = "structure:" + structure.id
        previous_progress = controls.progress if controls.target == target else 0.0
        if previous_progress + seconds + 1e-9 >= durations[structure.kind]:
            self.touch()
        if controls.target != target:
            controls.next_demolition_feedback = 0.0
        self.progress(controls, target, seconds)
        if self.elapsed + 1e-9 >= controls.next_demolition_feedback:
            self.emit_event("chop", player.id, structure.kind, player.x, player.y, target=structure.id, target_x=structure.x, target_y=structure.y, weapon=item.kind)
            controls.next_demolition_feedback = self.elapsed + 0.3
        if controls.progress + 1e-9 >= durations[structure.kind]:
            self.touch()
            if structure.kind == "tree":
                materials = [Item.create("wood") for count in range(self.event_random("harvest", structure.id).randint(1, 3))]
            elif structure.kind == "fence" or structure.kind in PANEL_DEMOLITION:
                materials = [Item.create(structure.kind)]
            else:
                materials = [Item.create("wood")]
            for material in materials:
                self.drop_item(material, structure.x, structure.y)
            self.emit_event("break", player.id, structure.kind, structure.x, structure.y, target=structure.id)
            self.remove_structure(structure)
            if item.uses is not None:
                item.uses -= 1
                if item.uses <= 0:
                    player.inventory[player.selected] = None
            controls.stop_attack()

    def knock_back(self, body, direction, distance, player_id=None, monster_id=None):
        direction_x, direction_y = normalized(*direction)
        if direction_x == direction_y == 0:
            direction_x = 1.0
        previous_x, previous_y = body.x, body.y
        self.move_body(body, direction_x * distance, direction_y * distance, player_id=player_id, monster_id=monster_id)
        if monster_id is not None:
            body.path = []
            body.next_plan = 0.0
            body.demolition = None
            body.demolition_progress = 0.0
            body.next_demolition_feedback = 0.0
        elif player_id in self.controls:
            controls = self.controls[player_id]
            controls.movement_epoch += 1
            controls.velocity_x = controls.velocity_y = 0.0
            if controls.demolition_container:
                controls.stop_attack()
            else:
                controls.target = None
                controls.progress = 0.0
        return [body.x - previous_x, body.y - previous_y]

    def hurt_monster(self, monster, amount, actor, kind, direction, shot=None, knockback=True, feedback=True):
        if monster.id not in self.monsters:
            return
        self.touch()
        impact_x, impact_y = monster.x, monster.y
        displacement = [0.0, 0.0]
        attacker = self.players.get(actor)
        if monster.kind in {"small", "fast"} and attacker and any(item and item.kind == "sheriff_badge" for storage in (attacker.inventory, attacker.backpack) for item in storage):
            amount *= PASSIVE_ITEMS["sheriff_badge"]["damage_multiplier"]
        monster.hp -= amount
        if monster.big and monster.hp > 0 and amount > 0 and not self.monster_inactive(monster) and attacker and attacker.id in self.online and attacker.temperature >= 5:
            target = self.players.get(monster.target)
            if target is None or target.id not in self.online or target.temperature < 5 or attacker.id != target.id and distance(monster, attacker) < distance(monster, target):
                self.set_monster_target(monster, attacker)
        impacts = self.shot_impacts.setdefault(shot, set()) if shot else None
        if impacts is None or monster.id not in impacts:
            position_x, position_y = monster.x, monster.y
            knockback = knockback and not ((monster.big or monster.fast) and self.monster_activity()[0])
            strength = (MELEE_WEAPONS[kind].get("knockback", KNOCKBACK["axe"]) if kind in MELEE_WEAPONS else KNOCKBACK[kind]) * (KNOCKBACK["big_monster_scale"] if monster.big else KNOCKBACK["fast_monster_scale"] if monster.fast else 1) if knockback else 0
            if knockback:
                displacement = self.knock_back(monster, direction, strength, monster_id=monster.id)
            if feedback:
                self.emit_event("hit", actor, kind, position_x, position_y, target=monster.id, target_type="monster", direction=list(normalized(*direction)), knockback=displacement)
            if impacts is not None:
                impacts.add(monster.id)
        if monster.hp <= 0:
            drops = MONSTER_COIN_DROPS[monster.kind]
            count = self.event_random("coin-drop", monster.id).choices([coins for coins, probability in drops], weights=[probability for coins, probability in drops])[0]
            for index in range(count):
                self.drop_item(Item.create("coin"), monster.x, monster.y)
            if monster.kind == "small" and self.event_random("food-drop", monster.id).random() < SMALL_MONSTER_FOOD_CHANCE:
                food = self.event_random("food-kind", monster.id).choices(list(SMALL_MONSTER_FOOD_WEIGHTS), weights=list(SMALL_MONSTER_FOOD_WEIGHTS.values()))[0]
                self.drop_monster_food(monster, food)
            if monster.kind == "crawler" and self.event_random("food-drop", monster.id).random() < 0.05:
                self.drop_monster_food(monster, "oreos")
            if monster.kind == "stalker" and self.event_random("wood-drop", monster.id).random() < 0.15:
                self.drop_item(Item.create("wood"), monster.x, monster.y)
            self.emit_event("death", monster.id, f"monster_{monster.kind}", impact_x, impact_y, source=actor, target=monster.id, target_type="monster", direction=list(normalized(*direction)), knockback=displacement)
            self.monsters.pop(monster.id, None)
            if self._body_index is not None:
                self._body_index.remove(monster.id)

    def drop_monster_food(self, monster, kind):
        if monster.big and (kind not in FOODS or kind in READY_TO_EAT_FOODS or FOODS[kind] > 4):
            return False
        self.drop_item(Item.create(kind), monster.x, monster.y)
        return True

    def hurt_player(self, player, amount, source=None, direction=None, knockback=0.0):
        self.touch()
        previous = player.temperature
        previous_hunger = player.hunger
        if source is not None and source not in self.players:
            amount *= carried_modifier(player, "damage_taken_multiplier", minimum=True)
            knockback *= carried_modifier(player, "knockback_taken_multiplier", minimum=True)
        player.temperature = max(0.0, player.temperature - amount)
        player.hunger = max(0.0, player.hunger - amount)
        if player.temperature < previous or player.hunger < previous_hunger:
            position_x, position_y = player.x, player.y
            if self.controls[player.id].seat and knockback > 0:
                knockback = max(0.65, knockback)
            displacement = self.knock_back(player, direction, knockback, player_id=player.id) if direction is not None and knockback > 0 else [0.0, 0.0]
            self.emit_event("hurt", player.id, "player", position_x, position_y, target=player.id, target_type="player", source=source, direction=list(normalized(*direction)) if direction is not None else [0.0, 0.0], knockback=displacement)
        controls = self.controls[player.id]
        if player.temperature < previous or player.hunger < previous_hunger:
            if controls.seat:
                controls.stop_attack()
            controls.seat = None
        if player.temperature < 5:
            controls.stop_attack()
            if previous >= 5:
                controls.movement_epoch += 1
                controls.ghost_monsters.update(monster.id for monster in self.monsters.values() if distance(player, monster) < BODY_RADIUS * 2)
            for monster in self.monsters.values():
                if monster.target == player.id:
                    self.clear_target(monster)

    def projectile_range(self, projectile):
        if projectile.range_player is None:
            if not projectile.hostile and projectile.owner in self.players:
                projectile.range_player = projectile.owner
            elif projectile.hostile:
                monster = self.monsters.get(projectile.owner)
                if monster and monster.target in self.players:
                    projectile.range_player = monster.target
                elif self.online:
                    projectile.range_player = min(self.online, key=lambda player_id: (distance(projectile, self.players[player_id]), player_id))
        player = self.players.get(projectile.range_player)
        if player:
            projectile.range_x, projectile.range_y = player.x, player.y
            controls = self.controls.get(player.id)
            if controls:
                projectile.range_radius = math.hypot(controls.view_width, controls.view_height) / 2
        if projectile.range_x is None or projectile.range_y is None:
            projectile.range_x = projectile.origin_x if projectile.origin_x is not None else projectile.x
            projectile.range_y = projectile.origin_y if projectile.origin_y is not None else projectile.y
        if projectile.range_radius is None:
            projectile.range_radius = PROJECTILE_RANGE
        offset_x, offset_y = projectile.x - projectile.range_x, projectile.y - projectile.range_y
        radius_squared = projectile.range_radius ** 2
        distance_squared = offset_x * offset_x + offset_y * offset_y
        if distance_squared > radius_squared + 1e-9:
            return -1.0
        direction_x, direction_y = normalized(projectile.velocity_x, projectile.velocity_y)
        projection = offset_x * direction_x + offset_y * direction_y
        return max(0.0, -projection + math.sqrt(max(0.0, projection * projection + radius_squared - distance_squared)))

    def update_homing_missile(self, projectile):
        target = self.monsters.get(projectile.target_id)
        if target is None or target.hp <= 0:
            self.touch()
            del self.projectiles[projectile.id]
            return
        if self.elapsed + 1e-9 >= projectile.detonates_at:
            self.touch()
            direction = (target.x - projectile.x, target.y - projectile.y)
            self.emit_event("explosion", projectile.owner, projectile.kind, target.x, target.y, radius=GUNS[projectile.kind]["impact_radius"], target=target.id)
            del self.projectiles[projectile.id]
            self.hurt_monster(target, projectile.damage, projectile.owner, "bullet", direction, shot=projectile.shot)
            return
        projectile.target_x, projectile.target_y = target.x, target.y
        projectile.x, projectile.y = homing_position(projectile, self.elapsed, target.x, target.y)

    def update_projectiles(self, seconds):
        with self.monster_collisions():
            self.step_projectiles(seconds)

    def step_projectiles(self, seconds):
        for projectile_id, projectile in list(self.projectiles.items()):
            if projectile.kind == "homing_missile":
                self.update_homing_missile(projectile)
                continue
            if projectile.kind in EXPLOSIVE_WEAPONS:
                if self.elapsed + 1e-9 >= projectile.detonates_at:
                    self.explode(projectile)
                continue
            speed = math.hypot(projectile.velocity_x, projectile.velocity_y)
            projectile.remaining = self.projectile_range(projectile)
            if projectile.remaining < 0 or speed <= 1e-9:
                del self.projectiles[projectile_id]
                continue
            travel = min(projectile.remaining, speed * seconds)
            end_x = projectile.x + projectile.velocity_x * travel / speed
            end_y = projectile.y + projectile.velocity_y * travel / speed
            padding = BODY_RADIUS + 1e-9
            left, right = min(projectile.x, end_x) - padding, max(projectile.x, end_x) + padding
            top, bottom = min(projectile.y, end_y) - padding, max(projectile.y, end_y) + padding
            candidates = []
            blockers = MONSTER_BULLET_BLOCKERS if projectile.hostile else BULLET_BLOCKERS
            for structure in self.nearby_structures(projectile.x, projectile.y, end_x, end_y):
                if structure.kind in blockers:
                    fraction = segment_box(projectile.x, projectile.y, end_x, end_y, structure.x, structure.y)
                    if fraction is not None:
                        candidates.append((fraction, 0, "structure", structure))
            for player_id in self.online:
                player = self.players[player_id]
                if not (left <= player.x <= right and top <= player.y <= bottom):
                    continue
                seat = self.seated_structure(self.controls[player_id])
                if player.temperature <= 0 or player_id == projectile.owner or (projectile.hostile and (player.temperature < 5 or seat and seat.kind == "mounted_gun")):
                    continue
                fraction = segment_circle(projectile.x, projectile.y, end_x, end_y, player.x, player.y)
                if fraction is not None:
                    candidates.append((fraction, 1, "player", player))
            if not projectile.hostile:
                for monster in self.nearby_monsters(left, top, right, bottom):
                    fraction = segment_circle(projectile.x, projectile.y, end_x, end_y, monster.x, monster.y)
                    if fraction is not None:
                        candidates.append((fraction, 2, "monster", monster))
            blocked = False
            for fraction, priority, kind, target in sorted(candidates, key=lambda candidate: (candidate[0], candidate[1])):
                if kind == "structure":
                    if projectile.hostile and target.kind == "mounted_gun":
                        self.emit_event("ricochet", projectile.owner, "mounted_gun", projectile.x + (end_x - projectile.x) * fraction, projectile.y + (end_y - projectile.y) * fraction, target=target.id)
                    blocked = True
                    break
                target_key = f"{kind}:{target.id}"
                if target_key in projectile.hit_targets:
                    continue
                if kind == "player":
                    if target.temperature <= 0 or (projectile.hostile and target.temperature < 5):
                        continue
                    if not projectile.hostile and target.id in self.shot_hits.get(projectile.shot, set()):
                        continue
                    self.touch()
                    projectile.hit_targets.append(target_key)
                    hit_players = self.shot_hits.setdefault(projectile.shot, set())
                    self.hurt_player(target, 5 if projectile.hostile else 1, source=projectile.owner, direction=(projectile.velocity_x, projectile.velocity_y), knockback=KNOCKBACK["monster_bullet" if projectile.hostile else "player_bullet"])
                    hit_players.add(target.id)
                elif kind == "monster" and target.id in self.monsters:
                    self.touch()
                    projectile.hit_targets.append(target_key)
                    self.apply_weapon_status(target, GUNS.get(projectile.weapon_kind, {}), projectile.owner)
                    self.hurt_monster(target, projectile.damage, projectile.owner, "bullet", (projectile.velocity_x, projectile.velocity_y), shot=projectile.shot)
            if blocked or speed * seconds > projectile.remaining + 1e-9:
                del self.projectiles[projectile_id]
            else:
                projectile.x, projectile.y = end_x, end_y
                projectile.remaining -= travel
        active_shots = {projectile.shot for projectile in self.projectiles.values()}
        self.shot_hits = {shot: players for shot, players in self.shot_hits.items() if shot in active_shots}
        self.shot_impacts = {shot: monsters for shot, monsters in self.shot_impacts.items() if shot in active_shots}
