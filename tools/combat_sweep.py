"""Compare combat loadouts over seeded four-wave survival encounters."""

import argparse
import csv
import itertools
import json
import math
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

if __package__:
    from .combat_trial import PLAYER, STEP, TICK_RATE, TrialWorld, blockers, position_of, step_clear
    from .replay_export import capture_view, recording_bytes, write_replay
else:
    from combat_trial import PLAYER, STEP, TICK_RATE, TrialWorld, blockers, position_of, step_clear
    from replay_export import capture_view, recording_bytes, write_replay

from cold_world_game.constants import BODY_RADIUS, BULLET_BLOCKERS, GUNS, MELEE_WEAPONS, MONSTER_BULLET_BLOCKERS, OPAQUE
from cold_world_game.geometry import normalized, segment_box, segment_circle
from cold_world_game.models import Item, Monster, Structure
from cold_world_game.storage import Storage
from cold_world_game.wildlife import MONSTER_TYPES


ENVIRONMENTS = {
    "open_field": (),
    "pine_woods": tuple(("tree", x, y) for x, y in (
        (-7, -3), (-5, 2), (-3, -5), (-1, 4), (2, -2), (3, 5), (5, 1), (7, -4), (8, 4),
    )),
    "ruins": tuple(("wall", x, y) for x, y in (
        (-6, -3), (-6, -2), (-6, -1), (-6, 1), (-6, 2), (-6, 3),
        (6, -3), (6, -2), (6, -1), (6, 1), (6, 2), (6, 3),
        (-2, -4), (-1, -4), (1, 4), (2, 4),
    )) + tuple(("floor", x, y) for x in range(-5, 6) for y in range(-3, 4)),
}
LOADOUTS = {
    "sidearm": ("handgun", "axe"),
    "spread": ("shotgun", "axe"),
    "automatic": ("storm_smg", "crowbar"),
    "precision": ("hunting_rifle", "snow_shovel"),
    "freeze": ("ice_carbine", "frost_spear"),
    "burn": ("ember_pistol", "fire_whip"),
}
GUN_RANGES = {"sidearm": 8, "spread": 4.5, "automatic": 6, "precision": 11, "freeze": 9, "burn": 7}
POLICIES = ("cautious", "bold")
DEFAULT_DENSITIES = (10, 16, 24)
WAVE_TICKS = tuple(TICK_RATE * second for second in (1, 7, 13, 19))
DURATION = 25
SAMPLE_TICKS = 4
ARENA_RADIUS = 9
DODGE_WINDOW = 0.75


@dataclass(frozen=True)
class Setup:
    environment: str
    policy: str
    category: str
    density: int
    seed: int
    dodge: bool = True
    carried: tuple[str, ...] = ()
    melee_followup: bool = False

    @property
    def loadout(self):
        return LOADOUTS[self.category]


@dataclass(frozen=True)
class Choice:
    reason: str
    move: tuple[float, float]
    aim: tuple[float, float]
    target: str | None = None
    weapon: str | None = None


