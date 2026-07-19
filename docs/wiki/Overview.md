# Overview

The full version of "what is this and why does it exist." Read this before the architecture — it
explains the problem the architecture is shaped around.

## The problem

Suppose you ask a capable language model to analyze a stock. It will produce something that reads
well: a market cap, a forward multiple, a margin trend, a verdict. The prose will be confident and
the structure will look right.

Three specific things can be wrong with it, and only one of them is easy to notice.

**1. The numbers can be silently wrong.** A model quoting a market cap from memory or from a web
snippet can be off by a quarter, or off by an entire company — ticker collisions are common, and
"AXT" versus "AXTI" is one character. The failure mode is not noise. Noise is visible. This
produces a number that *looks* correct, sits in a well-formed sentence, and inverts the conclusion
that divides by it. Nothing downstream catches it, because nothing downstream knows what the right
answer was.

**2. The judgment can be frozen into a formula.** The obvious fix is to compute everything. Write
a scoring function: weight the margin trend, the multiple, the insider flow, output a grade. Now
the numbers are right and reproducible — but you have moved the problem. A hundred thresholds are
now embedded in code, each one a judgment made once and never revisited. One stale criterion
inverts a call, and because the output is a number it *looks* objective. Worse, the score becomes
the answer: you stop reasoning and start deferring to it.

**3. The reasoning can be unrepeatable.** Ask the same question twice and get two different
frameworks — one answer that leads with the multiple, another that leads with the supply chain,
a third that never names what would prove it wrong. Without a fixed method there is no way to
tell whether a changed conclusion reflects changed evidence or just a differently-shaped
generation.

## The approach

One line, drawn deliberately and enforced mechanically:

> **Code loads facts. The analyst judges.**

Neither side is allowed to do the other's job.

**The code side** pulls every loadable number deterministically — market cap, price, multiples,
margins, free cash flow, debt, total assets, inventory, macro gauges, SEC filing disclosures — and
emits them as JSON. Same inputs, same bytes. The ticker is pinned, the period is pinned, and the
whole payload is replayable offline from a frozen fixture. This directly addresses problem 1.

**The judgment side** is documented, versioned, and human-owned. What kind of economic
concentration a company actually has, which valuation lens its capital structure demands, whether
a chokepoint is also a *winner*, what the price already reflects, how much conviction is
warranted — all of it stays in prose the analyst reads and applies. This addresses problem 2 by
refusing the shortcut: the method is written down so it repeats, but it is never compiled into a
score.

**The enforcement** is what makes the boundary real rather than aspirational. `serenity_harness.py
validate` replays all sixteen golden fixtures through the evidence builder and fails if any
verdict-shaped key or value appears anywhere in the output. `rating`, `risk_score`,
`objective_screen`, `regime`, a bare `"BUY"` string — all rejected, including in mixed case and
namespaced forms. At runtime, four lifecycle hooks check that an answer actually ran its
arithmetic and stated its bear case. This addresses problem 3.

## What "the code must not judge" means concretely

The distinction is sharper than it first sounds, and the line sits in a specific place.

| Emitted | Refused | Why the line falls here |
| --- | --- | --- |
| `vix_spot: 18.9` | `vix_regime: "panic"` | The reading is a measurement. The label is a claim about what it means. |
| `net_debt: 4.2e9` | `debt_health: "concerning"` | Subtraction over disclosed figures versus a threshold someone chose. |
| `ev_to_revenue: 12.4` | `valuation: "expensive"` | The ratio is arithmetic. "Expensive" depends on growth, structure, and what is already priced. |
| `revenue_by_quarter: [...]` | `trend_direction: "deteriorating"` | The series is fact. The adjective is a stage read. |
| `top_holders: [{name, shares}]` | `flow_assessment: "accumulating"` | Holdings are disclosed. What they imply is not. |

Pure arithmetic over disclosed inputs stays on the code side even when it produces a new number:
`net_debt`, `ev_to_fcf`, `real_fcf = reported FCF − stock-based compensation`. The moment a
constant appears that decides something — a 15× multiple assumed "fair", a score weight, a
severity cutoff — it has crossed over.

