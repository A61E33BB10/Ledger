# KARPATHY Adversarial Review — Phase 3 Round 1

**Reviewer:** KARPATHY (independent; first-principles, build-from-scratch lens).
**Target:** `phase2/proposal_v1.md` (the Phase-2 synthesis).
**Frame.** I asked one question for two days: *Could a smart engineer, handed only this 545-line document and the seven specialist files it points at, build a working data-layer prototype end-to-end in two weeks?* If no, the spec has failed at its primary job — being a curriculum from which the system can be reconstructed. The document is well-structured prose, but prose is not what an engineer compiles against. I attacked it on three axes: (1) is each leaf buildable from what's given? (2) what implicit knowledge is required and not surfaced? (3) where has jargon been substituted for understanding?

---

## §0. Methodology

I picked five leaves at random and tried to mentally write the simplest possible end-to-end loader for each (parser → validator → store → projection). For each one I asked:

1. What is the **minimum bytes-on-the-wire** I need to parse?
2. What is the **minimum schema** I write into storage?
3. What is the **simplest test** that proves the loader works?
4. What dependency must already exist before I can start?

The five leaves: L1 ProductTerms, L10 RawMarketObservation, L13 CalibratedMarketObject, L14 MoveStream, L19 Snapshot. These span all five mutation disciplines and exercise the hardest abstractions (bitemporal, hash-chain, content-addressed, witness-typed).

Result: **3 of 5 are not buildable in 2 weeks from this document alone.** The other 2 are buildable but only because they essentially rebuild what CDM already gives you. Details below.

---

## §1. Findings

### BLOCKING

#### B1. No data-layer loader is specified end-to-end for any leaf.

The proposal lists, for each of 24 leaves, a "minimum field set" sentence (one line) plus six pointer-letters (N/M/T/R/F/C) telling you to drill into seven specialist files. **It never shows the wire format → parsed type → stored row → projection round-trip for a single leaf.** Not one. The closest thing is L1 ProductTerms, which says `Min fields: unit_id, product_type, terms_payload, version_seq, t_known, attestor, signature` — but `terms_payload` is the 99% of the actual content of a productTerms record (the economic terms of an OTC swap, a bond, a structured note), and the document does not specify what its shape is. It says "see CDM `EconomicTerms`", which is a 2000-page schema. A junior engineer cannot ship from this. **Failed Junior Dev Test on every leaf.**

**Mitigation needed:** For at least one representative leaf in each of the six classes (so 6 worked examples), provide a concrete minimum specimen — an actual JSON/YAML payload of, say, 30 lines, the parsed type signature, the storage row shape, and a one-line projection example. Without these, "ProductTerms = NonEmpty<TermsVersion>" is not a specification, it is a label.

#### B2. The proposal cannot be executed without reading 7 sibling files in full.

§3 (per-leaf specification) compresses each leaf to ~6 lines and references seven specialist files for the actual content. The proposal admits this: "Where this document compresses a specialist's argument, the specialist file is the authoritative source." This means the document is not the specification — it is a **table of contents** for the specification, and the specification is distributed across 8 files. A reader who hasn't read all 8 files cannot evaluate any single leaf. This is the opposite of progressive disclosure: the leaf-level claim and the leaf-level evidence are in different files, and you must context-switch on every leaf.

**Mitigation needed:** Either (a) inline the specialist contributions into §3 so each leaf is self-contained (the doc would grow to ~3000 lines but be self-contained), or (b) acknowledge in §0 that the *minimum reading set is 8 files, ~?? thousand lines*, and provide that page count up front so reviewers know what they signed up for.

#### B3. "Witness types" / "arbitrage_certificate" / "snapshot_certificate" are named but not constructed.

