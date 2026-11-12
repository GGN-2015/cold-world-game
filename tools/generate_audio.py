import math
import random
import struct
import wave
from pathlib import Path


DESTINATION = Path(__file__).resolve().parents[1] / "cold_world_game" / "static" / "audio"
SAMPLE_RATE = 22050


def export(name, duration, sampler):
    samples = []
    generator = random.Random(name)
    for index in range(round(duration * SAMPLE_RATE)):
        seconds = index / SAMPLE_RATE
        value = sampler(seconds, generator)
        fade = min(1.0, max(0.0, (duration - seconds) / 0.015))
        samples.append(round(max(-0.85, min(0.85, value * fade)) * 32767))
    with wave.open(str(DESTINATION / f"{name}.wav"), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(struct.pack(f"<{len(samples)}h", *samples))


def gunshot(seconds, generator, decay, weight):
    attack = min(1.0, seconds / 0.0015)
    noise = generator.uniform(-1, 1)
    thump = math.sin(math.tau * (65 * seconds + 3.5 * (1 - math.exp(-seconds * 55))))
    crack = noise * math.exp(-seconds * decay) * 0.65
    body = thump * math.exp(-seconds * (decay * 0.55)) * weight
    mechanism = math.sin(math.tau * 1900 * seconds) * math.exp(-seconds * 110) * 0.12
    return attack * (crack + body + mechanism)


def eat(seconds, generator):
    result = 0.0
    for start, strength in ((0.0, 0.55), (0.14, 0.42), (0.3, 0.3)):
        age = seconds - start
        if age >= 0:
            envelope = min(1.0, age / 0.003) * math.exp(-age * 42)
            crunch = generator.uniform(-1, 1) * 0.85 + math.sin(math.tau * 1350 * age) * 0.15
            result += crunch * envelope * strength
    return result


def place(seconds, generator):
    result = 0.0
    for start, strength in ((0.0, 0.65), (0.045, 0.22)):
        age = seconds - start
        if age >= 0:
            envelope = min(1.0, age / 0.001) * math.exp(-age * 35)
            knock = math.sin(math.tau * 145 * age) * 0.7 + generator.uniform(-1, 1) * 0.3
            result += knock * envelope * strength
    return result


def hurt(seconds, generator):
    envelope = min(1.0, seconds / 0.003) * math.exp(-seconds * 18)
    impact = math.sin(math.tau * (95 * seconds + 1.8 * (1 - math.exp(-seconds * 35))))
    scrape = generator.uniform(-1, 1) * math.exp(-seconds * 35)
    grunt = math.sin(math.tau * 170 * seconds) * math.exp(-seconds * 10)
    return envelope * (impact * 0.5 + scrape * 0.35 + grunt * 0.15)


def chop(seconds, generator):
    envelope = min(1.0, seconds / 0.0015) * math.exp(-seconds * 28)
    wood = math.sin(math.tau * 210 * seconds) + 0.4 * math.sin(math.tau * 480 * seconds)
    return envelope * (wood * 0.36 + generator.uniform(-1, 1) * 0.3)


def wood_break(seconds, generator):
    result = 0.0
    for start, strength in ((0, 0.5), (0.055, 0.4), (0.12, 0.3), (0.21, 0.2)):
        age = seconds - start
        if age >= 0:
            result += min(1, age / 0.002) * math.exp(-age * 24) * strength * (generator.uniform(-1, 1) * 0.7 + math.sin(math.tau * 125 * age) * 0.3)
    return result


def hit(seconds, generator):
    envelope = min(1.0, seconds / 0.002) * math.exp(-seconds * 24)
    impact = math.sin(math.tau * (110 * seconds + 2 * (1 - math.exp(-seconds * 50))))
    return envelope * (impact * 0.6 + generator.uniform(-1, 1) * 0.3)


def swing(seconds, generator, monster=False):
    center = 0.1 if monster else 0.065
    envelope = math.exp(-((seconds - center) / (0.055 if monster else 0.035)) ** 2)
    frequency = 85 if monster else 800
    return envelope * (generator.uniform(-1, 1) * 0.38 + math.sin(math.tau * frequency * seconds) * (0.3 if monster else 0.07))


def axe_sweep(seconds, generator):
    first = math.exp(-((seconds - 0.065) / 0.035) ** 2)
    second = math.exp(-((seconds - 0.18) / 0.045) ** 2) * 0.8
    envelope = first + second
    tone = math.sin(math.tau * (1100 * seconds - 800 * seconds * seconds))
    return envelope * (generator.uniform(-1, 1) * 0.48 + tone * 0.055)


def monster_death(seconds, generator):
    envelope = min(1.0, seconds / 0.015) * math.exp(-seconds * 6)
    voice = math.sin(math.tau * (155 * seconds - 85 * seconds * seconds))
    rumble = math.sin(math.tau * 58 * seconds) * 0.3
    return envelope * (voice * 0.4 + rumble + generator.uniform(-1, 1) * 0.17)


def explosion(seconds, generator):
    envelope = min(1.0, seconds / 0.002) * math.exp(-seconds * 7)
    rumble = math.sin(math.tau * (48 * seconds + 1.8 * (1 - math.exp(-seconds * 35))))
    crackle = generator.uniform(-1, 1) * math.exp(-seconds * 5)
    return envelope * (rumble * 0.48 + crackle * 0.42)


def throw(seconds, generator):
    envelope = math.sin(math.pi * min(1, seconds / .22)) ** 2
    return envelope * (generator.uniform(-1, 1) * .22 + math.sin(math.tau * 380 * seconds) * .04)


def chainsaw(seconds, generator):
    envelope = min(1.0, seconds / .025) * min(1.0, (.3 - seconds) / .04)
    engine = math.sin(math.tau * (95 * seconds + .3 * math.sin(math.tau * 12 * seconds)))
    teeth = math.sin(math.tau * 760 * seconds) * .14 + math.sin(math.tau * 1480 * seconds) * .08
    return envelope * (engine * .26 + teeth + generator.uniform(-1, 1) * .12)


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    export("handgun", 0.23, lambda seconds, generator: gunshot(seconds, generator, 36, 0.3))
    export("shotgun", 0.4, lambda seconds, generator: gunshot(seconds, generator, 18, 0.4))
    export("rifle", 0.16, lambda seconds, generator: gunshot(seconds, generator, 50, 0.22))
    export("eat", 0.48, eat)
    export("place", 0.22, place)
    export("hurt", 0.3, hurt)
    export("chop", 0.2, chop)
    export("break", 0.4, wood_break)
    export("hit", 0.25, hit)
    export("axe", 0.3, axe_sweep)
    export("chainsaw", 0.3, chainsaw)
    export("monster_attack", 0.3, lambda seconds, generator: swing(seconds, generator, monster=True))
    export("monster_death", 0.65, monster_death)
    export("throw", 0.22, throw)
    export("explosion", 0.65, explosion)
    print(f"Exported 15 replaceable WAV sound effects to {DESTINATION}")


if __name__ == "__main__":
    main()
