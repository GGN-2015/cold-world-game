"""Run six short combat trials and export a self-contained browser replay."""

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cold_world_game.actions import GameError
from cold_world_game.constants import AXE, BODY_RADIUS, BULLET_BLOCKERS, GUNS, OPAQUE, SOLID, TICK_RATE
from cold_world_game.geometry import normalized, segment_box
from cold_world_game.models import Monster, Structure
from cold_world_game.storage import Storage
from cold_world_game.wildlife import MONSTER_TYPES
from cold_world_game.world import World
if __package__:
    from .replay_export import capture_view, write_replay
else:
    from replay_export import capture_view, write_replay


PLAYER = "combat-bot"
START = (0, 0)
GOAL = (14, 0)
STEP = 1 / TICK_RATE
SEED = 42
LIMIT = 10
SPAWN_TICK = TICK_RATE // 2
GOAL_RADIUS = 0.6


@dataclass(frozen=True)
class Scenario:
    name: str
    monster: str
    spawn: tuple[int, int]
    trees: tuple[tuple[int, int], ...] = ()


SCENARIOS = (
    Scenario("open_route", "small", (6, 0)),
    Scenario("fast_monster", "fast", (10, 0)),
    Scenario("blocked_shot", "fast", (7, 2), ((4, 1),)),
)


@dataclass(frozen=True)
class Policy:
    name: str
    bypass_slow: bool
    gun_range: float
    ammo_reserve: int
    retreat_distance: float
    reaction_ticks: int
    push_when_aiming: bool


POLICIES = (
    Policy("cautious", True, 6.0, 4, 2.5, 5, False),
    Policy("bold", False, 9.0, 0, 1.4, 3, True),
)


@dataclass(frozen=True)
class Decision:
    reason: str
    waypoint: tuple[float, float]
    aim: tuple[float, float]
    target: str | None = None
    weapon: str | None = None


def blockers(start, end, structures, kinds):
    return any(
        obstacle["kind"] in kinds
        and segment_box(*start, *end, obstacle["x"], obstacle["y"]) is not None
        for obstacle in structures
    )


def step_clear(start, end, structures):
    # Check a little to each side of the center line for the player's width.
    direction_x, direction_y = normalized(end[0] - start[0], end[1] - start[1])
    for offset in (-BODY_RADIUS, 0, BODY_RADIUS):
        shift_x, shift_y = -direction_y * offset, direction_x * offset
        origin = (start[0] + shift_x, start[1] + shift_y)
        destination = (end[0] + shift_x, end[1] + shift_y)
        if blockers(origin, destination, structures, SOLID):
            return False
    return True


def sidestep(position, target, structures):
    direction_x, direction_y = normalized(target[0] - position[0], target[1] - position[1])
    for distance in (1.8, 2.8, 4.0):
        for side in (-1, 1):
            point = (position[0] - side * direction_y * distance, position[1] + side * direction_x * distance)
            if step_clear(position, point, structures) and not blockers(point, target, structures, BULLET_BLOCKERS):
                return point
    return position


class CombatBot:
    def __init__(self, policy):
        self.policy = policy
        self.waypoints = []
        self.previous = {}

    def decide(self, state):
        player = state["you"]
        position = player["x"], player["y"]
        structures = state["structures"]
        monsters = [monster for monster in state["monsters"] if not monster["sleeping"]]
        threat = min(monsters, key=lambda monster: math.dist(position, (monster["x"], monster["y"])), default=None)
        if self.waypoints and math.dist(position, self.waypoints[0]) < 0.55:
            self.waypoints.pop(0)
        if self.waypoints:
            point = self.waypoints[0]
            return Decision("bypass", point, point)
        if threat is None:
            self.previous.clear()
            point = GOAL if step_clear(position, GOAL, structures) else sidestep(position, GOAL, structures)
            return Decision("advance" if point == GOAL else "obstacle", point, point)

        target = threat["x"], threat["y"]
        target_id = threat["id"]
        distance = math.dist(position, target)
        direction_x, direction_y = normalized(target[0] - position[0], target[1] - position[1])
        fast = threat["species"] == "fast"
        on_route = position[0] < target[0] and abs(target[1]) < 2.5
        if self.policy.bypass_slow and not fast and on_route and distance > AXE["range"]:
            side = -1 if target[1] >= position[1] else 1
            near = (position[0] + 1, position[1] + side * 3.4)
            far = (target[0] + 2.6, near[1])
            if step_clear(position, near, structures) and step_clear(near, far, structures):
                self.waypoints.extend((near, far))
                return Decision("bypass", near, near, target_id)

        if not fast and not on_route and distance > AXE["range"]:
            return Decision("advance", GOAL, GOAL)

        retreat = (position[0] - direction_x, position[1] - direction_y)
        if not step_clear(position, retreat, structures):
            retreat = position
        if fast and distance <= self.policy.retreat_distance:
            movement = retreat
        else:
            movement = GOAL if self.policy.push_when_aiming else position
        if distance <= AXE["range"] and not blockers(position, target, structures, OPAQUE) and not fast:
            return Decision("axe", retreat if distance < 1.4 else position, target, target_id, "axe")

        gun = next((item for item in player["inventory"] if item and item["kind"] == "handgun"), None)
        ammo = gun["ammo"] if gun else 0
        emergency = distance <= self.policy.retreat_distance or player["temperature"] < 18
        if fast and distance <= self.policy.gun_range and (ammo > self.policy.ammo_reserve or (ammo and emergency)):
            last = self.previous.get(target_id)
            self.previous[target_id] = (state["elapsed"], target)
            aim = target
            if last is not None:
                interval = state["elapsed"] - last[0]
                # Small lead from the last observed position, with bounded prediction.
                if interval > 0:
                    lead = min(distance / GUNS["handgun"]["speed"], 0.25)
                    aim = tuple(current + (current - prior) * lead / interval for current, prior in zip(target, last[1]))
            if blockers(position, aim, structures, BULLET_BLOCKERS):
                return Decision("blocked", sidestep(position, target, structures), aim, target_id)
            if math.dist(position, target) <= 1.0:
                aim = target
            return Decision("handgun", movement, aim, target_id, "handgun")

        if not step_clear(position, GOAL, structures) or (fast and blockers(position, target, structures, OPAQUE)):
            return Decision("obstacle", sidestep(position, target, structures), target, target_id)
        if fast and distance <= AXE["range"] and not blockers(position, target, structures, OPAQUE):
            return Decision("reserve", retreat, target, target_id, "axe")
        return Decision("close" if on_route else "advance", GOAL, target, target_id)


