#!/usr/bin/env python3
"""Entry point — run by cron daily."""
import logging
import os
import sys

os.makedirs("swiftcart/logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("swiftcart/logs/run.log"),
    ],
)

from swiftcart.scheduler import run_daily

if __name__ == "__main__":
    run_daily()
