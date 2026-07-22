import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"

STRATEGY_PATH = CONFIG_DIR / "strategy.json"
SETTINGS_PATH = CONFIG_DIR / "settings.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


STRATEGY = load_json(STRATEGY_PATH)
SETTINGS = load_json(SETTINGS_PATH)

DIRECTORIES = SETTINGS.get("directories", {})
OUTPUT_DIR = BASE_DIR / DIRECTORIES.get("output_directory", "data/exports")
CACHE_DIR = BASE_DIR / DIRECTORIES.get("cache_directory", "data/cache")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BENCHMARKS = STRATEGY["benchmarks"]

MARKET_CAP_CONFIG = STRATEGY["universe"]["market_cap"]
MIN_MARKET_CAP = MARKET_CAP_CONFIG["minimum"]
SWEET_SPOT_MIN = MARKET_CAP_CONFIG["sweet_spot_min"]
SWEET_SPOT_MAX = MARKET_CAP_CONFIG["sweet_spot_max"]
MAX_MARKET_CAP = MARKET_CAP_CONFIG["maximum"]

SECTOR_BONUSES = STRATEGY["sector_bonus"]
WEIGHTS = STRATEGY["weights"]
SCORING_CONFIG = STRATEGY["scoring"]
