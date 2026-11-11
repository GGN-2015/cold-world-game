ENTITY_COLLECTIONS = ("structures", "players", "monsters", "projectiles", "ground", "events")
STATE_OBJECTS = ("you", "environment", "movement", "interaction", "container")


def changed_fields(original, current):
    patch = {"fields": {key: value for key, value in current.items() if key not in original or value != original[key]}}
    unset = original.keys() - current.keys()
    if unset:
        patch["unset"] = sorted(unset)
    return patch


def state_delta(previous, current, revision):
    state = {}
    objects = {}
    for name, value in current.items():
        if name in ENTITY_COLLECTIONS or value == previous.get(name):
            continue
        if name in STATE_OBJECTS and isinstance(value, dict) and isinstance(previous.get(name), dict):
            objects[name] = changed_fields(previous[name], value)
        else:
            state[name] = value
    entities = {}
    for name in ENTITY_COLLECTIONS:
        before = {entity["id"]: entity for entity in previous[name]}
        after = {entity["id"]: entity for entity in current[name]}
        added = []
        updated = []
        for identifier, entity in after.items():
            original = before.get(identifier)
            if original is None:
                added.append(entity)
            elif entity != original:
                updated.append({"id": identifier, **changed_fields(original, entity)})
        removed = [identifier for identifier in before if identifier not in after]
        if added or updated or removed:
            entities[name] = {"add": added, "update": updated, "remove": removed}
    return {"type": "delta", "base": revision, "revision": revision + 1, "state": state, "objects": objects, "entities": entities}