class Arena(TrialWorld):
    def __init__(self, storage, setup):
        self.setup = setup
        super().__init__(storage, None)
        rng = random.Random(setup.seed)
        # The same ordered spawn list is used for paired gear and policy tests.
        self.waves = {}
        perimeter = [(x, y) for x in range(-12, 13) for y in range(-12, 13) if max(abs(x), abs(y)) in (10, 12)]
        for tick in WAVE_TICKS:
            rng.shuffle(perimeter)
            kinds = rng.choices(("small", "fast", "crawler", "armored", "stalker", "big"), (28, 28, 8, 12, 12, 12), k=len(perimeter))
            self.waves[tick] = list(zip(perimeter[:setup.density], kinds))
        self.emitted = 0
        self.ranged_hits = 0
        self.resolving_projectiles = False

    def update_projectiles(self, seconds):
        self.resolving_projectiles = True
        try:
            super().update_projectiles(seconds)
        finally:
            self.resolving_projectiles = False

    def hurt_player(self, player, amount, source=None, direction=None, knockback=0.0):
        previous = player.temperature
        super().hurt_player(player, amount, source, direction, knockback)
        if self.resolving_projectiles and player.temperature < previous:
            self.ranged_hits += 1
            self.emit_event("ranged_hurt", player.id, "bullet", player.x, player.y, source=source)

    def ensure_terrain(self, x, y):
        # Isolated fixture of blank, fully generated chunks with authored cover.
        if not self.chunks:
            self.chunks.update(itertools.product(range(-2, 3), repeat=2))
            self.origin_region = [(0, 0)]

    def prepare(self):
        self.join(PLAYER)
        with self.transaction():
            self.touch()
            self.elapsed = 20 * 60
            player = self.players[PLAYER]
            player.inventory[:3] = [*(Item.create(kind) for kind in self.setup.loadout), None]
            for slot, kind in enumerate(self.setup.carried):
                player.backpack[slot] = Item.create(kind)
            for index, (kind, x, y) in enumerate(ENVIRONMENTS[self.setup.environment]):
                self.add_structure(Structure(kind, x, y, id=f"cover-{index}"))

    def spawn_monster(self):
        wave = self.waves.get(self.tick_number, ())
        if wave:
            self.emit_event("wave", PLAYER, "wave", 0, 0, number=WAVE_TICKS.index(self.tick_number) + 1, count=len(wave))
        for index, ((x, y), species) in enumerate(wave):
            identifier = f"wave-{self.tick_number}-{index}"
            self.monsters[identifier] = Monster(
                x, y, id=identifier, species=species, fast=species == "fast", big=species == "big",
                hp=MONSTER_TYPES[species]["hp"],
            )
            self.emitted += 1
            self.emit_event("spawn", identifier, species, x, y)


def move_options(phase):
    return [(0, 0)] + [(math.cos(angle), math.sin(angle)) for angle in
                      ((step + phase) * math.pi / 4 for step in range(8))]


def choose_move(position, threats, structures, cautious, phase):
    if not threats:
        return normalized(-position[0], -position[1]) if math.hypot(*position) > 2 else (0, 0)
    nearest = min(math.dist(position, point) for point in threats)
    if nearest > (7.0 if cautious else 3.2):
        return (0, 0)
    def score(move):
        point = position[0] + 1.9 * move[0], position[1] + 1.9 * move[1]
        if max(map(abs, point)) > ARENA_RADIUS or not step_clear(position, point, structures):
            return -math.inf
        distances = sorted(math.dist(point, threat) for threat in threats)[:3]
        return distances[0] + 0.2 * sum(distances) - (0.12 if cautious else 0.32) * math.hypot(*point)

    return max(move_options(phase), key=score)


def incoming_shots(world, position, player_speed):
    for bullet in world.projectiles.values():
        if not bullet.hostile:
            continue
        velocity = bullet.velocity_x, bullet.velocity_y
        speed = math.hypot(*velocity)
        if speed == 0 or math.dist(position, (bullet.x, bullet.y)) > (speed + player_speed) * DODGE_WINDOW + BODY_RADIUS:
            continue
        horizon = min(DODGE_WINDOW, max(0, bullet.remaining) / speed)
        end = bullet.x + velocity[0] * horizon, bullet.y + velocity[1] * horizon
        for obstacle in world.nearby_structures(bullet.x, bullet.y, *end):
            if obstacle.kind in MONSTER_BULLET_BLOCKERS:
                fraction = segment_box(bullet.x, bullet.y, *end, obstacle.x, obstacle.y)
                if fraction is not None:
                    horizon = min(horizon, math.dist((bullet.x, bullet.y), end) * fraction / speed)
        if horizon > 0:
            yield bullet, horizon


def dodge_move(world, position, planned, phase):
    speed = world.player_speed(world.players[PLAYER])
    shots = list(incoming_shots(world, position, speed))
    if not shots:
        return planned, ()

    def impacts(move):
        times = []
        for bullet, horizon in shots:
            # In the moving player's frame the bullet travels at the relative velocity.
            end_x = bullet.x + (bullet.velocity_x - speed * move[0]) * horizon
            end_y = bullet.y + (bullet.velocity_y - speed * move[1]) * horizon
            fraction = segment_circle(bullet.x, bullet.y, end_x, end_y, *position, BODY_RADIUS + .06)
            if fraction is not None:
                times.append((horizon * fraction, bullet))
        return times

    danger = impacts(planned)
    if not danger:
        return planned, ()
    structures = [
        {"kind": obstacle.kind, "x": obstacle.x, "y": obstacle.y}
        for obstacle in world.nearby_structures(position[0] - 4, position[1] - 4, position[0] + 4, position[1] + 4)
    ]
    bodies = [(monster.x, monster.y) for monster in world.monsters.values()]

    def score(move):
        end = tuple(point + axis * speed * DODGE_WINDOW for point, axis in zip(position, move))
        if max(map(abs, end)) > ARENA_RADIUS or not step_clear(position, end, structures):
            return (-math.inf, -math.inf, -math.inf)
        hits = impacts(move)
        nearest = min((math.dist(end, body) for body in bodies), default=4)
        alignment = sum(first * second for first, second in zip(move, planned))
        return (-len(hits), min((time for time, _ in hits), default=DODGE_WINDOW), min(nearest, 4) + .35 * alignment)

    choice = max([planned, *move_options(phase)], key=score)
    return choice, tuple(bullet for _, bullet in danger) if choice != planned else ()


