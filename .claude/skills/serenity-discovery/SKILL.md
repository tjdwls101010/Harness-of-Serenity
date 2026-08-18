---
name: serenity-discovery
description: Discover US-listed expressions for an industry, sector, theme, supply-chain question, or what-if. Use when the user asks what could benefit, where value concentrates, which listed vehicle expresses a theme, or requests a chain map. Do not use to value one already-named ticker unless discovery is needed to test its alternatives.
---

# Discovery research

## Question frame

Use this mode to resolve an industry, sector, theme, supply-chain question, what-if, or US-listed expression; do not use it to value a known ticker unless discovery is needed to test alternatives. Start with `"$SERENITY_PYTHON" "$SERENITY_CLI" run start --mode discovery --question "<question>" --as-of YYYY-MM-DD`, then run `"$SERENITY_PYTHON" "$SERENITY_CLI" run start --help` before adding artifact arguments. Specify the demand change, the economic node to test, the US-listed vehicle question, and the cutoff; make a typed sector graph only when relationships will be reused or prose would lose material layers.

## Competing hypotheses

Keep rival maps live: a direct physical bottleneck, an incumbent profit pool being drained, an emerging standard, a merely correlated theme proxy, or no investable expression are examples when raw evidence supports them; allow another mechanism. Do not force every case through the same checklist. Do not start from a favorite ticker. For a physical claim, ask whether the headline node or its recursive bottom hop is scarce, and whether a sibling captures more of the economics.

## Evidence sought

Validate every causal hop with supplier-to-customer identity, material intensity, supplier share, inventory, qualification cycles, compatibility, vendor share, bill-of-materials content, adoption commitments, substitutability, alternatives, and end-market demand. A ticker-like label or trading venue is not issuer/security identity or revenue linkage. Never call a vehicle direct until identity binding is evidenced. Trace direct ownership and revenue capture separately from theme exposure. Seek a specific second-order allocation actor and shared failure nodes; mark a thin report as a lead until provider-level corroboration exists. Keep source, time, identity, and the US listing type beside every material relationship.

## Runtime interfaces

Chain evidence comes from `sec.filings`, `sec.filing-section`, `sec.segments`, and `sec.xbrl-facts` for issuer-side linkage, and from `usaspending.federal-awards`, `federal-register.rulemaking`, and `usitc.trade-data` for flows outside issuer control; read each contract with `"$SERENITY_PYTHON" "$SERENITY_CLI" evidence catalog --capability <id>` before constructing a request, and `"$SERENITY_PYTHON" "$SERENITY_CLI" evidence request --help` for the artifact arguments. A disabled capability answers `not_requested` with the reason it is unbound, which is a fact about the source rather than a gap in the chain. Record the map with `"$SERENITY_PYTHON" "$SERENITY_CLI" graph put --help`: each node's `us_expression.resolution` is `clean_vehicle`, `indirect_vehicle`, or `no_clean_vehicle`, and the third is the typed way to say a real bottleneck has no listed expression — an answer this mode is expected to reach, not a failure to route around by naming an adjacent ticker.

## Inference

Determine structural concentration from the binding relationship and revenue linkage before testing investability. Explain why the node is direct capture rather than adjacent exposure, whether demand can route around it, and what the price may already reflect. Investability, the US-listed vehicle, and action are separate gates. A real chokepoint may have no clean vehicle; a foreign economic winner may remain visible, but it is not automatically an actionable US expression.

## Action and falsifier

Return `MONITOR`, `PASS`, or `BLOCKED` when qualification, adoption, vendor share, substitute risk, or vehicle linkage is unresolved. If the link is missing, preserve it as unresolved and choose `BLOCKED`, `MONITOR`, or `PASS` as the facts warrant. Do not fabricate a direct-versus-indirect relation. Return no clean US-listed vehicle when the evidence does not support one; do not promote a familiar proxy to solve the gap. Falsify the map on absent qualification, stalled adoption, changed supplier share, substitution, or another component proving binding.

## Deliverable and hand-off

Deliver a compact chain map with competing maps, direct versus proxy labels, evidence gaps, the current action, and falsifiers. Hand a selected candidate to single-name research with only its cited relationships and unresolved tests; hand a material set to cohort research for a common comparison, not a pre-decided ranking.

Method claims: `claim-02-validate-every-causal-hop`, `claim-03-verify-identity-and-revenue-linkage`, `claim-06-test-catalyst-conversion-capacity`, `claim-10-treat-thin-reports-as-leads`, `aug-structural-concentration-and-priced-in`, and `aug-physical-chain-and-vehicle-contract` route chain validation, vehicle resolution, and recursive physical-bottleneck work here.