L13 says `CalibratedState with witness type arbitrage_certificate`. L19 says `Snapshot ... witness type snapshot_certificate`. These are gestures toward dependent-types or refinement-types features, but the proposal **does not specify the construction rule** for any witness, nor what proof-obligation produces it, nor what language feature provides it (Idris? Lean? F* refinements? Rust's typestate? GADTs?). MINSKY §0 is referenced but the proposal never states what concrete representation the witness has at the parse boundary. A junior engineer reading "with witness type X" will type a Boolean field called `is_certified: bool` and call it done — and the entire correctness story collapses, because that is exactly the failure mode witness-types are meant to prevent.

This is **jargon substituted for understanding**. The whole Bayesian-posterior/no-arbitrage/replay-determinism stack rests on these certificates being non-forgeable by construction; the proposal names them and moves on.

**Mitigation needed:** Pick a concrete language (the proposal seems to assume OCaml from the MINSKY references, but never says so). Show one full witness type with its constructor, the proof obligation it discharges, and the failure mode it prevents. One worked example is enough; without it, the witness story is incantation.

#### B4. `terms_payload` polymorphism: how is the unit_type variant actually closed?

§2.2 says "Listed-instrument detail (rejected) — Folded into L1 ProductTerms as a `unit_type` variant." V2 says "Folded into ProductTerms variants." But `ProductTerms` must hold the economic terms of: vanilla OTC IRS, asian option on a basket of equities, a callable structured note with KIKO barriers, a US Treasury bond with TIPS-style inflation linkage, an SBL collateral basket with rehypothecation rights, a tokenised real-world asset, a QIS index strategy, a mandate document, AND a listed instrument descriptor. The variants of `unit_type` are not enumerated anywhere in the proposal. CDM's `Product` has hundreds of leaf types; how many does the Ledger admit? Without the answer, you cannot write the parser and you cannot write the type. **This is the load-bearing polymorphism of the entire data layer**, and it is delegated to "CDM v6.0.0 vocabulary" in §0.4 — but §7 Gap #1 says half of what we need is CDM-missing.

**Mitigation needed:** Enumerate the closed sum-type for `unit_type` (or reference an exact CDM enum and identify the exact extensions). This is the single most important type-level decision for the data layer; it cannot be implicit.

### UNMITIGATED MAJOR

#### M1. The "MoveStream is canonical, everything else is a projection" claim is repeated four times but never schematised.

§0 anchor 2, §1.2 V13, §3.5 L14, §8 theorem 4 all assert: balances, P&L, positions, balance-sheet are projections of L14. **The proposal never specifies what the projection function from L14 to {balance, P&L, position} looks like.** Not even pseudocode. A reader cannot tell whether "projection" means SQL `GROUP BY`, a streaming fold, a ZK-proof-able query, or hand-written code per projection. If projections are hand-written, V13 ("no Trade/Position table") is a hollow win — the projection code is the table. If projections are derived mechanically, what is the derivation rule?

**Mitigation needed:** One concrete projection (e.g., `balance_at(wallet, asset, t) = sum over all moves m in L14 where m.wallet = wallet, m.asset = asset, m.t_known ≤ t of m.delta`). One example. Until that exists, "projection, not table" is a slogan.

#### M2. Bitemporal is mandatory but never *defined* in this document.

§0 anchor 3 declares "the bitemporal axis is mandatory for every leaf in C1 and C4." NAZAROV N6 and FORMALIS L4 are referenced. But the proposal never states the **two timestamps explicitly**: which one is `t_obs`? `t_known`? `t_valid`? `t_record`? Different bitemporal traditions use different names with different semantics (system-time vs valid-time; Snodgrass vs Allen). The proposal uses `t_obs` and `t_known` apparently as a pair, but never says "t_obs is the timestamp the world stamped on the observation; t_known is the time we learned it." A reader who has only encountered "bitemporal" as a phrase will write two `timestamp` columns and ship — and the entire restatement story silently breaks.

**Mitigation needed:** A 5-line, normative definition of (`t_obs`, `t_known`) at the top of §4 or §6, with one worked restatement example: "vendor sends correction at t=10 for value originally stamped at t=3; resulting two rows are ...". Without this, "bitemporal mandatory" is a label.

#### M3. The "thin sidecar" rebuttals to V8/V9/V10/V11 are negotiation artefacts, not engineering.

§3.1 L7 (Policy) negotiates with V9 by saying "L7 is admitted as a leaf with bitemporal/version-pinned discipline, but the realism budget is 'small sidecar, not a parallel data spine'. The veto is honoured by refusing to let L7 grow beyond ~30 fields." Same pattern for L5 vs V10, L24 vs V11. The number "30 fields" is asserted with no engineering basis. Why not 10? Why not 100? The reconciliation reads as a political compromise between two specialist views, not as a derived constraint.

**The Karpathy test fails here:** if I cannot derive the 30-field bound from first principles, the bound is folklore. Either delete the bound (and admit the veto won) or derive the bound (and show the calculation that gives 30).

**Mitigation needed:** Replace each "thin sidecar / ~30 fields" hand-wave with a concrete check (e.g., "L7 contents are enumerated in [appendix]; total 14 fields; growth requires governance review"). Without that, V9/V10/V11 are reconciled in name only.

#### M4. The 4 unwitnessed laws (L1, L4, L8, L13) are escalated to "surrogate strategies" without showing the surrogates.

§4 and §9.4 admit that 4 of 14 cross-layer laws cannot be tested by any finite suite. The proposal proposes "surrogate strategies": *trust registry + threat model + multi-source consensus* (for L1), *bounded chains + retention horizon* (L4), *content-addressing + erasure coding + cross-replica verification* (L8), *bounded-horizon test + structural induction* (L13). **None of these surrogates is specified concretely.** What threshold of multi-source consensus? Bounded-chain length? Erasure-coding parameters? Bounded-horizon length for liveness? The surrogate strategy is a label, not a specification. A reviewer cannot tell whether the surrogate is sufficient.

**Mitigation needed:** For each of the 4 surrogates, give the operational parameters. If the parameters cannot be set without further work, list them as deferred-but-named (e.g., "L1 surrogate parameters TBD: minimum source count for consensus, minimum entropy of attestor diversity"). Do not let the word *"surrogate"* substitute for the specification.

#### M5. The ingestion/parser ring is alluded to but not specified.

V4 says "per-vendor lives in the parser ring." §1.2 P5 says "Errors are values; `Result<Parsed, Error>`." But there is no §X "Parser Ring Architecture" in the proposal. What is a parser ring? Is it a per-vendor adapter pattern, a chain-of-responsibility, a content-type-dispatched dispatcher? How does it interact with L19 snapshot capture (P6)? Where does L20 idempotency check live (in the parser ring or after)? A reader who has not read jane_street.md cannot answer these questions, and the proposal does not flag them.

**Mitigation needed:** A §3.7 "Parser Ring" subsection of one page, with a diagram. Pick one leaf (L10 RawMarketObservation, since it has the highest vendor diversity) and walk the path: bytes → parser → Result → idempotency check → snapshot → store. One page. Right now the parser ring is invisible.

#### M6. The "snapshot pinning at every impure boundary" claim has no concrete rule for *what* gets pinned.

P6 says "every external read is captured in an L19 snapshot keyed by content hash." L19's "min fields" is a sentence: `Content-addressed bundle of (L10 ∪ L13) rows used for one reproducible computation cycle.` But what defines the boundary of a "computation cycle"? Is it per-valuation? Per-batch? Per-workflow? Per-day? If a single calibration of a yield curve consumes 5000 raw observations, is the snapshot the full 5000 rows? Are observations referenced by ID into L10 (snapshot is a manifest) or copied (snapshot is a bundle)? The performance and replay implications are radically different.

**Mitigation needed:** Specify whether L19 is **manifest** (FK list into L10/L13) or **bundle** (copy of payloads), and bound the cycle definition (per-valuation? per-pricing-call?).

### MINOR

#### m1. Specialist leaf-count reconciliation in §2.3 is impressive but not load-bearing.

The table showing how 7/24/31/41/62/16/57/3 leaf counts all fold cleanly into NAZAROV's 24 reads as a victory lap. It is fine, but the table itself is not a deliverable for the data layer. It belongs in an appendix; it is currently in the spine of the document and inflates the perceived rigour.

#### m2. §5 fault catalogue is referenced as "49 cells" but never expanded.

The proposal says "7 clusters × 7 fault classes = 49 cells" and refers to `correctness.md §3` for content. This is typical of the document — the body has the headline, the file has the substance. For a fault catalogue (which is one of the most important deliverables of a data spec), 49 cells should be inlined as a 49-row table.

#### m3. CDM v6.0.0 dependency is treated as if it were a closed library, but it is a moving target.

§0 anchor 4 says "CDM v6.0.0 is the canonical vocabulary." §6 C-A5 says "CDM/ISO schema stability within version" is a conditional assumption. §7 Gap #1 says critical layers are CDM-missing and may not land "for years." §3 leaf-by-leaf gives status `Direct / Partial / Missing` per leaf. **The proposal does not state what happens to a Ledger that has shipped on `v6.0.0` when CDM ships `v7.0.0` with breaking changes to types we've already adopted.** L21 version-pin is referenced but the migration story is not.

#### m4. The proposal occasionally drops named entities without context.

`StatesHome map 1 / map 2 / map 3` is referenced repeatedly without saying what StatesHome is. The reader is expected to know it from prior `v10.3` documents. For a Phase 3 reviewer parachuting in, this is friction. A glossary of `StatesHome`, `NOETHER`, `GROTHENDIECK`, `pricing DAG` would help. Same for `mandate-as-unit`, `QIS`, `KIKO` — many of these need context for someone outside the team.

#### m5. The "complexify one thing at a time" discipline is not visible in the build plan.

There is no §X "Build order" / "What to ship first." A two-week prototype must pick a path: do you build L1 ProductTerms first (because everything keys off `unit_id`)? Or L14 MoveStream (because it's canonical)? Or L10 RawMarketObservation (because it's the highest-throughput stream and forces ingestion concerns)? The proposal is timeless — it shows the system as a finished cathedral, not as a sequence of buildable increments. **This is the most "Karpathy" of the minor findings**: the proposal violates *"complexify only one thing at a time"* by not telling you which thing to do first.

---

## §2. Verdict

The proposal is **architecturally coherent** — the 24-leaf spine is a genuine convergence of seven independent specialist views, the conservation/lineage/replay invariants are real, the bitemporal-mandatory rule is sound, and the V8–V14 vetoes do correctly identify over-engineering traps the team would otherwise fall into.

But the proposal is **not yet a buildable specification.** It is a **map of where the specification will live** once the seven specialist files are reconciled and the missing pieces (worked examples, parser ring, projection definitions, witness type constructions, surrogate parameters, build order) are written. Today, a smart engineer cannot build a working prototype in two weeks from this artefact alone. They could possibly build one in 6–8 weeks if they read all 8 files exhaustively and made many independent design decisions on the un-specified bits — but those independent decisions are exactly where the design will fragment.

**The dominant pattern of the failure modes:** the document **labels** rather than **constructs**. Witness types, projections, parser rings, surrogates, bitemporal axes, polymorphic variants, thin sidecars — all are named and none are built. This is the Karpathy anti-pattern: jargon substituting for understanding. *"You should not be using a neural network as a black box."* Same here: do not let "MoveStream" or "witness-typed certificate" be opaque to your readers.

The document is correctly placed at Phase 2 (synthesis); the gap to Phase 3 (review-ready) and the gap to Phase 4 (build-ready) is large.

---

## §3. Grade

**Grade: C+ / "promising synthesis, not yet buildable."**

- **A+** — buildable in 1 week by a competent engineer.
- **A** — buildable in 2 weeks; one or two clarifying questions.
- **B** — buildable in 4 weeks; significant decisions required.
- **C+** ← **THIS DOCUMENT.** Buildable in 6–8 weeks with extensive cross-file reading and independent design decisions; high risk of design fragmentation.
- **C** — not buildable; major rework required.
- **F** — fundamentally inconsistent.

The C+ reflects that the **content** is good (architecture is sound, vetoes are correct, taxonomy converges) but the **artefact form** is wrong (fragmented across 8 files, leaf specs are pointer-letters, no worked examples, no build order). This is fixable: B1–B4 (blocking) plus M1, M2, M5, M6 (major) are all editorial deliverables — write them and the grade moves to A.

The criticism is **of the document, not of the project**. The team has done the hard thinking; now the hard *writing* must happen.

---

## §4. Suggested Round-2 deliverables

Ordered by leverage:

1. **Six worked-example leaves** — one per class — with full wire-format → parsed-type → storage-row → projection round-trip in self-contained 2-page sections. (Resolves B1 + part of M5.)
2. **Inline the specialist content into §3** so each leaf is self-contained, OR clearly mark the proposal as "table of contents" and give a total page count for the minimum reading set. (Resolves B2.)
3. **One concrete witness-type construction** — pick `arbitrage_certificate` for L13 — with constructor, proof obligation, language choice. (Resolves B3.)
4. **Closed enumeration of `unit_type`** with mapping into CDM types and named extensions for the missing variants. (Resolves B4.)
5. **One concrete projection** — `balance_at(wallet, asset, t)` over L14 — in pseudocode. (Resolves M1.)
6. **5-line normative bitemporal definition** with one restatement example. (Resolves M2.)
7. **L19 snapshot specification** — manifest vs bundle, cycle boundary. (Resolves M6.)
8. **§3.7 Parser Ring** — one page with diagram and one walked example. (Resolves M5.)
9. **Surrogate parameters** for L1, L4, L8, L13 unwitnessed laws. (Resolves M4.)
10. **Build order** — a 6–12 step sequence: which leaf first, which test first, what proof first. (Addresses m5.)

If these ten items land, the proposal goes from **C+** to **A**.

---

**End of KARPATHY review, Phase 3 Round 1.**
