import math
import shlex

from .actions import GameError
from .constants import ITEM_KINDS
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
            return {"output": "give PLAYER_ID ITEM_ID\nheal PLAYER_ID\ntp PLAYER_ID X Y\nitems [SEARCH]\nhelp\nQuote player IDs containing spaces. Command names and item IDs are case-sensitive English identifiers."}
        if command == "items" and len(parts) <= 2:
            query = parts[1] if len(parts) == 2 else ""
            items = [kind for kind in sorted(ITEM_KINDS) if query in kind]
            return {"output": "Items: " + ", ".join(items) if items else "No matching item IDs"}
        if command not in ("give", "heal", "tp"):
            raise GameError("admin_command", "Unknown command. Use help for available commands")
        usage = {"give": "give PLAYER_ID ITEM_ID", "heal": "heal PLAYER_ID", "tp": "tp PLAYER_ID X Y"}
        if len(parts) != {"give": 3, "heal": 2, "tp": 4}[command]:
            raise GameError("admin_command", "Usage: " + usage[command])
        target_id = parts[1]
        if target_id not in self.players:
            raise GameError("admin_player_missing", "Player does not exist: " + target_id)
        if target_id not in self.online:
            raise GameError("admin_player_offline", "Player is offline: " + target_id)
        target = self.players[target_id]
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
        if kind == "coin":
            target.money += 1
            destination = "money balance"
        else:
            item = Item.create(kind)
            for name, storage in personal_storages(target, ("backpack", "inventory")):
                if not insert_item([(name, storage)], item):
                    destination = name
                    break
            else:
                self.drop_item(item, target.x, target.y)
                destination = "ground at player's feet"
        return {"output": f"Gave {kind} to {target_id}: {destination}"}
