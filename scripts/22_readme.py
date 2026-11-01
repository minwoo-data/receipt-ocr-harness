"""22_readme.py - fill the generated blocks of README.md from src/harness/report_numbers.py.

Every table or sentence with a number sits between <!-- gen:NAME --> and <!-- /gen:NAME -->; this
script rewrites what is between the markers and nothing else, and fails if a marker is missing.
    python scripts/22_readme.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from harness.report_numbers import corrections, numbers  # noqa: E402

V = numbers()


def table(head: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def block_correction() -> str:
    corr = corrections(V)
    rows = [[r["label"], r["printed"], r["now"]] for r in corr]
    moved = {r["key"] for r in corr}
    same = [txt for k, txt in (("precA", f"{V['precA']} correct"), ("revA", f"{V['revA']} review"),
                               ("cloud_gap", f"{V['cloud_gap']} points below all-cloud")) if k not in moved]
    unchanged = f"Unchanged: the harness on scans, {', '.join(same)}." if same else ""
    return (f"**Corrected after printing, 2026-10-31.** The poster PDF is unchanged; the numbers below are the ones it printed that moved. "
            f"Cause: `src/harness/normalize.py`, which turns printed text into dates and amounts, misread four-digit amounts without a "
            f"thousands separator (`1039.00` as 103), decimal commas (`6,60` as 6.0), years written `Jul28'15`, and dates that were "
            f"repeated or glued to a time. It parses both the WildReceipt answer key and T1's OCR text, so {V['wild_fixed_values']} labels on "
            f"{V['wild_fixed_receipts']} WildReceipt receipts were wrong (`data/manifest/wild200_gt_corrections.jsonl`; the SROIE answer key had none) "
            f"and T1 missed dates printed with the time attached. Two changes came with the fix: T1's self-signal and the learned features are "
            f"recomputed with the current rules (`rules.refresh`), and in the policies with code checks T1's own date must pass the date check "
            f"before T1 is accepted. That check changes no number on real receipts; before it, a synthetic receipt dated two years ahead that "
            f"both OCR readers read the same way was auto-accepted at T1 without any check. {unchanged}\n\n"
            + table(["Number", "Printed", "Now"], rows))


def block_ladder() -> str:
    readers = [("1", "RapidOCR + rules (Tesseract as 2nd witness)", "local CPU", "T1"),
               ("2", "Qwen2.5-VL 3B via Ollama (Vulkan, RTX 2050 4 GB)", "local GPU", "T2"),
               ("3", "Gemini 3.1 Flash-Lite", "cloud", "T3"), ("4", "Gemini 3.6 Flash, thinking off", "cloud", "T4")]
    return table(["Tier", "Reader", "Where", "Date + total correct, SROIE 300", "Phone photos, Wild 200", "Median latency", "USD per 1k"],
                 [[n, r, w, V[f"a{t}"], V[f"w{t}"], f"{V[f's{t}']} s", V[f"c{t}"]] for n, r, w, t in readers])


def block_routing() -> str:
    rows = [[r["label"], r["accept"], r["review"], r["sent"], r["prec"], r["leaks_1k"], r["api"], r["people"], r["total"]] for r in V["routing_rows"]]
    return (table(["Policy", "Auto-accept", "Review", "Sent to cloud", "Accepted answers correct", "Wrong, auto-accepted per 1k",
                   "API USD per 1k", "People USD per 1k", "Total USD per 1k"], rows)
            + f"\n\nPeople's time is an assumption, not a measurement: {V['review_min']} min to key the date and total of a reviewed receipt at "
            f"${V['review_wage']}/h, ${V['review_usd']} per review (`REVIEW_MINUTES`, `REVIEW_WAGE_USD_H` in `src/harness/report_numbers.py`, or the "
            f"environment variables `HARNESS_REVIEW_MINUTES`, `HARNESS_REVIEW_WAGE_USD_H`). API cost is measured. Once people are priced, all-cloud "
            f"is the cheapest policy on scans: the harness saves ${V['api_saved']} of API per 1,000 receipts and sends {V['revA']} of them to people, "
            f"so it breaks even only if a review costs under ${V['breakeven_usd']} ({V['breakeven_s']} s of a person's time at ${V['review_wage']}/h). "
            f"The harness's case is where the images go ({V['t1i']} never leave the machine; local only keeps all of them, for "
            f"${V['totB']} per 1,000 in people's time), not its price.")


def block_uncertainty() -> str:
    rows = [["SROIE 300", f"{V['precA']} ({V['ciA']})", f"{V['precB']} ({V['ciB']})", f"{V['aT3']} ({V['ciT3']})",
             f"{V['gapA']} ({V['gapA_ci']})", f"{V['gapB']} ({V['gapB_ci']})"],
            ["Wild 200", f"{V['wA']} ({V['wciA']})", f"{V['wB']} ({V['wciB']})", f"{V['wT3']} ({V['wciT3']})",
             f"{V['wgapA']} ({V['wgapA_ci']})", f"{V['wgapB']} ({V['wgapB_ci']})"]]
    noise = lambda zero: "inside the sampling noise (its interval spans zero)" if zero else "larger than the sampling noise"  # noqa: E731
    photos = ("neither gap is distinguishable from zero" if V["wgapA_zero"] and V["wgapB_zero"] else
              f"the gap to all-cloud is {noise(V['wgapA_zero'])} and the gap to local only is {noise(V['wgapB_zero'])}")
    return (f"One run, so the uncertainty measured here is which receipts happened to be sampled: 95% percentile bootstrap, {V['boot_B']} "
            f"resamples of receipts, every policy replayed on the same resample so the differences are paired (`scripts/20_bootstrap.py`, "
            f"`results*/harness/bootstrap.json`).\n\n"
            + table(["Set", "Harness: accepted correct", "Local only", "All cloud, cheap", "All cloud minus harness, points",
                     "Harness minus local only, points"], rows)
            + f"\n\nOn scans the harness sends {V['sent']} ({V['ci_sentA']}) to the cloud and {V['revA']} ({V['ci_revA']}) to people, "
            f"at ${V['costA']} ({V['ci_costA']}) per 1,000. Reading: on scans the {V['cloud_gap']}-point gap to all-cloud is "
            f"{noise(V['gapA_zero'])}, and the {V['scan_gap']}-point gap between the harness and local only is {noise(V['gapB_zero'])}. "
            f"On photos {photos}. "
            + ("The API saving holds across the interval: its upper end is below the all-cloud price."
               if float(V["ci_costA"].split("–")[1]) < float(V["cT3"]) else "The API saving is not robust to the sample."))


def block_checks() -> str:
    return table(["Reader", "Wrong date/total answers", "Caught by code", "Leaked", "False flags"],
                 [[r["reader"], r["errors"], f"{r['caught']} ({r['pct']})", r["leaked"], r["false"]] for r in V["waterfall_rows"]])


def block_backstop() -> str:
    a = V["bs_audit"]
    rc = V["bs_recheck"]
    full, wfull = rc[-1], V["wbs_recheck"][-1]
    return (f"A leak is an auto-accepted answer that is wrong. In cloud mode on scans there are {V['bs_leaksA']} in {V['n']}: "
            f"{V['bs_leaksA_T1']} accepted at T1, where both OCR readers agreed on the same wrong answer, and {V['bs_small']} off by less than "
            f"0.10 (Malaysian 0.05 rounding), {V['bs_misstated']} misstated in all. Two backstops, replayed offline on the cached reads "
            f"(`scripts/19_backstop.py`, `results*/backstop/summary.md`):\n\n"
            "Random audit: a person re-keys a random share of auto-accepted receipts.\n\n"
            + table(["Audit", "Audited per 1k", "Leaks caught per 1k (expected)", "Share of leaks caught", f"P(finds at least one leak in this run of {V['n']})", "People USD per 1k"],
                    [[x["p"], x["per_1k"], x["caught_1k"], x["share"], x["p_find"], x["people_1k"]] for x in a])
            + "\n\nAmount-ranked re-read: the top X% of auto-accepted receipts by accepted total (no answer key needed to rank) are re-read "
            "by T4; if T4's date or total differs, the receipt goes to a person.\n\n"
            + table(["Top X% by total", "Re-read by T4", "Leaks caught", "Correct answers sent to people", "Extra API USD per 1k",
                     "Extra people USD per 1k", "Extra images to the cloud", "Misstated amount covered"],
                    [[x["x"], x["reread"], f"{x['caught']} of {x['of']}", x["false"], x["usd_1k"], x["people_1k"], x["sent"], x["misstated"]] for x in rc])
            + f"\n\nReading: an audit fixes only its own share of the leaks; its job is to measure the leak rate. Ranking by amount finds "
            f"{rc[2]['caught']} of {rc[2]['of']} in the top {rc[2]['x']}: on scans the leaks sit on mid-sized receipts and are mostly cents. "
            f"Re-reading every accepted receipt with T4 catches {full['caught']} of {full['of']}, but the API bill becomes "
            f"${float(V['costA']) + float(full['usd_1k']):.2f} per 1,000, above sending every receipt to T4 (${V['cT4']}, {V['aT4']} correct). "
            f"On photos there are {V['wbs_leaksA']} leaks and the full re-read catches {wfull['caught']}, with {wfull['false']} correct answers "
            f"sent to people. Card-statement matching, the other planned backstop, needs data this benchmark does not have.")


def block_learned() -> str:
    return (table(["Set", "AUC", "Rule router", "Learned at the router's cloud share", "Cloud share for the router's precision", "Verdict"],
                  [[r["set"], r["auc"], r["router"], r["learned"], r["share"], r["verdict"]] for r in V["lr_rows"]])
            + f"\n\nThe oracle gap ({V['oracle_cloudi']} vs {V['router_cloudi']} cloud on SROIE) is not closed by these features; richer signals are needed.")


def block_leaks() -> str:
    return (f"Of {V['leak_n']} SROIE answers that were wrong yet passed every check, {V['leak_other_printed']} were a different printed amount "
            f"(cash tendered, subtotal, a line item), {V['leak_swapped']} a day/month swap, {V['leak_both']} both fields. On Wild "
            f"({V['wleak_n']} leaks) dates and amounts split: {V['wleak_dates']} date errors ({V['wleak_swapped']} day/month swaps), "
            f"{V['wleak_other_printed']} other printed amounts.")


def block_gate() -> str:
    return table(["Set", "Leaks caught, verdicts (receipts)", "New false flags, verdicts (receipts)", "Harness: accepted correct",
                  "Harness: review", "Local only: accepted correct", "Local only: review"],
                 [[r["set"], r["caught"], r["false"], r["hA"], r["hA_rev"], r["lo"], r["lo_rev"]] for r in V["gate_rows"]])


def block_pii() -> str:
    """Masking experiment (docs/plan-pii-mask.md); every number from results*/harness/pii.json via report_numbers."""
    V = numbers()
    rows = []
    for r in V["pii_runs"]:
        k = r["key"]
        rows.append([r["set"], "label and pattern rules (r0)" if r["run"] == "r0" else "allowlist (rev1)",
                     V[k + "_gate"], V[k + "_hidden"], f"{V[k + '_t3']} ({V[k + '_t3ci']})", V[k + "_review"],
                     V[k + "_verdict"]])
    return (
        "The idea: when the local reader fails, hide the personal data on the image on this machine, then let the cloud "
        "read it. Tested on the cloud-bound receipts (30 per dataset), each read by Flash-Lite twice: the original (U) "
        "and the masked image (M1); differences are M1 minus U on the same receipts, in points.\n\n"
        + table(["Set", "Masking", "Refused before sending", "Personal items hidden",
                 "Date + total read correctly, points (95% interval)", "Sent to people, points", "Verdict"], rows) +
        "\n\n**Field rules missed most names; hiding everything except dates and amounts cost about 15 points of "
        "accuracy and sent almost every receipt to people.** Names are often printed without a label word, and hiding "
        "the shop name makes the missing-field check flag every answer. Where receipts may not leave the company, "
        "local-only mode stays the answer; a local name detector would be the next step.\n\n"
        "Read with care: labels are model-labeled (Gemini 3.1 Flash-Lite), so recall is relative to what it found; "
        "30 receipts per dataset show only whether a large loss was seen; the rules were frozen and committed before "
        "any label (`results*/pii/r0/freeze.json`), and the allowlist run (rev1) is a disclosed revision after r0, "
        "for which the experiment's spending limit was raised once; known misses: names without a label word and "
        "values printed on the line below their label; reviewers of the plan saw sample text in rounds 1 and 4; "
        "whether the fill covered the date or total is not decidable on receipts whose date is printed with the time "
        "glued to it (the frozen locator does not find it), and no hand check was made. Per-receipt reads and "
        "replays: `results*/pii/`."
    )


BLOCKS = {"pii": block_pii, "correction": block_correction, "ladder": block_ladder, "routing": block_routing, "uncertainty": block_uncertainty,
          "checks": block_checks, "backstop": block_backstop, "learned": block_learned, "leaks": block_leaks, "gate": block_gate}


def main() -> None:
    """Fill the same blocks in the English README and the Korean one (README.ko.md), so both carry identical
    numbers from report_numbers; a missing marker in either file stops the run."""
    texts = {name: fn() for name, fn in BLOCKS.items()}
    for fname in ("README.md", "README.ko.md"):
        path = ROOT / fname
        s = path.read_text(encoding="utf-8")
        for name, text in texts.items():
            pat = re.compile(rf"(<!-- gen:{name} -->\n)(.*?)(<!-- /gen:{name} -->)", re.S)
            if not pat.search(s):
                sys.exit(f"{fname}: marker gen:{name} missing")
            s = pat.sub(lambda m: m.group(1) + text + "\n" + m.group(3), s, count=1)
        path.write_text(s, encoding="utf-8", newline="\n")
        print(f"{fname}: filled", ", ".join(BLOCKS))


if __name__ == "__main__":
    main()