def decide(state, setup, phase):
    player = state["you"]
    position = player["x"], player["y"]
    structures = state["structures"]
    monsters = [monster for monster in state["monsters"] if not monster["sleeping"]]
    threats = [(monster["x"], monster["y"]) for monster in monsters]
    cautious = setup.policy == "cautious"
    move = choose_move(position, threats, structures, cautious, phase)
    if not monsters:
        return Choice("regroup", move, (position[0] + 1, position[1]))
    gun, melee = setup.loadout
    items = {item["kind"]: item for item in player["inventory"] if item}
    melee_range = MELEE_WEAPONS[melee]["range"]
    gun_range = GUN_RANGES[setup.category] + (0 if cautious else 2)

    def priority(monster):
        distance = math.dist(position, (monster["x"], monster["y"]))
        urgent = monster["species"] in ("fast", "big")
        return distance - (1.5 if cautious and urgent else 0)

    for monster in sorted(monsters, key=priority):
        target = monster["x"], monster["y"]
        distance = math.dist(position, target)
        urgent = monster["species"] in ("fast", "big")
        melee_clear = melee in items and distance <= melee_range and not blockers(position, target, structures, OPAQUE)
        followup = setup.melee_followup and state["elapsed"] >= monster["burning_until"]
        if melee_clear and (cautious and not urgent or gun not in items or followup):
            return Choice("melee_save", move, target, monster["id"], melee)
        if gun in items and distance <= gun_range:
            lead = min(distance / GUNS[gun]["speed"], .4)
            aim = (target[0] + monster["velocity_x"] * lead, target[1] + monster["velocity_y"] * lead)
            if not blockers(position, aim, structures, BULLET_BLOCKERS):
                return Choice("fire_threat" if urgent else "fire", move, aim, monster["id"], gun)
        if melee_clear:
            return Choice("melee_close", move, target, monster["id"], melee)
    target = threats[0]
    return Choice("reposition", move, target)


def run_match(job):
    setup, recording = job
    with TemporaryDirectory(prefix="cold-combat-arena-") as folder:
        storage = Storage(Path(folder) / "world.sqlite3")
        try:
            world = Arena(storage, setup)
            world.prepare()
            return play(world, setup, recording)
        finally:
            storage.close()


