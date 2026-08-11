# Adversarial review — semiconductor sector map

## TLDR

**CONFIRMED:** the file passes `serenity_sectormap.py validate`, but that validator checks shape, enums, parent references, and ticker syntax—not whether a layer is economically coherent, whether a `CONFIRMED` link has evidence, or whether a ticker owns the scarce attribute. The prose says “only about a third” of the 30 layers are bottlenecks; the JSON actually marks **14 bottleneck + 14 constraint + 2 risk**, so almost half are tagged bottleneck. It also says the independent criticism won on broad advanced packaging and that the bottleneck tag was retained “only for the equipment and inspection sub-layers,” while both the Markdown table and JSON still label broad `advanced-packaging` a bottleneck.

**DEDUCED:** reject this map as decision-grade in its present schema. Its central error is not one bad ticker. It assigns one `limitation_class` to composite industry buckets that contain different removal mechanisms, different owners, and different clocks. That mechanically turns fundable lines into “physics,” hides real bottlenecks inside broad `constraint`/`risk` buckets, and lets adjacent beneficiaries masquerade as owners.

---

## A. Wrong `limitation_class` calls

### A1. `bottleneck` tags that should be demoted or split

| Layer | Claim attacked | Correction | Falsifiable test |
|---|---|---|---|
| **HBM** | **CONFIRMED:** JSON says `"limitation_class": "bottleneck"` and explains that relief requires “a fab construction cycle.” | **DEDUCED:** that explanation proves **constraint/hybrid**, not permanent physical bottleneck, under the doctrine’s own test: capital + time can add wafer starts, bonding, test, and yield learning. The hard node may migrate among those substeps; “HBM” is too broad to own one class. | **DEDUCED:** track funded wafer, bonding, and test additions by generation. If qualified supply clears after those additions mature, it was a constraint. It earns bottleneck only if demand still cannot route around an irreducible step before the relevant generation peaks. |
| **Advanced packaging — CoWoS/SoIC/EMIB/FOPLP/OSAT** | **CONFIRMED:** Markdown and JSON still say `bottleneck`; later prose says the independent map’s `capital-and-time constraint` criticism was better and the tag was kept only below this layer. | **DEDUCED:** broad package integration is a **capital + yield-learning + qualification constraint**. CoWoS, EMIB, fan-out, and merchant OSAT are different routes; no single physical invariant covers all of them. The actual hard nodes may be substrate material, temporary-bond chemistry, alignment, known-good-die test, or inspection. | **DEDUCED:** compare funded qualified line additions with output. If capacity comes online and output rises once yield matures, demote. Bottleneck survives only if output remains capped by one non-substitutable integration step after capacity and lower-hop inputs are available. |
| **Packaging equipment — bonders, die attach, panel tools** | **CONFIRMED:** JSON gives the whole bucket `bottleneck`. | **DEDUCED:** this is mostly **constraint**. Tool build time and customer qualification are exactly what capital and time solve. A specific hybrid-bond alignment platform or temporary-bond chemistry may be a bottleneck during a generation transition, but KLIC bonders, VECO epi tools, ONTO inspection, and CAMT inspection do not share one removal test. | **DEDUCED:** after funded tool-factory expansion, can customers qualify a second tool/process before the HBM/package generation peaks? Yes means constraint. A bottleneck requires a specific sole-qualified process whose alternative repeatedly fails yield or schedule. |
| **FC-BGA + high-layer MLB** | **CONFIRMED:** JSON says `bottleneck` while admitting TTMI is “MLB, not FC-BGA.” | **DEDUCED:** split **IC-substrate fabrication** from **PCB/MLB** and from the lower-hop materials. Fabrication is near-term hybrid but ultimately fundable; ABF, low-expansion glass, or HVLP foil may be the harder node. A layer cannot inherit the lower material’s scarcity. | **DEDUCED:** observe qualified substrate output after new lines ramp while ABF/T-glass/foil are unconstrained. If output normalizes, fabrication was a constraint. If a material or process still caps all qualified lines, classify that atomic input—not the whole substrate bucket—as bottleneck. |
| **Glass-core substrate** | **CONFIRMED:** JSON calls a not-yet-volume architecture a `bottleneck`; its own watch signal asks whether any named customer reaches production rather than prototype. | **DEDUCED:** this is currently **risk/evolution**, not a binding bottleneck. A possible future standard cannot be today’s physical shortage before production demand and the winning process are established. LIDE tooling, glass supply, metrology, and substrate commercialization are separate nodes. | **DEDUCED:** require a named production platform, repeated volume qualification, and evidence that competing TGV/glass processes cannot qualify in the product window. Until then it is a design-standard option. |
| **Laser chips — CW/DFB/EML/ELS** | **CONFIRMED:** the whole device family is tagged `bottleneck`. | **DEDUCED:** split device fabrication from InP crystal, epitaxy, reliability qualification, drivers/TIAs, and external-laser architecture. Device capacity is generally **hybrid/constraint**; the strongest physical candidate is the purity/crystal/epi hop underneath it. DFB, EML, and an external CW source are not interchangeable economics. | **DEDUCED:** test whether funded epi/device capacity plus qualified second sources clear the shortage. If yes, constraint. If high-purity crystal or one reliability-qualified epi process remains the universal cap, that lower hop earns bottleneck. |
| **Compound substrates — InP/GaAs/SOI together** | **CONFIRMED:** JSON assigns one `bottleneck` class to InP, GaAs, Ge, epiwafers, and photonics-SOI. | **DEDUCED:** invalid aggregation. InP crystal purity may be a physical candidate; GaAs has a different supplier/capacity structure; photonics-SOI competes against bulk-silicon architectures and is at most hybrid. SLOIY and AXTI therefore cannot inherit one class. | **DEDUCED:** run supplier concentration, qualified-diameter/purity, substitution, and customer-portability separately for each material/process. If a foundry can port from SOI to bulk silicon within the product window, SOI is not a physical bottleneck even if InP is. |
| **Silicon-photonics foundry** | **CONFIRMED:** JSON says `bottleneck`; the prose separately calls the issue unresolved and quotes the independent map’s portability objection. | **DEDUCED:** default to **constraint** until a specific foundry module is shown to be unportable. PDK, process, and qualification create stickiness, but capital can add specialty capacity and a customer-owned PIC can be redesigned. | **DEDUCED:** a named volume customer must state that the module is sole-source and cannot be ported before the product window closes. Capacity reservation or prepayment helps prove that it binds; generic platform availability does not. |
| **Metrology and inspection** | **CONFIRMED:** the broad layer is `bottleneck` because inspection gates qualification. | **DEDUCED:** “gates qualification” is not equivalent to “capital cannot solve it.” Most wafer/package metrology is a concentrated **capital + recipe-qualification constraint**. Actinic EUV mask inspection may be a true physical subnode, but KLAC wafer inspection, ONTO package metrology, CAMT package inspection, and PDFS software do not share that scarcity. | **DEDUCED:** test modality by modality: funded tool output, qualified alternatives, recipe portability, and whether the process can ramp without that exact modality. Only a sole, non-substitutable modality that remains supply-limited earns bottleneck. |
| **Process materials and consumables** | **CONFIRMED:** resist, slurry, gas, precursor, target, filtration, and handling are collapsed into one `bottleneck`. | **DEDUCED:** unusable classification. A narrow EUV resist, purified molecule, or single-country refined metal can be physical; bulk gases, filtration, CMP families, and handling are generally constraints. The bucket must split before any ticker can inherit its class. | **DEDUCED:** identify the exact molecule/formulation/grade, qualified supplier count, time-to-qualify, available capacity, and real substitute. “Used by fabs” and “qualified” do not settle it. |
| **Package thermal — AlSiC/spreaders/TIM/vapour chambers** | **CONFIRMED:** JSON says `bottleneck`, but both public candidates are tagged `DEDUCED`, and the watch signal concedes that a named production qualification is still missing. | **DEDUCED:** current class should be **risk/evolution**. The map has a plausible materials hypothesis, not proof that the layer binds or that CPSH/MTRN captures it. TIM, lid/spreader, vapour chamber, and AlSiC also have different substitution sets. | **DEDUCED:** require a named production package, a disclosed supplier, persistent qualification across the next platform, and failed/late second-source evidence. Without that, this is a story option. |
| **EDA, IP, and ASIC design services** | **CONFIRMED:** the map calls the combined layer `bottleneck` because every tape-out needs the flow/IP. | **DEDUCED:** this is a durable **standard/IP profit pool**, not physical scarcity. EDA flow certification, ARM ISA, NoC IP, and custom-ASIC services have distinct moats and design-out paths. “Necessary” does not mean “physical.” | **DEDUCED:** ask the map’s own removal question. If a design team can replace the supplier through a tool-flow migration, IP redesign, or next-tapeout decision rather than rebuilding a physical process, it is a standard/constraint. |
| **Leading-edge foundry + US jurisdiction** | **CONFIRMED:** one row combines leading-edge process, domestic location, mature/specialty fabs, and five candidates under `bottleneck`. | **DEDUCED:** split at least three nodes: leading-edge qualified process (**hybrid**), legally required US-located qualified capacity (**possible jurisdiction bottleneck**), and mature/specialty capacity (**constraint by process**). A location is scarce only when a real customer/program must use that location and the process is qualified and utilized. | **DEDUCED:** require a named mandate or customer putting capital at risk for the specific US process, plus utilization/qualification evidence. A domestic fab shell or mature-node line does not become leading-edge scarcity by address. |