class TrialWorld(World):
    def __init__(self, storage, scenario):
        self.scenario = scenario
        super().__init__(storage, seed=SEED)

    def prepare(self):
        self.join(PLAYER, client_movement=False)
        with self.transaction():
            self.touch()
            # Keep the natural world outside the authored encounter.
            for structure in list(self.structures.values()):
                if -10 <= structure.x <= 20 and -10 <= structure.y <= 10:
                    self.remove_structure(structure)
            for index, point in enumerate(self.scenario.trees):
                self.add_structure(Structure("tree", *point, id=f"trial-tree-{index}"))
            player = self.players[PLAYER]
            player.x, player.y = START
            player.selected = 1
            self.elapsed = 20 * 60  # Fast monsters are awake.

    def spawn_monster(self):
        if self.tick_number == SPAWN_TICK:
            species = self.scenario.monster
            monster = Monster(
                *self.scenario.spawn, fast=species == "fast", species=species,
                id="trial-monster", hp=MONSTER_TYPES[species]["hp"],
            )
            self.monsters[monster.id] = monster
            self.emit_event("spawn", monster.id, species, monster.x, monster.y)

    def advance_paths(self, deadline):
        # One local monster per trial. Complete the normal search without a
        # wall-clock budget so a busy machine cannot change the encounter.
        super().advance_paths(math.inf)


def position_of(entity):
    return [round(entity["x"], 3), round(entity["y"], 3)]


def handgun_ammo(player):
    return next((item["ammo"] for item in player["inventory"] if item and item["kind"] == "handgun"), 0)


def replay_frame(state, decision):
    player = state["you"]
    held = player["inventory"][player["selected"]]
    return {
        "tick": state["tick"],
        "position": position_of(player),
        "temperature": round(player["temperature"], 3),
        "hunger": round(player["hunger"], 3),
        "ammo": handgun_ammo(player),
        "weapon": held["kind"] if held else None,
        "monsters": [{"id": monster["id"], "kind": monster["species"], "position": position_of(monster), "hp": monster["hp"]} for monster in state["monsters"]],
        "bullets": [position_of(projectile) for projectile in state["projectiles"]],
        "decision": asdict(decision) if decision else None,
    }


def run_trial(scenario, policy):
    with TemporaryDirectory(prefix="cold-combat-trial-") as folder:
        storage = Storage(Path(folder) / "world.sqlite3")
        try:
            world = TrialWorld(storage, scenario)
        except BaseException:
            storage.close()
            raise
        try:
            world.prepare()
            return record_trial(world, scenario, policy)
        finally:
            world.close()


