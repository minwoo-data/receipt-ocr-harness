# Triad round 1: poster v6.3 text (read-only)

Target: docs/discussion/poster-v6/poster_v6.md (snapshot in source.md). Lenses ran in parallel and independently; verdicts LLM REVISE, Architect REVISE, EndUser REVISE. Raw answers are condensed below (issue lines kept verbatim in meaning).

## Raw answers (condensed)
- **LLM**: (H) Controls row "gate fired 6" reads as 100% false alarms; column should say expected outcome. (H) "step 4" undefined; T3 also sends the image out. (H) one policy has five names (harness, simple rules, two simple rules, Router no checks, Cloud harness); "two simple rules" undefined; "did no better" has no baseline. (M) ladder suggests T1→T2→T3→T4 but the harness path is T1→T3(→T4)→people. (M) "38 of 51 / 5 of 8" lack model and dataset. (L) 2.7× and 3.4 do not match the printed rounded values (2.6×, 3.5).
- **Architect**: (H) ladder vs actual paths; "step 4" hides that T3 sends images out, which weakens message 3. (H) checks are not split into generic vs receipt-specific; new document types need new checks; missed errors pass silently. (M) the routing rule and Fig B's τ are not defined. (M) local-only "$0" hides the people cost. (M) Controls column semantics. (L) "escalate to people" is a price-dated claim; Claude failover mixes production into the benchmark ladder.
- **EndUser** (30-s takeaway: "code checks LLM answers, routes local → cloud → people, 96.9% at $0.37/1k"; did not learn it reads receipt date + total until the tables; local-only seen only as a question): (H) title/subtitle never say what is read. (H) 96.9% < all-cloud 97.3% reads as "just use the cloud"; the gain (cost, data kept local) is buried. (H) ladder vs paths; "step 4". (M) Controls row. (M) From production reads as this harness's result; the "why" is the fourth bullet. (L) "domain assets" line is vague ("one", "there"); two numbers sit at 56%.

## Synthesis (deduplicated, by agreement)
| # | Issue | Lenses | Decision |
|---|---|---|---|
| 1 | Paths unclear: draw "Cloud mode: T1 → T3 → T4 → people · Local-only: T1 → T2 → people"; replace "step 4" with "only the cloud readers (T3, T4) see the image" (T4 is used: 0.3% accepted there) | all 3 | ACCEPT |
| 2 | Controls row: rename column to "as expected" (controls = should pass, menus = should flag) | all 3 | ACCEPT |
| 3 | One name per policy: "Router = agree-and-confidence rule, no checks"; "Harness = router + 4 checks"; drop "two simple rules"; learned score "no better than the router (95.7%)" | all 3 | ACCEPT |
| 4 | Headline gain: "Within 0.4 points of all-cloud at 31% lower cost; 44% of receipts never leave the machine" | EndUser | ACCEPT |
| 5 | Say what is read: "date and total from receipt images" in the subtitle area | EndUser | ACCEPT |
| 6 | "38 of 51" → local VLM (Qwen2.5-VL 3B), scans; "5 of 8" → Flash-Lite, scans | LLM | ACCEPT |
| 7 | Ratios and gaps computed from the printed rounded values (2.6×, 3.5) | LLM | ACCEPT |
| 8 | Domain line rewritten: "A check tuned on scan errors caught 10 of 16 there but 1 receipt on held-out photos, with 1 false alarm" | EndUser, LLM | ACCEPT |
| 9 | From production: rollback bullet first; mark as separate production work | EndUser | ACCEPT (wording to confirm) |
| 10 | Generic vs receipt-specific check tags; "missed errors pass silently" | Architect | DEFER to user (honest but weakens first impression) |
| 11 | People cost not priced: footnote "people time not priced" | Architect | ACCEPT (one phrase) |
| 12 | "At 2026-10 prices" before the strong-model claim | Architect | ACCEPT |
| 13 | Claude failover only in From production, not on the T4 card | Architect, LLM | DEFER to user (user asked for it on the card) |
| 14 | "Seeking ..." line (role and season) as a call to action | EndUser (question) | DEFER to user |

## Open issues for round 2
Items 10, 13, 14 need the user's call. Round 2 runs after the edits, on the revised text.