### A2. `constraint` or `risk` buckets hiding physical bottlenecks

- **Front-end WFE — CONFIRMED:** JSON calls the whole layer `constraint` while putting ASML inside it and saying “EUV a true monopoly.” **DEDUCED correction:** generic deposition/etch/implant tool output is a constraint; EUV scanner + light source + projection optics is a separate physical-bottleneck candidate. **Falsifiable test:** a second production-capable scanner/light-source/optics chain must reach required throughput and yield before the leading-edge demand window. If it cannot, EUV cannot remain buried under the generic WFE class.

- **Photomask — CONFIRMED:** JSON calls `photomask and mask blanks` a `risk` because the listed merchant player does not capture leading-edge economics. **DEDUCED correction:** PLAB’s equity exposure is risk/weak capture; that says nothing about the physical status of mask writers, EUV-grade blanks, pellicles, or actinic inspection. The map has confused **vehicle failure** with **node non-scarcity**. **Falsifiable test:** separately establish whether each exact mask substep has a qualified second source and adequate output before demand peaks. The documents do not contain that binding evidence, so I cannot honestly upgrade all four to confirmed bottlenecks; they are high-priority bottleneck candidates.

- **Fibre/FAU/precision attach — CONFIRMED:** the broad layer is `constraint`, which is correct for fibre and connectors, but its own text says the scarce know-how sits in private precision alignment. **DEDUCED correction:** split commodity fibre/connectors from a particular production-yield attach process. **Falsifiable test:** a named optical engine must disclose that only one qualified attach method reaches insertion-loss/yield targets and that a second route cannot qualify in the platform window.

