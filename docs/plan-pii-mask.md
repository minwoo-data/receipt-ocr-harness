# Plan: mask personal data before a receipt goes to the cloud

Date: 2026-11-01 (v5, after triad-all rounds 1-4). Owner: Minwoo Park. Primary reader: whoever implements and reruns this (now, and for the 10k run); booth visitors see the results through separate text on the landing page.

**In two lines.** Before a receipt image goes to an outside AI service, this machine hides the names, member numbers and similar personal data on it; we then check that the outside service still reads the date and total correctly. If it does, receipts that may not leave the company because of the personal data on them can still use the cloud tier; whether masking satisfies a given company's rule is that company's decision, and M2 shows how much more can be hidden (shop and items) when the rule also covers business data.

**Why.** The cloud readers (T3, T4) are a third-party API. A receipt carries cashier names, card digits and customer phones of people who never agreed to share them. Where receipts may not leave the company (`docs/OVERVIEW.ko.md`, "데이터 반출 제약이 있을 때"), the only option today is `local_only`, which costs more human review. Masking would add a middle option.

**Status (2026-11-01).** Steps 1, 1b and 1c are done (commit 5d06a7e). Step 2 is done: the two library modules `src/harness/mask.py` and `src/harness/pii_run.py` with their tests from the dev set, the sidecars, the small changes to `rules.py`, `vlm.py`, `04_harness.py` and `24_pii_boxes.py`, and the freeze, which records the code's hashes before any label is requested, so the rules cannot be tuned to the labels. Next: step 3, the labels (the first paid calls). `scripts/25_pii_mask.py` has `freeze`; each later step adds its subcommand. It only wires the library: every decision lives in the two frozen modules.

## Flow

```text
production path, one line per step:
1. T1 self-signal passes                -> accept (nothing leaves the machine)
2. T1 self-signal fails                 -> mask on this machine -> Gate
3. Gate refuses                         -> person (no request at any tier)
4. Gate sends: T3 reads the masked image -> code checks + tag check: pass -> accept; fail -> step 5
5. T4 reads the same masked image        -> code checks + tag check: pass -> accept; fail -> person
```

**What the cloud sees** (invented values): the line `Cashier:ALEX` becomes `[P1]`; the line `Staff: LEE Date: 25/03/2018` becomes `Staff: [P1] Date: 25/03/2018`. Date and total stay readable.

Only the cloud steps change; T1, T2 and `local_only` are untouched. **In production only masked images leave the machine.** In this experiment, on public datasets whose images already went to the same API in the benchmark, these calls also send the original: the label call (and its one re-ask), the U read at T3 and, for flagged receipts, the U read at T4.

**One model per call.** Every cloud call names its chain from one table, `vlm.ENGINE_CHAINS` (step 2): `"gemini-lite"` = `(("gemini", vlm.GEMINI_LITE_MODEL),)` for label calls and T3 reads, `"gemini"` = `(("gemini", vlm.GEMINI_MODEL),)` for T4 reads; a test checks that `02_run_engine.py` uses the same chains for those names. `vlm.DEFAULT_CHAIN` is never used: it falls through to Claude, which would send an original image to another company. Before storing, code asserts `record["engine"]` is the expected model; a record with provider `none` is not stored and its job is `failed`. `pii.json` records the model id per tier.

## Background

| Term | Meaning |
|---|---|
| T1 | RapidOCR (reads the text in the image) + rules that pick date and total; Tesseract as a second reader. Local. |
| T2 | Qwen2.5-VL 3B, a small vision model on this laptop. **Not used on the path studied here.** |
| T3, T4 | Cloud: Gemini 3.1 Flash-Lite, then Gemini 3.6 Flash. |
| `harness` | The routing policy in `scripts/04_harness.py` `decide()`: T1 is accepted when its self-signal passes (both local readers agree, mean OCR confidence >= tau 0.9, date check passes); otherwise T3, and T4 when T3's answer fails the code checks; otherwise a person. |
| `local_only` | The policy that never calls the cloud: T1, then T2 with the code checks, then a person. |
| Code checks | `src/harness/verify.py`: sanitizer (rejects injected instructions and wrong types in a model answer), missing fields, arithmetic, date plausibility, agreement with the local OCR text. |
| Gate | The masker's send-or-refuse decision, made before any call. `refused` = no request at any tier; the receipt goes to a person. |
| Tag check | The `tags` option of `04_harness.py --gates`: a code check on the cloud answer, like those in verify.py. Not the Gate, and not the earlier `gate_total_label` experiment. |
| Replay | Re-running `decide()` on stored reads, no new calls. |
| `results*` | Both `results/` (SROIE) and `results_wild/` (WildReceipt). Dataset names are the manifest stems `sroie300`, `wild200`. |
| Run | `r0` = the frozen rules; `rev<k>` = a revision. Rule-dependent outputs are stored per run. |
| Accepted precision / review share | Share of auto-accepted receipts with date and total both right / share of receipts sent to a person. Points = percentage points. |
| Ledger | `results/spend_ledger.json`, the cost of every paid call (local only). |
| NFKC | Unicode normalization that turns full-width and look-alike characters into plain ones. |
| Detection | One RapidOCR text box, an item of the `tokens` list of a `run_rapidocr` record: `text`, `conf`, `box` (four `[x, y]` corners, original-image pixels), `id` (index) and `line` (index into `lines`); `id` and `line` exist from step 1b. |
| Label | An evaluation item: personal data that Gemini Flash-Lite marked on the original image (Labels). Used only to measure the masker. |
| Tag | The placeholder drawn over a hidden detection: `[P1]`, `[P2]` ... A tag is not an OCR detection and not a label. |
| Fill | The pixels painted white for one hidden detection: its quad expanded by the pad, minus every protected detection's quad. |
| Mask map | Local table per receipt and run: tag -> detection id, box, fill (polygon and the sha256 of the fill mask), compare value, local OCR text, rule, category. |
| Sidecar | `data/manifest/<dataset>.mask.json`: the masker's word lists, padding and `publish_reads` for one dataset. |
| U, M1, M2 | U = the image with nothing hidden (control). M1 = personal data hidden (the policy under test). M2 = M1 plus the shop block and item names (how far masking can go). |
| Dev set | Cloud-bound receipts outside the sample, saved as `dev_keys` in `sample.json` in step 2 (135 SROIE, 138 WildReceipt). Rules and tests are written from their cached OCR text only. Those cached reads have token `text` and the `lines` strings but no `box`, `id` or `line` (they predate step 1b), so tests build detections by hand: invented boxes, one `line` index per printed line. |

