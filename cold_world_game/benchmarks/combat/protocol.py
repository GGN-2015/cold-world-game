import json

import msgpack


class State:
    def __init__(self):
        self.revision = 0
        self.fields = []
        self.references = []
        self.scales = {}
        self.reference_fields = set()
        self.value = {}
        self.entities = {}

    def decode(self, raw):
        if isinstance(raw, str):
            return json.loads(raw)
        version, reset, added, payload = msgpack.unpackb(raw, raw=False, strict_map_key=False)
        if version != 1:
            raise ValueError("Unsupported wire version")
        if reset:
            self.references.clear()
        self.references.extend(added)

        def restore(value, field=None):
            if isinstance(value, dict):
                return {(name := self.fields[key] if isinstance(key, int) else key): restore(entry, name) for key, entry in value.items()}
            if isinstance(value, list):
                return [restore(entry, field) for entry in value]
            if type(value) in (int, float):
                if field in self.reference_fields and value < 0:
                    return self.references[-int(value) - 1]
                if field in self.scales:
                    return value / self.scales[field]
            return value

        return restore(payload)

    @staticmethod
    def patch(value, changes):
        value.update(changes.get("fields", {}))
        for name in changes.get("unset", []):
            value.pop(name, None)
        for name, entries in changes.get("slot_changes", {}).items():
            for slot, item in entries:
                value[name][slot] = item

    def apply(self, message):
        if message["type"] == "welcome":
            config = message["wire_config"]
            self.fields = config["fields"]
            self.scales = config["scales"]
            self.reference_fields = set(config["references"])
            self.references.clear()
            self.revision = message.get("state_revision", 0)
            self.value = message["state"]
            self.entities = {name: {entry["id"]: entry for entry in self.value.get(name, [])} for name in ("structures", "players", "monsters", "projectiles", "ground", "structure_states", "events")}
        elif message["type"] == "delta":
            if message["base"] != self.revision or message["revision"] != self.revision + 1:
                raise ValueError("State revision mismatch")
            self.revision = message["revision"]
            self.value.update(message.get("state", {}))
            for name, changes in message.get("objects", {}).items():
                self.patch(self.value[name], changes)
            for name, changes in message.get("entities", {}).items():
                collection = self.entities.setdefault(name, {})
                for identifier in changes.get("remove", []):
                    collection.pop(identifier, None)
                for entry in changes.get("add", []):
                    collection[entry["id"]] = entry
                for entry in changes.get("update", []):
                    self.patch(collection[entry["id"]], entry)
