"""Persist and retrieve the last-synced marker between runs."""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def _default_start(lookback_days: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    return dt.isoformat()


def load(path: str, lookback_days: int = 90) -> dict:
    p = Path(path)
    if p.exists():
        with open(p) as f:
            state = json.load(f)
        logger.info("Sync state loaded: last_synced=%s", state.get("last_synced"))
        return state
    logger.info("No sync state found; starting from %d days ago.", lookback_days)
    return {
        "last_synced": _default_start(lookback_days),
        "synced_order_ids": [],
        "synced_transaction_ids": [],
        "reconciled_group_ids": [],
    }


def save(path: str, state: dict):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Keep sets JSON-serialisable
    for key in ("synced_order_ids", "synced_transaction_ids", "reconciled_group_ids"):
        if isinstance(state.get(key), set):
            state[key] = list(state[key])
    with open(p, "w") as f:
        json.dump(state, f, indent=2, default=str)
    logger.debug("Sync state saved to %s.", path)


def mark_now(state: dict):
    state["last_synced"] = datetime.now(timezone.utc).isoformat()