- **Test — CONFIRMED:** ATE, probe cards, handlers, burn-in, sockets, and contactors are compressed into `constraint`. **DEDUCED correction:** ATE/handlers are generally constraints; burn-in insertion is a design/process risk; a device-specific probe interface can become a near-term qualification bottleneck. **Falsifiable test:** prove a sole qualified contact architecture with no workable second source before the stack ramps. The current documents do not settle that.

### A3. Other class errors that do not point toward a physical bottleneck

- **Yield analytics — CONFIRMED:** JSON says `constraint`; the independent map says workflow software can be bundled or internalized. **DEDUCED:** class it `risk / emerging workflow standard`, not a manufacturing-capacity constraint.

- **Electrical interconnect — CONFIRMED:** Markdown says `risk`, JSON says `constraint`. **DEDUCED:** the Markdown is closer. Retimers/AEC/CXL are design-slot or standard profit pools unless a standard mandates an implementation with no interoperable alternative.

- **Memory interface — CONFIRMED:** JSON says `constraint`, but the falsifier is internal silicon displacing the merchant part. **DEDUCED:** split standards-qualified RCD/DB hardware from HBM PHY IP and CXL controllers; several are `risk / standard`, not capacity constraints.

---

## B. Missing layers versus the 54-layer taxonomy

### B1. Omissions that matter to an investor

| Missing or improperly collapsed layer | Why the omission matters |
|---|---|
| **Scale-up/scale-out switch silicon, NICs, DPUs** | **CONFIRMED:** absent as a standalone layer; AVGO/MRVL are instead parked under “accelerators.” **DEDUCED:** this hides a separate standards/profit pool and its Ethernet-versus-proprietary falsifier. It materially changes candidate placement and peer comparison. |
| **Clocking, timing, management, security silicon** | **CONFIRMED:** absent. **DEDUCED:** probably not a physical bottleneck, but investor-relevant because it is recurring board content with a different design-out risk from retimers. SITM/MCHP-class economics should not disappear into generic interconnect. |
| **Lithography scanner, light source, and projection optics** | **CONFIRMED:** collapsed into generic WFE. **DEDUCED:** this is the most costly omission because the hard physical node is precisely the exception to WFE’s fundable class. It also hides the honest result that Zeiss SMT is not separately ownable. |
| **Prime silicon wafers** | **CONFIRMED:** absent; engineered and compound wafers are combined elsewhere. **DEDUCED:** lower AI purity makes it less exciting, but omission prevents the recursive hop and confuses foundry exposure with wafer-material ownership. |
| **Fab automation/wafer handling** | **CONFIRMED:** absent. **DEDUCED:** lower priority because it is fundable and lacks a clean US pure-play, but it should remain a map node/leading indicator rather than vanish. |
| **Mask writers; blanks/pellicles; merchant masks; actinic inspection** | **CONFIRMED:** compressed into one `photomask` row plus generic metrology. **DEDUCED:** these must be four nodes because they have different owners, classes, and vehicles. PLAB’s weak capture cannot erase NuFlare/JEOL, HOYA/Shin-Etsu, or Lasertec economics. |
| **Photoresists/underlayers; gases; wet chemicals/filtration; CMP; quartz/ceramics; targets/precursors; UPW utilities** | **CONFIRMED:** mostly collapsed into one process-materials bucket; quartz/ceramics and UPW disappear entirely. **DEDUCED:** photoresist, narrow gases, quartz/ceramics, and targets matter because the exact high-grade cut may be the recursive bottom hop. Wet chemistry, CMP, and UPW can remain grouped for navigation only if no single class or “owner” is inherited by the group. |
| **Hybrid bonding; temporary bond/debond; thinning/dicing** | **CONFIRMED:** collapsed into packaging equipment even though the ladder separately promotes BESIY and DSCSY. **DEDUCED:** material omission. These steps have different tools, consumables, replacement actions, and revenue clocks. The ladder cannot claim an exact foreign owner while the taxonomy lacks the exact node. |
| **Back-end OSAT separate from package integration** | **CONFIRMED:** AMKR/ASX and TSM CoWoS sit in the same row. **DEDUCED:** investor-material. An OSAT earns assembly/test margins; TSM owns a captive foundry-package platform. Input scarcity can hurt the OSAT while benefiting the input owner. |
| **ABF/BT separate from CCL/T-glass/HVLP/PCB** | **CONFIRMED:** all are one `substrate-materials` layer. **DEDUCED:** material because AJNMY, Nittobo, copper-foil suppliers, and PCB fabricators do not capture the same economics. “Upstream substrate material” is not an investable unit. |
| **Underfill, mold compound, adhesives, TIM** | **CONFIRMED:** only the thermal subset appears. **DEDUCED:** the omission matters at advanced-package yield transitions, but exact formulation owners are mostly foreign/private and diversified. Keep as a map node until materiality is disclosed. |
| **Probe cards; sockets/contactors; ATE/handlers; burn-in; package inspection** | **CONFIRMED:** five distinct insertions are compressed into two broad rows. **DEDUCED:** material because FORM, COHU, ATEYY/TER, AEHR, and ONTO/CAMT have different wear cycles, customer decisions, and stage timing. The current compression makes ATEYY look like the exact owner of all “HBM test.” |
| **Optical drivers/TIAs/SerDes/DSP** | **CONFIRMED:** absent as an atomic layer; MTSI is put under laser chips and AVGO/MRVL/CRDO are scattered elsewhere. **DEDUCED:** material design-slot profit pool and necessary to avoid calling an analog/DSP vendor a laser owner. |
| **CPO and optical circuit switching** | **CONFIRMED:** discussed repeatedly but not represented as a layer. **DEDUCED:** material precisely because it is an emerging-standard risk, not proven volume. A dedicated row would stop a CPO slide from upgrading lasers, foundries, and glass into confirmed bottlenecks simultaneously. |
| **PMIC/vertical power versus wide-bandgap/HVDC** | **CONFIRMED:** MPWR, VICR, NVTS, POWI, and WOLF share one power row. **DEDUCED:** material. Point-of-load control, vertical modules, GaN/SiC devices, substrates, and rack HVDC are competing architectures and different archetypes; a demo in one does not confirm the others. |
| **Specialty/mature foundry separate from leading edge and jurisdiction** | **CONFIRMED:** TSEM/GFS/SKYT/UMC move between the photonics and jurisdiction rows. **DEDUCED:** material because process qualification—not generic “US fab”—determines the customer dependency and valuation peer set. |

