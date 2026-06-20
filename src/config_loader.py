"""Load and validate config.yaml."""

import os
import yaml
from datetime import date
from pathlib import Path


def load(path: str = "config.yaml") -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path.resolve()}")
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    # Resolve file paths relative to config file's directory
    base = config_path.parent
    for key in ("workbook", "sync_state", "sync_log"):
        val = cfg["paths"][key]
        if not os.path.isabs(val):
            cfg["paths"][key] = str(base / val)

    # Parse rate schedule dates
    for entry in cfg["profit_share"]["rate_schedule"]:
        if isinstance(entry["effective_date"], str):
            entry["effective_date"] = date.fromisoformat(entry["effective_date"])

    return cfg


def profit_share_rate(cfg: dict, txn_date: date, supplier: str) -> float:
    """Return the profit-share rate for a given date and supplier (0 if not covered)."""
    covered = {s.lower() for s in cfg["profit_share"]["covered_suppliers"]}
    if supplier.lower() not in covered:
        return 0.0
    schedule = sorted(cfg["profit_share"]["rate_schedule"],
                      key=lambda e: e["effective_date"])
    rate = 0.0
    for entry in schedule:
        if txn_date >= entry["effective_date"]:
            rate = entry["rate"]
    return rate
