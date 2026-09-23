#!/usr/bin/env python3
"""The regression command. Passes before any task runs and must still pass after."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shop import inventory, pricing, report  # noqa: E402

PASS = []


def check(name, cond):
    PASS.append(bool(cond))
    print(f"[{'OK' if cond else 'FAIL'}] {name}")


check("a line total multiplies", pricing.line_total(3.0, 4) == 12.0)
check("an order applies tax", abs(pricing.order_total([(10.0, 1)]) - 10.7) < 1e-9)
check("a reservation reduces stock", inventory.reserve({"a": 5}, "a", 2) == 3)
check("a release increases stock", inventory.release({"a": 1}, "a", 2) == 3)
check("money formats two places", report.money(1.5) == "$1.50")
check("percent formats one place", report.percent(1, 4) == "25.0%")

print(f"\n{sum(PASS)}/{len(PASS)} checks passed")
sys.exit(0 if all(PASS) else 1)