### B2. Collapses that are defensible

- **CONFIRMED:** AI workload/system architecture is represented by `compute-buyer`, and accelerators/host processors are represented by `ai-accelerator` plus `server-cpu`. **DEDUCED:** this is adequate for a dependency map if those rows remain demand/reference nodes and do not receive physical-bottleneck conviction.

- **CONFIRMED:** broad passives and rack power/cooling are each retained. **DEDUCED:** keeping them broad is acceptable because the map already treats them as fundable constraints; split only when a named high-spec product is proven material to a candidate.

- **CONFIRMED:** wet chemicals, CMP, and fab utilities have no clearly demonstrated pure US vehicle in the documents. **DEDUCED:** they can be collapsed for portfolio routing, but not into a single `bottleneck` class. The honest output is often “map node/indicator,” not a proxy ticker.

### B3. The earlier 54-layer map is not an answer key

- **CONFIRMED:** the independent map separated the economics more cleanly, but it labeled mask writers and actinic inspection `PHYSICAL`, and ABF `PHYSICAL/qualification`, without showing the doctrine’s binding arithmetic: demand > supply, oligopoly/monopoly, and no substitute before demand peaks. **DEDUCED:** those should be **bottleneck candidates**, not confirmed bottlenecks, until supply/output and qualification evidence are added.

- **CONFIRMED:** the independent map verified several ADR programs but repeatedly left liquidity as `NEEDS VERIFICATION`. **DEDUCED:** that was correct; it would be wrong to promote those symbols to accumulation vehicles merely because the later pipeline found a quote.

- **CONFIRMED:** its recursive chains label functional dependencies “CONFIRMED” and then label value capture “DEDUCED.” **DEDUCED:** even some functional chains need narrower wording: the existence of a process dependency is confirmed; the vendor-specific allocation, shortage, and revenue transfer are not.

---

## C. Wrong or unsupported candidate placements

### C1. Placements contradicted by the map’s own role text

- **Server CPU / `ARM` — CONFIRMED:** the role says ARM is “the IP the hyperscalers’ custom server CPUs are built on.” ARM does not become a server-CPU producer because its IP is inside one. **DEDUCED correction:** keep ARM in reusable IP/ISA; do not assign it CPU manufacturing economics.

- **NAND/eSSD / `WDC`, `STX` — CONFIRMED:** their roles say HDD, while the layer mechanism is NAND capacity and QLC qualification. **DEDUCED correction:** split NAND/eSSD from nearline HDD/storage. HDD may benefit from AI data lakes, but it does not own a NAND shortage.

