"""Package recorded world states with the game's renderer for offline viewing."""

import base64
import gzip
import json
import re
from pathlib import Path

from cold_world_game.world import World


TOOLS = Path(__file__).resolve().parent
STATIC = TOOLS.parent / "cold_world_game" / "static"
MODULE_IMPORT = re.compile(r"(\bfrom\s+['\"])\./([\w-]+\.js)(['\"])")


def script_json(data):
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")


def data_url(content, mime):
    return f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"


def renderer_modules():
    imports = {}
    pending = ["renderer.js", "i18n.js"]
    while pending:
        name = pending.pop()
        if f"@cold/{name}" in imports:
            continue
        source = (STATIC / "js" / name).read_text(encoding="utf-8")
        pending.extend(match[1] for match in MODULE_IMPORT.findall(source))
        source = MODULE_IMPORT.sub(r"\1@cold/\2\3", source)
        imports[f"@cold/{name}"] = data_url(source.encode("utf-8"), "text/javascript")
    return {"imports": imports}


def capture_view(state):
    player = state["you"]
    inventory = [
        {key: item[key] for key in ("kind", "ammo", "uses")} if item else None
        for item in player["inventory"]
    ]
    return {
        "elapsed": state["elapsed"], "environment": state["environment"],
        "players": state["players"], "monsters": state["monsters"],
        "projectiles": [
            {key: value for key, value in projectile.items() if key not in {"hit_targets", "shot", "owner", "damage"}}
            for projectile in state["projectiles"]
        ],
        "ground": [{"x": item["x"], "y": item["y"], "item": {"kind": item["item"]["kind"]}} for item in state["ground"]],
        "you": {key: player[key] for key in ("id", "x", "y", "temperature", "hunger", "selected", "downed")} | {"inventory": inventory},
        "interaction": state["interaction"],
    }


def recording_bytes(report):
    return gzip.compress(script_json(report).encode("utf-8"), mtime=0)


def write_replay(path, report=None):
    manifest = json.loads((STATIC / "assets" / "manifest.json").read_text(encoding="utf-8"))
    images = {
        name: data_url((STATIC / "assets" / entry["file"]).read_bytes(), "image/png")
        for name, entry in manifest["assets"].items()
    }
    assets = {"images": images, "animations": manifest["animations"], "effects": manifest["effects"], "monsterHitboxes": manifest.get("monster_hitboxes"), "catalog": World.catalog()}
    template = (TOOLS / "combat_replay.html").read_text(encoding="utf-8")
    slots = {
        "<!-- REPLAY_DATA -->": base64.b64encode(recording_bytes(report)).decode("ascii") if report else "",
        "<!-- GAME_MODULES -->": script_json(renderer_modules()),
        "<!-- GAME_ASSETS -->": script_json(assets),
    }
    for marker, data in slots.items():
        template = template.replace(marker, data, 1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(template, encoding="utf-8")
