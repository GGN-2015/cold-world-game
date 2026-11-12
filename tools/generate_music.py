import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.request
import wave

import mido
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "tools" / "music"
DESTINATION = ROOT / "cold_world_game" / "static" / "music"
SAMPLE_RATE = 22050


def score_source(definition, download):
    score = SOURCES / (definition["id"] + ".mid")
    credit = SOURCES / (definition["id"] + ".json")
    if download or not score.exists() or not credit.exists():
        page = f"https://www.mutopiaproject.org/cgibin/piece-info.cgi?id={definition['piece_id']}"
        source = urllib.request.urlopen(page, timeout=60).read().decode("utf-8")
        copyright_cell = re.search(r"Copyright:</b>(.*?)</td>", source, re.S).group(1)
        if "Public Domain" not in copyright_cell:
            raise ValueError("The selected score is not marked Public Domain: " + page)
        url = re.search(r'href="(https://[^\"]+\.mid)"', source).group(1)
        content = urllib.request.urlopen(url, timeout=60).read()
        if not content.startswith(b"MThd"):
            raise ValueError("Invalid MIDI score: " + url)
        maintainer = re.search(r"Maintainer:</b>(.*?)</td>", source, re.S).group(1)
        metadata = {"page": page, "midi": url, "license": "Public Domain", "maintainer": html.unescape(re.sub("<[^>]+>", "", maintainer)).strip(), "sha256": hashlib.sha256(content).hexdigest()}
        score.write_bytes(content)
        credit.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata = json.loads(credit.read_text(encoding="utf-8"))
    if metadata.get("license") != "Public Domain":
        raise ValueError("The cached score is not marked Public Domain: " + str(credit))
    if hashlib.sha256(score.read_bytes()).hexdigest() != metadata["sha256"]:
        raise ValueError("MIDI source checksum mismatch: " + str(score))
    return score, metadata


def notes_from(score):
    active = {}
    notes = []
    elapsed = 0.0
    for message in mido.MidiFile(score):
        elapsed += message.time
        if message.type not in {"note_on", "note_off"}:
            continue
        key = message.channel, message.note
        if message.type == "note_on" and message.velocity:
            active.setdefault(key, []).append((elapsed, message.velocity))
        elif active.get(key):
            started, velocity = active[key].pop(0)
            notes.append((started, max(0.03, elapsed - started), message.note, velocity))
    for (channel, pitch), held in active.items():
        notes.extend((started, max(0.03, elapsed - started), pitch, velocity) for started, velocity in held)
    return notes, elapsed


def piano_note(pitch):
    frequency = 440 * 2 ** ((pitch - 69) / 12)
    duration = max(1.5, min(5.0, 4.5 - (pitch - 36) * 0.035))
    times = np.arange(round(duration * SAMPLE_RATE), dtype=np.float32) / SAMPLE_RATE
    result = np.zeros(times.size, dtype=np.float32)
    for harmonic in range(1, 14):
        overtone = frequency * harmonic * (1 + 0.000025 * harmonic ** 2) ** 0.5
        if overtone >= SAMPLE_RATE * 0.45:
            break
        decay = np.exp(-times * (0.8 + harmonic * 0.48 + frequency / 1800))
        strength = (1.0 if harmonic == 1 else 0.75 if harmonic == 2 else 0.45 / (harmonic - 1))
        for detune in (-0.0009, 0.0007):
            result += strength * decay * np.sin(2 * np.pi * overtone * (1 + detune) * times + harmonic * 0.17) * 0.5
    result *= np.minimum(1, times / 0.004)
    return result * 0.17


def render(score, destination, start=0, length=180):
    notes, full_duration = notes_from(score)
    duration = min(length, max(0, full_duration - start))
    if duration <= 1:
        raise ValueError("Music excerpt has no playable score")
    mixed = np.zeros(round((duration + 1) * SAMPLE_RATE), dtype=np.float32)
    samples = {}
    for began, held, pitch, velocity in notes:
        began -= start
        if began + held < 0 or began >= duration:
            continue
        if pitch not in samples:
            samples[pitch] = piano_note(pitch)
        sample = samples[pitch]
        count = min(sample.size, round((held + 0.22) * SAMPLE_RATE))
        voice = sample[:count].copy()
        release = min(count, round(0.22 * SAMPLE_RATE))
        voice[-release:] *= np.linspace(1, 0, release, dtype=np.float32) ** 2
        offset = round(began * SAMPLE_RATE)
        trim = max(0, -offset)
        offset = max(0, offset)
        count = min(count - trim, mixed.size - offset)
        if count > 0:
            mixed[offset:offset + count] += voice[trim:trim + count] * (velocity / 100) ** 1.35
    for delay, gain in ((0.027, 0.1), (0.047, 0.07), (0.083, 0.045)):
        shift = round(delay * SAMPLE_RATE)
        mixed[shift:] += mixed[:-shift].copy() * gain
    mixed = np.tanh(mixed)
    mixed *= 0.78 / max(0.001, float(np.max(np.abs(mixed))))
    fade = min(round(SAMPLE_RATE * 2), mixed.size // 3)
    mixed[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
    mixed[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    with tempfile.TemporaryDirectory(prefix="cold-world-piano-") as folder:
        wave_path = Path(folder) / "piano.wav"
        with wave.open(str(wave_path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(SAMPLE_RATE)
            output.writeframes((mixed * 32767).astype("<i2").tobytes())
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wave_path), "-codec:a", "libmp3lame", "-b:a", "64k", "-map_metadata", "-1", str(destination)], check=True)
    return round(mixed.size / SAMPLE_RATE, 3)


def main():
    parser = argparse.ArgumentParser(description="Render public-domain piano scores to bundled, sample-free BGM")
    parser.add_argument("--download", action="store_true", help="Refresh and verify Public Domain score sources")
    options = parser.parse_args()
    DESTINATION.mkdir(parents=True, exist_ok=True)
    tracks = []
    for definition in json.loads((SOURCES / "sources.json").read_text(encoding="utf-8")):
        score, credit = score_source(definition, options.download)
        destination = DESTINATION / (definition["id"] + ".mp3")
        duration = render(score, destination, definition.get("start_seconds", 0))
        tracks.append({**definition, "file": destination.name, "duration": duration, "bytes": destination.stat().st_size, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "source": credit})
        print(f"Rendered {destination.name}: {duration:g}s, {destination.stat().st_size} bytes", flush=True)
    (DESTINATION / "manifest.json").write_text(json.dumps({"license": "CC0-1.0", "performance": "Cold World deterministic procedural piano; no recorded samples", "tracks": tracks}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