**Sample** (done, `scripts/24_pii_boxes.py`): under `harness`, 165 of 300 SROIE scans and 168 of 200 WildReceipt photos reach T3; 30 of each drawn with seed 20261031 (`results*/pii/sample.json`). Reviewers quoted seven strings from sample receipts in round 1 and counted box geometry on sample receipts in round 4; no sample text is used in rules or tests, and README block `gen:pii` says that sample text was seen. Step 2 writes `pool_keys` and `dev_keys` into `sample.json`; 24 then prints any later difference from the current pool instead of stopping, and a test checks that every receipt cited in the tests is in `dev_keys`.

## Success criteria (fixed before any call; M1, per dataset of 30)

1. **Headline.** Receipts with a labeled item not hidden: **0**. Scope: M1 receipts the Gate did not refuse, whether or not a read came back (masking quality does not depend on the answer). Not decidable only when that dataset has `invalid` labels.
2. Receipts where the stored fill overlaps a detection holding the ground-truth date or total (located by `mask.locate_gt`, see Metrics): **0**. Same scope as 1. Receipts where the ground truth could not be located are `unknown`; criterion 2 holds only if every `unknown` receipt is checked by hand in step 4b and recorded as `clear` (neither date nor total covered). `covered` is a failure; `cannot tell` or an unresolved `unknown` makes criterion 2 not decidable.
3. T3-alone date + total exact, M1 minus U, paired bootstrap 95% interval (the receipts read in both variants, resampled 10,000 times; the middle 95% of M1 minus U): holds when the upper end is at least 0, i.e. no clear loss; an interval entirely above 0 is reported as an improvement. Receipts without a read in both variants are left out of the pairs and listed; not decidable only if no pair remains. (With 30 receipts this shows only that no large loss was seen, not that there is none.)
4. Review share of the M1 replay minus the U replay: **at most 5 points**, i.e. at most 1 extra receipt of 30; refused receipts count as review. Any `missing` read in either replay makes criterion 4 not decidable.

All four hold -> "works on this sample". Incomplete inputs make a criterion not decidable under the condition written in that criterion, never a pass. A failed criterion is reported as "fails criterion k" with the receipts and categories behind it; it is a finding of this run, not a reason to change rules after the labels (that would be a revision, see Freeze). The verdict is per dataset and is computed only when both parts of a run in `pii.json` carry the same provenance.

**Known misses, counted by criterion 1, not excused:** an address printed without the label word `ADDRESS`; a value printed on the line below its label (`BILL TO:` then a name); a name printed without a label word (dev receipt W0045_90028d102689 has one on the line below the card number). Step 2 found a dev receipt (X51006389963) that prints a customer address after `ADDRESS :`, so the sidecars map `ADDRESS` to `customer_address`. `BILL TO` is not a label word: `BILL TOTAL` would match it (letters may follow a label) and refuse the receipt.

## Two layers of pseudonymization

Pseudonymization = replacing who or what with a meaningless label that only this machine can turn back.

**Layer 1, per call: request ID.** Today nothing that names the receipt reaches the cloud, and in this run the request ID is never sent in any form (no batch API, no request metadata). It is the only key that links a cloud answer back to a receipt, and it lives only in the local job table; if calls later go through a batch API, which needs a key per request, this ID is what the cloud sees, never the receipt number. The job table (`pii_run.JobTable`) is an append-only jsonl (`format_version` 1; the last row per job key is its state): job key `(run, dataset, receipt, variant, tier, attempt)` -> `uuid4`, status `planned / sent / done / failed / refused`, payload sha256, read path, and `reask: true` on the one label re-ask (at most one such row per receipt). A `done` job is never re-sent. A job left `sent` without a stored answer (interrupted) becomes `failed` and is re-sent as `attempt + 1`. Each attempt is exactly one API request: the runner calls `run_cloud_chain(..., max_attempts=1)` and does its own retries as new attempts, so every request passes the budget check (Budget). When a cap stops a job, the runner appends it as `planned` again (nothing left the machine).

