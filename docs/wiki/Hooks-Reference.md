# Hooks Reference

The four lifecycle hooks in `.claude/hooks/`, what each inspects, and exactly when it blocks,
warns, or stays silent.

## Why hooks exist

Everything in `CLAUDE.md` and the skills is advisory. A model producing a long answer under
pressure will skip a step it "knows" — not from ignorance, but because the answer already feels
complete. Advisory rules degrade exactly when they matter most.

A hook fires regardless. These are the four points where that determinism is worth its cost:

| Event | Hook | Enforces |
| --- | --- | --- |
| `SessionStart` | `session_status.py` | The harness is structurally sound before any work begins |
| `UserPromptSubmit` | `evidence_discipline.py` | Market questions start from the pipeline, not from memory |
| `PostToolUse` (Bash) | `data_integrity_guard.py` | The numbers are arithmetically self-consistent |
| `Stop` | `verdict_gate.py` | The answer carries its required structural elements |

## Shared contract

All four:

- Read a JSON payload from stdin and **exit 0 unconditionally**.
- Wrap stdin parsing in a bare `except: return` — a hook must never crash a turn.
- Communicate through three levels:

| Level | Mechanism | Effect |
| --- | --- | --- |
| **SILENT** | No output | Nothing happens. The default. |
| **SOFT** | `additionalContext` in the JSON response | Guidance injected; the model may act on it |
| **HARD** | `{"decision": "block", "reason": "..."}` | The answer is rejected and must be revised |

There is exactly **one hard block** across all four hooks. Everything else nudges. That ratio is
deliberate — a hook that blocks often becomes a hook people disable.

Hooks are wired in `.claude/settings.json` in **exec-form** (a `command` plus an `args` array,
never a single shell string), because shell form allowed a shell-profile banner to corrupt a
JSON-emitting hook's stdout and silently no-op it.

---

## `session_status.py` — SessionStart

Runs `serenity_harness.py validate` and reports only when something is wrong.

| Condition | Behavior |
| --- | --- |
| The venv interpreter or validator script is missing | SILENT |
| The subprocess or JSON parse fails | SILENT |
| Validation returns `ok: true` | **SILENT** — green stays quiet, no per-session context cost |
| Validation returns `ok: false` | SOFT — names the failing checks and their detail |

The message on failure:

> `[harness-status] serenity_harness.py validate is RED (pass=… warn=… fail=…). Failing: {check}:
> {detail}. The deterministic layer or a skill regressed — fix the wiring before trusting a call.`

Timeout is 35 seconds at the settings level, 30 in the subprocess call. The design choice worth
noting is that **success is silent**. A hook that announces itself every session trains people to
skip its output, so the signal is reserved for the case that needs it.

---

## `evidence_discipline.py` — UserPromptSubmit

Classifies the incoming prompt and, when it reads as a market question, injects a reminder before
reasoning starts.

### Classification

Three regexes, all case-insensitive:

**`_INTENT`** — is this a market question? Matches cashtags (`$NVDA`), finance nouns (stock,
ticker, valuation, P/E, PEG, moat, bottleneck, capex, dilution, ATM, convertible, short interest,
float, regime, liquidity), action phrases (`should i buy`, `buy the dip`, `priced in`,
`too late to buy`), and the maintainer's Korean market phrasings (`뭐 사`, `살까`, `매수`, `종목`,
`장 어때`, `물타`, `존버`). Bare ALL-CAPS words are deliberately excluded — too many false hits.

**`_META`** — is this harness development rather than a market question? Matches `harness`,
`hook`, `skill`, `SKILL.md`, `CLAUDE.md`, `settings.json`, `.py`, `pipeline code`, `subagent`,
`refactor`, `eval`, `workflow`, `commit`, `spec`, and their Korean equivalents. Suppresses the
reminder.

**`_MARKET_ANCHOR`** — overrides `_META`. A prompt containing a cashtag, `매수`/`매도`, `목표가`,
`price target`, `valuation`, or `should i buy` is a real market question even when it also
mentions the harness.

### Decision

```
empty prompt                          → SILENT
_META matches and no _MARKET_ANCHOR   → SILENT
_INTENT matches                       → SOFT (print the reminder)
otherwise                             → SILENT
```

Worked examples from the fixture suite:

| Prompt | Result | Why |
| --- | --- | --- |
| `should i buy $NVDA here or wait for a dip?` | FIRE | Cashtag plus action phrase |
| `장 어때? 지금 들어가도 되나` | FIRE | Korean macro phrasing |
| `does the bottleneck-check reminder in the hook fire right?` | SILENT | "bottleneck" trips `_INTENT`; `_META` suppresses it |
| `analyze $NVDA then update the analysis skill accordingly` | FIRE | `$NVDA` anchor beats the meta guard |
| `what's a good recipe for pasta carbonara?` | SILENT | No match |

