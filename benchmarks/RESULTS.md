# Benchmark: Single Agent vs. Single Agent (Checked) vs. Swarm Lite

This benchmark tests whether the `autonomous-evolutionary-agent-swarm` skill pack justifies its token and wall-clock overhead compared to a single coding agent on the same model (`inherit`). The harness is [`evaluate_benchmarks.py`](evaluate_benchmarks.py); raw per-run data and summary statistics are in [`results.json`](results.json), and subagent conversation IDs and wall times are in [`telemetry_meta.json`](telemetry_meta.json).

**Status:** All 8 tasks (`T1`–`T8`) complete (`n = 3` runs per cell: **3 arms × 6 tasks × 3 runs = 54 workspaces** for `T1`–`T6`, plus **2 arms × 2 tasks × 3 runs = 12 workspaces** for `T7`–`T8` = **66 workspaces total**, spanning 120 agent conversations including 36 Discriminator Gate reviewer invocations). See [`NEXT_RUN.md`](NEXT_RUN.md) and §6 for the `T7`–`T8` protocol and results. A further set of runs in Claude Code (§7: 4 harder, oracle-graded tasks `T9`–`T12`, 21 agent conversations) searched for tasks a single agent fails and tested shared-goal peers. §8 (`T13`) runs four arms on 20 SWE-bench Verified instances graded by their hidden tests (72 graded runs, about 8.5M tokens).

---

## 1. Executive Summary

### What the data shows

1. **Self-checks and explicit acceptance criteria (`single_agent_checked`) capture 100% of the quality gain across all 8 tasks (`24 / 24` runs passed) at a fraction of the token and wall-clock cost of `swarm_lite`.**
   - On `T1`–`T6` (18 runs per arm), `single_agent` passed **16 / 18** runs, `single_agent_checked` passed **18 / 18**, and `swarm_lite` passed **18 / 18**. On `T7`–`T8` (6 runs per arm), both `single_agent_checked` and `swarm_lite` passed **6 / 6** (`24 / 24` total).
   - Adding the *Acceptance Criteria & Self-Checks* section (`single_agent` → `single_agent_checked` on `T1`–`T6`) eliminated all UI defects on T4 (`1/3` passed → `3/3` passed) at about the same cost: **+1.8% transcript tokens** (`194.0k` → `197.5k`) and **−9.0% wall-clock time** (`6,010 s` → `5,472 s`). Both differences are within the run-to-run spread in §2, so read them as "no measurable extra cost", not as a saving.
