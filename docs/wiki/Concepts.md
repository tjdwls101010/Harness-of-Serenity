# Concepts

The vocabulary the rest of these docs assume, defined in dependency order — each term uses only
terms defined above it. Finance fundamentals (EV/Revenue, PEG, 10-K, ATM offering) are assumed;
what is defined here is how *this project* uses them.

---

## The boundary

The founding distinction. **Facts** are loadable, checkable, and reproducible: a market cap, a
disclosed revenue figure, a VIX reading. **Judgment** is interpretation: whether that market cap
is cheap, what that revenue trajectory implies, whether that VIX reading means risk-off.

The project's rule is that deterministic code owns facts exclusively and never touches judgment.
Not as a style preference — as an enforced invariant, because a judgment compiled into code
becomes a constant that nobody revisits, and a stale constant inverts conclusions silently while
looking objective.

**The test for which side something falls on:** could this be wrong in a way that a person
reading the output would not notice? If it is a number with a source, a wrong value is checkable
against that source. If it is a label produced by a threshold, a wrong label is invisible — it
just reads as the answer.

Pure arithmetic over disclosed inputs stays on the fact side even when it creates a new number:
`net_debt = total_debt − cash`, `real_fcf = reported_fcf − stock_based_compensation`. A constant
that decides something crosses over.

## Evidence contract

Every pipeline payload opens with an `evidence_contract` block — the data layer declaring in-band
what it is and what it has not done:

```json
{
  "kind": "serenity_evidence",
  "judgment_owner": "agent",
  "code_role": "load_and_normalize_evidence",
  "boundary": "No verdicts, portfolio actions, numeric conviction scores, option vehicles, or a regime/risk_level label — the macro_inputs gauges are raw; the agent classifies the regime."
}
```

Three variants exist, one per command (`serenity_evidence`, `serenity_macro_evidence`,
`serenity_discovery_comparator`). It is not decoration: the contract tests assert
`judgment_owner == "agent"` on every fixture, so removing or weakening it fails the build.

Behind it sit three enforcement mechanisms in `scripts/pipeline/_evidence.py`:

| Mechanism | Catches |
| --- | --- |
| `FORBIDDEN_EVIDENCE_KEYS` (normalized) | `risk_score`, `Risk_Score`, `risk-score`, `RiskScore` — all the same key after stripping non-alphanumerics |
| `FORBIDDEN_KEY_SUBSTRINGS` = `("regime", "risklevel")` | `vix_regime`, `macro_regime`, `x_risk_level` — even namespaced |
| `FORBIDDEN_VALUE_PATTERN` | Any string value matching `strong buy`, `buy`, `sell`, `accumulate`, `avoid`, `moonshot` |

`rating` and `recommendation` are matched **exactly**, never as substrings, so the legitimate
fields `rs_rating` (IBD relative strength) and `recommendation_distribution` (the raw analyst
tally) survive. Details in [Testing and Validation](Testing-and-Validation.md).

## Archetype

**The shape of economic concentration a company actually has.** Naming it is the first analytical
step, because the discovery question, the qualifying tests, and the valuation anchor all rotate
depending on which shape it is. Getting it wrong mis-frames everything downstream.

Three shapes:

| Archetype | Definition | Typical evidence |
| --- | --- | --- |
| **Chokepoint** | A physical step demand cannot route around. The scarce attribute may be a *jurisdiction* (a US-only fab, a single-country refining step), not only a component. | Concentrated supply, long qualification cycles, customers funding peers to replicate the footprint |
| **Disruption** | An incumbent profit pool a faster entrant is draining. | Share shifting on a cost or distribution advantage, incumbent margins compressing |
| **Evolution** | An emerging standard that a datable step-change just made investable. | A specific technical or regulatory event that moved the thing from research to procurement |

Hardware and materials default to **chokepoint**. Relabeling to disruption or evolution requires
positive evidence — a demonstrably drained profit pool, a datable step-change — and never happens
merely to unlock a softer valuation. The inverse error costs the same: a disruption narrative
pinned onto a clean physical chokepoint mis-values it just as badly.

**The archetype is never emitted by code.** No field anywhere in the pipeline carries it.

## Valuation lens

**The denominator a company's structure demands.** A multiple by itself carries no information —
30× forward earnings is cheap at 60% growth and expensive at 5%. The lens is the choice of what
to divide by, and it follows from the capital structure and the archetype, not from convention.

