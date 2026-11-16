import math
import shlex

from .actions import GameError
from .biome_layout import BIOME_RING, polar, sectors
from .constants import CREATIVE_ITEMS, ITEM_KINDS
from .models import Item
from .inventory import insert_item, personal_storages


def admin_id(value):
    if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 64 or not value.isprintable()):
        raise ValueError("Admin ID must contain 1-64 printable characters")
    return value


class Administration:
    def admin_command(self, actor, text):
        if self.admin is None or actor.id != self.admin:
            raise GameError("admin_forbidden", "Only the configured server administrator can use this console")
        if not isinstance(text, str) or not text.strip() or len(text) > 512 or not text.isprintable():
            raise GameError("admin_command", "Enter a command containing 1-512 printable characters")
        try:
            parts = shlex.split(text)
        except ValueError as error:
            raise GameError("admin_command", "Invalid quoting; use double quotes around player IDs containing spaces") from error
        command = parts[0] if parts else ""
        if command == "help" and len(parts) == 1:
            return {"output": "give PLAYER_ID ITEM_ID\ncreative [PLAYER_ID]\nheal PLAYER_ID\ntp PLAYER_ID X Y\nbiomes\nitems [SEARCH]\nhelp\nQuote player IDs containing spaces. Command names and item IDs are case-sensitive English identifiers."}
        if command == "biomes" and len(parts) == 1:
            inner_approach = BIOME_RING["radius"] - BIOME_RING["half_width"] - 31
            result = []
            for kind, start, end in sectors(self.seed):
                angle = (start + end) / 2
                x, y = polar(inner_approach, angle)
                result.append(f"{kind} ({start % 360:.0f}°–{end % 360:.0f}°): {x} {y}")
            return {"output": "Inner approaches (X Y):\n" + "\n".join(result)}
        if command == "items" and len(parts) <= 2:
            query = parts[1] if len(parts) == 2 else ""
            items = [kind for kind in sorted(ITEM_KINDS) if query in kind]
            return {"output": "Items: " + ", ".join(items) if items else "No matching item IDs"}
        usage = {"give": "give PLAYER_ID ITEM_ID", "creative": "creative [PLAYER_ID]", "heal": "heal PLAYER_ID", "tp": "tp PLAYER_ID X Y"}
        if command not in usage:
            raise GameError("admin_command", "Unknown command. Use help for available commands")
        if command == "creative" and len(parts) == 1:
            parts.append(actor.id)
        if len(parts) != {"give": 3, "creative": 2, "heal": 2, "tp": 4}[command]:
            raise GameError("admin_command", "Usage: " + usage[command])
        target_id = parts[1]
        if target_id not in self.players:
            raise GameError("admin_player_missing", "Player does not exist: " + target_id)
        if target_id not in self.online:
            raise GameError("admin_player_offline", "Player is offline: " + target_id)
        target = self.players[target_id]
        if command == "creative":
            self.touch()
            outputs = [f"{kind}: {self.admin_give(target, kind)}" for kind in CREATIVE_ITEMS]
            self.activate_creative_vitals(target)
            return {"output": f"Gave creative kit to {target_id}\n" + "\n".join(outputs)}
        if command == "tp":
            try:
                horizontal, vertical = float(parts[2]), float(parts[3])
            except ValueError as error:
                raise GameError("admin_coordinates", "Coordinates must be finite decimal numbers within +/-10000000") from error
            if any(not math.isfinite(coordinate) or abs(coordinate) > 10_000_000 for coordinate in (horizontal, vertical)):
                raise GameError("admin_coordinates", "Coordinates must be finite decimal numbers within +/-10000000")
            self.touch()
            self.ensure_terrain(horizontal, vertical)
            destination = (horizontal, vertical) if self.can_stand(horizontal, vertical) else self.return_destination(horizontal, vertical)
            self.teleport_player(target, destination, "admin")
            return {"output": f"Teleported {target_id} to {target.x:g}, {target.y:g}"}
        if command == "heal":
            self.touch()
            self.restore_player(target)
            self.emit_event("heal", target.id, "admin", target.x, target.y, source=actor.id)
            return {"output": "Healed player: " + target_id}
        kind = parts[2]
        if kind not in ITEM_KINDS:
            raise GameError("admin_item_unknown", "Unknown item ID: " + kind + ". Use items to list valid IDs")
        self.touch()
        destination = self.admin_give(target, kind)
        if kind in CREATIVE_ITEMS:
            self.activate_creative_vitals(target)
        return {"output": f"Gave {kind} to {target_id}: {destination}"}

    def admin_give(self, target, kind):
        if kind == "coin":
            target.money += 1
            return "money balance"
        item = Item.create(kind)
        for name in ("backpack", "inventory"):
            storage = getattr(target, name)
            if None in storage:
                storage[storage.index(None)] = item
                return name
        self.drop_item(item, target.x, target.y)
        return "ground at player's feet"