The bias is stated in the source: *an extra fire is cheap context; a suppressed real market
question is not.* The anchor list stays generous on purpose.

### The reminder

Four bullets:

1. Run `serenity_pipeline.py` **first** — never quote market cap, price, multiples, margins, or a
   regime from memory. Use the `serenity-filings` subagent for filing prose and disclosure
   numbers.
2. Scan for a **dated catalyst** first — a known ticker plus a catalyst is an event, not a
   standalone single-name read.
3. Pick the archetype's valuation lens **at intake**, not at the verdict.
4. If `sessions/INDEX.md` lists these tickers, plan to reconcile deltas **after** fresh
   scorecards — never re-derive blind, never read the old ranking first.

---

## `data_integrity_guard.py` — PostToolUse (Bash)

Fires only after a Bash call whose command contains both `serenity_pipeline` and `analyze`. Parses
the JSON from the tool's stdout and runs seven arithmetic identity checks.

**Never blocks.** It reports arithmetic, not judgment.

| # | Check | Trips when | Severity |
| --- | --- | --- | --- |
| 1 | `marketCap` ≈ `currentPrice × sharesOutstanding` | relative gap > 10% | HARD above 35%, else soft |
| 2 | `floatShares` ≤ `sharesOutstanding` | float exceeds shares | HARD |
| 3 | `operatingMargins` ≤ `grossMargins` | operating exceeds gross | HARD |
| 4 | `currentPrice` within the 52-week range | outside by > 2% | soft |
| 5 | `enterpriseValue` ≈ MC + debt − cash | relative gap > 15% | soft |
| 6 | Revenue agreement (`key_facts` TTM vs `debt_and_cash` annual) | relative gap > 12% | note |
| 7 | `inventory` ≤ `total_assets` − `cash` | inventory exceeds the remainder | HARD |

Check 1 carries an explicit caveat in the source: a dual-class share structure produces exactly
this discrepancy legitimately, and the two cases cannot be told apart programmatically. Check 7 is
described as "the canonical phantom-inventory catch" — a balance sheet that does not balance is
a data error, and a data error on the anchor numbers is not noise. It is potentially *the*
mispricing.

Output when something trips:

> `[data-integrity] Deterministic identity checks on the analyze numbers (NOT a thesis judgment)
> tripped — reconcile before tagging an archetype:`
> `- [HARD] marketCap vs price × shares: $2.1T observed vs $1.4T implied — reconcile`

The parenthetical is doing real work. This hook checks whether the *numbers* are self-consistent,
never whether the thesis is right, and the message says so to prevent the output being read as a
verdict.

**Note:** it parses the tool's stdout, so a piped or redirected `analyze` run is invisible to it.
That is deliberate — a pipe is not a failure — but it does mean `analyze NVDA > out.json` skips
the audit.

---

## `verdict_gate.py` — Stop

The structural contract on the finished answer. Everything downstream requires a `TLDR` in the
message; without one the hook returns immediately, so ordinary conversation is unaffected.

### Signals it detects

| Signal | Detected by |
| --- | --- |
| `signoff` | `NFI` / `NFA`, "not financial advice", or the Korean equivalent |
| `single_name` | `Downside`, `PT`, `price target`, `rating`, `conviction`, `LEAPS`, `CSP`, `covered call`, `vehicle`, or Korean equivalents |
| `strong_verdict` | `priced in`, `overvalued`, `undervalued`, `fairly valued`, `WATCH`, `overweight`, `underweight` |
| `finance_signal` | `single_name` or `strong_verdict` or a cashtag |
| `valuation_verdict` | `strong_verdict` or `cheap` / `expensive` / `pass on` / `hard pass` |
| `lens_named` | `EV/Rev`, `EV/FCF`, `PEG`, `forward P/E`, `content ×`, `$/MW`, `levered IRR`, `replacement cost`, `no-growth`, `pro-forma` |
| `lens_marker` | A literal `Lens:` line containing `×`, `÷`, or `*` **and** `=` on the same line |

A bare `pass` ("tests pass") and the word `bottleneck` are deliberately excluded from
`strong_verdict` — they false-fire on ordinary engineering answers, and a fixture guards against
the regression.

### The one hard block

```
finance_signal AND NOT signoff  →  BLOCK
```

An answer that reads as a market verdict but carries no "not financial advice" sign-off is
rejected. It is the only hard block in the entire harness, on the reasoning that a market opinion
delivered without that disclaimer is a categorically different artifact from one that carries it.

### The soft nudges

| Nudge | Fires when |
| --- | --- |
| **Missing `Lens:` line** | A lens is named or a valuation verdict is stated, but no `Lens:` line with real arithmetic exists |
| **Missing bear block** | A single-name answer with no `Downsides` / bear case / 리스크 |
| **Missing falsifier** | A single-name answer with no "breaks if" / "kill signal" / "wrong if" |
| **Half-run fork** | A downside leg was run (floor, dilution, net debt, ATM, overhang) with no upside leg (re-rate, replacement cost, bridge, pro-forma, levered IRR, supply shock) |
| **Missing `Saved:` mark** | A verdict was delivered but not archived |