The project's own history is the clearest illustration. An earlier version of the pipeline
computed regime labels, five health gates, a 0–60 composite screen, a 0–100 "priced-in risk
score", dilution classifications, and an options vehicle menu. All of it still exists, quarantined
under `scripts/pipeline/legacy/`, unreachable from the live path and asserted absent by the
validator. It was not deleted, so you can read exactly what was removed and why. See
[Architecture](Architecture.md#the-legacy-quarantine).

## What you can do with it

- **Build a reproducible evidence dossier** for any US-listed equity in one command, with the
  identity of every number pinned.
- **Compare a basket side by side** on normalized metrics, explicitly as a routing aid rather
  than a ranking.
- **Pull SEC filing facts** — customer concentration, geographic revenue split, purchase
  obligations, financing structure — reproduced from XBRL with the concept cited, so a figure
  stays stable across runs.
- **Read macro gauges raw** — VIX term structure, net liquidity, ERP, Fed-funds probabilities —
  without a regime label pre-attached.
- **Run a documented analytical method** through the agent harness, with runtime checks that the
  method was actually followed.
- **Measure reproduction**, using a seeded eval that scores whether the harness reached the same
  structural insight on real past cases.

## Who it is for

- **Analysts who code.** The primary audience. You know what EV/Revenue and a 10-K are; you want
  the data plumbing to be reliable and the judgment to stay yours. These docs assume the finance
  and explain the Python.
- **Engineers building LLM harnesses.** The equity domain is incidental. What generalizes is the
  pattern: a mechanically enforced boundary between deterministic tooling and model judgment,
  with contract tests and lifecycle hooks holding the line. See
  [Agent Harness](Agent-Harness.md) and [Hooks Reference](Hooks-Reference.md).
- **Anyone studying reproducible research tooling.** The [Eval Harness](Eval-Harness.md) is an
  unusual artifact: a measurement of whether a documented method survives contact with a model,
  designed so that fixing a recurring miss means *generalizing an existing principle* rather than
  appending a special case.

## Non-goals

Stating these sharply, because they define the project as much as the goals do.

- **Not a generic finance data SDK.** The module set is what one method needs, not broad coverage.
  There is no options-chain surface, no fundamentals-screening API, no backtester. If you want a
  general data layer, use a general data library.
- **Not an automated trading or signal system.** Nothing here generates an entry, sizes a
  position, or executes anything. The `discover` comparator is explicitly not a ranking verdict.
- **Not a robo-advisor.** No recommendations, no portfolio construction, no risk profiling. The
  code refuses to emit a rating by design, and the validator enforces the refusal.
- **Not multi-market.** US-listed only — common stock, ADRs, and ETFs. Foreign names are handled
  by resolving to a US-listed expression, not by adding exchanges.
- **Not a stable public API.** Interfaces change without deprecation. Pin a commit if you depend
  on one.
- **Not backtested.** The eval measures whether the *method* is reproduced, never whether the
  method makes money. No performance claim is made anywhere in this repository.

## How it compares

| | Harness of Serenity | Data libraries (yfinance, edgartools) | Screeners / terminals | General LLM assistants |
| --- | --- | --- | --- | --- |
| Fetches market data | ✅ (wraps them) | ✅ | ✅ | ⚠️ unreliable identity |
| Reproducible run to run | ✅ contract-tested | ✅ | ⚠️ varies | ❌ |
| Enforces a documented method | ✅ | ❌ | ❌ | ❌ |
| Emits a rating or score | ❌ by design | ❌ | ✅ | ✅ |
| Offline replay of a past run | ✅ fixtures | ❌ | ❌ | ❌ |

The honest summary: it is a thin, opinionated layer over excellent existing libraries, plus a
substantial amount of machinery whose only purpose is to stop a judgment from quietly becoming a
constant.

---

**Next:** [Getting Started](Getting-Started.md) to run it, or [Concepts](Concepts.md) for the
vocabulary the rest of the docs assume. · [Back to index](README.md)
