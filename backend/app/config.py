"""DealPilot AI Configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file safely if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    try:
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
    except Exception:
        pass

DB_PATH = os.environ.get("DEALPILOT_DB_PATH", str(BASE_DIR / "dealpilot.db"))
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
PORT = int(os.environ.get("DEALPILOT_PORT", "8000"))
SECRET_KEY = os.environ.get("DEALPILOT_SECRET_KEY", "dealpilot-secret-key-3690")