- **Packaging equipment / `VECO` — CONFIRMED:** the role itself says MOCVD/ion-beam tools “CREATE InP laser and compound-semi capacity.” **DEDUCED correction:** move VECO to compound-epi/process tools under the optical chain; it is not a packaging-equipment candidate.

- **Packaging equipment / `ONTO`, `CAMT` — CONFIRMED:** both roles are inspection/metrology. **DEDUCED correction:** keep them in advanced-package inspection. A tool that qualifies a packaging line is not a bonder/die-attach owner.

- **FC-BGA / `TTMI` — CONFIRMED:** the note explicitly says “MLB, not FC-BGA” and “not the same node.” **DEDUCED correction:** remove TTMI as the primary route for FC-BGA and create a separate high-layer PCB/MLB row. An adjacent public route is not ownership.

- **Glass-core substrate / `LPKFF` — CONFIRMED:** LPKF is described as the LIDE **tool** owner, not a substrate fabricator; ONTO is metrology, and GLW is broad glass. **DEDUCED correction:** the current candidate list spans tool, inspection, and possible material supply while no one owns commercial substrate output. Split the nodes; otherwise “glass-core bottleneck” has no matching equity owner.

- **Laser chips / `MTSI` — CONFIRMED:** the JSON role supplied is “laser drivers, TIAs and RF/analog content,” which supports the omitted optical-electronics layer, not this laser-chip placement. **DEDUCED correction:** either cite the exact MACOM laser product that earns inclusion or move the role as written to drivers/TIAs.

- **Compound substrates / `SLOIY` — CONFIRMED:** Soitec is described as photonics-SOI, while AXTI/IQE occupy compound crystal/epi. **DEDUCED correction:** give engineered SOI its own layer and architecture-substitution test; do not let InP scarcity confer a bottleneck tag on SOI.

- **Silicon-photonics foundry / `SKYT` — CONFIRMED:** the role says “jurisdiction is the scarce attribute here, not the node.” **DEDUCED correction:** that sentence disqualifies the placement. Put SKYT in trusted/specialty US foundry, subject to process/customer qualification.

- **Metrology / `PDFS` — CONFIRMED:** PDFS is yield-analytics software. **DEDUCED correction:** software adjacency does not make it an inspection-equipment owner; keep it in yield analytics.

- **Photomask + blanks / `PLAB` — CONFIRMED:** the row admits PLAB is merchant mask while blanks are the concentrated Japanese node. **DEDUCED correction:** PLAB can be a merchant-mask counterexample, never the candidate for blank scarcity.

- **MLCC / `VSH`, `LFUS` — CONFIRMED:** the notes say VSH is not the high-spec MLCC expression, while LFUS is circuit protection/power. **DEDUCED correction:** neither belongs as owner of the scarce high-spec MLCC cut. If MRAAY is not an executable vehicle, the correct result is no faithful route—not two wrong US proxies.

- **Process materials / `LIN`, `APD` — CONFIRMED:** the JSON itself calls LIN “theme exposure, not bottleneck ownership” and says APD has the same dilution. **DEDUCED correction:** mark both broad analogs, not candidates owning the bottleneck. Their inclusion under a bottleneck-class row violates the map’s stated doctrine even with the caveat.

- **Leading-edge + US jurisdiction / `GFS`, `SKYT`, `UMC` — CONFIRMED:** their own roles are mature/specialty, trusted, and mature-node; UMC is not a US-location expression. **DEDUCED correction:** only a candidate with the exact process and jurisdiction demanded by the customer belongs in that atomic row. These names require separate specialty/mature/trusted-foundry rows.

- **Power semis / `NVTS`, `WOLF` — CONFIRMED:** their product categories exist, but the documents supply no named repeat-production AI-rack qualification. **DEDUCED correction:** product existence is CONFIRMED; AI value capture remains DEDUCED. WOLF is additionally an asset/restructuring case, not a clean high-density-power content play.

### C2. `CONFIRMED` is scoped incorrectly

**CONFIRMED:** the JSON contains 82 candidate placements tagged `CONFIRMED` and only 13 tagged `DEDUCED`. No candidate object contains a citation or distinguishes these three claims:

1. the company makes a product;
2. the product is in this AI chain or a named customer platform;
3. the company captures material economics from the layer’s scarcity.

**DEDUCED:** most existing `CONFIRMED` tags prove only claim 1. ARM/server CPU, TTMI/FC-BGA, UMC/US-jurisdiction, LIN/APD/process-material bottleneck, and PLAB/mask blanks show why that is fatal: the product/company fact can be true while the layer placement and value-capture claim are false. Replace `link` with separately sourced fields such as `role_evidence`, `customer_link`, `scarce_attribute_owned`, and `economic_materiality`; each needs its own `CONFIRMED`/`DEDUCED`.

**CONFIRMED — UNRESOLVED:** the source note says every `CONFIRMED` link rests on a company release, conference disclosure, or third-party source, but none of those sources is attached to the corresponding candidate. I cannot settle the status of SIVEF’s CPO production link, LPKF’s alleged sole LIDE position, XFABF’s photonics role, or several current AI qualifications from these artifacts. The missing data are the exact issuer/source URL, date, claim excerpt, production-versus-demo status, and named-customer/materiality evidence.

