from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cold_world_game.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["test", "combat", *sys.argv[1:]]))