def play(world, setup, recording):
    phase = random.Random(setup.seed).random()
    player = world.players[PLAYER]
    gun, melee = setup.loadout
    initial_ammo = player.inventory[0].ammo
    initial_uses = player.inventory[1].uses or 0
    events, frames = [], []
    shots = kills = hurt = last_event = dodge_count = 0
    dodged = set()
    last_reason = None
    choice = None
    outcome = "survived"
    frame_limit = DURATION * TICK_RATE
    reaction_ticks = 5 if setup.policy == "cautious" else 3

    def stock(slot, kind, field):
        item = player.inventory[slot]
        return (getattr(item, field) or 0) if item and item.kind == kind else 0

    def capture(state):
        frames.append({
            "tick": world.tick_number, "position": position_of(state["you"]),
            "temperature": player.temperature, "hunger": player.hunger,
            "ammo": stock(0, gun, "ammo"),
            "weapon": player.inventory[player.selected].kind if player.inventory[player.selected] else None,
            "decision": asdict(choice) if choice else None, "view": capture_view(state),
        })

    def send(command, **metadata):
        result = world.execute(PLAYER, command)
        if recording and metadata:
            events.append({"tick": world.tick_number, "type": "command", "command": command, "result": result, **metadata})

    for tick in range(frame_limit):
        if tick % reaction_ticks == 0:
            choice = decide(world.snapshot(PLAYER), setup, phase)
            signature = choice.reason, choice.weapon
            if recording and signature != last_reason:
                events.append({"tick": tick, "type": "decision", **asdict(choice)})
                last_reason = signature
        position = player.x, player.y
        move, threats = dodge_move(world, position, choice.move, phase) if setup.dodge else (choice.move, ())
        for bullet in threats:
            if bullet.id in dodged:
                continue
            dodged.add(bullet.id)
            dodge_count += 1
            if recording:
                events.append({"tick": tick, "type": "dodge", "x": player.x, "y": player.y,
                               "move": move, "bullet": [bullet.x, bullet.y]})
        if recording and tick % SAMPLE_TICKS == 0:
            capture(world.snapshot(PLAYER))
        send({"type": "input", "move": list(move), "aim": list(choice.aim), "target_id": choice.target})
        melee_attack = choice.weapon == melee
        slot = 1 if melee_attack else 0
        target = world.monsters.get(choice.target)
        cooldown = player.next_axe_attack if melee_attack else player.next_shot
        equipped = player.inventory[slot]
        click = bool(choice.weapon and target and equipped and equipped.kind == choice.weapon and world.elapsed + 1e-9 >= cooldown)
        if click and melee_attack:
            click = math.hypot(target.x - player.x, target.y - player.y) <= MELEE_WEAPONS[melee]["range"]
        if click and not melee_attack:
            click = not any(
                obstacle.kind in BULLET_BLOCKERS
                and segment_box(player.x, player.y, *choice.aim, obstacle.x, obstacle.y) is not None
                for obstacle in world.nearby_structures(player.x, player.y, *choice.aim)
            )
        if click:
            if slot != player.selected:
                send({"type": "select", "slot": slot}, weapon=choice.weapon)
            send({"type": "attack", "pressed": True, "attack_id": f"arena-{tick}"}, weapon=choice.weapon, aim=choice.aim, target=choice.target)
        world.tick(STEP)
        for event in world.events:
            if event["id"] <= last_event:
                continue
            last_event = event["id"]
            is_shot = event["type"] == "shot" and event["actor"] == PLAYER
            shots += is_shot
            kills += event["type"] == "death" and event.get("source") == PLAYER
            hurt += event["type"] == "hurt" and event["actor"] == PLAYER
            if recording:
                event_tick = round((event["time"] - 1200) * TICK_RATE)
                entry = {"tick": event_tick, **event}
                if is_shot:
                    entry.update(ammo_after=initial_ammo - shots, ammo_before=initial_ammo - shots + 1)
                events.append(entry)
        if click:
            send({"type": "attack", "pressed": False})
        if player.temperature < 5:
            outcome = "downed"
            break

    ammo_used = initial_ammo - stock(0, gun, "ammo")
    if shots != ammo_used:
        raise RuntimeError("Recorded shots and consumed ammunition disagree")
    summary = {
        "outcome": outcome, "seconds": round(world.tick_number * STEP, 2),
        "kills": kills, "spawned": world.emitted, "ammo_used": ammo_used,
        "uses_spent": initial_uses - stock(1, melee, "uses"),
        "hurt": hurt, "ranged_hits": world.ranged_hits, "dodges": dodge_count,
        "temperature": round(player.temperature, 3), "hunger": round(player.hunger, 3),
        "waves_survived": sum(world.tick_number >= deadline for deadline in (*WAVE_TICKS[1:], frame_limit)),
    }
    result = {**asdict(setup), "loadout": setup.loadout, "scenario": setup.environment, "summary": summary}
    if recording:
        capture(world.snapshot(PLAYER))
        events.append({"tick": world.tick_number, "type": "end", "outcome": outcome})
        events.sort(key=lambda event: event["tick"])
        result.update(
            frames=frames, events=events, sample_ticks=SAMPLE_TICKS,
            center=[0, 0], chunks=sorted(world.chunks),
            structures=[{"id": structure.id, "kind": structure.kind, "x": structure.x, "y": structure.y, "lit": structure.lit} for structure in world.structures.values()],
        )
    return result


