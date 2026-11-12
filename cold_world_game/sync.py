ENTITY_COLLECTIONS = ("structures", "players", "monsters", "projectiles", "ground", "events")
STATE_OBJECTS = ("you", "environment", "movement", "interaction", "container")


def changed_fields(original, current, slot_deltas=False):
    patch = {"fields": {key: value for key, value in current.items() if key not in original or value != original[key]}}
    if slot_deltas and any(name in patch["fields"] for name in ("inventory", "backpack", "slots")):
        for name in ("inventory", "backpack", "slots"):
            before, after = original.get(name), current.get(name)
            if name in patch["fields"] and isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
                patch.setdefault("slot_changes", {})[name] = [[index, value] for index, value in enumerate(after) if value != before[index]]
                del patch["fields"][name]
    unset = original.keys() - current.keys()
    if unset:
        patch["unset"] = sorted(unset)
    return patch


def state_delta(previous, current, revision, slot_deltas=False, collections=ENTITY_COLLECTIONS):
    state = {}
    objects = {}
    for name, value in current.items():
        if name in collections or value == previous.get(name):
            continue
        if name in STATE_OBJECTS and isinstance(value, dict) and isinstance(previous.get(name), dict):
            objects[name] = changed_fields(previous[name], value, slot_deltas)
        else:
            state[name] = value
    entities = {}
    for name in collections:
        before = {entity["id"]: entity for entity in previous.get(name, [])}
        after = {entity["id"]: entity for entity in current.get(name, [])}
        added = []
        updated = []
        for identifier, entity in after.items():
            original = before.get(identifier)
            if original is None:
                added.append(entity)
            elif entity != original:
                updated.append({"id": identifier, **changed_fields(original, entity, slot_deltas)})
        removed = [identifier for identifier in before if identifier not in after]
        if added or updated or removed:
            entities[name] = {"add": added, "update": updated, "remove": removed}
    return {"type": "delta", "base": revision, "revision": revision + 1, "state": state, "objects": objects, "entities": entities}
