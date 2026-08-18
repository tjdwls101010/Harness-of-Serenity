---
name: serenity-macro-event
description: Analyze macro regime, policy, geopolitical headlines, selloffs, displacement claims, or mechanical catalysts affecting US-listed equities. Use when the question asks what an event changes, whether a drawdown is fundamental, or how a regime changes research conditions; use before a single-name or cohort read when it changes the frame. Do not use for a routine named-ticker valuation without an event or macro premise.
---

# Macro and event research

## Question frame

Use this mode for a regime, policy, geopolitical headline, selloff, displacement claim, or mechanical catalyst; do not use it for a routine named-ticker valuation with no event or macro premise. Start with `"$SERENITY_PYTHON" "$SERENITY_CLI" run start --mode macro-event --question "<question>" --as-of YYYY-MM-DD`, pinned to the question’s cutoff, then run `"$SERENITY_PYTHON" "$SERENITY_CLI" run start --help` before adding artifact arguments. Frame the question as: what changed, for whom, on what time horizon, and does it alter demand, supply, pricing, financing, or only sentiment? This mode's `--subject` values are **series identifiers** such as `DGS10`, not tickers, so they take no security snapshot; `snapshot security` pins a security's identity, and a FRED series has no identity to resolve. Pin a security only when the read narrows onto one, and then say so as a single-name hand-off.

## Competing hypotheses

Write at least two live explanations before collecting supportive detail: for example durable economic conversion versus a headline or positioning move; a binding supply restriction versus substitutes or unqualified capacity; structural displacement versus a temporary scare. A sharp price move or short interest is a research trigger, never a verdict.

## Evidence sought

Seek dated company disclosures, primary policy or contract text, news, volume, and peer or sector moves. For a claimed restriction or contract, test scope, displaced capacity, substitutes, customer qualification, usable capacity, value, duration, revenue recognition, margins, financing needs, and execution capacity. Treat an anecdote as a lead: corroborate with provider waitlists, utilization, reservations, pricing, or comparable customer reports. Preserve source time, series/security identity, availability, and any missing or conflicting fact.

## Runtime interfaces

Macro series come from `alfred-fred.macro-series`, which returns the one vintage in force at the run cutoff, and `alfred-fred.vintage-series`, which returns every vintage published by then; ask the second when the question is whether a number was revised after the fact, since the first cannot show a revision it has already replaced. Both are vintage-addressed and refuse a request with no `provider_policy.historical_cutoff`. Sector and policy context comes from `bls.labor-data`, `bea.national-accounts`, `eia.energy-data`, `cftc.commitments-of-traders`, and `federal-register.rulemaking`. Read any contract with `"$SERENITY_PYTHON" "$SERENITY_CLI" evidence catalog --capability <id>` and the artifact arguments with `"$SERENITY_PYTHON" "$SERENITY_CLI" evidence request --help`; bound a vintage history with `observation_start`, because an unbounded one returns a row per observation per vintage and has written over a thousand artifacts from a single request.

## Inference

Explain the causal chain that the evidence supports and where it breaks. A catalyst matters only if it can convert into usable economics; distinguish immediate facts from the forward implication. If no incremental information or abnormal activity explains the move, if competitors retain access, or if capacity is not usable, reject the durable-repricing inference rather than inventing a macro story.

## Action and falsifier

State the current action and the condition that would change it. Use `MONITOR` or `BLOCKED` when the event-to-economics link, identity, or timing is unresolved; use a conditional action only with an observable trigger and a non-trade reassessment state. Name the strongest bear case and falsifier, such as substitute qualification, absent demand transfer, or an isolated capacity report.

## Deliverable and hand-off

Deliver a dated event ledger: facts, hypotheses, causal inference, action, trigger, bear case, and falsifier. If a security or comparison remains material, hand off only explicit implications and evidence gaps to single-name or cohort research; do not smuggle a macro conclusion in as their verdict. A regime call whose falsifier has a date can be registered with `"$SERENITY_PYTHON" "$SERENITY_CLI" outcomes register` and revisited with `outcomes refresh` on that date; it stays optional, because a decision never revisited is a research choice.

Method claims: `claim-01-screen-price-and-positioning-before-inference`, `claim-06-test-catalyst-conversion-capacity`, `claim-10-treat-thin-reports-as-leads`, `aug-identity-time-provenance-boundary`, and `aug-adaptive-evidence-not-decision-code` route price moves, catalyst conversion, thin reports, identity, and adaptive evidence here.
