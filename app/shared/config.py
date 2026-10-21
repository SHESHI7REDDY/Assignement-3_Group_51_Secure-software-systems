from pathlib import Path

# Paths are independent of the current working directory.
BASE = Path(__file__).resolve().parents[2]
FRONTEND = BASE / "frontend"
DATA = BASE / "data"