### C3. DEDUCED links promoted too far in prose

- **CONFIRMED:** “the bottleneck has already migrated off the die” is presented as settled, but the immediate support is Kiwoom’s scaffold, explicitly labeled “not evidence.” **DEDUCED correction:** migration is generation-, customer-, and date-specific; treat it as a hypothesis until independent supply/demand data show wafer/accelerator availability easing while the downstream node still binds.

- **CONFIRMED:** the ladder section says the ADRs “trade fine in the US,” then later admits spread and liquidity may make every tranche expensive. **DEDUCED correction:** a quote proves existence, not execution quality. The first sentence is stronger than the evidence and should be deleted.

- **CONFIRMED:** DSCSY is called “close to a monopoly,” and its high gross margin is described as “consistent with genuine monopoly economics.” **DEDUCED correction:** margin cannot prove market structure. Required evidence is process-specific share, qualified alternatives, customer switching data, and the inability of competing grinding/dicing routes to qualify in time.

- **CONFIRMED:** BESIY is called the “bottleneck-within-the-bottleneck for HBM4-class 3D stacking.” **DEDUCED correction:** this overstates one process route before the map establishes which HBM generation/platform uses hybrid bonding, at what volume, and whether competing tools/processes qualify.

---

## D. ADR ladder claims

### D1. Standard the map should have used

**CONFIRMED:** a pipeline quote answers only “does a data vendor return a price?” It does not answer sponsorship, issuer involvement, depositary rights/fees, active issuance/cancellation, DTC eligibility, broker access, market-maker depth, median spread, effective spread, local-share parity, or slippage at the intended tranche size.

**DEDUCED:** a multi-year `SCALE-IN` vehicle should not pass rung 1 until it has all of the following: official program status and ratio; books open/DTC eligibility; broker availability; sustained multi-month trading rather than isolated prints; live two-sided NBBO; displayed and executable depth at the planned tranche; measured effective spread/slippage versus the local ordinary after FX/ratio; and known depositary/corporate-action fees. The decisive execution test is a sequence of small limit-order probes, not a yfinance close.

### D2. Ticker-by-ticker verdict