**The `Lens:` check is the subtle one.** An earlier version inferred "arithmetic ran" from the
presence of `= <digit>` — which `EV/Rev = 12x` satisfies, and that bare top-down multiple was
exactly the miss it was built to catch. The current check requires a real operator, so a
substituted-in driver calculation is structurally distinguishable from a quoted multiple.

**The half-run-fork nudge is soft on purpose.** A genuine clean-kill verdict legitimately has no
upside leg, so blocking would be wrong. But running only the downside leg silently converts a
potential large winner into a pass, which is the most consequential direction error available —
so it is surfaced every time.

**The `Saved:` check verifies the filesystem, not the string.** Four outcomes:

| Situation | Message |
| --- | --- |
| No mark at all | "this verdict isn't archived" |
| Mark present but not a valid session path | "not a valid session path" |
| Valid shape, folder does not exist | "no such session folder exists" |
| Folder exists but holds no `.md` | "holds no `.md` scorecard/synthesis" |

The last two exist because a costless `mkdir` or a `Saved: sessions/INDEX.md` token would
otherwise be a compliance marker that falsely certifies archiving. The check resolves the path
against the real filesystem and requires actual content.

---

## Testing the hooks

Hooks are behavioral code, and behavioral code needs fixtures. There are 22:

```bash
scripts/.venv/bin/python .claude/hooks/tests/run_fixtures.py
# → all fixtures passed (exit 0)
```

A fixture is the exact stdin payload the hook receives, and the runner asserts on stdout:

```json
// .claude/hooks/tests/verdict_gate/hard_nfi.json
{ "last_assistant_message": "TLDR: $AVGO ...", "stop_hook_active": false }
```

### `verdict_gate` fixtures

| Fixture | Guards against |
| --- | --- |
| `silent_full` | A complete verdict must not nag |
| `soft_lens` | Valuation verdict with no `Lens:` line → only the lens nudge |
| `hard_nfi` | Complete verdict without a sign-off → hard block |
| `coding_silent` | "refactored the parser; all tests pass" must stay silent |
| `macro_hard` | A macro overweight call without a sign-off still blocks |
| `meta_silent` | A harness-dev answer containing the literal string `Saved:` must not fire |
| `bear_leg_soft` | Downside leg only → the half-run nudge, nothing else |
| `saved_missing` | Verdict with no `Saved:` line |
| `saved_folder_missing` | Valid shape pointing at a nonexistent folder |
| `saved_wrong_shape` | `Saved: sessions/INDEX.md` — the gameable token |
| `saved_empty_folder` | A folder with no `.md` — the costless `mkdir` |
| `saved_backtick_silent` | Markdown backticks around the path must be tolerated |
| `false_fire_guard` | "the bottleneck was in the parser; all tests pass" must stay silent |

### `evidence_discipline` fixtures

Cover the cashtag, Korean, English-phrase, and macro firing cases; the meta suppression cases; the
anchor override; a non-market control; and one pinning the session-retrieval line in the reminder.

The `Saved:`-mark `verdict_gate` fixtures depend on real committed directories, which live in the
suite's own sandbox at `.claude/hooks/tests/fixtures/sessions/`:

- `990101.hook-fixture/FIXT.md` — a folder that **does** contain a `.md`
- `990102.hook-empty/.gitkeep` — a folder that deliberately contains **no** `.md`
- `990199.hook-missing/` — referenced but deliberately absent

The 9901xx dates (1999) make them obviously non-real. **Do not add a `.md` to `990102.hook-empty`**
— that would silently stop the empty-folder fixture from testing what it claims.

`run_fixtures.py` sets `CLAUDE_PROJECT_DIR` to that sandbox explicitly, rather than relying on
`verdict_gate`'s `or os.getcwd()` fallback. The fallback only applies when the variable is unset, so
depending on it would pass in a terminal and fail at every real SessionStart — where Claude Code
sets the variable to the repo root. Verify any change to the runner with the variable both unset and
set.

## Adding a hook

1. Write it in `.claude/hooks/`, following the shared contract: parse stdin defensively, exit 0
   always, emit `additionalContext` for soft and `{"decision": "block"}` for hard.
2. Wire it in `.claude/settings.json` in exec-form with the venv interpreter path.
3. **Add fixtures** for both the firing case and the near-miss case. Every existing hook has a
   false-fire guard, because the failure mode of a noisy hook is that people disable it.
4. Run `serenity_harness.py validate` — the `hooks` check asserts the exact event-to-script map,
   so it will fail until settings and files agree.

---

**Next:** [Session Archive](Session-Archive.md) · [Testing and Validation](Testing-and-Validation.md) · [Back to index](README.md)