Examples of lens selection:

| Structure | Lens | Why the default fails |
| --- | --- | --- |
| High growth | PEG | A raw P/E ignores the growth that justifies it |
| Asset-financed buildout | Levered IRR per unit of capacity ($/MW) | A thin gross margin is really a financing return |
| Mid-restructuring, asset-heavy | Replacement cost per unit of physical capacity | A melting income statement is the *source* of the mispricing, not a disqualifier |
| Margin inflection | Pro-forma FCF at a normalized margin | Trailing margins describe the trough, not the business |
| Countable end units | Content per unit × unit volume ÷ market cap | The supplier's own multiple just re-prices consensus |

**Naming the lens is not running it.** This distinction is load-bearing and mechanically checked.
A lens is *run* only when the driver arithmetic is shown with each input traced to a specific
pipeline field:

```
Lens: content×volume÷MC — $180/unit × 4.2M units ÷ $12.4B = 6.1% of MC
```

The `Stop` hook scans the answer for a literal `Lens:` line containing a real `×`, `÷`, or `*`
operator alongside `=`. A bare top-down multiple (`EV/Rev = 12x`) does not satisfy it — that was
precisely the miss the check was built to catch.

**Forked lens.** Some structures require two legs: a downside floor (dilution, net debt, a
discount) and an upside case (re-rating, replacement-cost value, an FCF bridge). Both must be run
and allowed to conflict. Running only the floor leg silently converts a potential large winner
into a pass — the single most consequential direction error in the method.

## Winner gates

**Owning a chokepoint is necessary but not sufficient.** A company can sit on a genuinely scarce
node and still be a poor investment: no pricing power, a customer who designs it out, capacity
that arrives too late. The gates are the qualifying tests separating "structurally important" from
"a good position to own."

They rotate by archetype — a chokepoint's gates test durability and allocation control; an
evolution name's gates test whether the funding is real. Gate outcomes are recorded as `pass`,
`fail:<gate>`, `conditional:<which>`, or `blocked:<line>` in a scorecard. Like the archetype, they
are never computed by code.

## Funded versus self-minted

**Applied when an asset is still a promise to build something.** The question asked of any
"funded" claim is: *who put capital at risk, and on what terms?*

- **Funded** — third-party contract capital. A customer prepayment, an above-market equity
  placement, asset-backed debt secured on an offtake agreement. Someone external accepted
  downside.
- **Self-minted** — capital the issuer created by selling the story. An at-the-market equity
  program, serial dilution. This de-risks nothing; the company is betting with money raised from
  the buyers it dilutes.

The distinction comes from the filing, never a press release, which is why
[`serenity-filings`](Filings-and-SEC.md) reports financing terms exactly and neutrally — size,
coupon, maturity, size relative to market cap — without pre-labeling anything "dilutive." The
labeling is the analyst's.

## Priced-in

**Decomposing the current price into what the market has already absorbed and what it has not.**
Not a yes/no. The useful form names which specific facts are reflected in the price and which
specific expectation is not.

An answer that restates consensus multiples has not done this — it has reproduced the reference
point the whole exercise is measured against.

## Falsifier and bear case

**The falsifier** is the specific, checkable condition that would prove the thesis wrong, stated
in advance: "breaks if the second supplier qualifies before Q4." Defining it before committing is
what makes a later revision an update rather than a rationalization.

**The bear case** is the strongest argument against the position, constructed deliberately rather
than acknowledged in passing.

Both are checked at runtime. The `Stop` hook flags a single-name answer missing a `Downsides:`
block or lacking falsifier language ("breaks if…", "kill signal", "wrong if"). Neither hard-blocks
— they are nudges — but their absence is surfaced every time.

## Cycle stage

**Where a name sits on a five-rung ladder** from early accumulation to late-cycle distribution. On
a single name it is one evaluation input among several. On a basket it becomes the ordering and
sizing spine: a stage-5 name cannot occupy a top conviction tier regardless of how well it
qualifies on other dimensions.

## Rank-N protocol

**The fixed procedure for ranking N names**, designed so that two runs on the same cohort produce
comparable output.

What is fixed: the scorecard fields, the precedence order, the tie-breaks, the tier vocabulary,
the output format. What is deliberately **not** fixed: any threshold, weight, or formula that
would assign a tier automatically — a composite score would be the removed legacy screen
reappearing under a new name.