def survival_rates(results):
    rates = {}
    for result in results:
        row = rates.setdefault(result["density"], {"survived": 0, "trials": 0})
        row["trials"] += 1
        row["survived"] += result["summary"]["outcome"] == "survived"
    return dict(sorted(rates.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--densities", nargs="+", type=int, default=DEFAULT_DENSITIES, metavar="MONSTERS_PER_WAVE")
    parser.add_argument("--repeats", type=int, default=4, help="independent spawn seeds per combination")
    parser.add_argument("--seed", type=int, default=42, help="first spawn seed")
    parser.add_argument("--jobs", type=int, default=2, help="parallel local simulation workers")
    parser.add_argument("--categories", nargs="+", choices=LOADOUTS, default=tuple(LOADOUTS))
    parser.add_argument("--environments", nargs="+", choices=ENVIRONMENTS, default=tuple(ENVIRONMENTS))
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=POLICIES)
    parser.add_argument("--no-dodge", action="store_true", help="paired control without projectile avoidance")
    parser.add_argument("--record", choices=("all", "boundary", "first", "none"), default="boundary",
                        help="record all matches, the first seed near the survival boundary or at each density, or statistics only")
    parser.add_argument("--split-recordings", action="store_true", help="export a standalone player and one compressed file per recorded match")
    parser.add_argument("--output", type=Path, default=Path("replays/combat-sweep"), help="output path without extension")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 100 or not 1 <= args.jobs <= 16 or not all(1 <= value <= 40 for value in args.densities):
        parser.error("expected 1–100 repeats, 1–16 jobs, and 1–40 monsters per wave")
    densities = sorted(set(args.densities))
    setups = [Setup(*values) for values in itertools.product(
        dict.fromkeys(args.environments), dict.fromkeys(args.policies), dict.fromkeys(args.categories), densities,
        range(args.seed, args.seed + args.repeats), (not args.no_dodge,),
    )]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        print(f"Running {len(setups)} matches", flush=True)
        results = []
        for result in executor.map(run_match, ((setup, args.record == "all") for setup in setups), chunksize=2):
            results.append(result)
            if len(results) % 36 == 0:
                print(f"{len(results)}/{len(setups)}", flush=True)
        rates = survival_rates(results)
        boundary = min(rates, key=lambda density: (abs(rates[density]["survived"] / rates[density]["trials"] - .5), density))
        if args.record != "none":
            recorded = [setup for setup in setups if setup.seed == args.seed and (args.record == "first" or setup.density == boundary)]
            trials = results if args.record == "all" else list(executor.map(run_match, ((setup, True) for setup in recorded), chunksize=1))
            result_index = {
                (row["scenario"], row["policy"], row["loadout"], row["density"], row["seed"]): row["summary"]
                for row in results
            }
            for trial in trials:
                key = (trial["scenario"], trial["policy"], trial["loadout"], trial["density"], trial["seed"])
                if trial["summary"] != result_index[key]:
                    raise RuntimeError(f"Recording changed the simulation result for {key}")
            recording = {"tick_rate": TICK_RATE, "seed": args.seed, "trials": trials, "sweep": True,
                         "rates": rates, "wave_seconds": [tick * STEP for tick in WAVE_TICKS]}
            if args.split_recordings:
                directory = args.output.parent / (args.output.name + "-recordings")
                directory.mkdir(exist_ok=True)
                for trial in trials:
                    name = "-".join(str(trial[key]) for key in ("scenario", "policy", "category", "density", "seed"))
                    (directory / (name + ".replay.gz")).write_bytes(recording_bytes(recording | {"trials": [trial]}))
                write_replay(args.output.parent / "replay-player.html")
            else:
                args.output.with_suffix(".replay.json").write_text(
                    json.dumps(recording, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8",
                )
                write_replay(args.output.with_suffix(".html"), recording)
    if args.record == "all":
        results = [{key: row[key] for key in ("scenario", "policy", "category", "loadout", "density", "seed", "dodge", "summary")} for row in results]
    report = {"duration": DURATION, "wave_seconds": [tick * STEP for tick in WAVE_TICKS], "rates": rates, "boundary_recorded": boundary if args.record == "boundary" else None, "results": results}
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with args.output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
        rows = [{"environment": row["scenario"], "policy": row["policy"], "category": row["category"], "loadout": "+".join(row["loadout"]),
                 "density": row["density"], "seed": row["seed"], **row["summary"]} for row in results]
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for density, counts in rates.items():
        print(f"{density:2d} per wave: {counts['survived']:3d}/{counts['trials']} survived")


if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()
    main()
