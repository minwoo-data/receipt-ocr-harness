"""palette.py - one color set for the poster, charts, workflow pages, companion and landing page.

Meaning, not decoration: local readers are one blue family (T1 strong, T2 light),
cloud readers one orange family (T3 strong, T4 light), human review is grey.
The accent is the T1 blue. Keep poster/poster.template.html :root in step.
"""

TIER = {"T1": "#2a78d6", "T2": "#8cb9ee", "T3": "#eb6834", "T4": "#f5ad83", "review": "#a9adb3"}
TIER_TINT = {"T1": "#dce9fa", "T2": "#eaf3fd", "T3": "#fde3d6", "T4": "#fdeee5", "review": "#f0f1f2"}
INK, INK2, MUTED, GRID = "#0f1217", "#4f5663", "#8a909a", "#dde1e6"
ACCENT = TIER["T1"]
ACCENT_TEXT = "#1d62b8"                  # accent for small text on white (contrast >= 4.5:1)
CLOUD_TEXT = "#c4501f"                   # orange for small text on white
GOOD, BAD = "#0ca30c", "#6b7079"         # accept label green; review is grey, not red
