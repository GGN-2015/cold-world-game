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


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    export("handgun", 0.23, lambda seconds, generator: gunshot(seconds, generator, 36, 0.3))
    export("shotgun", 0.4, lambda seconds, generator: gunshot(seconds, generator, 18, 0.4))
    export("rifle", 0.16, lambda seconds, generator: gunshot(seconds, generator, 50, 0.22))
    export("eat", 0.48, eat)
    export("place", 0.22, place)
    export("hurt", 0.3, hurt)
    print(f"Exported 6 replaceable WAV sound effects to {DESTINATION}")


if __name__ == "__main__":
    main()