**Layer 2, per detection: tags.** Each hidden detection gets a fill and a tag drawn in its place. Fill geometry (`mask.render`): the detection's quad expanded outward by the sidecar's `pad` (`{"frac_of_height": 0.1, "min_px": 2}`, so the pad scales with the image), rasterized into an image-size boolean mask; the fill mask is the union of those polygons minus the quads of all protected detections. If a hidden detection's own quad shares a pixel with a protected quad, the Gate refuses. Overlap = at least one shared pixel; coverage = shared pixels / box pixels. Quads, not axis-aligned rectangles, because photos are tilted. The mask map stores the polygons and the sha256 of the fill mask, and every coverage and over-masking measure uses that mask. Tags are numbered in reading order (line, then left x) within one receipt, so `[P1]` appears on many receipts and never means the same person; a tag is never derived from the hidden value (a hash of a short member number can be reversed by trying every number). Because tags are `[P1]..[Pn]`, the count `n` alone says which tags a receipt issued.

**On return.** Prompt and schema are unchanged (`src/harness/schema.py`, 10 fields), so U and M1 stay comparable with the benchmark and the arithmetic check still works. The tag check (`mask.check_tags(record, n_tags)`, run by `04_harness.py --gates tags`, off by default so existing runs do not change; done in 1c; `verify.py` itself is not edited, because its sha256 is part of the recorded gate experiment in `results*/gate_total_label/comparison.json`) flags a string field holding a tag above `n` or below 1, or a broken tag such as `[P3` or `P3]`, and `date` holding any tag (`total` is numeric; a tag there already fails the sanitizer). A tag flag is a flag like any other (T3 -> T4 -> person). The schema has no personal field, so nothing is restored into the extracted record; the mask map stays local for audit, and a future schema that asks for, say, a member number would get the tag back and replace it from the map.

## Masker (`src/harness/mask.py`, library with tests)

**Functions**, so rules can be tested without images or OCR: `plan_mask(record, sidecar, day_first, variant) -> MaskPlan` (pure: hide set, refusal and reason, tags, compare values), `render(image, plan) -> (image, fill)`, `post_check(payload, plan, ocr=run_rapidocr)` with the OCR injectable, `item_hidden`, `locate_gt`, `detections_sha256(detections)` (sha256 of `json.dumps([[d["id"], d["text"], d["box"]] for d in detections], ensure_ascii=False, separators=(",", ":"))`, the one serialization used by labels and mask maps), the label prompt `LABEL_PROMPT`, `CATEGORIES`, `LABEL_SCHEMA`, `validate_labels`, `load_labels`, and `code_provenance`. `pii_paths` (built in 1c) stays here and changes in step 2 (Inputs).

**Inputs.** The detections of one receipt with `id`, `box`, `line`. The sidecar (`version` 1): `label_words` as a map to a category (`"CASHIER": "staff_name"`, `"SERVED BY"`, `"STAFF"`, `"OPERATOR"`, `"SALESPERSON"` -> `staff_name`; `"MEMBER"`, `"MEMBER NO"` -> `member_no`; `"CARD NO"`, `"A/C"` -> `card_fragment`; `"CUSTOMER"`, `"NAME"`, `"ATTN"` -> `customer_name`; `"ADDRESS"` -> `customer_address`), `exclude_words` (`DISCOUNT`, `POINTS`, `COPY`, `SERVICE`, `THANK`), `pad`, and `publish_reads` (`full` this run). `day_first` stays the per-row manifest field (absent = true). Dates and amounts come from existing code, imported, never copied: date = `verify.ocr_date_candidates`; amount = `rules.MONEY`; total keyword = `rules.has_total_keyword(line)` (true for `_STRONG` or `_MEDIUM`, ignoring `_EXCLUDE`, so `Total Savings -0.56` is protected too, the cautious side). Step 2 adds `MONEY` and `has_total_keyword` to `rules.py` as public names without changing its behaviour; `mask.py` imports no `_` name. Paths: step 2 changes `pii_paths(results_root, manifest)` to `pii_paths(results_root, manifest, run="r0")` and returns, besides today's keys: `job_table` (renamed from `jobs`), `freeze` = `results*/pii/<run>/freeze.json`, `variant` = `{v: {jobs_json, reads_t3, reads_t4, harness}}` under `results*/pii/<run>/<v>/`, run-dependent local paths `images`, `mask_maps`, `post_ocr`, `gt_checks` under `pii_local/<dataset>/<run>/`, shared local paths `boxes`, `labels`, `job_table` under `pii_local/<dataset>/`, `pii_json`, `sidecar`, `budget`; `manifests` is dropped (nothing uses it). `tests/test_mask.py` and the 04 docstring are updated with it.

