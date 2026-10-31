"""06_charts.py - Poster figures (300 dpi PNG + SVG) from results/.

Figures:
    fig_outcomes.png   stacked bars per policy: where each receipt ended
                       (local T1 / local VLM T2 / cloud cheap T3 / cloud strong T4 / review),
                       with accepted-precision labels
    fig_sweep.png      escalation curve: cloud share vs accepted precision for the
                       router and the harness across tau, with oracle and all-cloud marks
    fig_waterfall.png  per VLM tier: model errors -> caught by code -> leaked

Color roles follow the data-viz reference palette (categorical slots in fixed
order; review in muted ink). Poster fonts are sans-serif (Arial).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "results" / "harness"
FIG = ROOT / "results" / "figures"

sys.path.insert(0, str(ROOT / "src"))
from harness import palette as PAL  # noqa: E402

# One palette for poster, charts and pages: local = navy family, cloud = burgundy family, review = grey.
C = {**PAL.TIER, "ink": PAL.INK, "ink2": PAL.INK2, "muted": PAL.MUTED, "grid": PAL.GRID, "surface": "#ffffff",
     "critical": PAL.BAD, "good": PAL.GOOD}
LABEL = {"T1": "Local OCR + rules", "T2": "Local VLM (Qwen2.5-VL 3B)", "T3": "Cloud, cheap (Gemini 3.1 Flash-Lite)",
         "T4": "Cloud, strong (Gemini 3.6 Flash)", "review": "Human review"}
POLICY_LABEL = {"all_local": "All local", "all_qwen": "All local VLM", "all_lite": "All cloud (cheap)",
                "all_strong": "All cloud (strong)", "router": "Router, no checks", "harness": "Harness",
                "harness_ladder": "Harness + local VLM", "oracle": "Oracle router", "local_only": "Local only + checks"}

plt.rcParams.update({
    "font.family": "Arial", "font.size": 9, "axes.edgecolor": "#c3c2b7", "axes.linewidth": 0.8,
    "axes.labelcolor": C["ink2"], "xtick.color": C["ink2"], "ytick.color": C["ink2"],
    "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white",
})


def _load(name: str):
    return json.loads((H / name).read_text(encoding="utf-8"))


def fig_outcomes(policies: list[dict]) -> None:
    """Wide and short so it fills a poster column: one-row legend on top, two
    labelled number columns on the right (accepted correct, USD per 1k)."""
    order = ["all_local", "local_only", "all_lite", "all_strong", "router", "harness", "harness_ladder"]
    rows = [p for o in order for p in policies if p["policy"] == o]
    short = {"T1": "Local OCR + rules", "T2": "Local VLM", "T3": "Cloud, cheap", "T4": "Cloud, strong", "review": "Human review"}
    fig, ax = plt.subplots(figsize=(6.6, 3.5), dpi=300)
    y = list(range(len(rows)))[::-1]
    left = [0.0] * len(rows)
    for tier in ("T1", "T2", "T3", "T4"):
        vals = [p["tier_share"][tier] * 100 for p in rows]
        ax.barh(y, vals, left=left, color=C[tier], height=0.64, label=short[tier], edgecolor="white", linewidth=1.2)
        left = [l + v for l, v in zip(left, vals)]
    vals = [p["review_share"] * 100 for p in rows]
    ax.barh(y, vals, left=left, color=C["review"], height=0.64, label=short["review"], edgecolor="white", linewidth=1.2)
    xp, xc = 104, 128                                   # number columns, in data units past the 100% axis
    for yi, p in zip(y, rows):
        prec, cost = p["accepted_money_precision"], p.get("cost_usd_per_1k")
        if prec is not None:
            ax.text(xp, yi, f"{prec*100:.1f}%", va="center", ha="left", fontsize=11, color=C["ink"], fontweight="bold", clip_on=False)
        if cost is not None:
            ax.text(xc, yi, f"${cost:.2f}", va="center", ha="left", fontsize=11, color=C["ink2"], clip_on=False)
    top = max(y) + 0.62
    ax.text(xp, top, "accepted\ncorrect", va="bottom", ha="left", fontsize=8, color=C["ink2"], clip_on=False, linespacing=1.0)
    ax.text(xc, top, "USD\n/ 1k", va="bottom", ha="left", fontsize=8, color=C["ink2"], clip_on=False, linespacing=1.0)
    ax.set_yticks(y)
    ax.set_yticklabels([POLICY_LABEL[p["policy"]] for p in rows], fontsize=11, color=C["ink"])
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.tick_params(axis="x", labelsize=9.5)
    ax.set_xlabel("share of 300 receipts (%)", fontsize=10)
    ax.xaxis.grid(True, color=C["grid"], linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.55, -0.21), ncol=5, frameon=False, fontsize=9.5,
              handlelength=1.1, handletextpad=0.4, columnspacing=1.0)
    fig.subplots_adjust(left=0.24, right=0.80, bottom=0.24, top=0.9)
    fig.savefig(FIG / "fig_outcomes.png", bbox_inches="tight")
    fig.savefig(FIG / "fig_outcomes.svg", bbox_inches="tight")
    plt.close(fig)


def fig_sweep(sweep: list[dict], policies: list[dict]) -> None:
    fig, ax = plt.subplots(figsize=(5.0, 2.2), dpi=300)                 # wide and short: fits a poster side column
    import os
    variant = os.environ.get("SWEEP_VARIANT", "")          # "" (agree) or "_solo"
    for pol, color, name in ((f"router{variant}", C["muted"], "Router, no checks"), (f"harness{variant}", C["T1"], "Harness, code checks")):
        pts = sorted({(round(s["cloud_sent_share"] * 100, 2), round(s["accepted_money_precision"] * 100, 2), s["tau"]) for s in sweep
                      if s["policy"] == pol and s["accepted_money_precision"] is not None})
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, linewidth=2.2, marker="o", markersize=4.5, label=name)
        if pts:
            for i, (x, yv, tau) in enumerate((pts[0], pts[-1])):
                if pol.startswith("router"):
                    off, ha = (4, -9), "left"
                elif i == 0:                                   # harness start: up-left, clear of the rising line
                    off, ha = (-4, 4), "right"
                else:
                    off, ha = (4, 5), "left"
                ax.annotate(f"τ={tau:g}", (x, yv), textcoords="offset points", xytext=off, ha=ha,
                            fontsize=8, color=C["ink2"])
    lr = H / ".." / "learned_router" / "curve.json"
    if lr.exists():
        pts = sorted({(round(q["cloud_share"] * 100, 2), round(q["accepted_precision"] * 100, 2))
                      for q in json.loads(lr.read_text(encoding="utf-8"))["points"]})
        ax.plot([q[0] for q in pts], [q[1] for q in pts], color=C["T3"], linewidth=1.6, linestyle="--",
                label="Learned signal (out of fold)")
    by = {p["policy"]: p for p in policies}
    for key, marker, name in (("oracle", "*", "Oracle router"), ("all_lite", "s", "All cloud (cheap)"), ("all_local", "D", "All local")):
        p = by.get(key)
        if p and p["accepted_money_precision"] is not None:
            ax.scatter([p["cloud_sent_share"] * 100], [p["accepted_money_precision"] * 100], marker=marker, s=64,
                       color=C["ink"], zorder=5, label=name)
    ax.set_xlabel("receipts sent to the cloud (%)", fontsize=9.5)
    ax.set_ylabel("accepted correct (%)", fontsize=9.5)
    ax.set_ylim(70, 101)
    ax.tick_params(labelsize=8.5)
    ax.yaxis.grid(True, color=C["grid"], linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="lower right", handlelength=1.5, labelspacing=0.3, borderaxespad=0.2)  # empty corner: curves sit above 90%
    ax.set_title("How much cloud buys how much accuracy", loc="left", fontsize=10.5, color=C["ink"], pad=6)
    fig.tight_layout()
    fig.savefig(FIG / "fig_sweep.png", bbox_inches="tight")
    fig.savefig(FIG / "fig_sweep.svg", bbox_inches="tight")
    plt.close(fig)


def fig_waterfall(falls: list[dict]) -> None:
    tiers = [w for w in falls if w["n"]]
    fig, axes = plt.subplots(1, len(tiers), figsize=(1.75 * len(tiers) + 0.4, 1.9), dpi=300, sharey=False)
    if len(tiers) == 1:
        axes = [axes]
    for ax, w in zip(axes, tiers):
        tier = w["tier"].upper()
        vals = [w["model_errors"], w["errors_caught"], w["errors_leaked"]]
        colors = [C[tier], C["good"], C["critical"]]
        bars = ax.bar(["model\nerrors", "caught\nby code", "leaked"], vals, color=colors, width=0.62, edgecolor="white", linewidth=1.2)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + max(vals + [1]) * 0.03, str(v), ha="center", va="bottom", fontsize=8, color=C["ink"])
        ax.set_title(f"{LABEL[tier].split(' (')[0]}\n n={w['n']}, false flags={w['false_flags']}", fontsize=7.5, color=C["ink2"])
        ax.set_ylim(0, max(vals + [1]) * 1.3)
        ax.tick_params(axis="x", labelsize=7)
        ax.yaxis.set_visible(False)
        ax.spines["left"].set_visible(False)
    fig.suptitle("Of the model's wrong date/total answers, how many did code catch?", x=0.02, ha="left", fontsize=9.5, color=C["ink"])
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(FIG / "fig_waterfall.png", bbox_inches="tight")
    fig.savefig(FIG / "fig_waterfall.svg", bbox_inches="tight")
    plt.close(fig)


def fig_hedge(root: Path, name: str) -> None:
    f = root / "hedge" / "curve.json"
    if not f.exists():
        return
    rows = json.loads(f.read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(4.0, 2.6), dpi=300)
    for sc, color, label in ((1.0, C["T2"], "local VLM as measured (28 s median)"), (0.25, C["T1"], "local VLM 4x faster (assumed GPU)")):
        pts = [(r["D"], r["cloud_fired_share"] * 100, r["accepted_money_precision"] * 100) for r in rows if r["scale"] == sc and r["D"] != "inf" and float(r["D"]) != float("inf")]
        pts.sort()
        ax.plot([q[0] for q in pts], [q[1] for q in pts], color=color, linewidth=2, marker="o", markersize=3.5, label=label)
        for d, cs, pr in pts:
            if d in (5.0, 30.0):
                ax.annotate(f"{pr:.1f}% correct", (d, cs), textcoords="offset points", xytext=(4, 4), fontsize=6.5, color=C["ink2"])
    ax.set_xlabel("time budget D before the cloud is also called (s)")
    ax.set_ylabel("receipts that reached the cloud (%)")
    ax.yaxis.grid(True, color=C["grid"], linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=6.5)
    ax.set_title("Hedging: how a time budget moves receipts to the cloud", loc="left", fontsize=9.5, color=C["ink"], pad=8)
    fig.tight_layout()
    fig.savefig(FIG / f"fig_hedge_{name}.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    policies = _load("policies.json")
    sweep = _load("tau_sweep.json")
    falls = _load("waterfall.json")
    fig_outcomes(policies)
    fig_sweep(sweep, policies)
    fig_waterfall(falls)
    fig_hedge(ROOT / "results", "results")
    fig_hedge(ROOT / "results_wild", "results_wild")
    print("figures written to", FIG)


if __name__ == "__main__":
    main()