def record_trial(world, scenario, policy):
    bot = CombatBot(policy)
    state = world.snapshot(PLAYER)
    frames = [replay_frame(state, None) | {"view": capture_view(state)}]
    events = []
    last_event = 0
    last_decision = None
    decision = None
    unresolved_shot = None
    end = "timeout"

    def capture_events(tick):
        nonlocal last_event, unresolved_shot
        for event in world.events:
            if event["id"] > last_event:
                entry = {"tick": tick, **event}
                if entry["type"] == "shot" and entry["actor"] == PLAYER:
                    entry["ammo_after"] = next(
                        (item.ammo for item in world.players[PLAYER].inventory if item and item.kind == "handgun"), 0,
                    )
                    entry["ammo_before"] = entry["ammo_after"] + 1
                    unresolved_shot = next(
                        projectile.shot for projectile in world.projectiles.values()
                        if projectile.owner == PLAYER and projectile.spawned_at == event["time"]
                    )
                elif entry["type"] == "hit" and entry["actor"] == PLAYER and entry["kind"] == "bullet":
                    # The bot waits for the preceding shot to hit or disappear.
                    unresolved_shot = None
                events.append(entry)
                last_event = event["id"]
        if unresolved_shot and not any(projectile.shot == unresolved_shot for projectile in world.projectiles.values()):
            events.append({"tick": tick, "type": "miss"})
            unresolved_shot = None

    def send(command, log=True, **details):
        try:
            result = world.execute(PLAYER, command)
        except GameError as error:
            result = {"accepted": False, "error": error.code}
            log = True
        if log:
            events.append({"tick": state["tick"], "type": "command", "command": command, "result": result, **details})
        capture_events(state["tick"])

    for tick in range(LIMIT * TICK_RATE):
        player = state["you"]
        position = player["x"], player["y"]
        if tick % policy.reaction_ticks == 0 or decision is None:
            decision = bot.decide(state)
            frames[-1]["decision"] = asdict(decision)
            signature = (decision.reason, decision.weapon, decision.target)
            if signature != last_decision:
                events.append({"tick": tick, "type": "decision", **asdict(decision)})
                last_decision = signature
        move = normalized(decision.waypoint[0] - position[0], decision.waypoint[1] - position[1])
        send({"type": "input", "move": list(move), "aim": list(decision.aim), "target_id": decision.target}, log=False)

        click = False
        target = next((monster for monster in state["monsters"] if monster["id"] == decision.target), None)
        if decision.weapon and target and not target["sleeping"]:
            slot = next((index for index, item in enumerate(player["inventory"]) if item and item["kind"] == decision.weapon), None)
            if slot is not None and player["selected"] != slot:
                send({"type": "select", "slot": slot})
            melee = decision.weapon == "axe"
            cooldown = player["next_axe_attack" if melee else "next_shot"]
            in_flight = any(not projectile["hit_targets"] for projectile in state["projectiles"] if not projectile["hostile"])
            if melee:
                clear = math.dist(position, (target["x"], target["y"])) <= AXE["range"] and not blockers(position, decision.aim, state["structures"], OPAQUE)
            else:
                clear = not in_flight and not blockers(position, decision.aim, state["structures"], BULLET_BLOCKERS)
            if slot is not None and state["elapsed"] + 1e-9 >= cooldown and clear:
                send(
                    {"type": "attack", "pressed": True, "attack_id": f"trial-{tick}"},
                    weapon=decision.weapon, aim=decision.aim, target=decision.target,
                )
                click = True
        world.tick(STEP)
        state = world.snapshot(PLAYER)
        capture_events(state["tick"])
        if click:
            send({"type": "attack", "pressed": False}, weapon=decision.weapon)
        frames.append(replay_frame(state, decision) | {"view": capture_view(state)})
        if state["you"]["downed"]:
            end = "downed"
            break
        if math.dist((state["you"]["x"], state["you"]["y"]), GOAL) <= GOAL_RADIUS:
            end = "reached"
            break

    shots = sum(event["type"] == "shot" and event["actor"] == PLAYER for event in events)
    ammo_used = frames[0]["ammo"] - frames[-1]["ammo"]
    if shots != ammo_used:
        raise RuntimeError(f"Shot events ({shots}) and ammunition used ({ammo_used}) disagree")
    events.append({"tick": frames[-1]["tick"], "type": "end", "outcome": end})
    return {
        "scenario": scenario.name,
        "policy": policy.name,
        "trees": scenario.trees,
        "structures": [{"id": f"trial-tree-{index}", "kind": "tree", "x": x, "y": y} for index, (x, y) in enumerate(scenario.trees)],
        "chunks": sorted(world.chunks),
        "loadout": ["handgun", "axe"],
        "seed": SEED,
        "frames": frames,
        "events": events,
        "summary": {
            "outcome": end,
            "seconds": round(frames[-1]["tick"] * STEP, 2),
            "ammo_used": ammo_used,
            "swings": sum(event["type"] == "melee" and event["actor"] == PLAYER for event in events),
            "bullet_hits": sum(event["type"] == "hit" and event["kind"] == "bullet" for event in events),
            "misses": sum(event["type"] == "miss" for event in events),
            "axe_hits": sum(event["type"] == "hit" and event["kind"] == "axe" for event in events),
            "hurt": sum(event["type"] == "hurt" for event in events),
            "temperature": frames[-1]["temperature"],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("replays/combat-replay.html"), help="standalone replay HTML")
    parser.add_argument("--json", type=Path, help="also save machine-readable trial data")
    args = parser.parse_args()
    if args.json and args.json.resolve() == args.output.resolve():
        parser.error("--output and --json must be different paths")
    trials = [run_trial(scenario, policy) for scenario in SCENARIOS for policy in POLICIES]
    report = {"tick_rate": TICK_RATE, "seed": SEED, "start": START, "goal": GOAL, "trials": trials}
    data = json.dumps(report, separators=(",", ":"), allow_nan=False)
    write_replay(args.output, report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(data + "\n", encoding="utf-8")
    for trial in trials:
        print(trial["scenario"], trial["policy"], trial["summary"])
    print(args.output.resolve())


if __name__ == "__main__":
    main()
