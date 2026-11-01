"""Prices for everything the studio can spend on. Standard library only.

Seed figures live in pricing.json (credits, with a confidence label). This
module reads them and answers "roughly what will this cost" before a click.

Usage:
    python tools/pricing.py            # price of one photo per provider
"""

import json
import os
import sys
from pathlib import Path

# Overridable so a suite can price against a disposable copy (a real charge
# must never overwrite the seed file during a test run).
PRICING_PATH = Path(os.environ.get("AIVS_PRICING_FILE")
                    or (Path(__file__).resolve().parent / "pricing.json"))

USD_PER_CREDIT = 0.005
CHECK_MODEL = "openrouter-vision-check"


def load_pricing():
    with PRICING_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def estimate(model, units, pricing=None, **options):
    """(credits, confidence, note) for `units` images or seconds.

    `units` is images for an image model and seconds for a video one, which is
    what the table's `unit` field says. Returns None credits when the model is
    not in the table (or has no credit price) rather than inventing a number.
    """
    pricing = pricing or load_pricing()
    cfg = (pricing.get("models") or {}).get(model)
    if not cfg:
        return None, "unknown", "{} is not in pricing.json".format(model)
    if cfg.get("credits_per_unit") is None:
        return None, cfg.get("confidence", "unknown"), cfg.get("note", "")

    total = float(cfg.get("credits_per_unit", 0)) * float(units)
    for name, table in (cfg.get("multipliers") or {}).items():
        value = options.get(name)
        if value is None:
            continue
        key = str(value).lower() if isinstance(value, bool) else str(value)
        for candidate, factor in table.items():
            if str(candidate).lower() == key.lower():
                total *= float(factor)
                break
    return round(total), cfg.get("confidence", "estimated"), cfg.get("note", "")


def photo_price(provider, resolution="1K"):
    """What one photo costs: the image itself plus the picture check."""
    pricing = load_pricing()
    check_cfg = (pricing.get("models") or {}).get(CHECK_MODEL) or {}
    check = {"usd": float(check_cfg.get("usd_per_unit", 0.01)),
             "confidence": "estimated"}
    if provider == "kie":
        credits, confidence, _ = estimate("nano-banana-pro", 1, pricing,
                                          resolution=resolution)
        usd = None if credits is None else round(credits * USD_PER_CREDIT, 4)
        return {"image": {"credits": credits, "usd": usd, "confidence": confidence},
                "check": check,
                "label": "about ${:.2f}".format(usd) if usd is not None
                else "unknown"}
    return {"image": {"credits": None, "usd": None, "confidence": "unknown"},
            "check": check,
            "label": "unknown, billed by Higgsfield"}


if __name__ == "__main__":
    for name in ("kie", "higgsfield"):
        print(name, json.dumps(photo_price(name)))
    sys.exit(0)
