"""Intentionally problematic Python fixture — issues expected by tests.

Issues this file contains:
  - nested loop (nested_loop)
  - unused import (unused_import)
  - long function >50 lines (long_function)
"""

import os          # used
import sys         # unused — should be flagged
import json        # unused — should be flagged


def find_duplicates(items: list) -> list:
    """Find duplicates using a nested loop — O(n²)."""
    duplicates = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):     # nested loop → flagged
            if items[i] == items[j] and items[i] not in duplicates:
                duplicates.append(items[i])
    return duplicates


def long_function_example(data: list) -> dict:
    """Intentionally long function exceeding 50 lines."""
    result = {}

    # Block 1 — basic processing
    processed = []
    for item in data:
        if item is not None:
            processed.append(item)

    # Block 2 — categorise
    categories: dict = {}
    for item in processed:
        key = str(type(item).__name__)
        if key not in categories:
            categories[key] = []
        categories[key].append(item)

    # Block 3 — count
    counts = {k: len(v) for k, v in categories.items()}

    # Block 4 — build summary
    summary = []
    for k, v in counts.items():
        summary.append(f"{k}: {v}")

    # Block 5 — fake enrichment
    enriched = {}
    for k, v in categories.items():
        enriched[k] = {
            "count": len(v),
            "items": v,
            "label": k.upper(),
        }

    # Block 6 — merge
    result["categories"] = categories
    result["counts"] = counts
    result["summary"] = summary
    result["enriched"] = enriched
    result["total"] = len(processed)
    result["path"] = os.getcwd()

    # Block 7 — padding to exceed 50 lines
    result["extra_1"] = None
    result["extra_2"] = None
    result["extra_3"] = None
    result["extra_4"] = None
    result["extra_5"] = None

    return result