**Matching contract.** Text is NFKC-normalized and upper-cased. Matching runs on detection text. A label word matches at the start of a detection or after a space, `:` or `.` inside it, and also with its internal spaces removed (`MEMBERNO`, `CARDNO`); letters may follow it (`MEMBERCARDNO`). Where label words overlap at the same place, the longest wins (`MEMBER NO` before `MEMBER`). An exclude word matches as a substring of its line's text with non-letters removed (`CUSTOMER'SCOPY` -> `CUSTOMERSCOPY` contains `COPY`). A line with an exclude word fires no label rule and no phone rule.

**Rules.**
1. **Label rule.** A detection holding a label word hides its value. If letters or digits follow the label inside the same detection (after optional `: . # ,` and spaces), the whole detection is hidden. Otherwise the value candidate is the next detection on the same line: if it is protected, the Gate refuses (rule 3); if not, it and the following detections on the line are hidden, up to the first protected detection or the first detection that ends with `:` (the next field's label). A value printed on the line below its label is not handled (dev receipt X00016469612 has `Member:` followed by the title `CASH BILL`, which a next-line rule would hide); that costs recall, and the labels measure it.
2. **Pattern rule.** Email (`[A-Z0-9._%+-]+@[A-Z0-9-]+(\.[A-Z]{2,})+`; `FISHBALLNOODLE@7.0O` is not one); card fragment (`[*X]{4,}\d{4}`, or `\d{4}([ -]\d{4}){3}`); phone (`\+?\d[\d -]{7,}\d`) on a line below the shop block. Categories: `customer_email`, `card_fragment`, `customer_phone`. A match that `verify.ocr_date_candidates` reads as a date or `rules.MONEY` reads as an amount is not a hit (in the dev set about one receipt in five has a dashed date like `25-03-2018`, which the phone pattern would otherwise match). The phone pattern also hides barcodes, registration and receipt numbers, and a shop's own phone printed low on the receipt (in the dev set about one receipt in three has such a detection): accepted over-masking, reported in the share of detections hidden. Shop block = lines above the first line holding a date or an amount.
3. **Protection.** A detection holding a date candidate, or an amount on a line with a total keyword, is never hidden. If the label rule's value candidate is a protected detection, the Gate refuses the receipt for that variant. A card or email match on a protected detection also refuses (it would otherwise be sent readable); a phone-shaped string there is ignored, because dates, times and amounts share its characters.
4. **Gate.** For M1 and M2 only, refuses `(receipt, variant)` when rule 3 conflicts, when a hidden quad shares a pixel with a protected quad, when the receipt has fewer than 10 detections (none in this sample: minimum 25 SROIE, 20 WildReceipt), or when the post-mask check fails. U does not go through the Gate (its hide set is empty), so U's reads are always attempted.

**Post-mask check.** `data, mime = vlm.payload_bytes(masked file)` gives the exact bytes that will be sent; the job row stores `sha256(data)` of those raw bytes. The same bytes are written to `post_ocr/<key>.<variant>.<ext>` and re-read with `run_rapidocr`. Each hidden detection carries a compare value from `plan_mask`: the text after the label and separator when label and value share a detection, the whole text for a value detection after its label, the match for a pattern hit, the whole text for an M2 hide. After NFKC, upper-casing and removing spaces, the check fails if a new detection contains a compare value of 3 or more characters; tag strings are ignored. Right before each call, `pii_run.sendable(job, plan, path)` recomputes `payload_bytes` and raises (nothing sent, job stays `planned`, "rerun 25 mask") if the sha256 differs from the job row, if the job is `refused`, or if the chain has more than one link.

**Examples** (each row becomes a test in step 2). The shape of each detection comes from the dev-set OCR of the receipt in brackets; names and card digits are replaced with invented ones of the same shape (`*` below), here and in the tests, so no person's name or card number is quoted in this repository's prose or tests. Rows marked "made up" have no source receipt; `|` separates detections on one line.

| Detection text (receipt) | Result | Why |
|---|---|---|
| `Cashier:ALEX`\* (X51006414532) | hide | label + value in one detection |
| `STAFF:Sam`\* (W0030_d3759910dd53) | hide | label + value |
| `YOUR CASHIER TODAY WAS JORDAN`\* (W0018_4377) | hide | label after a space, value after it |
| `Staff:` \| `LEE`\* \| `Date:` \| `25/03/2018` (X51005719905) | hide `LEE`; keep `Date:` and the date | the value stops at the next field's label; the date is protected |
| line `Member:` with nothing after it (X00016469612) | keep; the next line `CASH BILL` is kept too | no value on its line |
| `CARD N0.400000******0000`\* (X51006311714) | hide | card pattern (OCR read `NO` as `N0`, so the label word alone would miss it) |
| `XXXXXXXXXXXX0000`\* (W0045_90028d102689) | hide | card pattern |
| `REG CASHIER 09-16-2015` (W0167_3810) | refuse | label rule and a date in one detection; the receipt goes to a person and counts as gate cost |
| `Staff:` \| `25/03/2018` (made up) | refuse | the label's value candidate is protected |
| `CUSTOMER'SCOPY` (X51006557507) | keep | exclude word inside glued text |
| `ustomer ServiceHot1ine:03-2726-5600` (X51005230616) | keep | exclude word; the shop's line |
| `BE A POPULAR CARD MEMBER` (X51006008092) | keep | `MEMBER` ends the detection and nothing follows on its line |
| `FISHBALLNOODLE@7.0O` (X51006401977) | keep | not an email |
| `TOTAL 26.50` (made up) | keep | protected |
| `Date: 25-03-2018` (made up) | keep | a dashed date is not a phone |
| `Tel: 012-345 6789` (made up, below the shop block) | hide | phone pattern |
| `1234567890123` (made up, below the shop block) | hide | phone pattern on a barcode: accepted over-masking |
| `MEMBER NO` \| `123456` (made up) | hide `123456` | the longest label wins, so `NO` is not taken as the value |
| two tilted neighbouring quads, one holding a date (made up) | keep the date; the neighbour's fill stops at the date's quad | fill minus protected quads |

