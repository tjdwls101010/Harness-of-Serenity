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

Request filings and official issuer evidence adaptively. Before using any financial observation, run the identity gate across the requested security, provider identity bindings, and every filing ticker, CIK, issuer, and exchange field. Any non-null identifier conflict is unresolved identity: do not use the remaining economics, and emit `Action: BLOCKED` until reconciled—`MONITOR` is not a substitute. Read earnings releases, prepared remarks, Q&A, call transcripts, and IR presentations as different evidence surfaces: separate each management claim from a hard operating observation, preserve the time horizon, constraint or dependency, omission or evasion, and counterevidence, and mark a named relationship as disclosed, corroborated, inferred, or contradicted. Cross-company read-through remains an inference candidate until another source corroborates the same operating mechanism; a CEO vision or partnership mention is not forward revenue by itself. For asset value, test ownership, adjusted net asset value, liabilities, tax leakage, governance, operating-business economics, and monetization. For capital, test per-share dilution, price, use of proceeds, contract economics, execution funding, capacity, and completion. For options, treat the premium hurdle as distinct from probability and inspect premiums, open interest, liquidity, implied volatility, strikes, expiries, and the catalyst window. Every `Fact` carries source, time, provenance, and identity; preserve missing or conflicting facts instead of repairing them.

## Runtime interfaces

This mode reaches for `sec.filings`, `sec.filing-section`, `sec.filing-text`, `sec.xbrl-facts`, `sec.statement`, `sec.segments`, `sec.eightk`, and `issuer-ir.document`. Run `"$SERENITY_PYTHON" "$SERENITY_CLI" evidence catalog --capability <id>` for the parameter contract the registry checks before a provider is constructed, and `"$SERENITY_PYTHON" "$SERENITY_CLI" evidence request --help` for the artifact arguments; a shape the contract rejects is named back to you rather than spent on an external request that returns an uninformative failure. A collected result answers with its value's shape, not its value: pull spans with `evidence read RUN_ID RESULT_ID --match REGEX --context N`, whose character offsets let a later reader slice the same span out of the stored artifact and check your citation, and reserve `--value` for a payload you have already decided is small. One risk-factors section measured 91k-144k characters, which is why bulk narrative goes to the `serenity-filings` subagent instead of into this context.

## Inference

Write `Inference` as a falsifiable explanation, not a label. Show whether forward economics can exceed dilution, whether a stake is realizable, and whether the price has already discounted the operating path. A numeric target or priced-in claim requires a saved lens whose fact references, units, formula, and validity resolve; an invalid lens cannot support the action. Price alone does not validate or defeat a thesis—reassess contracts, demand, qualification, scalable capacity, multi-sourcing, and milestones.

## Action and falsifier

Write one `Action` enum. An `ENTER_ON_TRIGGER` decision needs exactly one observable primary trigger with source, expiry, and a reassessment state, never an automatic trade. `BLOCKED` is required for unresolved identity, invalid required lens, or an unresolvable lifecycle condition. Include the strongest bear case and concrete falsifiers such as failed monetization, undisciplined dilution, missed qualification, demand deterioration, multi-sourcing, or a failed architecture ramp.

## Deliverable and hand-off

Deliver separated `Fact`/`Inference`/`Action`, the lens or its evidence gap, current trigger, bear case, and falsifiers. Use `NFA` only for actionable `RECOMMEND_NOW` or `ENTER_ON_TRIGGER` conclusions. Hand only a remaining peer question to cohort research or a missing chain relationship to discovery; do not ask a downstream mode to replace the single-name decision.

Method claims: `claim-04-separate-asset-value-from-realizability`, `claim-05-match-derivative-hurdle-to-thesis-window`, `claim-07-evaluate-capital-by-per-share-conversion`, `claim-08-resolve-dilution-growth-contradiction`, `claim-09-use-milestone-falsifiers-not-price-alone`, `claim-12-separate-timing-error-from-thesis-failure`, `aug-fact-referenced-lens-validity`, and `aug-immutable-action-lifecycle` route valuation, per-share capital conversion, falsifiers, lens validity, and lifecycle here.
