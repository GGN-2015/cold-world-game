from dataclasses import replace

from .constants import NORMAL_STORAGE_KINDS, PERSONAL_STORAGE_KINDS, STACK_LIMITS
from .models import identifier


def stack_limit(kind, storage_kind):
    return STACK_LIMITS.get(kind, 1) if storage_kind in NORMAL_STORAGE_KINDS else 1


def storage_slots(owner, storage_kind):
    if storage_kind in PERSONAL_STORAGE_KINDS:
        return getattr(owner, storage_kind)
    if storage_kind == "chest":
        return owner.slots
    raise ValueError(f"Unsupported storage kind: {storage_kind}")


def personal_storages(player, order=PERSONAL_STORAGE_KINDS):
    return [(storage_kind, storage_slots(player, storage_kind)) for storage_kind in order]


def iter_personal_items(player):
    for _, storage in personal_storages(player):
        yield from (item for item in storage if item is not None)


def has_personal_item(player, item_kind):
    return any(item.kind == item_kind for item in iter_personal_items(player))


def mergeable(first, second):
    return first is not None and second is not None and first.kind in STACK_LIMITS and first.kind == second.kind and first.ammo == second.ammo and first.uses == second.uses


def capacity(storages, item):
    total = 0
    for kind, storage in storages:
        limit = stack_limit(item.kind, kind)
        for existing in storage:
            if existing is None:
                total += limit
            elif limit > 1 and mergeable(existing, item):
                total += max(0, limit - existing.count)
    return total


def can_insert(storages, item):
    if capacity(storages, item) < item.count:
        return False
    return True


def insert_item(storages, item):
    remaining = item.count
    for kind, storage in storages:
        limit = stack_limit(item.kind, kind)
        if limit > 1:
            for existing in storage:
                if mergeable(existing, item):
                    amount = min(remaining, max(0, limit - existing.count))
                    existing.count += amount
                    remaining -= amount
                    if not remaining:
                        return 0
        for slot, existing in enumerate(storage):
            if existing is not None:
                continue
            amount = min(remaining, limit)
            if amount == remaining:
                item.count = amount
                storage[slot] = item
                return 0
            storage[slot] = replace(item, id=identifier(), count=amount)
            remaining -= amount
    item.count = remaining
    return remaining


def take_item(storage, slot, amount=1):
    item = storage[slot]
    if item.count == amount:
        storage[slot] = None
        return item
    item.count -= amount
    return replace(item, id=identifier(), count=amount)


def consume_selected(player):
    return take_item(player.inventory, player.selected)


def clear_selected_if(player, item):
    if player.inventory[player.selected] is item:
        player.inventory[player.selected] = None
        return True
    return False


def consume_use(storage, slot, item, amount=1):
    if item.uses is None:
        return False
    item.uses -= amount
    if item.uses <= 0 and storage[slot] is item:
        storage[slot] = None
        return True
    return False


def clone_storages(player):
    return [(kind, [replace(item) if item else None for item in storage]) for kind, storage in personal_storages(player, ("backpack", "inventory"))]


def count_kind(storages, item_kind):
    return sum(item.count for _, storage in storages for item in storage if item and item.kind == item_kind)


def consume_kind(storages, item_kind, amount):
    remaining = amount
    for _, storage in storages:
        for slot, item in enumerate(storage):
            if not item or item.kind != item_kind or not remaining:
                continue
            taken = min(remaining, item.count)
            take_item(storage, slot, taken)
            remaining -= taken
    return remaining