**M2** also hides every detection in the shop block, and on item lines (below the shop block, holding an amount, not protected) the detections without digits. Hiding the shop name may make the missing-field check flag `vendor` (an answer of `[P1]` passes it), so M2 is reported as T3-alone accuracy only, by scope: no replay, no T4.

## Running and judging (`src/harness/pii_run.py`, library with tests)

Everything that decides whether an image leaves the machine, or whether a criterion holds, is library code frozen with `mask.py`; `25_pii_mask.py` subcommands only load files and call it. `JobTable` (append, last row per key, `planned -> sent -> done / failed`, next attempt, `reask`); `sendable` (above); `Budget` (reserve and settle, below); `write_jobs_view(paths, variant)`; `replay_args(paths, variant)` (the 04 arguments, from `pii_paths`); `metrics(paths, run)` (every row of the Metrics table); `verdict(metrics)` (criteria 1-4, "works on this sample", "fails criterion k", "not decidable"); `write_pii_json(paths, run, part, data)`. The calls are injected, so step 2 tests use a fake caller to check that a refused receipt causes no call at any tier and that a changed payload stays `planned`.

**Freeze.** At the end of step 2, before any label is requested, `25_pii_mask.py freeze` writes `results*/pii/r0/freeze.json` with `mask.code_provenance()`. It runs `[sys.executable, "-c", "import harness.mask, harness.pii_run"]` in a fresh interpreter, lists the `harness.*` modules that process loaded (so `vlm.py`, which sets the bytes sent, is included through `pii_run`), and records their sha256, the sidecars' sha256, and the `rapidocr_onnxruntime` and Pillow versions. `freeze.json` keeps the module list; later checks rehash the same list and report newly loaded modules separately. Steps 3-7 add only wiring in `25_pii_mask.py` and the publishing code of step 7; any later edit to a frozen file makes the provenance differ.

Two kinds of hash, two jobs. **Provenance** (code): each run in `pii.json` records its frozen and current provenance; the `replay` part adds the sha256 of `04_harness.py` and `scoring.py`, which route and score it. If frozen and current differ, `revised: true` and both sets of numbers are printed (r0 and the latest `rev<k>`), never a failure. **Inputs** (data): each part records the sha256 of the files it was computed from (`replay`: the committed reads, `jobs.json` files, the manifest, and the `results*/rapidocr` and `tesseract` caches; `local`: mask maps, labels, boxes, the job table and `gt_checks.json`). `run_all.py` first compares the recorded inputs with those files where they exist; on a mismatch it fails and changes nothing (a stale aggregate). Only when they match does it rerun the replays and rewrite the `replay` part. Where the local files are absent it keeps `local` as is and marks it `inputs_checked: false`. `pii.json` is written with sorted keys and no time stamps, so an unchanged rerun leaves it byte-identical.

**Revision.** A revision `rev<k>` = edit the rules, then `freeze`, `mask`, `read`, `t4`, `summary` with `--run rev<k>`. It reuses the r0 labels (same `detections_sha256`) and U reads (same U payload sha256) through the job table, because they do not depend on the rules, and re-sends only M1 and M2 reads and T4 (about 70 calls). It never rewrites an r0 output.

## Labels (model-labeled)

**Format** (the same for synthetic and human labels at 10k): `{"format_version": 1, "receipt", "labeler", "detections_sha256", "items": [{"item_id", "category", "text", "detection_ids": [...], "box": null}]}`. `detections_sha256` is `mask.detections_sha256` of every detection the labeler saw; `mask.load_labels` refuses a file whose hash differs from the current boxes. An item no detection covers has `detection_ids: []`. Mask maps carry the same `detections_sha256` and `format_version`.

