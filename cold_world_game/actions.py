import math
import time

from .constants import BACKPACK_SLOTS, BUILDINGS, CONTAINERS, DRINKS, DROP_DISTANCE, EXPLOSIVE_WEAPONS, FOODS, GUNS, HARVEST_TOOLS, HEALING_ITEMS, IGNITERS, INVENTORY_SLOTS, MACHINE_OFFERS, MAX_COINS, MELEE_WEAPONS, PANEL_DEMOLITION, PICKUP_RADIUS, RECIPES, RETURN_ITEMS, REVIVAL_ITEMS
from .geometry import DIRECTIONS, circle_square, distance, normalized, segment_box, tile
from .constants import AMMO_PACKS, BUILDING_WANDS, CREATIVE_ITEMS, DOWNED_BUILDINGS, NORMAL_STORAGE_KINDS, PERSONAL_STORAGE_KINDS, THROWABLE_WEAPONS
from .inventory import capacity, clone_storages, consume_kind, count_kind, insert_item, mergeable, personal_storages, stack_limit, storage_slots, take_item
from .models import GroundItem, Item, Structure
from .wildlife import REPAIRABLE, SEATS


TAKE_ALL_BACKPACK_ONLY = {"wood", "spare_part", "papyrus"} | AMMO_PACKS.keys() | IGNITERS.keys()


class GameError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def number(value, name, limit=10_000_000):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or abs(value) > limit or not math.isfinite(value):
        raise GameError("invalid_argument", f"{name} must be a finite number within +/-{limit}")
    return float(value)