| Ticker | What is actually established | Vehicle verdict |
|---|---|---|
| **ATEYY** | **CONFIRMED:** [Advantest’s own IR page](https://www.advantest.com/en/investors/shares-and-corporate-bonds/share-information/) identifies ATEYY as an OTC ADR with JPMorgan as depositary; [BNY’s DR directory](https://www.adrbny.com/directory/dr-details/_jcr_content/root/drDetailsComponent.overview.overview.00762U200.html) identifies the program as sponsored and shows recurring monthly trading. | **DEDUCED — SURVIVES:** strongest rung-1 accumulation vehicle of the six. Still require live spread/depth and broker confirmation before sizing; sponsorship and recurring activity do not guarantee a good fill on a volatile day. |
| **DSCSY** | **CONFIRMED:** [BNY’s DR directory](https://www.adrbny.com/directory/dr-details/_jcr_content/root/drDetailsComponent.overview.overview.25461D100.html) identifies DSCSY as an unsponsored ADR with multiple depositaries and shows recurring monthly trading. | **DEDUCED — SURVIVES EXECUTIONALLY, WITH PROGRAM RISK:** not a quote-only artifact. Actual activity is sufficient to keep it on the ladder, but unsponsored status means weaker issuer involvement, potentially variable fees, and more corporate-action complexity. Limit orders and parity checks remain mandatory. |
| **MRAAY** | **CONFIRMED:** [BNY’s DR directory](https://www.adrbny.com/directory/dr-details/_jcr_content/root/drDetailsComponent.overview.overview.626425102.html) identifies MRAAY as unsponsored with multiple depositaries and shows sustained recurring trading. | **DEDUCED — SURVIVES EXECUTIONALLY:** the unsponsored label alone does not kill it; the trading record is real. The investment-expression problem is separate: Murata is diversified and high-spec AI MLCC materiality is not established here. |
| **AJNMY** | **CONFIRMED:** [Ajinomoto’s own IR page](https://www.ajinomoto.co.jp/company/en/ir/stock/adr.html) identifies AJNMY as its JPMorgan OTC ADR. BNY’s [conversion notice](https://www.adrbny.com/content/dam/adr/documents/books-closed/files/BC2001277.pdf) shows the old unsponsored AJINY facility converting to sponsored, and its [successor-program directory](https://www.adrbny.com/directory/dr-details/_jcr_content/root/drDetailsComponent.overview.overview.009707308.html) shows recurring trading under the new CUSIP. | **DEDUCED — CONDITIONAL SURVIVOR:** likely usable for patient retail accumulation, but the sponsored program is new enough that a longer spread/depth history is still needed. More importantly, it fails **exposure purity**, not necessarily execution: ABF is embedded in a broad conglomerate. |
| **BESIY** | **CONFIRMED:** [BNY’s DR directory](https://www.adrbny.com/directory/dr-details/_jcr_content/root/drDetailsComponent.overview.overview.073320103.html) identifies BESIY as a sponsored OTC program with books open and recurring monthly trading. | **DEDUCED — CONDITIONAL, NOT “TRADES FINE”:** it is not quote-only, but the documents do not establish spread, depth, or tranche slippage. Keep it rung 1 only for small, patient limit-order accumulation after live execution tests; otherwise buy the local ordinary where permitted or keep it a map node. |
| **SLOIY** | **CONFIRMED:** Citi identifies [SLOIY as an unsponsored ADR](https://depositaryreceipts.citi.com/adr/common/file.asp?idf=3923), DTC-eligible with books open, and its [current program page](https://depositaryreceipts.citi.com/adr/guides/pgm_dispabook.aspx?cusip=83409F208&pageId=15&subpageID=111) shows recent trades. **DEDUCED:** those pages do not establish robust multi-month depth, and the observed activity is thin relative to the stronger routes above. | **DEDUCED — FAILS AS DEFAULT SCALE-IN VEHICLE:** this is the closest of the six to a quote-only artifact. It can support a tiny limit-order position, not an assumed repeated-tranche program, until 60–90 day NBBO/depth/slippage data prove otherwise. |

**CONFIRMED — UNRESOLVED:** no artifact contains the intended tranche size, the user’s broker/OTC permissions, a live Level 2 book, or effective-spread/slippage history. Those data are necessary to turn the conditional BESIY/AJNMY calls and the SLOIY rejection into final execution judgments. Program sponsorship alone cannot settle them.

---

## E. Doctrine violations

### E1. Number discipline

- **CONFIRMED:** the raw macro values are explicitly attributed to the session’s pipeline run. The exact combined capex number is arithmetically traceable to the four displayed inputs. **DEDUCED problem:** those inputs mix company reporting periods (`Q1` for three companies and `Q2` for one), so “combined latest-quarter” is a rolling latest-report aggregate, not a synchronized quarter. It should not be interpreted as one period’s industry spend.

- **CONFIRMED:** `_macro.md` asserts “periodic **20–40% drawdowns** in high-beta semi names” without a pipeline field, cited historical sample, or visible calculation. **DEDUCED correction:** remove the range or source a defined cohort, window, and drawdown calculation.

- **CONFIRMED:** the JSON and prose make exact or count-like concentration claims—“three suppliers worldwide,” “two global ATE suppliers,” “three-player oligopoly,” “two-player duopoly,” “one credible tool owner,” “five-ish suppliers”—without candidate-level sources. **DEDUCED correction:** these are load-bearing bottleneck inputs and require a dated source; otherwise label them DEDUCED.

- **CONFIRMED:** comparative financial statements such as “fastest revenue growth,” “highest gross margin,” “mid-single-digit consolidated growth,” and PLAB’s exact insider-sale count are globally attributed to the pipeline, but the raw discover/analyze JSON is not archived beside the map. **DEDUCED correction:** the stated source avoids a memory-number violation, but reproducibility is still inadequate. Save the raw evidence artifact or record the exact command, ticker cohort, field, and as-of period per claim.

- **CONFIRMED:** the prose says “only about a third” of layers are bottlenecks, while the machine file marks `14 / 30`. **DEDUCED correction:** this is not a sourcing problem; it is a direct arithmetic inconsistency and should fail validation.

### E2. Counterparties, contracts, and country shares

**CONFIRMED:** I found no explicit invented country-revenue percentage or clearly fabricated named contract in the orchestrator’s map. It often avoids customer names and explicitly leaves TSEM customer concentration and NBIS financing unresolved.

**CONFIRMED:** that is not enough to validate the `CONFIRMED` links. Candidate entries have no source IDs, and several notes imply current program/customer relevance from generic product capability. **DEDUCED correction:** a product page can confirm capability; only a named production disclosure can confirm the customer/program link; only segment/backlog/filing evidence can confirm material economics. The map needs all three rails.

### E3. Theme exposure is repeatedly treated as bottleneck ownership

- **CONFIRMED:** LIN/APD are included under a bottleneck row while the note admits “theme exposure, not bottleneck ownership.”
- **CONFIRMED:** VSH/LFUS are listed under high-spec MLCC while the notes admit they do not own that cut.
- **CONFIRMED:** TTMI is the “primary US-listed route” under FC-BGA while the note admits it is only MLB.
- **CONFIRMED:** GLW, ONTO, and LPKFF are grouped as glass-core candidates even though they represent possible material, inspection, and tool roles—not commercial substrate ownership.
- **CONFIRMED:** GFS/SKYT/UMC are grouped under leading-edge + US jurisdiction despite their own roles describing mature/specialty or non-US capacity.

**DEDUCED:** caveating a proxy after placing it in the candidate column does not cure the violation. The machine-readable consumer still receives the ticker as a candidate for that layer. Add a distinct `relationship: owner | tool | consumer | adjacent_proxy | indicator` field and exclude `adjacent_proxy` from ownership cohorts.

### E4. N9 data-integrity hard block was not honored

**CONFIRMED:** `_macro.md` says every filing dossier was null because EDGAR returned 403 and explicitly says gates requiring filings must be `conditional` or `blocked`. JSON nevertheless calls NBIS “an Evolution-archetype name,” while admitting its discriminator—funded versus dilution-funded—is unavailable.

**DEDUCED:** NBIS must be `UNRESOLVED`, not tagged Evolution with one unproven gate. N9 says a blocked filing line hard-blocks the archetype before downstream judgment. More broadly, sector-layer hypotheses may remain DEDUCED during an EDGAR outage, but phrases such as “the finding I’d act on first,” “best expression,” and single-name chokepoint ownership are not licensed. They require the identity fork and filing-dependent gates first.

### E5. The thesis DB was used without authorization

**CONFIRMED:** `_sectormap.md` says, “The thesis DB was consulted as a candidate pool only,” and the JSON cites it in SIVEF, ONTO–LPKF, and AEHR notes. The user did not ask for cross-validation.

**DEDUCED:** this directly violates non-negotiable 8. “Candidate pool only” is not an exception. Remove every DB-derived confirmation, re-derive candidates independently, and retain a link as DEDUCED until an issuer/filing/conference source confirms it.

### E6. Bottleneck checks were tagged, not run

**CONFIRMED:** most `bottleneck` rows state concentration and a mechanism but do not quantify a demand-versus-supply imbalance, do not establish no substitute before demand peaks, and do not show pricing realization. The map also lacks per-unit layer economics.

**CONFIRMED:** the required recursive check asks for the bottom hop, a **specific** second-order allocator, a chain-sibling ranking, and priced layer economics. The map names some lower hops but gives no specific allocator for most, no content/output/pricing arithmetic, and no consistent substrate-versus-tool-versus-module economics.

**DEDUCED:** the current `bottleneck` field means “plausibly scarce,” not “passed the doctrine.” Rename it `bottleneck_candidate` until all three binding tests and the recursive check are present.

### E7. Macro confidence exceeds the evidence

**CONFIRMED:** two of four regime pillars—net liquidity and credit—are unread, yet `_macro.md` ends with “Full conviction is allowed on structure.” The doctrine says an unresolved pre-answer check drops conviction a tier.

**DEDUCED:** “constructive, staged” is defensible; “full conviction” is not. The missing credit/liquidity pillars and EDGAR-wide hard block should cap the cohort below full conviction. BDI strength also cannot, by itself, be promoted into proof of AI-material demand.

### E8. The map crosses from map to action without completing the funnel

**CONFIRMED:** the document calls itself a structural map and says numbers expire, but then uses “where the real money is” and “the finding I’d act on first.” No single-name winner gates, current valuation lens, stage scorecard, float/dilution read, or vehicle execution test accompanies that action language.

**DEDUCED:** either keep the artifact strictly as candidate generation or complete `analyze -> N9 -> winner gates -> stage -> lens -> vehicle` for each actionable name. It cannot be both a non-valuation map and an action list.

---

## F. The framing most likely to be wrong

**DEDUCED — highest conviction criticism:** `limitation_class` is attached to the wrong object. Scarcity is not a stable property of an industry noun such as “advanced packaging,” “test,” “process materials,” or “compound substrates.” It is a property of an **atomic scarce attribute on a dated product-generation edge**: HBM generation × bonding route × customer qualification window; optical architecture × light-source choice × epi source; package design × substrate stack × exact dielectric/foil/glass grade.

**CONFIRMED:** the map itself supplies the evidence against its schema:

- “advanced packaging” includes captive CoWoS, merchant OSAT, bonders, and inspection;
- “test” includes ATE, probe cards, sockets, burn-in, and package inspection;
- “process materials” includes resist, gas, slurry, targets, and filtration;
- “compound substrates” includes InP/GaAs/Ge and photonics-SOI;
- “photomask” includes merchant masks and blanks;
- “leading-edge + US jurisdiction” includes leading-edge, mature-node, trusted, US, and non-US capacity.

**DEDUCED:** because each composite row is forced to accept one class, every downstream field becomes contaminated. A lower-hop bottleneck lends its label to a fundable assembler; a listed consumer/adjacent tool becomes the “route”; `CONFIRMED` product existence becomes `CONFIRMED` economic capture; and the count of bottlenecks changes merely with taxonomy granularity. That is why the prose can say “only about a third,” the JSON can say 14, and both can feel plausible—the denominator is arbitrary.

**DEDUCED correction:** normalize the graph to atomic nodes and put classification on a time-bounded edge. Minimum required fields:

`node -> exact scarce_attribute -> generation/customer window -> minimum removal action -> demand evidence -> qualified supply evidence -> substitute/qualification time -> owner -> consumer/tool/proxy relation -> evidence scope/source -> vehicle status`.

**DEDUCED falsifier:** this criticism is wrong only if every candidate inside each current row owns the same scarce attribute, can be removed by the same minimum action, faces the same substitute/qualification clock, and captures the same pricing economics. The map’s own role text already falsifies that condition in advanced packaging, test, process materials, glass core, photomask, power, and foundry. Until the schema is fixed, polishing individual `bottleneck` labels will not repair the map.