**Categories** (`mask.CATEGORIES`; data about a person only; the shop's own name, address, phone, registration and invoice numbers are never labeled; examples invented):

| Category | Label | Do not label |
|---|---|---|
| `staff_name` | `Cashier: ALEX` | a till or staff number such as `Cashier: 01` |
| `customer_name` | `Name: J. LEE` | the shop's name |
| `member_no` | `Member No: 123456` | a points balance |
| `card_fragment` | `XXXXXXXXXXXX0000` | an approval or terminal code |
| `customer_phone` | `Tel: 012-345 6789` printed for a customer | the shop's phone |
| `customer_email` | `alex@example.com` | the shop's email or website |
| `customer_address` | `Deliver to: 1 Example Road` | the shop's address |

**Labeler.** Gemini 3.1 Flash-Lite (`ENGINE_CHAINS["gemini-lite"]`) gets the unmasked image, the numbered detection list and `mask.LABEL_PROMPT`, with `schema=mask.LABEL_SCHEMA` and `validate=mask.validate_labels` (`vlm.py` takes both since 1c), so label calls go through the same budget and ledger. On an invalid answer the runner re-asks once (`reask: true`); still invalid -> that receipt's labels are `invalid` and criterion 1 is not decidable for its dataset.

Reported as **"model-labeled (Gemini 3.1 Flash-Lite)"**. Recall is relative to what Flash-Lite found.

## Reads and replay

Per sampled receipt, Flash-Lite reads U, M1 and M2 (a refused M1 or M2 job is not sent). U is the masker's output with an empty hide set, written and encoded by the same code, so the only difference between variants is what was hidden. Reads are stored where `02_run_engine.py` would put them, `results*/pii/<run>/<variant>/<engine>/<receipt key>.json`, where `<engine>` is 02's folder name (`gemini-lite` for T3, `gemini` for T4), in the same record shape (no `request_id`; the job table links IDs to these paths).

**`jobs.json`** (committed, one per run and variant) is a view derived from the job table and the read files; `pii_run.write_jobs_view` rewrites it at the end of every subcommand that changes state (`mask`, `read`, `t4`). No text, no request ID:

```json
{"format_version": 1, "run": "r0", "variant": "M1",
 "receipts": {"X51005288570": {"n_tags": 2, "t3": "read", "t4": "not_needed"}}}
```

`t3` is `pending` (after step 4, before step 5), `read`, `refused` or `missing`; `t4` is `pending` (before step 6b), `read`, `not_needed`, `refused` or `missing`. U always has `n_tags` 0 and is never `refused`; M2 always has `t4: not_needed`. `read` is used here, not `sent`, because the job table's `sent` means "sent, answer not yet stored".

In step 2, `04_harness.py --jobs` changes as follows; without `--jobs` every output stays byte-identical, checked with `run_all.py` as in 1c.
- It requires `format_version` 1 and checks both directions (a `read` tier has its read file; a read file has `read`).
- It refuses a view with any `t3: pending`.
- It stops with "T4 selection stale: rerun 25 t4" on a row whose `t3` is `read`, whose `flags.t3` is non-empty and not only `UNAVAILABLE`, and whose `t4` is `not_needed`.
- A `refused` receipt gets `row["refused"] = True`. In `decide()` for `harness`, once `local_ok` is false, such a row returns review with path `[T1]`, so the replay does not count it as sent to the cloud.
- In this mode 04 computes and writes only the `harness` policy: `policies.json` with that row, `per_receipt.jsonl`, and `per_receipt.schema.json` listing `refused` as an optional row key. It writes no tau sweep, waterfall or hedge, so no other policy's numbers are published for masked reads.

Then, per dataset, from the repository root; `25_pii_mask.py replay` builds 04's arguments from `pii_paths`, so no path is typed by hand:
- **6a.** `25_pii_mask.py replay --results results --manifest data/manifest/sroie300.jsonl --run r0 --variant U`, then `--variant M1`; for WildReceipt `--results results_wild --manifest data/manifest/wild200.jsonl`. Replays write only under `results*/pii/<run>/<variant>/harness/`, never `results*/harness/`.
- **6b.** `25_pii_mask.py t4` joins that variant's `jobs.json` with its `harness/per_receipt.jsonl` and calls T4 for a receipt when `t3` is `read` and `flags.t3` is non-empty and not only `UNAVAILABLE` (04's flag for a missing read). Fresh reads for both variants, so the comparison is symmetric; 11 of the 60 cached T3 answers are flagged today, so about 25 calls. Receipts not selected get `t4: not_needed`.
- **6c.** `25_pii_mask.py replay` again for U and M1, with the T4 reads.

## Metrics (per dataset; denominators fixed)

Public aggregates go to `results*/harness/pii.json` (`schema_version` 1), read only through `report_numbers.py`, shown in README block `gen:pii` and a landing-page section. Only `pii_run.write_pii_json(paths, run, part, data)` writes it, so parts and runs never overwrite each other: `replay` (T3-alone accuracy, accepted precision of the replay, review share; rewritten when `run_all.py` calls `25_pii_mask.py summary --replay-only`, which first reruns `replay` for U and M1, then aggregates) and `local` (gate cost, recall, headline, over-masking, the verdict; written only by `25_pii_mask.py summary` where the local files exist). Shape (invented values):

```json
{"schema_version": 1, "runs": {"r0": {
  "replay": {"provenance": {}, "inputs": {}, "models": {"t3": "gemini-3.1-flash-lite", "t4": "gemini-3.6-flash"}, "sroie300": {}},
  "local": {"provenance": {}, "inputs": {}, "inputs_checked": true, "revised": false,
            "sroie300": {"verdict": "fails criterion 1", "criterion_1": {"receipts": ["<key>"], "categories": ["customer_address"]}, "criterion_2": "holds"}}}}}
```

