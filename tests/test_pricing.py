"""pricing.py: the kept home of the price table and photo_price."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import pricing  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("  OK   " if cond else "  FAIL ") + name + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(name)


kie = pricing.photo_price("kie")
check("kie_price", kie["image"]["credits"] == 24, str(kie))
check("kie_usd", abs(kie["image"]["usd"] - 0.12) < 1e-9)
check("check_price", kie["check"] == {"usd": 0.01, "confidence": "estimated"})
check("higgsfield_unknown", "unknown" in pricing.photo_price("higgsfield")["label"])
check("higgsfield_no_credits", pricing.photo_price("higgsfield")["image"]["credits"] is None)
check("estimate_moved", pricing.estimate("nano-banana-pro", 2)[0] == 48)
check("null_credit_model_is_none", pricing.estimate("openrouter-vision-check", 1)[0] is None)

print()
if fails:
    print("FAILED: " + ", ".join(fails))
    sys.exit(1)
print("ALL PRICING CHECKS PASSED")