def integer(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise GameError("invalid_argument", f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def boolean(value, name):
    if not isinstance(value, bool):
        raise GameError("invalid_argument", f"{name} must be a boolean")
    return value


class Actions:
    def action(self, player, controls, command):
        kind = command.get("type")
        if kind == "admin":
            return self.admin_command(player, command.get("command"))
        if kind == "input":
            move = command.get("move", [controls.move_x, controls.move_y])
            aim = command.get("aim", [controls.aim_x, controls.aim_y])
            if not isinstance(move, list) or len(move) != 2 or not isinstance(aim, list) or len(aim) != 2:
                raise GameError("invalid_argument", "move and aim must be two-element arrays")
            move_x, move_y = number(move[0], "move.x", 1), number(move[1], "move.y", 1)
            aim_x, aim_y = number(aim[0], "aim.x"), number(aim[1], "aim.y")
            target = command.get("target_id", controls.aim_target)
            if target is not None and (not isinstance(target, str) or len(target) > 64):
                raise GameError("invalid_argument", "target_id must be an entity ID or null")
            view_width, view_height = controls.view_width, controls.view_height
            if "viewport" in command:
                viewport = command["viewport"]
                if not isinstance(viewport, list) or len(viewport) != 2:
                    raise GameError("invalid_argument", "viewport must be a two-element array in world units")
                view_width, view_height = number(viewport[0], "viewport.width", 64), number(viewport[1], "viewport.height", 64)
                if view_width <= 0 or view_height <= 0:
                    raise GameError("invalid_argument", "viewport dimensions must be positive")
            if controls.seat and (move_x or move_y):
                controls.seat = None
                controls.stop_attack()
            position = command.get("position")
            if controls.client_movement and position is not None:
                velocity = command.get("velocity", [0, 0])
                if not isinstance(position, list) or len(position) != 2 or not isinstance(velocity, list) or len(velocity) != 2:
                    raise GameError("invalid_argument", "position and velocity must be two-element arrays")
                position_x, position_y = number(position[0], "position.x"), number(position[1], "position.y")
                velocity_x, velocity_y = number(velocity[0], "velocity.x"), number(velocity[1], "velocity.y")
                epoch = integer(command.get("movement_epoch"), "movement_epoch", 0, 2 ** 53 - 1)
                if epoch == controls.movement_epoch and player.temperature >= 5 and not controls.seat:
                    if self.barrier_blocks_movement(player.x, player.y, position_x, position_y):
                        controls.movement_epoch += 1
                    else:
                        player.x, player.y = position_x, position_y
                        controls.velocity_x, controls.velocity_y = velocity_x, velocity_y
            if math.hypot(move_x, move_y) > 1:
                move_x, move_y = normalized(move_x, move_y)
            controls.move_x, controls.move_y = move_x, move_y
            controls.aim_x, controls.aim_y = aim_x, aim_y
            controls.aim_target = target
            controls.view_width, controls.view_height = view_width, view_height
            controls.last_input = time.monotonic()
        elif kind == "sit":
            return self.sit(player, controls, command.get("id"))
        elif kind == "toggle_door":
            identifier = command.get("id")
            return self.toggle_door(player, controls, self.structures.get(identifier) if isinstance(identifier, str) else None)
        elif kind == "select":
            selected = integer(command.get("slot"), "slot", 0, 9)
            if selected != player.selected:
                controls.stop_attack()
                controls.reload_target = None
                player.selected = selected
        elif kind == "reload":
            return self.begin_reload(player, controls)
        elif kind == "attack":
            pressed = boolean(command.get("pressed"), "pressed")
            shift = boolean(command.get("shift", False), "shift")
            cancelled = boolean(command.get("cancelled", False), "cancelled")
            throw_only = boolean(command.get("throw_only", False), "throw_only")
            attack_id = command.get("attack_id")
            if attack_id is not None and (not isinstance(attack_id, str) or not attack_id or len(attack_id) > 64 or not attack_id.isprintable()):
                raise GameError("invalid_argument", "attack_id must be a printable token of 1-64 characters")
            controls.last_input = time.monotonic()
            if not pressed:
                item = player.inventory[player.selected]
                swing = False
                if not cancelled and not controls.ui and controls.held and not controls.throw_only and item and item.kind in THROWABLE_WEAPONS and controls.charge_item == item.id and controls.progress + 1e-9 < THROWABLE_WEAPONS[item.kind]["throw_duration"]:
                    controls.attack_id = attack_id
                    swing = bool(self.strike_melee(player, controls))
                controls.stop_attack()
                return {"accepted": True, "swing": swing, **({"attack_id": attack_id} if attack_id is not None else {})}
            if controls.ui or controls.reload_target:
                return {"accepted": False}
            seat = self.seated_structure(controls)
            if seat and seat.kind != "park_bench":
                controls.held = True
                return {"accepted": True}
            item = player.inventory[player.selected]
            target = self.structure_at(tile(controls.aim_x), tile(controls.aim_y))
            if target and target.kind == "door" and not shift and distance(player, target) <= 2:
                return self.toggle_door(player, controls, target)
            if target and target.kind == "cable_station" and target.repaired:
                return self.use_cable(player, target)
            if item and item.kind == "repair_wrench" and target and target.kind in REPAIRABLE:
                return self.repair_device(player, controls, target, item)
            if target and target.kind in SEATS:
                return self.sit(player, controls, target.id)
            if target and target.kind in CONTAINERS and (item is None or item.kind not in EXPLOSIVE_WEAPONS and item.kind not in THROWABLE_WEAPONS and item.kind not in REVIVAL_ITEMS and item.kind != "homing_missile") and (not shift or target.kind in PANEL_DEMOLITION) and distance(player, target) <= 2 and self.visible(player.x, player.y, target.x, target.y, ignore=target.id):
                self.open_container(player, controls, target.id)
                return {"opened": target.id}
            if player.temperature < 5 and item and item.kind not in FOODS and item.kind not in HEALING_ITEMS and item.kind not in RETURN_ITEMS and item.kind not in REVIVAL_ITEMS and item.kind not in DRINKS:
                controls.stop_attack()
                return {"accepted": False}
            swing = False
            if not controls.held:
                controls.pending_shot = True
                if item and item.kind in THROWABLE_WEAPONS:
                    controls.charge_item = item.id
                    controls.throw_only = throw_only
                elif item and item.kind in MELEE_WEAPONS:
                    controls.attack_id = attack_id
                    swing = bool(self.strike_melee(player, controls))
            controls.held = player.inventory[player.selected] is not None
            controls.shift = shift
            if item and item.kind == "flamethrower" and controls.pending_shot:
                self.spray_fire(player, controls, item)
                controls.pending_shot = False
            if item and item.kind in GUNS and controls.pending_shot:
                self.fire_gun(player, controls, item)
                controls.pending_shot = False
            if attack_id is not None:
                return {"accepted": True, "swing": swing, "attack_id": attack_id}
        elif kind in ("dismantle_chest", "dismantle_container"):
            pressed = boolean(command.get("pressed"), "pressed")
            controls.last_input = time.monotonic()
            if not pressed:
                controls.stop_attack()
                return {"accepted": True}
            structure = self.access_container(player, command.get("id"))
            item = player.inventory[player.selected]
            allowed = ("chest",) if kind == "dismantle_chest" else PANEL_DEMOLITION
            if not controls.ui or controls.container != structure.id or structure.kind not in allowed:
                raise GameError("invalid_container", "Open this container before dismantling it")
            if not structure.empty:
                code = "bank_not_empty" if structure.kind == "piggy_bank" else "fire_not_empty" if structure.kind == "campfire" else "chest_not_empty"
                raise GameError(code, "Remove all stored items before dismantling this container")
            if player.temperature < 5 or item is None or item.kind not in HARVEST_TOOLS or (item.uses is not None and item.uses <= 0) or self.demolition_locked(structure.id):
                raise GameError("demolition_unavailable", "Dismantling requires an axe or usable chainsaw, a standing player and no monster dismantling this structure")
            if controls.demolition_container != structure.id:
                controls.stop_attack()
            controls.demolition_container = structure.id
            controls.held = True
            return {"accepted": True}
        elif kind == "stop":
            controls.stop_attack()
            controls.reload_target = None
            controls.move_x = controls.move_y = 0.0
            controls.velocity_x = controls.velocity_y = 0.0
        elif kind == "ui":
            controls.ui = boolean(command.get("open"), "open")
            controls.container = None
            if controls.ui:
                controls.reload_target = None
            controls.stop_attack()
        elif kind == "open":
            self.open_container(player, controls, command.get("id"))
        elif kind == "close":
            controls.container = None
            controls.ui = False
            controls.stop_attack()
        elif kind == "craft":
            return self.craft(player, controls, command.get("recipe"))
        elif kind == "copy_scroll":
            return self.copy_scroll(player, controls, command.get("kind"))
        elif kind == "trade":
            return self.trade(player, controls, command)
        elif kind == "bank":
            return self.bank(player, controls, command)
        elif kind == "place":
            return self.place(player, controls, command)
        elif kind == "drop":
            slot = integer(command.get("slot", player.selected), "slot", 0, INVENTORY_SLOTS - 1)
            item = player.inventory[slot]
            if item is None:
                raise GameError("empty_slot", "The source slot is empty")
            self.ensure_droppable(item)
            position = self.drop_position(player, controls)
            self.touch()
            self.cancel_selected(player, controls, slot)
            dropped = take_item(player.inventory, slot)
            ground = self.drop_item(dropped, *position, player.id)
            return {"ground_id": ground.id}
        elif kind == "transfer":
            return self.transfer(player, controls, command)
        elif kind == "take_all":
            return self.take_all(player, controls, command.get("id"))
        elif kind == "sort_backpack":
            return self.sort_backpack(player)
        elif kind == "light":
            return self.light(player, controls, command.get("id"))
        elif kind == "ping":
            return {"elapsed": self.elapsed}
        else:
            raise GameError("unknown_command", "Unknown command type")
        return {"accepted": True}

    @staticmethod
    def cancel_selected(player, controls, slot):
        if slot == player.selected:
            controls.stop_attack()
            controls.reload_target = None

    def craft(self, player, controls, recipe_id):
        if not isinstance(recipe_id, str) or recipe_id not in RECIPES:
            raise GameError("invalid_recipe", "Unknown recipe")
        recipe = RECIPES[recipe_id]
        inputs = recipe["inputs"]
        if recipe_id != "recycle_fences" and player.creative_effects().get("free_craft"):
            inputs = {}
        return self.consume_and_produce(player, controls, recipe, inputs)

    def trade(self, player, controls, command):
        structure = self.access_container(player, command.get("id"))
        if structure.kind not in MACHINE_OFFERS:
            raise GameError("invalid_container", "This building is not a trading machine")
        if not controls.ui or controls.container != structure.id:
            raise GameError("container_closed", "Open the trading machine before trading")
        offers = MACHINE_OFFERS[structure.kind]
        offer_id = command.get("offer")
        if not isinstance(offer_id, str) or offer_id not in offers:
            raise GameError("invalid_offer", "Unknown offer for this trading machine")
        offer = offers[offer_id]
        inputs = offer["inputs"]
        if "coin" in inputs and player.creative_effects().get("free_purchases"):
            inputs = {kind: amount for kind, amount in inputs.items() if kind != "coin"}
        return self.consume_and_produce(player, controls, offer, inputs)

    def bank(self, player, controls, command):
        structure = self.access_container(player, command.get("id"))
        if structure.kind != "piggy_bank":
            raise GameError("invalid_container", "This building is not a piggy bank")
        if not controls.ui or controls.container != structure.id:
            raise GameError("container_closed", "Open the piggy bank before transferring coins")
        operation = command.get("operation")
        if operation not in ("deposit", "withdraw"):
            raise GameError("invalid_argument", "operation must be deposit or withdraw")
        amount = integer(command.get("amount"), "amount", 1, MAX_COINS)
        if operation == "deposit":
            if player.money < amount:
                raise GameError("insufficient_money", "Not enough money to deposit")
            if structure.balance > MAX_COINS - amount:
                raise GameError("balance_limit", "The piggy bank balance would exceed the coin limit")
        else:
            if structure.balance < amount:
                raise GameError("insufficient_bank_balance", "Not enough coins in the piggy bank")
            if player.money > MAX_COINS - amount:
                raise GameError("balance_limit", "The player balance would exceed the coin limit")
        self.record_structure(structure.id, checkpoint=True)
        change = amount if operation == "deposit" else -amount
        structure.balance += change
        player.money -= change
        return {"balance": structure.balance, "money": player.money, "amount": amount, "operation": operation}

    def consume_and_produce(self, player, controls, recipe, inputs):
        storages = clone_storages(player)
        payment = inputs.get("coin", 0)
        if player.money < payment:
            raise GameError("insufficient_money", "Not enough money")
        for item_kind, quantity in inputs.items():
            if item_kind == "coin":
                continue
            if consume_kind(storages, item_kind, quantity):
                raise GameError("materials_missing", "Not enough required materials")
        if recipe["output"] != "coin" and insert_item(list(reversed(storages)), Item.create(recipe["output"], recipe["count"])):
            raise GameError("inventory_full", "Not enough room for every output item")
        self.touch()
        player.money -= payment
        controls.stop_attack()
        controls.reload_target = None
        for kind, storage in storages:
            setattr(player, kind, storage)
        if recipe["output"] == "coin":
            player.money += recipe["count"]
        return {"output": recipe["output"], "count": recipe["count"]}

    def place(self, player, controls, command):
        target_x = integer(command.get("x"), "x", -10_000_000, 10_000_000)
        target_y = integer(command.get("y"), "y", -10_000_000, 10_000_000)
        item = player.inventory[player.selected]
        wand = BUILDING_WANDS.get(item.kind) if item else None
        building = wand["building"] if wand else item.kind if item else None
        if controls.ui or building not in BUILDINGS:
            raise GameError("invalid_item", "Select a building and close the interface before placing")
        if player.temperature < 5 and building not in DOWNED_BUILDINGS:
            raise GameError("downed", "Downed players can only place campfires, walls, floors and doors")
        if math.hypot(target_x - player.x, target_y - player.y) > 3 or not self.generated(target_x, target_y):
            raise GameError("out_of_range", "Placement must be within 3 units in a generated chunk")
        if wand:
            vertical = bool(wand.get("rotate")) and boolean(command.get("vertical", False), "vertical")
            result = self.place_with_wand(player, wand, target_x, target_y, vertical)
        else:
            structure = self.place_tile(player, building, target_x, target_y)
            take_item(player.inventory, player.selected)
            result = {"id": structure.id}
        controls.stop_attack()
        for monster in self.monsters.values():
            monster.next_plan = 0
        return result

    def place_with_wand(self, player, wand, target_x, target_y, vertical):
        building = wand["building"]
        wood_cost = RECIPES[building]["inputs"]["wood"]
        storages = personal_storages(player, ("backpack", "inventory"))
        wood = count_kind(storages, "wood")
        if wood < wood_cost:
            raise GameError("materials_missing", "The building wand needs wood")
        ids = []
        first_blocked = None
        for dx, dy in wand["tiles"]:
            if wood < wood_cost:
                break
            x, y = (target_x + dy, target_y + dx) if vertical else (target_x + dx, target_y + dy)
            try:
                if max(abs(x), abs(y)) > 10_000_000 or not self.generated(x, y):
                    raise GameError("out_of_range", "Placement must be in a generated chunk")
                structure = self.place_tile(player, building, x, y)
            except GameError as error:
                if first_blocked is None:
                    first_blocked = error
                continue
            consume_kind(storages, "wood", wood_cost)
            wood -= wood_cost
            ids.append(structure.id)
        if not ids:
            raise first_blocked
        return {"ids": ids, "count": len(ids)}

    def place_tile(self, player, building, target_x, target_y):
        surface = self.structure_at(target_x, target_y)
        lake = "lake" in self.biomes_at(target_x, target_y)
        supported_fire = lake and building == "campfire" and surface and surface.kind in {"floor", "bridge_deck"}
        if lake and (building == "campfire" and not supported_fire
                     or building == "floor" and not self.frozen_lake(target_x, target_y)):
            raise GameError("lake_surface", "Freeze the lake, place a floor, then build your fire")
        if surface and not supported_fire:
            raise GameError("occupied", "This tile is occupied")
        if building in CONTAINERS:
            for offset_x, offset_y in DIRECTIONS:
                neighbor = self.structure_at(target_x + offset_x, target_y + offset_y)
                if neighbor and neighbor.kind in CONTAINERS:
                    raise GameError("adjacent_container", "Chests, campfires, piggy banks and trading machines cannot touch in any of eight directions")
        if building != "floor" and (any(circle_square(self.players[player_id].x, self.players[player_id].y, target_x, target_y) for player_id in self.online) or any(circle_square(monster.x, monster.y, target_x, target_y) for monster in self.monsters.values())):
            raise GameError("occupied", "An entity overlaps this tile")
        self.touch()
        if supported_fire:
            self.remove_structure(surface)
        structure = Structure(building, target_x, target_y, slots=[None] * 30 if building == "chest" else [], owner=player.id if building == "landmine" else None, on_floor=bool(supported_fire))
        self.add_structure(structure)
        if -7 <= target_x <= 7 and -7 <= target_y <= 7 and not self.origin_spawn_points():
            self.remove_structure(structure)
            raise GameError("spawn_blocked", "The last origin spawn route must remain open")
        self.emit_event("place", player.id, structure.kind, structure.x, structure.y)
        return structure

    def toggle_door(self, player, controls, door):
        if door is None or door.kind != "door":
            raise GameError("invalid_item", "This door no longer exists")
        if controls.ui or distance(player, door) > 2 or not self.visible(player.x, player.y, door.x, door.y, ignore=door.id):
            raise GameError("out_of_range", "The door must be visible and within 2 units")
        if door.door_open:
            bodies = [self.players[player_id] for player_id in self.online]
            if any(circle_square(body.x, body.y, door.x, door.y) for body in (*bodies, *self.monsters.values())):
                raise GameError("occupied", "An entity is in the doorway")
        self.record_structure(door.id, checkpoint=True)
        door.door_open = not door.door_open
        self.invalidate_chunk(door)
        self._terrain_revision += 1
        controls.stop_attack()
        for monster in self.monsters.values():
            monster.next_plan = 0
        return {"door_open": door.door_open}

    def open_container(self, player, controls, structure_id):
        structure = self.access_container(player, structure_id)
        controls.stop_attack()
        controls.reload_target = None
        controls.ui = True
        controls.container = structure.id

    def access_container(self, player, structure_id):
        if not isinstance(structure_id, str):
            raise GameError("invalid_container", "A container ID is required")
        structure = self.structures.get(structure_id)
        if structure is None or structure.kind not in CONTAINERS:
            raise GameError("invalid_container", "Container no longer exists")
        if distance(player, structure) > 2 or not self.visible(player.x, player.y, structure.x, structure.y, ignore=structure.id):
            raise GameError("out_of_range", "Container is too far away or occluded")
        return structure

    def validate_container(self, player, controls):
        if controls.container:
            try:
                self.access_container(player, controls.container)
            except GameError:
                controls.container = None
                controls.ui = False
                controls.stop_attack()

    def take_all(self, player, controls, structure_id):
        chest = self.access_container(player, structure_id)
        if chest.kind != "chest":
            raise GameError("invalid_container", "Only chests can be looted")
        if not controls.ui or controls.container != chest.id:
            raise GameError("container_closed", "Open the chest before taking its contents")

        storages = personal_storages(player)
        backpack = storages[1:]
        taken = 0
        activate_creative = False
        for slot, item in enumerate(chest.slots):
            if item is None:
                continue
            destination = backpack if item.kind in TAKE_ALL_BACKPACK_ONLY else storages
            available = MAX_COINS - player.money if item.kind == "coin" else capacity(destination, item)
            amount = min(item.count, available)
            if amount <= 0:
                continue
            if taken == 0:
                self.record_structure(chest.id, checkpoint=True)
            moved = take_item(chest.slots, slot, amount)
            if moved.kind == "coin":
                player.money += amount
            else:
                insert_item(destination, moved)
                activate_creative |= moved.kind in CREATIVE_ITEMS
            taken += amount
        remaining = [item for item in chest.slots if item]
        if not taken and remaining:
            if all(item.kind == "coin" for item in remaining):
                raise GameError("balance_limit", "The player balance would exceed the coin limit")
            if all(item.kind == "coin" or item.kind in TAKE_ALL_BACKPACK_ONLY for item in remaining):
                raise GameError("backpack_full", "No room in the backpack for the remaining supplies")
            raise GameError("inventory_full", "No space in the hotbar or backpack")
        if activate_creative:
            self.activate_creative_vitals(player)
        return {"count": taken, "remaining": sum(item.count for item in remaining)}

    def sort_backpack(self, player):
        def order(item):
            kind = item.kind
            if kind in MELEE_WEAPONS or kind in GUNS or kind in EXPLOSIVE_WEAPONS:
                return 0, kind
            if kind in AMMO_PACKS:
                return 1, kind
            if kind in FOODS or kind in DRINKS:
                return 2, kind
            return 3, kind

        items = sorted((item for item in player.backpack if item is not None), key=order)
        contents = items + [None] * (len(player.backpack) - len(items))
        if contents != player.backpack:
            self.touch()
            player.backpack[:] = contents

    def endpoint(self, player, controls, endpoint, destination=False):
        if not isinstance(endpoint, dict):
            raise GameError("invalid_endpoint", "Transfer endpoints must be objects")
        kind = endpoint.get("kind")
        if kind in PERSONAL_STORAGE_KINDS:
            slot = integer(endpoint.get("slot"), "slot", 0, (INVENTORY_SLOTS if kind == "inventory" else BACKPACK_SLOTS) - 1)
            return kind, player, slot
        if kind == "wallet" and destination:
            return kind, player, None
        if kind == "ground":
            if destination:
                return kind, self.drop_position(player, controls), None
            ground_id = endpoint.get("id")
            ground = self.ground.get(ground_id) if isinstance(ground_id, str) else None
            if not ground or distance(player, ground) > PICKUP_RADIUS or not self.visible(player.x, player.y, ground.x, ground.y):
                raise GameError("out_of_range", "Ground item is missing or too far away")
            if ground.dropped_by == player.id and self.elapsed < ground.immune_until:
                raise GameError("pickup_cooldown", "Wait one second before retrieving your own drop")
            return kind, ground, None
        if kind in ("chest", "fuel", "igniter"):
            structure = self.access_container(player, endpoint.get("id"))
            if controls.container != structure.id:
                raise GameError("container_closed", "Open the container before transferring items")
            if kind == "chest" and structure.kind == "chest":
                return kind, structure, integer(endpoint.get("slot"), "slot", 0, len(structure.slots) - 1)
            if kind in ("fuel", "igniter") and structure.kind in {"campfire", "fixed_heater"}:
                return kind, structure, None
        raise GameError("invalid_endpoint", "Invalid transfer endpoint")

    @staticmethod
    def endpoint_item(endpoint):
        kind, owner, slot = endpoint
        if kind in NORMAL_STORAGE_KINDS:
            return storage_slots(owner, kind)[slot]
        if kind == "igniter":
            return owner.igniter
        if kind == "fuel":
            return Item.create("wood") if owner.fuel else None
        if kind == "ground":
            return owner.item if owner else None

    def transfer(self, player, controls, command):
        source = self.endpoint(player, controls, command.get("from"))
        destination = self.endpoint(player, controls, command.get("to"), destination=True)
        if source == destination:
            raise GameError("same_endpoint", "Source and destination must differ")
        item = self.endpoint_item(source)
        if item is None:
            raise GameError("empty_slot", "The source is empty")
        if ("item_id" in command or "swap_item_id" in command) and item.id != command.get("item_id"):
            raise GameError("stale_item", "The source item has changed")
        if "item_kind" in command and item.kind != command["item_kind"]:
            raise GameError("stale_item", "The source item has changed")
        if item.kind == "coin" and destination[0] in ("inventory", "backpack"):
            destination = "wallet", player, None
        target_kind, target, target_slot = destination
        if "swap_item_id" in command:
            if {source[0], target_kind} != {"inventory", "backpack"}:
                raise GameError("invalid_endpoint", "Swap requires a backpack and a hotbar slot")
            replacement = self.endpoint_item(destination)
            if replacement is None or replacement.id != command["swap_item_id"]:
                raise GameError("stale_item", "The target item has changed")
            self.touch()
            self.cancel_selected(player, controls, source[2] if source[0] == "inventory" else target_slot)
            storage_slots(player, source[0])[source[2]] = replacement
            storage_slots(player, target_kind)[target_slot] = item
            return {"item_id": item.id, "count": item.count}
        amount = item.count
        if target_kind == "ground":
            self.ensure_droppable(item)
        if target_kind == "wallet":
            if item.kind != "coin":
                raise GameError("invalid_currency", "Only coins can be collected as money")
        elif target_kind == "fuel":
            if item.kind != "wood" or target.fuel >= 16:
                raise GameError("invalid_fuel", "Fuel accepts wood only, with a capacity of 16")
            amount = min(amount, 16 - target.fuel)
        elif target_kind == "igniter":
            if item.kind not in IGNITERS or not item.uses or target.igniter is not None:
                raise GameError("invalid_igniter", "The igniter slot must be empty and the item usable")
        elif target_kind not in ("ground", "wallet"):
            existing = self.endpoint_item(destination)
            limit = stack_limit(item.kind, target_kind)
            if existing is not None and (limit == 1 or not mergeable(existing, item) or existing.count >= limit):
                raise GameError("occupied_slot", "Destination slot is full or contains a different item")
            amount = min(amount, limit - (existing.count if existing else 0))
        self.touch()
        source_kind, owner, slot = source
        if source_kind in ("chest", "fuel", "igniter"):
            self.record_structure(owner.id)
        if source_kind == "inventory":
            self.cancel_selected(player, controls, slot)
        if source_kind in NORMAL_STORAGE_KINDS:
            storage = storage_slots(owner, source_kind)
            moved = take_item(storage, slot, amount)
        elif source_kind == "ground" and amount < item.count:
            item.count -= amount
            moved = Item.create(item.kind, amount)
        else:
            self.set_endpoint(source, None, player, controls)
            moved = item
        self.set_endpoint(destination, moved, player, controls)
        if moved.kind in CREATIVE_ITEMS and target_kind in ("inventory", "backpack"):
            self.activate_creative_vitals(player)
        return {"item_id": moved.id, "count": amount}

    def set_endpoint(self, endpoint, item, player, controls):
        kind, owner, slot = endpoint
        if kind in ("chest", "igniter", "fuel"):
            self.record_structure(owner.id)
        if kind in NORMAL_STORAGE_KINDS:
            if kind == "inventory":
                self.cancel_selected(player, controls, slot)
            storage = storage_slots(owner, kind)
            existing = storage[slot]
            if item and existing and mergeable(existing, item):
                existing.count += item.count
            else:
                storage[slot] = item
        elif kind == "igniter":
            owner.igniter = item
        elif kind == "fuel":
            owner.fuel += item.count if item else -1
        elif kind == "wallet":
            owner.money += item.count
        elif kind == "ground":
            if item:
                self.drop_item(item, *owner, player.id)
            else:
                del self.ground[owner.id]

    @staticmethod
    def ensure_droppable(item):
        if item.kind == "axe":
            raise GameError("item_not_droppable", "Axes cannot be dropped; store them in a chest instead")

    def drop_position(self, player, controls):
        direction_x, direction_y = normalized(controls.aim_x - player.x, controls.aim_y - player.y)
        if direction_x == direction_y == 0:
            raise GameError("invalid_drop_direction", "Aim away from the player before dropping an item")
        target_x = player.x + direction_x * DROP_DISTANCE
        target_y = player.y + direction_y * DROP_DISTANCE
        travel = DROP_DISTANCE
        for tile_x in range(tile(min(player.x, target_x)) - 1, tile(max(player.x, target_x)) + 2):
            for tile_y in range(tile(min(player.y, target_y)) - 1, tile(max(player.y, target_y)) + 2):
                structure = self.structure_at(tile_x, tile_y)
                if self.generated(tile_x, tile_y) and (structure is None or not structure.solid):
                    continue
                fraction = segment_box(player.x, player.y, target_x, target_y, tile_x, tile_y)
                if fraction is not None:
                    travel = min(travel, max(0.0, fraction * DROP_DISTANCE - 1e-6))
        if travel <= 1e-6:
            raise GameError("drop_blocked", "No reachable drop position in this direction")
        return player.x + direction_x * travel, player.y + direction_y * travel

    def drop_item(self, item, x, y, dropped_by=None):
        ground = GroundItem(item, x, y, dropped_by=dropped_by, immune_until=self.elapsed + 1 if dropped_by else 0)
        self.ground[ground.id] = ground
        return ground

    def light(self, player, controls, structure_id):
        fire = self.access_container(player, structure_id)
        if controls.container != fire.id or fire.kind not in {"campfire", "fixed_heater"}:
            raise GameError("invalid_container", "Open this campfire first")
        if fire.kind == "fixed_heater" and not fire.repaired:
            raise GameError("device_broken", "Repair this heater before lighting it")
        if "lake" in self.biomes_at(fire.x, fire.y) and not self.supports_lake_fire(fire):
            raise GameError("lake_surface", "A fire needs a floor on the lake")
        if fire.lit or fire.fuel < 1 or not fire.igniter or not fire.igniter.uses:
            raise GameError("cannot_light", "An unlit fire needs fuel and a usable igniter")
        self.touch()
        self.record_structure(fire.id)
        fire.igniter.uses -= 1
        if fire.igniter.uses == 0:
            fire.igniter = None
        elif None in player.backpack:
            player.backpack[player.backpack.index(None)] = fire.igniter
            fire.igniter = None
        fire.fuel -= 1
        fire.burn_remaining = self.fire_duration(fire)
        return {"lit": True}
