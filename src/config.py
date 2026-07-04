"""Small helper for loading config.yaml consistently across the pipeline."""
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"
OUTPUT_DIR = REPO_ROOT / "output"
TEMPLATES_DIR = REPO_ROOT / "templates"


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    path = Path(path)
    with open(path) as f:
        cfg = yaml.safe_load(f)

    weights = [a["weight"] for a in cfg["portfolio"]["assets"]]
    total = sum(weights)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Portfolio weights in {path} sum to {total}, expected 1.0")

    OUTPUT_DIR.mkdir(exist_ok=True)
    return cfg


def tickers(cfg: dict) -> list[str]:
    return [a["ticker"] for a in cfg["portfolio"]["assets"]]


def weights(cfg: dict):
    import numpy as np
    return np.array([a["weight"] for a in cfg["portfolio"]["assets"]])