Precedence, in order:

1. **Gates determine membership.** A failed gate excludes the name outright, with the failed gate
   stated.
2. **Cycle stage is the ordering spine.**
3. **Within a rung**, gate strength first, then conviction.
4. **Tie-breaks**: the floor leg's valuation gap as a fraction of current price, then vehicle
   practicality. If four steps cannot separate two names, they are declared tied rather than
   ordered arbitrarily.

For N ≥ 5, one [`serenity-scorecard`](Agent-Harness.md#serenity-scorecard) subagent runs per name
with an identical, deliberately colorless launch message — no "the obvious top pick" hints — so
that each scorecard forms independently. Macro runs once and is passed verbatim to all of them.
Full mechanics in [Agent Harness](Agent-Harness.md#the-rank-n-protocol).

## Session archive

**Persisted analysis under `sessions/{yymmdd}.{topic-slug}/`** — one Markdown file per name in a
pinned schema, `_ranking.md` for a basket synthesis, `_macro.md` for the regime read.

Two rules make the archive safe to reuse:

- **Numbers expire; structure does not.** A figure from a past session is never a current input —
  re-run the pipeline. What carries forward is the judgment structure: the tier, the thesis, the
  falsifier. A prior number may appear only inside an explicit delta line tagged as-of-then.
- **Fresh judgment first, comparison second.** On a repeat question, complete the new assessment
  from current evidence *before* opening the prior ranking, then explain every changed tier.
  Reading the old ranking first anchors you; skipping the comparison hides drift. Both are the
  failure the rule exists to prevent.

`sessions/INDEX.md` carries one line per folder and **deliberately holds no verdicts** — an index
line stating a past conclusion would anchor the next reading before fresh judgment forms. The
validator asserts the index is verdict-free. Full detail in
[Session Archive](Session-Archive.md).

## The thesis DB

`data/analysis_Serenity.db` is a committed SQLite file archiving the posts of one analyst — the
practitioner whose method this harness reproduces. A single `tweets` table: `id`, `user`, `type`
(`post` / `reply` / `subscriber`), `created_at`, `content`, `tickers`, `media`. Query it with
`scripts/serenity_tweets.py` (`search`, `get`, `stats`).

It is refreshed twice daily by `.github/workflows/scheduled-scrape.yml`, which runs
`scripts/serenity_scrape.py` on a self-hosted runner and commits the updated file to `main`. So
**`main` is the source of truth and a local copy is only as fresh as your last `git pull`** — which
is fine, because the rule below means you consult it rarely and deliberately. Run the scraper
locally only if you know why; two writers produce divergent binaries that git cannot merge.

**It is an answer key, not a data source**, and the usage rule is strict: consult it *only* on an
explicit cross-validation request, never during routine analysis, and only after independently
forming a view. This is one of the project's non-negotiable rules, not a suggestion.

The reason is the project's purpose. The harness exists to reproduce a *method* well enough to
reach conclusions independently. Consulting the archive first collapses that into retrieval —
you get a parrot of stale, name-specific calls instead of a working method. Leaving the answer key
accessible but rule-fenced is what makes the [Eval Harness](Eval-Harness.md) possible: it can
score blind reproduction precisely because the answers exist but are withheld from the run.

Contents are public posts, archived for method-reproduction research. The MIT license covers this
repository's own code; it grants no rights over third-party content. If you fork this for
redistribution, consider whether you should carry the database with you.

## The three-layer mental model

Everything above sorts into three layers, and every question about where a piece of behavior
belongs resolves by asking which layer owns it:

```
┌─────────────────────────────────────────────────────────┐
│  JUDGMENT     CLAUDE.md · skills · subagents            │
│               archetype · lens choice · gates · rating  │
├─────────────────────────────────────────────────────────┤
│  ENFORCEMENT  hooks · serenity_harness.py validate      │
│               contract tests · golden fixtures          │
├─────────────────────────────────────────────────────────┤
│  FACTS        serenity_pipeline.py · modules/           │
│               serenity_filings.py — JSON only           │
└─────────────────────────────────────────────────────────┘
```

The enforcement layer is the unusual one. It belongs to neither side; its entire job is keeping
the other two from bleeding into each other.

---

**Next:** [Architecture](Architecture.md) for how these map onto files. · [Back to index](README.md)