| Metric | Definition |
|---|---|
| Gate cost | receipts the Gate refused / 30 (`t3: refused` in that variant's `jobs.json`), per variant (M1, M2) |
| Item hidden | `mask.item_hidden(item, mask_map)`: with a `box`, the fill covers at least 90% of it; otherwise `detection_ids` is non-empty and every id is in the hide set. Each item records `hidden_by: coverage | ids`, and recall is also reported per rule |
| Detection recall | \|H ∩ L\| / \|L\|, where L = labeled `(receipt, detection_id)` pairs and H = hidden pairs; M1 receipts in the criterion 1 scope with valid labels; pooled over receipts (micro) |
| End-to-end recall | hidden items / labeled items, same receipts, pooled; items with no detection count as not hidden |
| Headline | criterion 1: receipts in its scope with at least one item not hidden |
| Over-masking | criterion 2: receipts in its scope where a detection holding the ground-truth date or total overlaps the fill; also the share of all detections hidden. `mask.locate_gt(detections, gt)` finds that detection without the protection code: the date is written in its printed forms (`DD/MM/YYYY`, `DD-MM-YYYY`, `DD.MM.YYYY`, `DD/MM/YY`, `YYYY-MM-DD`, and month-first too, the cautious side) and searched in detection text with spaces and separators removed; the total is searched as `26.50` and `26,50`. Not found -> `unknown` |
| T3-alone accuracy | date + total exact via `scoring.predicted_fields`, `correct_fields`, `money_fields_ok` on `results*/pii/<run>/<variant>/gemini-lite/`, for U, M1, M2; criterion 3 pairs as stated there |
| Replay | accepted precision of the replay and review share, `harness`, U and M1, over all 30; not decidable if any `missing` |

A receipt with no labeled item has recall N/A. The paired bootstrap is `bootstrap.paired_ci(a, b, n_boot=10000, seed=20261031)` (done in 1c), which returns a − b over two key-aligned 0/1 arrays; criterion 3 calls `paired_ci(m1_ok, u_ok)`.

## Order and budget

Every `25_pii_mask.py` subcommand takes `--results` and `--manifest` (as 24) and `--run` (default `r0`), and runs from the repository root.

| Step | Status | Command | Writes | Calls |
|---|---|---|---|---|
| 1. Sample + boxes | done 2026-10-31, 60/60 text equal to cache | `24_pii_boxes.py` | `results*/pii/sample.json` | 0 |
| 1b. `run_rapidocr` adds `id`, `line`; 24 writes to `data/raw/pii_local/<dataset>/boxes/` and gains `--force` | done 2026-10-31 (commit 5d06a7e): 60/60 tokens and lines equal to cache, id/line on every detection | `24_pii_boxes.py --force ...` | local boxes | 0 |
| 1c. Code seams: tag check `mask.check_tags` via 04 `--gates tags`; 04 `--keys`, `--jobs`; `vlm.py` `schema=`, `validate=`, `payload_bytes()`, `SpendCapReached`, cap read at call time; `bootstrap.paired_ci`; `pii_paths`; pre-commit refuses `pii_local` paths | done 2026-10-31 (commit 5d06a7e): pytest 37 passed, `run_all.py` leaves every result file unchanged, `bootstrap.json` byte-identical | `pytest`; `run_all.py` | code | 0 |
| 2. `mask.py` and `pii_run.py` as listed above; `rules.MONEY`, `rules.has_total_keyword`; `vlm.py`: `run_cloud_chain(..., max_attempts=None)`, public `MAX_OUTPUT_TOKENS`, `max_request_usd(model, input_tokens)`, `ENGINE_CHAINS` (defaults keep today's behaviour); `pii_paths` with `run`; 04 `--jobs` as above; `sample.json` `pool_keys`, `dev_keys` and 24's diff report; sidecars; tests from the dev set; the `pii_local` pattern moves into `.githooks/private-paths`; `25_pii_mask.py freeze` | done 2026-11-01: pytest 85 passed (`test_mask_rules.py` holds one test per Examples row), `run_all.py` leaves every result file unchanged, both datasets frozen in `results*/pii/r0/freeze.json` | `pytest`; `run_all.py` (byte-identical); `25_pii_mask.py freeze` | `freeze.json` | 0 |
| 3. Labels | to build | `25_pii_mask.py label` | local labels | 60 (+ re-asks) |
| 4. Masked images + post-mask check (runs the frozen code) | to build | `25_pii_mask.py mask` | local images, mask maps; `jobs.json` (`t3: pending` or `refused`) | 0 |
| 4b. Hand check of `unknown` | to build | `25 mask` ends by listing the M1 receipts where `locate_gt` returned `unknown`; the owner opens each masked image in `data/raw/pii_local/<dataset>/r0/images/` and records it | `gt_checks.json`: `{"<receipt>": {"result": "clear" \| "covered" \| "cannot tell", "fill_sha256": "..."}}` (an entry whose `fill_sha256` differs from the mask map is void) | 0 |
| 5. Reads U, M1, M2 | to build | `25_pii_mask.py read` | `results*/pii/r0/<variant>/gemini-lite/` | 180 minus refused |
| 6. 6a replay, 6b T4 for flagged, 6c replay | to build | `25_pii_mask.py replay`, `t4`, `replay` | `results*/pii/r0/<variant>/{gemini,harness}/` | about 25 |
| 7. Publishing code: `report_numbers.py` pii keys, `22_readme.py` `gen:pii` with the disclosures (Publishing) and a test for them, `18_landing.py` section, `run_all.py` calling `25_pii_mask.py summary --replay-only` after the input check; then run them and pytest | to build | `25_pii_mask.py summary`; `22_readme.py`; `18_landing.py`; `run_all.py` | `results*/harness/pii.json` | 0 |

If `same_text_as_cache` is false for any receipt in 1b, stop and find out why before step 2.

**Budget.** About 270 calls expected, about $0.16; this is an estimate, not a bound (re-asks, T4 selection and retries change it). The bound is the allowance, kept in one file for both datasets, `data/raw/pii_local/budget.json`, by campaign: `{"format_version": 1, "campaigns": {"booth-2026-11": {"cap_base_usd": ..., "allowance_usd": 0.20, "reserved_usd": 0.0, "runs": ["r0"]}}}`. The first paid subcommand writes `cap_base_usd` (the ledger total then) once; it is never reset within a campaign. r0 and its revisions share this campaign's $0.20, so a revision may not fit after r0; the 10k run opens its own campaign. Each request is reserved before it is sent (`pii_run.Budget`): it may go only if `ledger − cap_base_usd + reserved_usd + vlm.max_request_usd(model, input_bound)` is at most `allowance_usd`. `max_request_usd` prices `input_bound` input tokens plus `vlm.MAX_OUTPUT_TOKENS` output tokens; `input_bound` = the largest `input_tokens` among that model's stored benchmark reads plus the prompt's length in characters. The reservation is written to `budget.json` before the request; when the ledger shows the request's cost it is released; a request that returned no recorded cost (an empty answer or an error after sending) keeps its reservation, counted as spent. A request refused by this check, or by `SpendCapReached`, leaves the job `planned`, and the summary lists the receipt as `missing`. As a second guard each paid subcommand sets `os.environ["HARNESS_SPEND_CAP_USD"] = f"{cap_base_usd + allowance_usd:.6f}"` in its own process. Heavy local jobs (RapidOCR, post-mask check) run one at a time.

**Dates.** 11-01: steps 2-3 (rules frozen before labels). 11-02: steps 4-6, including the hand check (4b). 11-03: step 7, published after the owner reviews the public wording. 11-04: booth.

## Publishing (publish less)

Committed: `mask.py`, `pii_run.py`, sidecars, tests, scripts 24-25, `results*/pii/sample.json`, per run `freeze.json`, the reads, `jobs.json` files and the `harness` replays under `results*/pii/<run>/<variant>/`, `results*/harness/pii.json`. Reads are committed in full because `publish_reads` is `full` for these public datasets.
Local only, under the git-ignored root `data/raw/pii_local/`: per dataset in `<dataset>/`, the job table with request IDs, boxes and labels; per run in `<dataset>/<run>/`, masked images, mask maps, post-mask OCR and `gt_checks.json`; at the root, the one `budget.json`. The pre-commit hook refuses any path listed in `.githooks/private-paths` (`data/raw/` today; step 2 adds the `pii_local` pattern there and a test that `mask.LOCAL_ROOT` is covered by the list).

Every public place that shows pii numbers (README `gen:pii`, the landing section) carries: model-labeled (Gemini 3.1 Flash-Lite); reviewers saw sample text in rounds 1 and 4; 30 receipts per dataset show only that no large loss was seen; the known misses; both sets of numbers when `revised: true`. A test checks that the generated block holds these.

## What 60 receipts cannot say, and the 10k plan

Public receipts carry little personal data, so 60 receipts give few items and wide intervals: this run shows whether the method works and what it costs, not a precise recall. For the 10k run (`docs/OVERVIEW.ko.md`, "10k 로 갈 때"):
- Reused as is: boxes with `id`/`line` (also the planned layout features), `mask.py` and `pii_run.py`, the tag check, the job table with `run` in its key, the label format with `detections_sha256` and `item_hidden` (coverage on the fill mask), `pii_paths`, `25 replay`, and replay by swapping the T3/T4 read folders (no `_masked` twin of any policy).
- Per dataset: a sidecar. The shop-block and item-line rules are heuristics for SROIE and WildReceipt; CORD (Indonesian) gets its own dev-set fixtures before its numbers are trusted. If the 10k run uses one combined manifest, a per-row `mask_profile` field will choose the sidecar (absent = the manifest stem); open until that decision.
- New code needed: planting synthetic names, phones and member numbers into receipts with category, text and final box (the renderer in `scripts/07_synth.py` can be reused); that gives exact labels in the thousands at no labeling cost.
- Real, non-public receipts: the label call and the U read cannot send originals; labels come from the local VLM (T2) or people; `publish_reads` is `fields` or `none`, because a masked read's free text can hold what the masker missed.
- Its own budget campaign.

## Decided

2026-10-31: baseline `harness` (T2 not on the path); prompt and schema unchanged; success criteria above; labels by Flash-Lite; two layers. Kept defaults: an invoice number is not personal data; tags are opaque (`[P3]`, not `[NAME1]`); the request ID is never sent and never committed. Round 2 defaults (owner may override): the tag check runs on both U and M1 replays; local-only metrics keep their last committed values when local files are absent; criterion 3 judges T3-alone accuracy, replay precision is reported, not judged.

2026-11-01, round 3 defaults (accepted by the owner): a phone or card match that reads as a date or amount is not a hit; U skips the Gate; every cloud call names a one-model chain; `customer_address` stays a category and counts in criterion 1 (a known miss, not excused); a revision is a new `run`, never a rewrite of `r0`; staleness is judged on input data, code changes only set `revised`. The landing wording is decided at step 7 from the results.

2026-11-01, round 4 defaults (owner may override): one API request per job attempt, each reserved against the allowance before it is sent; one campaign of $0.20 covers r0 and its revisions; a revision reuses the r0 labels and U reads; the phone pattern's over-masking of barcodes, registration numbers and low-printed shop phones is accepted and reported; criterion 3 holds when the interval's upper end is at least 0 (no clear loss); masked replays publish only the `harness` policy; every decision about sending or judging lives in the two frozen modules.