2. **On the UI task (T4), an unchecked single agent fails 2 out of 3 runs; a self-checked single agent passes 3 out of 3.**
   - `single_agent` shipped real layout/structural bugs in 2 of 3 runs (`r1`: `off-centre-frame @768px` leaving 38% of the tablet viewport empty on the right; `r2`: `late-title @1440px` missing a primary `<h1>` heading) and triggered `slop-side-stripe @1440px` (`border-left: 4px solid`) in all 3 runs (`r1`–`r3`).
   - Both `single_agent_checked` and `swarm_lite` ran `web_ui_validator.py index.html --mode operate` before finishing and achieved **0 layout/runtime defects and 0 style findings across all 6 runs**.
   - The sample is small: `1/3` vs `3/3` alone gives p ≈ 0.4 (Fisher's exact test); pooling both checked arms (`6/6` vs `1/3`) gives p ≈ 0.08. The transcripts show the mechanism directly (every checked T4 run called the validator 6–9 times), which is why the result is credible despite the counts. `late-title` (no `<h1>` in a dashboard) is arguably a structure rule rather than a bug; without it `single_agent` is `2/3` on T4.
3. **On a 6-module parallel decomposition (`T7`), coordination overhead outweighs 3-way parallelism at this task size (`2.91×` wall time, `7.59×` transcript tokens).**
   - Splitting `T7` into `T7.0` (shared contract) → `T7.A`/`T7.B`/`T7.C` (3 concurrent workers) → `T7.D` (integration) with a reviewer per sub-task produced `0` integration defects (`3 / 3` passed all 11 held-out checks), matching `single_agent_checked` (`3 / 3`).
   - However, because a single checked agent completes all 6 modules in **269 s** `[213–312]` (`13.0k` tokens), running 3 sequential waves of worker + audit + reviewer subagents took **782 s** `[687–859]` (**2.91× slower**) and **99.0k** tokens `[96.8k–101.9k]` (**7.59× tokens**, or **5.62×** counting only the 10 worker+reviewer subagents per run). All 15 sub-task reviews passed on round 1 with `0` findings.
4. **The backend tasks (`T1`–`T3`, `T5`–`T8`) hit a model ceiling: `single_agent_checked` and `swarm_lite` passed every held-out check across all 7 backend tasks (`21 / 21` backend runs per arm).**
   - `T5` (a 6-file legacy billing codebase with 6 seeded bugs) and `T6` (MVCC + CRC32 WAL + compaction) test spec-following on multi-file and storage invariants.
   - `T8` states only 4 general invariants (exact money, conservation, determinism, side-effect-free validation) and withholds 12 implied edge-case traps (exact parsing without a float round-trip, `-0.05` formatting, remainder-cent tie-breaking across shuffled dict keys, negative-amount refunds flipping remainder direction, duplicate `expense_id` atomicity). Both `single_agent_checked` (`3 / 3`, mean `252 s`, `9.5k` tokens) and `swarm_lite` (`3 / 3`, mean `543 s` = `2.16×`, `30.8k` tokens = `3.24×`) derived and passed all 12 held-out checks on round 1. The traps are still too easy for this model (`inherit`), so `T8` does not separate the arms.
5. **Across all 36 Discriminator Gate reviews (`18` on `T1`–`T6`, `15` on `T7`, `3` on `T8`), the reviewer subagent caught zero blocking defects (`0` failed rounds, `0` Critical, `0` Important, `8` Minor).**
   - On `T1`–`T6`, adding the reviewer doubled transcript tokens (`197.5k` → `433.2k`, `2.19×`) and increased wall time by `1.35×`. On `T7`–`T8` (where the orchestrator conversation is also counted), `swarm_lite` cost `5.75×` the tokens (`67.7k` → `389.6k`) and `2.55×` the wall time (`1,561 s` → `3,974 s`) of `single_agent_checked` without changing functional correctness.
6. **Acceptance criteria can narrow the spec, and workers follow the criteria (T1).**
   - The T1 spec says idempotency raises `ValueError` "on conflicting reuse of the same key"; the acceptance bullet rephrased this as "identical postings replay, differing amount/account raises". All 3 `single_agent` runs compared both `tx_id` and postings on replay; **all 6 runs given the criteria compared postings only** (`0/6`).
   - Two of three reviewers noticed the gap but rated it Minor, so the narrowed behaviour shipped. No held-out check covers this case, so the pass rates above do not reflect it. See §3.3.
7. **A single checked agent also solved every harder task we could build (§7).** Four tasks graded against reference implementations — npm semver ranges (1,880 cases), cron schedules (187), `.gitignore` matching (495), and a full CommonMark 0.31.2 renderer (the spec's 652 examples) — were each solved perfectly by one checked agent, the CommonMark renderer three times out of three. No task left a quality gap for any multi-agent design to close.
8. **Shared-goal peers made a large task finish faster at equal quality (§7, CommonMark, `n = 3`).** Three peers with one goal, no orchestrator, no reviewer, coordinating only through a board, finished in **0.57×** the wall time of a single checked agent (`617 s` vs `1,075 s` mean; every peer run beat every single run) for **1.92×** the tokens (`351k` vs `183k`), with identical output (`652/652` in all 6 runs). This is the first configuration in this benchmark where adding agents bought something: time, at roughly a 2× token price, on a task that takes one agent ~15–20 minutes. On smaller tasks (3.5 and 7 minutes solo) the same peers saved no time (1.24× and 0.97×) at ~3× the tokens.
9. **On real bugs graded by hidden tests (SWE-bench Verified, §8), the extra agents finally changed outcomes, but modestly.** One checked agent resolved **14 / 20**; `best_of_3` **17 / 20** at 3.0× the tokens; `swarm_lite` with a reviewer also **17 / 20** at 2.1×; shared-goal peers **10 / 12** on the Django subset at 3.1× (checked: 9 / 12, `swarm_lite`: 11 / 12). The `swarm_lite` gate and reviewer stopped 5 of the 19 tasks they checked (the 20th hit the time cap first). They produced the only resolve no other arm got (django-12325), and caught 3 regressions the workers introduced that the hidden tests cannot see. No arm broke a previously passing test, and two misses were shared by every arm. With one run on 20 instances, these differences are suggestive, not significant.
10. **The narrowing in finding 6 came from where the narrowed sentence sat, not from missing guards (§9).**
   - Setup: the spec stated the full rule, and the narrowed wording appeared only as a checklist item.
   - All 3 current-pack runs built the full rule; in each, the Step 0.1 re-check rewrote the item.
   - All 3 runs with the v2.7 pack, which has no guards, also built it, following the spec over the checklist.
   - No stronger guard is needed.

### Practical recommendation

- **Use `single_agent_checked` as the default for single-repo tasks of this scale (~300–600 LOC, ≤ 6 modules):** include explicit acceptance criteria, executable outcome one-liners, and automated validators (`web_ui_validator.py --mode operate`, `goal_loop.py --audit-task`) in a single worker's prompt. It passed **24 / 24** runs (`100%`) across `T1`–`T8` at `1/2` to `1/7` the token cost and `1.35×` to `2.91×` faster wall-clock time than `swarm_lite`.
- **Check every acceptance-criteria item against the spec clause it covers** so the checklist never states a requirement more narrowly than the spec (finding 6).
- **Do not split small multi-module tasks (~300–500 LOC) across parallel worker subagents.** At `T7`'s scale (6 modules, ~4.5 minutes for one agent), 3-wave orchestration and per-task reviews cost `2.91×` wall time and `7.59×` tokens. Reserve parallel subagent dispatch for tasks where individual modules each require substantial independent work (e.g., ≥ 15–20 minutes per module) so parallel execution saves more time than multi-wave handoffs cost.
- **Use `/peer-swarm` (shared-goal peers) when a single build takes one agent ~15+ minutes, splits along natural module boundaries, and finishing sooner is worth about twice the tokens** (finding 8). Below that size, or when tokens matter more than time, use one checked agent.
- **Skip the separate Discriminator Gate reviewer subagent when deterministic checks (`verification_cmd`, `outcome_cmd`, AST wiring, authenticity, `web_ui_validator.py`) cover the spec.** Across 36 reviews on `T1`–`T8`, the reviewer recorded `0` blocking findings.
- **Use the reviewer when the real acceptance is not available as a command, such as fixing an issue in an existing codebase whose maintainers' tests you cannot see.** On SWE-bench (§8) it stopped 5 of 20 tasks, turned one miss into a resolve, and caught 3 regressions the workers introduced, for about 2.1× the tokens of one checked agent. `best_of_3` resolved the most instances (+3 at 3×) when its attempts diverged.

---

## 2. Aggregate & Per-Task Results (`n = 3` runs per cell, 66 runs total)

### Aggregate across `T1`–`T6` (all 3 arms, 18 runs per arm)

| Metric | `single_agent` | `single_agent_checked` | `swarm_lite` (Worker + Gate) | Ratio (`checked` / `single`) | Ratio (`swarm` / `checked`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Runs passing all post-hoc checks** | **16 / 18** (88.9%) | **18 / 18** (100%) | **18 / 18** (100%) | — | — |
| **Held-out / layout defects found afterwards** | **2** (T4 `r1`, `r2`) | **0** | **0** | — | — |
| **UI style findings (`slop-*`, reported separately)** | **3** (T4 `r1`–`r3`) | **0** | **0** | — | — |
| **Gate rounds failed / Critical+Important / Minor** | n/a | n/a | **0 / 0 / 6** | — | — |
| **Subagents spawned** | 18 | 18 | 36 (18 workers + 18 reviewers) | 1.00× | **2.00×** |
| **Total wall-clock time (sum of 18 runs)** | 6,010 s | 5,472 s | 7,396 s | 0.91× | **1.35×** |
| **Total planner steps** | 500 | 479 | 904 | 0.96× | **1.89×** |
| **Total tool calls** | 251 | 244 | 508 | 0.97× | **2.08×** |
| **Transcript tokens (est., sum of 18 runs)** | 194.0k | 197.5k | 433.2k | 1.02× | **2.19×** |

### Aggregate across `T7`–`T8` (2 arms, 6 runs per arm; includes orchestrator conversation in `swarm_lite`)

| Metric | `single_agent_checked` | `swarm_lite` (Orchestrator + Workers + Gate) | `swarm_lite` (Workers + Gate only) | Ratio (`swarm` total / `checked`) | Ratio (`swarm` subagents / `checked`) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Runs passing all post-hoc checks** | **6 / 6** (100%) | **6 / 6** (100%) | **6 / 6** (100%) | — | — |
| **Held-out defects found afterwards** | **0** | **0** | **0** | — | — |
| **Gate rounds failed / Critical+Important / Minor** | n/a | **0 / 0 / 2** | **0 / 0 / 2** | — | — |
| **Conversations (orchestrators + workers + reviewers)** | 6 | 42 (6 orch + 18 workers + 18 reviewers) | 36 (18 workers + 18 reviewers) | **7.00×** | **6.00×** |
| **Total wall-clock time (sum of 6 runs)** | 1,561 s | 3,974 s | — | **2.55×** | — |
| **Total planner steps** | 180 | 950 | — | **5.28×** | — |
| **Total tool calls** | 91 | 487 | — | **5.35×** | — |
| **Transcript tokens (est., sum of 6 runs)** | 67.7k | 389.6k | 278.6k | **5.75×** | **4.11×** |

### Per-task breakdown (`mean [min–max]` across `r1`, `r2`, `r3`)

| Task | `single_agent`: Pass / Wall (s) / Tokens (est.) / Defects | `single_agent_checked`: Pass / Wall (s) / Tokens (est.) / Defects | `swarm_lite`: Pass / Wall (s) / Tokens (est.) / Defects / Gate Minor |
| :--- | :--- | :--- | :--- |
| **T1** Multi-currency ledger & reconciler CLI (11 checks) | **3/3** · 352 s `[303–379]` · 11.1k `[10.6k–11.8k]` · 0 defects | **3/3** · 241 s `[235–251]` · 9.7k `[9.0k–10.7k]` · 0 defects | **3/3** · 341 s `[317–362]` · 20.0k `[19.3k–21.3k]` · 0 defects · 3 minor |
| **T2** Token-bucket + sliding-window rate limiter (6 checks) | **3/3** · 241 s `[213–256]` · 9.7k `[9.6k–9.8k]` · 0 defects | **3/3** · 201 s `[178–229]` · 8.3k `[7.3k–8.7k]` · 0 defects | **3/3** · 347 s `[294–406]` · 22.1k `[21.6k–22.6k]` · 0 defects · 1 minor |
| **T3** Dependency DAG workflow scheduler (8 checks) | **3/3** · 279 s `[242–339]` · 9.5k `[9.2k–9.8k]` · 0 defects | **3/3** · 227 s `[197–255]` · 9.3k `[9.2k–9.4k]` · 0 defects | **3/3** · 297 s `[255–352]` · 23.6k `[22.3k–25.6k]` · 0 defects · 0 minor |
| **T4** Log query engine, spike detector & HTML console (6 checks + 3-viewport UI) | **1/3** · 385 s `[356–415]` · 10.8k `[10.3k–11.7k]` · **2 defects** (+3 style) | **3/3** · 418 s `[405–442]` · 14.3k `[13.7k–14.8k]` · **0 defects** (0 style) | **3/3** · 601 s `[509–664]` · 35.1k `[27.5k–47.6k]` · **0 defects** (0 style) · 0 minor |
| **T5** Legacy billing, proration & EU VAT refactor (8 checks, 6 seeded bugs) | **3/3** · 318 s `[301–347]` · 12.4k `[12.3k–12.5k]` · 0 defects | **3/3** · 337 s `[306–358]` · 14.0k `[13.4k–14.5k]` · 0 defects | **3/3** · 417 s `[380–443]` · 23.4k `[22.9k–24.1k]` · 0 defects · 0 minor |
| **T6** Transactional MVCC KV store + CRC32 WAL + compaction (6 checks) | **3/3** · 429 s `[383–504]` · 11.2k `[10.1k–12.3k]` · 0 defects | **3/3** · 401 s `[377–428]` · 10.3k `[10.1k–10.5k]` · 0 defects | **3/3** · 463 s `[427–525]` · 20.2k `[18.4k–21.3k]` · 0 defects · 2 minor |
| **T7** Multi-warehouse order fulfilment (11 checks, 5 sub-tasks / 3 parallel) | *not run* | **3/3** · 269 s `[213–312]` · 13.0k `[12.8k–13.4k]` · 0 defects | **3/3** · 782 s `[687–859]` · 99.0k `[96.8k–101.9k]` (73.3k subagents) · 0 defects · 0 minor |
| **T8** Shared-expense ledger & settlement (12 unstated edge-case checks) | *not run* | **3/3** · 252 s `[248–259]` · 9.5k `[8.0k–10.9k]` · 0 defects | **3/3** · 543 s `[457–641]` · 30.8k `[30.5k–31.2k]` (19.5k subagents) · 0 defects · 2 minor |

---

## 3. Detailed Findings

### 3.1 T4 (`task_4_log_query_workbench`): Why `single_agent_checked` fixes the UI failures

`web_ui_validator.py index.html --mode operate` renders the page in headless Chromium across three viewports (`1440×900`, `768×1024`, `390×844`) and checks layout geometry, interactive elements, accessibility landmarks, and runtime console/page errors:

- **`single_agent` (`1 / 3` passed):**
  - **`r1` (Failed — `off-centre-frame @768px`):** Outer page content sat off-centre at `768px` with a `43px` left margin and `289px` right margin (leaving 38% of the tablet viewport empty on one side). Also triggered `slop-side-stripe @1440px` (`border-left: 4px solid` on `article.spike-alert-card`).
  - **`r2` (Failed — `late-title @1440px`):** Used a `<div>` instead of a primary `<h1>` element for the console title (`Primary <h1> element is missing from the page`). Also triggered `slop-side-stripe @1440px` on `div.spike-card`.
  - **`r3` (Passed layout checks, 1 style finding):** Passed functional and geometric checks, but triggered `slop-side-stripe @1440px` on `article.spike-card`.
- **`single_agent_checked` (`3 / 3` passed) and `swarm_lite` (`3 / 3` passed):**
  - Every run in both arms invoked `web_ui_validator.py index.html --mode operate` as part of its self-check before finishing, caught any initial layout or styling issue in its own edit-test loop (taking `16.7` mean tool calls in `single_agent_checked` vs `13.7` in `single_agent`), and finished with **0 layout/runtime defects and 0 style findings**.
  - This confirms the hypothesis from the preliminary `r1` analysis: the quality improvement on T4 comes entirely from giving the worker agent the validator command and acceptance criteria (`single_agent_checked`), not from the post-hoc Discriminator Gate (`swarm_lite`).

### 3.2 Harder Backend Tasks (`T5` and `T6`): Why all three arms still achieved `3 / 3`

To test whether multi-file legacy codebases or tricky concurrency/storage invariants would separate the arms on backend work, we added two substantially harder tasks to [`evaluate_benchmarks.py`](evaluate_benchmarks.py):

1. **`T5` (`task_5_legacy_billing_refactor` — 6-File Legacy Subscription Billing, Proration & Tax Refactor, 8 held-out checks):**
   - Unlike T1–T4 (which start from an empty workspace), T5 seeds a 6-file legacy codebase (`src/models.py`, `src/discounts.py`, `src/tax.py`, `src/billing.py`, `src/cli.py`, `tests/test_billing.py`) containing **6 interacting latent bugs**:
     1. `apply_discounts` mutates `LineItem.unit_price_cents` in-place, corrupting subsequent calls or retries.
     2. `create_invoice(..., preview=True)` mutates `CustomerAccount.credit_balance_cents`, stores the draft invoice in `_invoices`, and records `idempotency_key`.
     3. Coupons apply in arbitrary input order instead of `PERCENT` before `FIXED_CENTS` and fail to reject multiple `exclusive=True` coupons.
     4. Fixed-cent coupons allocate discounts purely to the first item instead of proportionally across eligible items via the largest-remainder method (breaking `tax_exempt` vs. taxable subtotals).
     5. EU B2B VAT reverse-charge (`0%` tax when `vat_registered=True` and `buyer_country != seller_country`) mistakenly zeroes out domestic B2B invoices (`DE` → `DE`).
     6. Negative net invoices from plan downgrades are clamped to `0` instead of crediting `account.credit_balance_cents`, and `void_invoice` fails to claw back generated credit (or reject voiding when that credit has already been spent) and restore spent credit.
   - In addition to fixing all 6 bugs, the agent must extract subscription proration (`prorate_subscription_change`) into a new module `src/proration.py` and wire it into `src/billing.py` and `src/cli.py`.
2. **`T6` (`task_6_mvcc_wal_store` — Transactional MVCC Key-Value Store with Framed CRC32 WAL & Snapshot Compaction, 6 held-out checks):**
   - Requires implementing `src/wal.py` (`WriteAheadLog` with `<crc32_hex_8chars>\t<compact_json>\n` framing, distinguishing torn-write EOF truncation without a trailing `\n` from mid-file or newline-terminated corruption that must raise `CorruptWALError`), `src/mvcc.py` (`MVCCStore` with Snapshot Isolation, First-Committer-Wins atomic conflict detection raising `WriteConflictError`, staged delete tombstone shadowing in both `get()` and `scan()`, and full state reconstruction on `MVCCStore.open()`), `src/compaction.py` (`compact_store()` computing `watermark_ts = min(active_tx_snapshots)` and purging obsolete versions plus tombstones whose older history is completely pruned), and `src/cli.py`.

**Result on T5 and T6:** All three arms passed **9 / 9 runs on T5** and **9 / 9 runs on T6** (`0` held-out defects across all 18 workspaces). Why? Because `TASK_SPEC.md` stated the domain specification clearly, and on backend Python tasks the model (`inherit`) naturally writes comprehensive `unittest` suites (averaging 18.3 tool calls on T5 and 13.7 on T6 in `single_agent`) and iterates until all invariants pass. Unlike visual CSS layout geometry at 768px (which an LLM cannot "see" without running a headless browser check), backend invariants described in the prompt are directly testable by the agent's own unit tests.

### 3.3 Discriminator Gate Behavior & Acceptance Criteria Narrowing the Spec

Across all 18 `swarm_lite` runs, the Discriminator Gate passed every worker on the first review round (`0` Critical, `0` Important, `6` Minor non-blocking findings deferred to `.swarm/deferred_minor_ledger.md`):

- **Where the 6 Minor findings occurred:**
  - `T1 r1`: 0 minor; `T1 r2`: 1 minor; `T1 r3`: 2 minor.
  - `T2 r3`: 1 minor (narrowing `raw_policies: Any` type annotation in `src/router.py`).
  - `T6 r1` & `T6 r3`: 1 minor each (`src/cli.py` calling `wal.recover()` before `MVCCStore.open(path)`, which calls `recover()` a second time).
- **Acceptance criteria narrowing the spec on T1 (summary finding 5):**
  - In `T1`, the base `TASK_SPEC.md` (`spec_md`) states: *"Enforces idempotency via `tx.idempotency_key` (safe replay for identical transactions; raises `ValueError` on conflicting reuse of the same key)."* All 3 `single_agent` runs (`r1`–`r3`) checked both `existing.tx_id == tx.tx_id` and `existing.postings == tx.postings` on idempotency replay.
  - However, the *Acceptance Criteria & Self-Checks* `review_focus` bullet (appended to `single_agent_checked` and `swarm_lite`) phrased the check as: *"Idempotency key replay with identical postings returns original transaction without double-counting, while differing amount/account raises ValueError."* Focusing on that bullet, all 6 runs of `single_agent_checked` (`r1`–`r3`) and `swarm_lite` (`r1`–`r3`) compared only `postings` (`_postings_match`) and did not check `existing.tx_id == tx.tx_id` when postings were identical.
  - Two of the three `swarm_lite` Discriminator Gate reviewers (`T1 r2` and `T1 r3`) spotted that `_postings_match` did not check `existing.tx_id != tx.tx_id` but logged it as Minor, so it was deferred and shipped. This is the only case in 18 reviews where the reviewer saw something the worker missed, and its severity call meant nothing changed. `/discriminator-gate` now classifies a requirement implemented more narrowly than the spec as a Missing Requirement (Spec `FAIL`).

---

## 4. Threats to Validity

| Issue | Effect | Status |
| :--- | :--- | :--- |
| Swarm Lite's brief contained the review focus, outcome command, and UI grading rule; `single_agent`'s spec did not. | Information advantage for `swarm_lite`, decisive on T4. | **Resolved:** `single_agent_checked` and `swarm_lite` receive the exact same *Acceptance Criteria & Self-Checks* section in `TASK_SPEC.md`, isolating the effect of self-checks from the Discriminator Gate. |
| Single run per cell (`n = 1`) in initial report. | Could not separate signal from run-to-run variance. | **Resolved:** All 3 arms × 6 tasks now have `n = 3` independent runs (`r1`, `r2`, `r3` = 54 workspaces). |
| `slop-*` style rules counted as defects. | Pack's aesthetic rule would grade the pack. | **Resolved:** Reported separately as `ui_style_findings` and excluded from `total_defects`. |
| Backend tasks (`T1`–`T3`, `T5`, `T6`, `T8`) hit a ceiling. | Every arm passes every check, so the backend data cannot separate the arms. | **Tested in T8, ceiling persists:** Even when `T8` stated only 4 invariants and withheld 12 implied edge-case traps, both `single_agent_checked` (`3/3`) and `swarm_lite` (`3/3`) passed all 12 checks on round 1. |
| The swarm's intended use case (parallel workers on a shared contract) was not tested. | Results only cover single-worker tasks. | **Resolved in T7:** Tested a 6-module task split into `T7.0` → parallel `T7.A`/`B`/`C` → `T7.D`. Both arms passed `3/3` (`0` integration defects), and `swarm_lite` took `2.91×` wall time and `7.59×` tokens due to 3-wave coordination overhead. |
| Acceptance criteria restated a T1 spec clause more narrowly (finding 6). | All 6 runs with criteria implemented the narrow version; no held-out check covers it. | **Mitigated for future runs:** task briefs and the skills now state that `review_focus` adds to the spec and never replaces it. T8's criteria restate only the spec's invariants. Old runs are unchanged. |
| `n = 3` per cell. | The T4 difference alone is not statistically significant (p ≈ 0.4; pooled p ≈ 0.08). | **Open:** credible because the transcripts show the mechanism; more runs would firm it up. |
| Token figure is `chars / 4` of `transcript.jsonl`. | Includes JSON framing and tool output, excludes prompt prefix re-reads on each turn; not billed API tokens. | **Labelled:** Reported as `transcript_tokens_est` alongside exact `planner_steps`, `tool_calls`, and `wall_seconds`. |

---

## 5. Method

### Experimental Arms

All subagents run on the same model (`inherit`) in isolated workspaces under `benchmarks/runs/<arm>/<task>/r<1..3>/`:

| Arm | Input Provided in Workspace | Execution Process |
| :--- | :--- | :--- |
| `single_agent` | `TASK_SPEC.md` (core specification only) | 1 worker agent builds and tests until satisfied |
| `single_agent_checked` | `TASK_SPEC.md` + *Acceptance Criteria & Self-Checks* (`review_focus`, `verification_cmd`, `outcome_check_cmd`, `ui_validator_cmd`) | 1 worker agent builds, runs self-checks/validators, and finishes |
| `swarm_lite` | Same as `single_agent_checked`, plus `.swarm/goal_loop.json` and `.swarm/briefs/<id>.md` | 1 worker agent + `goal_loop.py --generate-review-package` + 1 independent Discriminator Gate reviewer subagent + `goal_loop.py --record` |

- Comparing `single_agent` → `single_agent_checked` isolates the value of **explicit acceptance criteria and self-check tools**.
- Comparing `single_agent_checked` → `swarm_lite` isolates the value of **the independent Discriminator Gate review loop**.

### Post-Hoc Evaluation Suite (68 Checks for T1–T8 + 3-Viewport Browser Validation)

Every completed workspace is graded by [`evaluate_benchmarks.py`](evaluate_benchmarks.py) on:
1. **68 held-out functional checks** across the 8 tasks (`T1`: 11, `T2`: 6, `T3`: 8, `T4`: 6, `T5`: 8, `T6`: 6, `T7`: 11, `T8`: 12), none of which are shown to the agents.
2. **AST call-site wiring (`goal_loop.verify_wiring`)** confirming required symbols are actively imported and called across entrypoints.
3. **Authenticity scan (`goal_loop.audit_authenticity`)** checking for `TODO`/`FIXME`/`NotImplementedError` stubs, hardcoded constant returns, mock-only tests, and orphan modules.
4. **Unit test execution (`unittest discover`)** verifying the agent's own test suite exits `0`.
5. **Real-browser 3-viewport UI validation (`T4` only)** via `web_ui_validator.py index.html --mode operate` at `1440px`, `768px`, and `390px`.
6. **Discriminator Gate ledger inspection (`swarm_lite` only)** reading review rounds, finding counts, and (from T7 on) whether each verdict came from a reviewer subagent or a self-check, from `.swarm/goal_loop.json`.

---

## 6. T7 and T8 Results: Parallel Modules & Unstated Edge-Case Traps

Tasks `T7` and `T8` test the two questions left open by `T1`–`T6`. Each was run in interleaved order (`T7 checked`, `T7 swarm`, `T8 checked`, `T8 swarm` across `r1`, `r2`, `r3` = 12 runs) following [`NEXT_RUN.md`](NEXT_RUN.md). Both check sets were validated before the run against a reference implementation and 14 deliberately broken variants (7 for `T7`, 7 for `T8`). Preparing `T7` also fixed a bug in `goal_loop.py` where a module built by a parallel sub-task failed its own audit as `UNWIRED_MODULE` before its dependent integration task ran.

| Task | Question | Arm | Pass | Wall Time (s) `mean [min–max]` | Planner Steps `mean [min–max]` | Tool Calls `mean [min–max]` | Transcript Tokens (est.) `mean [min–max]` | Gate Rounds / Failed / Crit+Imp / Minor / Sources |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **T7** Multi-warehouse order fulfilment (6 modules, 11 checks) | Do parallel workers on a locked contract save wall time without adding integration defects? | `single_agent_checked` | **3/3** | **268.7 s** `[213–312]` | **32.3** `[29–34]` | **17.3** `[16–20]` | **13.0k** `[12.8k–13.4k]` | n/a |
| **T7** | *(5 sub-tasks: `T7.0` → parallel `T7.A`/`B`/`C` → `T7.D`)* | `swarm_lite` (11 convs/run) | **3/3** | **781.7 s** `[687–859]` (**2.91×**) | **241.7** `[230–264]` (**7.47×**) | **125.0** `[119–135]` (**7.21×**) | **99.0k** `[96.8k–101.9k]` (**7.59×**; `73.3k` / **5.62×** subagents only) | `5/run` (`15` total) / `0` failed / `0` / `0` / `{"reviewer": 5}` |
| **T8** Shared-expense ledger & settlement (4 modules, 12 checks) | When the spec states invariants but not implied edge cases, does a reviewer catch what a worker misses? | `single_agent_checked` | **3/3** | **251.7 s** `[248–259]` | **27.7** `[24–32]` | **13.0** `[11–15]` | **9.5k** `[8.0k–10.9k]` | n/a |
| **T8** | *(1 task `T8` + reviewer per Step 1.5b)* | `swarm_lite` (3 convs/run) | **3/3** | **543.0 s** `[457–641]` (**2.16×**) | **75.0** `[71–78]` (**2.71×**) | **37.3** `[34–41]` (**2.87×**) | **30.8k** `[30.5k–31.2k]` (**3.24×**; `19.5k` / **2.05×** subagents only) | `1/run` (`3` total) / `0` failed / `0` / `2` (`r2`, `r3`) / `{"reviewer": 1}` |

### 6.1 Interpretation of T7 (Parallel Workers on a Shared Contract)

- **Quality (`3/3` vs `3/3`, `0` integration defects):** Locking `src/contracts.py` in `T7.0` before dispatching `T7.A` (`src/catalog.py`), `T7.B` (`src/inventory.py`), and `T7.C` (`src/shipping.py`) concurrently prevented any cross-module contract drift. All 3 `swarm_lite` runs integrated cleanly in `T7.D` (`src/orders.py`, `src/cli.py`) on the first attempt (`0` failed review rounds, `0` held-out defects across all 11 integration seam checks).
- **Speed & Cost (`2.91×` wall time, `7.59×` tokens):** Despite `T7.A`, `T7.B`, and `T7.C` executing concurrently in the middle wave, `swarm_lite` was **2.91× slower** (`781.7 s` vs `268.7 s`) and used **7.59× more transcript tokens** (`99.0k` vs `13.0k`) than `single_agent_checked`.
- **Where the swarm's time went** (per-conversation timestamps from the transcripts, mean of 3 runs):

  | Stage | Time |
  | :--- | :---: |
  | Contract worker `T7.0` | 93 s |
  | Parallel wave `T7.A`/`B`/`C` (started within 4 s of each other) | 129 s, vs 331 s if run one after another |
  | Integration worker `T7.D` | **256 s**, about as long as the whole single-agent run (269 s) |
  | Reviewers, plus time when only the orchestrator was working | the rest of the 782 s |

  Parallelism saved about 200 s in the middle wave, but the dependency chain (contract → modules → integration) puts three agent start-ups in a row, and the integration worker re-reads everything the others wrote. Even with no reviewers and no orchestrator time, the swarm would have averaged about 480 s, roughly 1.8× the single agent. By role, workers alone used about 3.6× the single agent's tokens (each re-reads the spec, contract and brief); the orchestrator and the reviewers each added roughly another quarter of the total. Per the decision rubric in [`NEXT_RUN.md`](NEXT_RUN.md) §6: *coordination overhead outweighs parallelism at this size; use a single checked agent unless individual modules are much larger*.

### 6.2 Interpretation of T8 (Invariants Stated, Edge Cases Implied)

- **Both arms passed all 12 held-out traps (`3/3` vs `3/3`, `0` defects):** `T8`'s specification states only 4 invariants (exact money with no binary floats, conservation of cents, determinism independent of dict/insertion order, and side-effect-free `ValueError` on invalid input) without listing the 12 edge cases tested by the evaluator (e.g., parsing `"19.99"` exactly as `1999` cents where a float round-trip gives `1998`, formatting `-5` cents as `"-0.05"` where naive floor division gives `"-1.95"`, deterministic remainder-cent distribution across shuffled participant weights, negative-amount refunds flipping remainder direction, rejecting zero total weight, rejecting duplicate `expense_id` without mutating state, and settling balances deterministically).
- **Ceiling effect persists:** Every `single_agent_checked` worker and every `swarm_lite` worker reasoned from the 4 stated invariants to cover all 12 edge cases in its own implementation and unit test suite (`17`–`20` unit tests per run) before finishing. All 3 `swarm_lite` reviewer runs passed on Round 1 (`0` Critical, `0` Important, `2` Minor annotations on `typing.Any` in `src/cli.py` JSON parsing). Per [`NEXT_RUN.md`](NEXT_RUN.md) §6: *the traps are still too easy for this model (`inherit`), so `T8` does not separate the arms*.

## 7. Claude Code Runs: Searching for Headroom, and Shared-Goal Peers

Every task in §2–§6 was solved by a single checked agent, so no multi-agent design could show a quality gain there. These runs looked for tasks a single agent fails, and tested a design not tried before: peers that share one goal and organise themselves.

**Setup.** All runs used Claude Code subagents on one model (a different harness and model from the Antigravity runs above, so compare arms only within this section). Workspaces lived outside the repository so agents could not find the grading code; every transcript was scanned afterwards for network use, reference-tool use (`node`, `git`, `croniter`, Markdown packages), and file access outside the workspace — none found. Token counts are the harness's own per-agent totals (`telemetry_claude_code.json`), not the `chars / 4` estimate used above, so they are not comparable with the Antigravity figures. Completed workspaces are archived in `runs_claude_code/`; graded results are in `results_claude_code.json`.

### 7.1 Tasks with a reference oracle (`T9`–`T12`)

Each task names a public standard instead of spelling out its rules, and the hidden checks come from the reference implementation (`oracle_tasks.py`, `oracles/`). Every check set was validated before use with a perfect stand-in (score `1.0`) and deliberately corrupted ones (only the corrupted cases fail; an endless loop costs only its own cases via a timeout).

| Task | Oracle | Cases | Single checked agent |
| :--- | :--- | :---: | :--- |
| `T9` npm semver ranges (`valid`, `compare`, `satisfies`, `max_satisfying`) | node `semver` 7.8.5 | 1,880 | `r1`: **1.0**, 431 s, 91k tokens |
| `T10` cron next-fire times, crontab(5) syntax | `croniter` 6.2.4 (cases where it departs from crontab(5) excluded) | 187 | `r1`: **1.0**, 155 s, 52k tokens |
| `T11` `.gitignore` matching, one root file | `git ls-files --ignored` (git 2.53.0) | 495 | `r1`: **1.0**, 211 s, 59k tokens |
| `T12` CommonMark 0.31.2 renderer | the spec's 652 examples | 652 | `r1`–`r3`: **1.0** each (652/652 exact), 894–1,265 s |

All four were solved perfectly from memory, so `best_of_3` (with `scripts/attempt_picker.py`) and `spec_tester` were not run: with nothing left to fix, they could only add cost. Both remain provisioned in the harness for tasks that do leave a gap.

### 7.2 Shared-goal peers on `T12` (`n = 3`)

Three peers started at the same moment in one workspace with the same goal (`TASK_SPEC.md` and its acceptance checks), a board (`skills/peer-swarm/board_template.md`), no orchestrator and no reviewer. The single-agent and peer runs for `r2` and `r3` ran at the same time, so shared load affected both arms equally.

| Run | Single checked: wall / tokens | 3 peers: wall / tokens | Peers vs single |
| :--- | :---: | :---: | :---: |
| `r1` | 1,265 s / 207k | 736 s / 366k | 0.58× time, 1.77× tokens |
| `r2` | 1,067 s / 183k | 575 s / 357k | 0.54× time, 1.94× tokens |
| `r3` | 894 s / 157k | 539 s / 331k | 0.60× time, 2.11× tokens |
| **Mean** | **1,075 s / 183k** | **617 s / 351k** | **0.57× time, 1.92× tokens** |

- **Quality:** `652/652` exact in all six runs; both arms passed the evaluator's wiring, authenticity and unit-test checks.
- **Speed:** every peer run was faster than every single run (one-sided exact rank test p = 0.05 at `n = 3`; the paired ratios were 0.54–0.60).
- **How the peers organised themselves** (from the boards): in all three runs they split the work along the spec's own seams (block parser / inline parser / wrapper, CLI and test suite), wrote interfaces under *Decisions* before building on them (in `r1` one peer withdrew its own interface proposal to follow the other two), and tested each other's work. In `r1` and `r2` one peer found a `RecursionError` on deeply nested input in another peer's module, and the owner fixed it.
- **Why this worked when `T7`'s orchestrated split did not:** `T12` takes one agent ~15–20 minutes instead of ~4.5, and the peers had no sequential stages — they negotiated interfaces while already writing code, instead of waiting for a contract task, and there was no orchestrator or reviewer start-up on the critical path.
- **Task size decides it.** The same peer protocol on two smaller tasks (one run each) saved no time:

  | Task | Single checked (wall / tokens) | 3 peers (wall / tokens) | Peers vs single |
  | :--- | :---: | :---: | :---: |
  | `T11` gitignore (~3.5 min solo) | 211 s / 59k | 261 s / 186k | **1.24× time**, 3.17× tokens |
  | `T9` semver (~7 min solo) | 431 s / 91k | 419 s / 259k | **0.97× time**, 2.84× tokens |
  | `T12` CommonMark (~18 min solo, `n = 3`) | 1,075 s / 183k | 617 s / 351k | **0.57× time**, 1.92× tokens |

  Both small-task peer runs passed every case too (score `1.0`). Below roughly 7–10 minutes of single-agent work, splitting, negotiating interfaces and cross-checking cost as much time as they save; the token premium is highest there.
- **Integrity note:** in the `T11` peer run one peer used `git diff` and `git status` in its own workspace to see the other peers' edits. That is version control, not git's ignore matching (the oracle), so the run counts.
- **Limits:** one task in the regime where peers pay off, `n = 3` there and `n = 1` on the small tasks, one model and harness, and only 3 peers. The speed-up should shrink for work that does not split into independent parts, and peers editing the same file concurrently is a known risk that did not occur here.

### 7.3 Pack changes from these runs

- New skill `/peer-swarm` (the protocol above) and `scripts/attempt_picker.py` (cross-testing selection among independent attempts, with tests; not yet validated in a benchmark because no task left a gap).
- `goal_loop.py`: `pass`-only methods in a handler family (3+ methods sharing a prefix such as `visit_`, at least half with real bodies) are now an advisory instead of a blocking stub; `T12`'s first run was failed by the audit for a legitimate no-op `r_document()` handler.

## 8. SWE-bench Verified (`T13`): Real Bugs with Hidden Tests

`T1`–`T12` never separated the arms because one checked agent solved everything. `T13` uses 20 instances from [SWE-bench Verified](https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified) rated "1–4 hours" or harder (12 Django, 5 SymPy, 3 pytest; [`swe/instances.json`](swe/instances.json)). Each is a real GitHub issue in a real repository, graded by the official SWE-bench harness (swebench 5.0.2) against the issue's own hidden tests. Harness: [`swe/swe_bench.py`](swe/swe_bench.py); results: [`swe/results_claude_code.json`](swe/results_claude_code.json); telemetry: [`swe/telemetry_claude_code.json`](swe/telemetry_claude_code.json). The Antigravity/Argon protocol is in [`swe/NEXT_RUN_SWE.md`](swe/NEXT_RUN_SWE.md).

**Setup.** Claude Code subagents, one model, one run per instance and arm. Each workspace is a checkout of the instance's Docker image; agents run tests only through `run_tests.sh` (the instance image, `--network none`) and see the issue text, not the hidden tests. The graded patch is the workspace's change to non-test files. Every run was capped at 60 minutes, and whatever was on disk at the cap was graded.

- `single_agent_checked`: one agent with acceptance criteria (regression test that fails before and passes after; run the related test modules).
- `best_of_3`: three independent checked attempts, then `scripts/attempt_picker.py` runs each attempt's new tests against every attempt's code and keeps the one that passes most (no model involved).
- `swarm_lite`: `/invoke-swarm lite` with the orchestrator (the main session) doing worker dispatch → deterministic gate (`goal_loop.py --audit-task`) → reviewer subagent (Step 1.5b, since acceptance cannot be checked by a command when the tests are hidden) → fix loop.
- `swarm_peers`: three peers in one workspace with the shared goal and a board (`/peer-swarm`). Stopped after the 12 Django instances to save quota.

### 8.1 Results

| Arm | Resolved | Mean tokens / instance | Mean wall / instance |
| :--- | :---: | ---: | ---: |
| `single_agent_checked` | **14 / 20** | 53k | 345 s |
| `best_of_3` | **17 / 20** | 158k (3.0×) | 527 s |
| `swarm_lite` | **17 / 20** | 111k (2.1×) | 803 s |
| `swarm_peers` (Django only) | **10 / 12** | 163k (3.1×) | 200 s |

On the 12 Django instances, where all four arms ran:

| Arm | Resolved | Mean tokens | Mean wall |
| :--- | :---: | ---: | ---: |
| `single_agent_checked` | 9 / 12 | 52k | 110 s |
| `best_of_3` | 10 / 12 | 151k | 206 s |
| `swarm_peers` | 10 / 12 | 163k | 200 s |
| `swarm_lite` | **11 / 12** | 110k | 518 s |

Per instance, only these differed (✓ resolved, · not, – not run):

| Instance | checked | best_of_3 | swarm_lite | peers | What decided it |
| :--- | :---: | :---: | :---: | :---: | :--- |
| django-12325 | · | · | ✓ | · | Every attempt made the same narrow fix; only `swarm_lite`'s reviewer failed it (an unmarked `OneToOneField` could still become the parent link) and the worker's fix round resolved it |
| django-14011 | · | ✓ | ✓ | ✓ | The checked agent closed connections only; every other arm also passed the live server's `connections_override` to request threads |
| sympy-16597 | · | ✓ | ✓ | – | Runs in every arm hit the 60-minute cap in SymPy test sweeps and were graded as they stood: the checked agent's change was incomplete, the picker kept the one attempt that also changed `mod.py`, and the `swarm_lite` worker's change resolved it before reaching the gate or reviewer |
| pytest-10356 | · | ✓ | · | – | The hidden test checks the exact order of merged marks; two of three `best_of_3` attempts used that order |
| django-16263 | · | · | · | · | All arms missed: the hidden test also expects unused `alias()` annotations pruned |
| sympy-18199 | · | · | · | – | All arms missed: the hidden test expects composite-modulus support in `solveset`, beyond the issue |

No arm lost an instance that the checked agent resolved, and no change broke a test that passed before (`PASS_TO_PASS` failures: 0 in all 72 graded runs). With 20 instances and one run each, differences of 2–3 instances are suggestive, not significant (`best_of_3` vs checked: 3 wins, 0 losses, one-sided sign test p = 0.125).

### 8.2 What the reviewer did on hidden-test work

On `T1`–`T8` the reviewer caught nothing blocking in 36 reviews. On `T13` the `swarm_lite` gate and reviewer stopped **5 of the 19** tasks they checked (sympy-16597's worker hit the 60-minute cap before the gate):

| Instance | Caught by | Finding | Outcome |
| :--- | :--- | :--- | :--- |
| django-12325 | reviewer, Important | Fix incomplete: an unmarked `OneToOneField` to the parent could still become the parent link | Fixed in round 1 → **resolved** (no other arm resolved it) |
| sympy-14248 | reviewer, Important | The worker's pretty-printer change dropped the parentheses on a negated sum after the first term (`A^-1 - B + C` for `A^-1 - (B + C)`), changing the expression's meaning | Fixed in round 1; resolved either way, so the hidden tests would not have shown this regression |
| django-16263 | reviewer, Critical | The worker's change inlined a window-function annotation into `aggregate()`, raising `OperationalError` on SQLite where the base commit worked | Fixed in round 1; still unresolved (see 8.1) |
| pytest-10356 | reviewer, Important | The worker's change silently dropped all class marks for users of the issue's own metaclass workaround | Fixed in round 1; still unresolved (mark order) |
| sympy-18199 | deterministic gate | The worker reported its regression test passing; it failed on the worker's own code | Test corrected in round 1 |

Three of the five were **regressions the worker introduced and its own tests missed** — real quality the resolve rate does not measure, because the hidden tests do not cover those paths. Every finding was confirmed by the reviewer running code through `run_tests.sh`; all were fixed in one round; re-reviews were scoped to the fix diff. The 14 other checked tasks passed review on round 1 with only Minor notes. A fix round cost about 1.3–1.4× a task that passed directly.

**Caveat (memorisation).** In the django-12325 review the reviewer suggested a test it named `test_onetoone_with_parent_model`, which is the name of the hidden upstream test. The name appears nowhere in the workspace or in any command the reviewer ran, so the model recalled it from training data. The finding itself was verified by running code, but familiarity with Django's history may have helped. This can affect any arm.

### 8.3 What best-of-3 and peers did

- **`best_of_3` gains when attempts diverge and loses nothing when they agree.** On the three instances it gained, at least one attempt found the fuller fix and the picker kept it. On django-12325, 16263 and sympy-18199 all three attempts made the same narrow fix, so there was nothing better to pick. **Picker limit:** it scores whole test files by exit code, so where a file already fails at the base commit (SymPy stats and printing), every attempt scores 0 or ties and the pick falls back to attempt 1.
- **Peers matched `best_of_3` on Django at about the same tokens and wall time**, and their cross-checking caught two real bugs: on django-15128 one peer's regression test exposed a case the other peer's first fix missed, and on django-15957 a peer found that a sliced prefetch without `to_attr` still failed. Without a reviewer they converged on the narrow django-12325 fix like everyone else. Coordination hazards seen: two claim races on the board, two peers writing the same test file, and two `git stash` runs in the shared tree that briefly removed other peers' edits (nothing was lost).
- **Wall time:** peers and `best_of_3` ran their agents in parallel (about 200 s on Django); `swarm_lite` is sequential (worker → gate → reviewer → fix round) and took about 4.7× the checked agent's wall time on Django.

### 8.4 Harness notes

- The deterministic gate initially failed on 3 instances (sympy-13878, sympy-14248, pytest-6197) only because the worker's validation command covered test files that already fail at the base commit; the orchestrator narrowed the command to the worker's new tests, as [`NEXT_RUN_SWE.md`](swe/NEXT_RUN_SWE.md) now describes.
- Reviewers reported that the review package listed only target files and left out the worker's tests. From `django-13128` on, the reviewer prompt also pointed to `git diff <base> HEAD`; `goal_loop.py --review-package` now includes changed test files itself.
- Token figures are the harness's per-agent totals; a resumed agent reports a cumulative total, so fix rounds are counted as the increase.
- In django-10554 the `swarm_lite` reviewer made a throwaway copy of the repository inside the test container while checking a finding; no files were left behind. From django-13128 on, the reviewer prompt forbade creating or copying files in the workspace. `/discriminator-gate` now states this as Iron Law 6.

### 8.5 Recommendation for bug fixing against hidden acceptance

- **Keep `single_agent_checked` as the default.** It resolved 14 / 20 at the lowest cost, and every miss was a partial fix that passed its own checks.
- **When correctness matters and the acceptance tests are not available, run `/invoke-swarm lite` with the reviewer (Step 1.5b).** For about 2.1× the tokens it resolved 3 more instances than the checked agent (tying `best_of_3` at 17 / 20 for two-thirds of its tokens) and stopped 3 worker-introduced regressions that grading cannot see. This is the first evidence in this benchmark that the reviewer pays for itself.
- **Use `best_of_3` when the fix can go several ways** (it gained as many instances as `swarm_lite`, at 3× and in less wall time), but not as a substitute for review: identical attempts give the picker nothing to choose.
- **Peers** cost the same as `best_of_3` here and added cross-checking, but no quality beyond it; prefer them for large builds (§7.2).

## 9. Existing narrowing guards (benchmark `T1`)

Finding 6 showed that all six runs given a narrowed acceptance bullet built the narrow idempotency rule. Since then the pack added three guards: the task brief says review-focus items never replace the spec; the reviewer rates a narrowed requirement as Spec `FAIL`; and `/invoke-swarm` Step 0.1 asks the orchestrator to re-check each `review_focus` item against the spec clause it covers. This section measures them ([design](../docs/designs/skill-pack-v3.md), goal G1).

**Setup.** `T1`, `swarm_lite`, provisioned with `evaluate_benchmarks.py --setup --spec-only`. `TASK_SPEC.md` holds the plain spec with the full rule ("safe replay for identical transactions; raises `ValueError` on conflicting reuse of the same key"). The narrowed bullet appears only as a `review_focus` item in `.swarm/goal_loop.json`, where an orchestrator would put it.
- **Arms:** the current pack (`cur`), and the v2.7 pack from commit `fefd7ad` (`v27`). The v2.7 pack predates all three guards, and its briefs were regenerated with its own `goal_loop.py`.
- **Isolation:** both pack copies had README, benchmarks, docs and probe tests removed, so no agent could read the expected answer.
- **Orchestrator:** each run had a fresh general-purpose orchestrator subagent that started its own worker and reviewer. The reviewer was forced on ("the user asks for an independent review").
- **Grading:** [`t1_reuse_probe.py`](t1_reuse_probe.py) reuses a key with identical postings and a different `tx_id`. On the archived runs it reproduces finding 6 exactly (3 `single_agent` runs `FULL_RULE`, 6 checked runs `NARROW_RULE`).

| Run | Probe | Tokens | Wall | Fix rounds | Guard that acted |
| :--- | :---: | ---: | ---: | :---: | :--- |
| t1g-cur-r1 | `FULL_RULE` | 232,774 | 596 s | 0 | Step 0.1: orchestrator rewrote the item to quote the spec |
| t1g-cur-r2 | `FULL_RULE` | 228,829 | 516 s | 0 | Step 0.1: orchestrator rewrote the item to quote the spec |
| t1g-cur-r3 | `FULL_RULE` | 188,109 | 333 s | 0 | Step 0.1: orchestrator rewrote the item to quote the spec |
| t1g-v27-r1 | `FULL_RULE` | 270,224 | 525 s | 1 | none: the narrowed item stayed; the worker followed `TASK_SPEC.md` |
| t1g-v27-r2 | `FULL_RULE` | 217,044 | 427 s | 0 | none: the narrowed item stayed; the worker followed `TASK_SPEC.md` |
| t1g-v27-r3 | `FULL_RULE` | 311,478 | 664 s | 1 | none: the narrowed item stayed; the worker followed `TASK_SPEC.md` |

**Results:**
- **G1 is met.** 3 of 3 current-pack runs build the full rule.
- **The control shows the guards were not needed here.** 3 of 3 v2.7 runs also build the full rule with the narrowed item left in place.
- **What caused finding 6 was placement, not the absence of guards.** When the narrowed sentence is part of `TASK_SPEC.md`, workers follow it. When the spec states the full rule and the narrowed wording is only in the checklist, workers follow the spec.
- **Step 0.1 works as written.** In all three current-pack runs the orchestrator found the narrowed item (and a second narrowed item about batch rollback) and rewrote both to quote the spec before dispatch.
- **The reviewer guard was never tested,** because no run built the narrow rule. It still guards the case that matters: a narrowed sentence in a spec nobody re-checks.
- **No stronger guard is needed.** The quoted-clause rule and the brief-check subagent stay unbuilt (design, Future Improvements).

**Side observations** (n = 3 per arm, so suggestive only):
- **Fix rounds.** The current-pack runs needed no fix round. Two of three v2.7 runs needed one, for unrelated Important findings: Decimal precision in JSONL parsing, an AttributeError on malformed replay, and InvalidOperation on huge amounts. Step 0.1 also added test items for overdraft, FX, reconciliation and the CLI, which may explain the cleaner first pass.
- **Cost.** Mean cost was 217k tokens per run for `cur` and 266k for `v27`, against an estimate of about 70k per run in the design. The forced reviewer and the orchestrator each cost roughly as much as the worker.
- **A skill defect.** All three current-pack orchestrators found that `/invoke-swarm` Step 2.5 calls `quality_validator.py --workspace --test-cmd`, which the script does not accept, because it only smoke-tests game binaries.
- **A harness limitation of nested orchestration.** When an orchestrator subagent resumes its worker for a fix round, the worker's completion notice goes to the top-level session, not to the orchestrator, which then stops waiting. Two v2.7 runs had to be resumed with a neutral "continue to the end" message. In one, the worker's report was relayed word for word.

Telemetry: `~/agent-swarm-bench/t1-guards/telemetry.json` (outside the repository). Workspaces: `~/agent-swarm-bench/t1-guards/{cur,v27}/`. Published `T1` results and `results.json` are unchanged.

## 10. Reproducing

```bash
# Provision missing workspaces (existing runs are preserved; --clean deletes ALL runs)
python3 benchmarks/evaluate_benchmarks.py --setup --runs 3

# Evaluate all completed workspaces and write benchmarks/results.json
python3 benchmarks/evaluate_benchmarks.py --evaluate

# Claude Code runs (§7): provision outside the repo, then grade with the harness's own token telemetry
python3 benchmarks/evaluate_benchmarks.py --setup --runs 3 --runs-dir <dir> --tasks T9,T10,T11,T12
python3 benchmarks/evaluate_benchmarks.py --evaluate --runs-dir benchmarks/runs_claude_code --tasks T9,T10,T11,T12 \
  --telemetry-file benchmarks/telemetry_claude_code.json --results-file benchmarks/results_claude_code.json

# SWE-bench Verified (T13, §8): pull images, provision workspaces outside the repo, pick best_of_3 winners, grade
benchmarks/swe/.venv/bin/python benchmarks/swe/swe_bench.py pull
benchmarks/swe/.venv/bin/python benchmarks/swe/swe_bench.py setup --runs-dir <dir>
benchmarks/swe/.venv/bin/python benchmarks/swe/swe_bench.py pick --runs-dir <dir> --instance <instance_id> --run r1
benchmarks/swe/.venv/bin/python benchmarks/swe/swe_bench.py evaluate --runs-dir <dir> --harness claude_code \
  --telemetry-file benchmarks/swe/telemetry_claude_code.json --results-file benchmarks/swe/results_claude_code.json
```
