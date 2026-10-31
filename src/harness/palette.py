"""palette.py - one color set for the poster, charts, workflow pages, companion and landing page.

Meaning, not decoration: local readers are one navy family (T1 dark, T2 light),
cloud readers one burgundy family (T3 dark, T4 light), human review is grey.
The accent is the same navy as T1. Keep poster/poster.template.html :root in step.
"""

TIER = {"T1": "#1f3a5f", "T2": "#7d9cc6", "T3": "#8c2f39", "T4": "#d39aa0", "review": "#a9adb3"}
TIER_TINT = {"T1": "#e3e9f1", "T2": "#eef2f8", "T3": "#f4e4e6", "T4": "#f9eff0", "review": "#f0f1f2"}
INK, INK2, MUTED, GRID = "#14181f", "#4f5663", "#8a909a", "#dde1e6"
ACCENT = TIER["T1"]
GOOD, BAD = "#2f6b3a", "#8c2f39"        # used sparingly for accept / review labels
