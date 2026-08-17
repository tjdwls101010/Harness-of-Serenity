---
name: serenity-single-name
description: Research a named US-listed ticker’s structural position, valuation, and conditional entry. Use for buy/sell/pass questions, thesis checks, valuation targets, earnings or filing-driven updates, and drawdowns tied to one security. Do not use for a broad theme or comparison unless the named ticker is the subject after discovery or macro context is resolved.
---

# Single-name research

## Question frame

Use this mode for a named US-listed ticker’s thesis, valuation, earnings or filing update, drawdown, or conditional entry; do not use it as a broad theme or peer comparison until discovery or macro context has resolved the subject. Start with `"$SERENITY_PYTHON" "$SERENITY_CLI" run start --mode single-name --question "<question>" --subject TICKER --as-of YYYY-MM-DD`, pin security identity and cutoff, then run `"$SERENITY_PYTHON" "$SERENITY_CLI" run start --help` before adding artifact arguments. State the decision question: structural capture, what is priced in, and what observation would make the action change.

## Competing hypotheses

Write alternatives from raw facts: scarce economics versus theme exposure; realizable asset value versus an illiquid or encumbered stake; productive growth financing versus destructive dilution; timing error versus failed operating thesis. Familiarity is not evidence. Keep business quality, valuation, timing, and vehicle separate until evidence resolves their conflict.

## Evidence sought

Request filings and other evidence adaptively. For asset value, test ownership, adjusted net asset value, liabilities, tax leakage, governance, operating-business economics, and monetization. For capital, test per-share dilution, price, use of proceeds, contract economics, execution funding, capacity, and completion. For options, treat the premium hurdle as distinct from probability and inspect premiums, open interest, liquidity, implied volatility, strikes, expiries, and the catalyst window. Every `Fact` carries source, time, provenance, and identity; preserve missing or conflicting facts instead of repairing them.

## Inference

Write `Inference` as a falsifiable explanation, not a label. Show whether forward economics can exceed dilution, whether a stake is realizable, and whether the price has already discounted the operating path. A numeric target or priced-in claim requires a saved lens whose fact references, units, formula, and validity resolve; an invalid lens cannot support the action. Price alone does not validate or defeat a thesis—reassess contracts, demand, qualification, scalable capacity, multi-sourcing, and milestones.

## Action and falsifier

Write one `Action` enum. An `ENTER_ON_TRIGGER` decision needs exactly one observable primary trigger with source, expiry, and a reassessment state, never an automatic trade. `BLOCKED` is required for unresolved identity, invalid required lens, or an unresolvable lifecycle condition. Include the strongest bear case and concrete falsifiers such as failed monetization, undisciplined dilution, missed qualification, demand deterioration, multi-sourcing, or a failed architecture ramp.

## Deliverable and hand-off

Deliver separated `Fact`/`Inference`/`Action`, the lens or its evidence gap, current trigger, bear case, and falsifiers. Use `NFA` only for actionable `RECOMMEND_NOW` or `ENTER_ON_TRIGGER` conclusions. Hand only a remaining peer question to cohort research or a missing chain relationship to discovery; do not ask a downstream mode to replace the single-name decision.

Method claims: `claim-04-separate-asset-value-from-realizability`, `claim-05-match-derivative-hurdle-to-thesis-window`, `claim-07-evaluate-capital-by-per-share-conversion`, `claim-08-resolve-dilution-growth-contradiction`, `claim-09-use-milestone-falsifiers-not-price-alone`, `claim-12-separate-timing-error-from-thesis-failure`, `aug-fact-referenced-lens-validity`, and `aug-immutable-action-lifecycle` route valuation, per-share capital conversion, falsifiers, lens validity, and lifecycle here.
