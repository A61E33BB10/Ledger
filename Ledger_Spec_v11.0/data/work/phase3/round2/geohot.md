# GEOHOT — Phase 3 Round 2 Closure-Check of `proposal_v2.md`

**Stance.** Radical simplicity. Delete aggressively. Beautiful code reveals truth. I attacked v1 at C+. v2 went 545 → 654 lines defending 19 leaves instead of 545 lines defending 24. Question: did the substance change, or did the diplomacy improve?

**Verdict up front.** Substance moved. Not enough. v2 closes B1 cleanly, B3 cleanly, B2 *partially* (vetoes now have CI hooks but the qualifying-paragraph pattern survived in §15), and ignores M5 entirely (no LoC budget anywhere). Net: meaningful structural progress, residual diplomatic accretion. **Grade: B−.**

---

## 1. Closure of R1 BLOCKING findings

### B1 — "24 leaves too many; cut to 16."

**CLOSED** (with documented escape valve).

Citation: proposal_v2 §4.1: "Phase-2 v1 proposed 24 leaves… v2 rules the **minimalist path**: collapse to FORMALIS-aligned 16 + 3 ADR-sanctioned additions = **19 leaves**."

Verification of my kill list (§4.2 disposition table):
- L4 Calendar — kept as separate leaf (NOT folded into L2). Disagreement noted; v2 cites mode-1 pin discipline as justification. Acceptable: ADR-5 documents the pin policy. Borderline.
- L5 SettlementInfra — *deleted as proposed leaf*; the v1 "L5 SSI" is gone; v2's L5 is now UnitStatus (renumbered). Closed.
- L7 Policy — kept as L7P with cap enforced via CI per ADR-12. Closed (V9 has teeth now).
- L17 AttestationEnvelope — folded as field. **Closed exactly as I asked.**
- L18 IdentityKeys — folded as field. **Closed.**
- L20 IdempotencyToken — folded as closed-sum field. **Closed.**
- L22 HashChainAnchor — folded as field on L13. **Closed.**
- L24 OrchestrationState — *deleted from spine* per V11. **Closed exactly as I asked.**
- L19 Snapshot — reclassified as named view. **Closed.**

Net: 7 of my 8 deletions honoured (L4 retained with ADR justification — defensible). L19 reclassification honoured. The 3 ADR-sanctioned additions (L17 RegSub, L18 BreakReg, L19 ClockAuth) each cite a specific regulatory or symmetry-carrier requirement that no member of the FORMALIS-16 discharges. Each addition has a per-leaf ADR (ADR-2, ADR-3, ADR-4). This is the discipline I demanded.

19 leaves with documented justifications beats 24 with hand-waving. **Closed.**

### B2 — "§9.2 vetoes V8/V9/V10/V11 are not actually reconciled."

**PARTIALLY CLOSED.**

What v2 did right (§3.2): each veto V1–V14 now has (i) a falsifying predicate, (ii) a named CI mechanism. "No enforcement = wish" is now the explicit ruling. V7 leaf-count ceiling pushed to ≤20 (was 7) — concession to the 19 + ADR design. V9 field-cap enforced via `count_check.py::test_l7p_field_cap`. V11 enforced via `arch_test.py::test_no_econ_orch_dep`. V13 has documented carve-out (ADR-1) instead of silent violation.

This is the right shape. Vetoes with truth conditions and CI tests have teeth.

What v2 still gets wrong: **§15 "Surfaced disagreements" is the resurrected tension box under a different name.** §15.1 through §15.5 each restate a disagreement, name a "Resolution," cite a specialist file. The pattern is: name the conflict → invoke an ADR → declare resolved. This is exactly the "tension box" diplomatic pattern jane-street M2 banned, with serial-numbered ADR badges replacing italicised headers. The §15 section claims "tension box pattern is **banned** in v2" — and then performs the pattern.

Test: §15.4 "D4 C2/C3 elevation vs projection of L13" reads "L5 / L6 are stored caches with single-writer invariants… ADR-1 documents V13 carve-out." That is a paragraph of qualifying language attached to a kept-leaf. The disagreement is "should L5/L6 be caches or projections?" The resolution is "they're caches — see ADR." Does ADR-1 actually constrain the cache discipline? Yes — §3.2 "ADR-1 (V13 override for L5/L6 stored caches)" cites CIv-1/CIv-2/CIv-3 cache-invalidation rules and Th-4b. So this one *does* have teeth. But the format is the format I told you to delete.

Also: V14 falsifying predicate ("Regulator-discriminated obligation tables") is fine, but the SBL Finding-2 disagreement on regulator-discrimination of L17 sub-types is unsettled — §13's tokenised-collateral disagreement (§15.2) reads "DigitalAsset is NOT the host" and resolves by combination. That's actual structure, not diplomacy.

Verdict: V8/V9/V10/V11 each have CI mechanisms named (V8 → `test_no_cdm_enum_table`; V9 → `test_l7p_field_cap`; V10 → `test_no_ssi_write`; V11 → `test_no_econ_orch_dep`). **The enforcement-vacuum is closed.** The diplomatic-format residue is cosmetic. Partial closure: substance won, format lost.

### B3 — "L19 Snapshot should be view, not leaf."

**CLOSED.**

Citation: §4.2: "L19 Snapshot — **Reclassified as named view** (not a leaf) — Aggregation of L9+L12 rows; content-addressed; queryable but not a stored table." The leaf slot L19 in v2 is now ClockAuthority (the new S3 carrier). V13 applied consistently.

Bonus: L8 UnitStatus and L9 PositionState reclassification challenge handled via ADR-1 carve-out citing StatesHome C11 single-writer-per-field. This is the right move — they are caches with provable invariants, not arbitrary stored projections. The cache-coherence theorem Th-4b discharges the projection-vs-leaf tension structurally.

---

## 2. Convergence checklist (verbatim)

- Net 19 leaves (16 + 3 ADR): **YES** — §4.1 explicit.
- Tension-box format banned per §15: **PARTIALLY** — banned in name, performed in §15.1–§15.5 as ADR-attached resolutions. Substance has teeth (CI hooks) but the format is the same shape I called out as Worst Pattern.
- L19 Snapshot reclassified (was L19 in v1, now ClockAuthority is L19): **YES** — §4.2 confirms reclassification; new L19 is ClockAuthority (ADR-4).
- C6 Provenance & Orchestration class folded (v1: 8 leaves; v2: 1 — L16 ReferenceMaster): **YES** — §4.4 spine listing shows C6 contains only L16. L19 SnapshotView, L21 VersionPin, L23 Capability all folded as fields or as the §11 Versioning Algebra structure. This is exactly what I asked for in §2 of my R1 ("8 leaves of C6 is cargo… result: C6 collapses from 8 leaves to 2 (L21 + L23) plus L19 as a named view"). v2 went further: 1 leaf instead of 2.
- L24 OrchestrationState deleted from spine: **YES** — §4.2 explicit "Deleted from spine — V11 violation; not economic data."
- LoC budget mentioned anywhere: **NO** — searched §0 through §18. No mention of "LoC", line-count budget, or implementation complexity ceiling. **M5 unaddressed.** This is the single biggest remaining failure. Without a budget, the spec will grow. Every future "the spec already covers it" is a free option.

---

## 3. Beauty diagnostic

Does v2 *feel* simpler, or more diplomatic?

**Honest answer: neither — it feels denser.** v2 is 654 lines (v1 was 545). The leaf count went down (24→19, a 21% cut) but the document grew 20%. The growth is in: §11 Versioning Algebra (warranted — closes T8), §12 Operational Floor (warranted — closes T4), §16 ADR register (mostly warranted — gives kept leaves teeth), §10.2 conditional-assumption table with detection/compensation/blast-radius (warranted — closes T11). These are all real engineering content I asked for in spirit, even when I didn't ask explicitly.

But: §15 (5 sub-sections of "Surfaced disagreements") and §17 (9 reviewer-instruction bullets) and §18 (Phase 3 R2 instructions) and Appendix A/B are 70+ lines of *meta* content — instructions to readers about how to read the document. **Documents that explain how to read themselves are documents that have not earned their structure.** Delete §17, §18, Appendix B. Move §15 into the relevant ADRs.

The §4.4 spine listing (the 19-leaf catalogue) is the single most beautiful thing in the document. 30 lines, ASCII art, six classes, 19 leaves, each with a one-phrase description. *This is the spec.* Everything else is appendix. If you printed §4.4 alone on a single page and threw the rest in a drill-down folder, the spec would be more useful.

L13 MoveStream still does not get the standalone prose section I demanded. It is mentioned in passing in §4.4 ("L13. MoveStream (canonical record; tx_id formula corrected)") and in §5.1 as a 4-line bullet. The single most important leaf in the entire spec gets ~12 lines total. That is committee-speak compressed. **Promote L14… sorry, L13 (renumbered) to its own section.**

So: simpler in the spine, more diplomatic in the meta-layer. Net: a wash. v2 is *more correct* but not *more beautiful*. Beauty did not win this round.

---

## 4. NEW findings

### BLOCKING

**B1-NEW. No LoC budget anywhere.** v1 M5 unaddressed. The spec is now 654 lines; there are 19 leaves, 6 theorems, 15 cross-layer laws, 17 boundaries, 15 mutation operators, 5 Goodhart traps, 12 conditional assumptions, 12 ADRs, 14 SBL sub-leaves. Without a complexity budget, every leaf will accrete fields, every law will accrete oracles, every theorem will accrete hypotheses. State: **core implementation must fit in ≤10,000 LoC excluding adapters and tests; if it does not, the spec is wrong, not the budget.** This was my v1 M5 and is now elevated.

**B2-NEW. §15 performs the banned pattern.** §15 declares the tension box "banned" then performs five tension-box resolutions. Either delete §15 entirely (move resolutions into the relevant ADRs and §13) or rename §15 honestly as "ADR pointer index." Currently it is the diplomatic format wearing an ADR costume.

### UNMITIGATED MAJOR

**M1-NEW. ADR register is 12 entries; 4 are "elevations" of new leaves.** ADR-2, ADR-3, ADR-4 each justify a leaf addition over the FORMALIS-16 baseline. These are individually defensible. But three more leaves at ADR cost is a precedent: every future leaf can argue "I have an ADR." **State the ADR ceiling: ≤4 leaf-elevation ADRs total; further additions require deletion of an existing leaf.** Otherwise leaf-creep is a free option with paperwork.

**M2-NEW. L13 MoveStream is still not promoted to standalone prose.** v1 Beauty finding survived. The single most important leaf in the spec gets a one-line entry in §4.4 and a 4-line bullet in §5.1. The 11 invariants on L13 deserve a section, not a row in a table. This is the spec's structural keystone — write it that way.

**M3-NEW. §5 per-leaf integrated specification is a stub pointing at specialist files.** §5 reads "The full per-leaf section is ~12k words at the volume R1 reviewers demanded; here we summarise the load-bearing changes vs v1. Reviewers should drill into `phase2/{nazarov,minsky,...}_v2.md` for full content." This is exactly the v1 pattern halmos B2 / karpathy B2 / feynman MAJOR-J4 / my Beauty finding called out. v2 names the disease and ships it anyway. Either inline §5 (the spec is then a real spec) or rename the document "proposal navigation index" and stop calling it a specification.

**M4-NEW. 7 canonicalisation pin variants.** §11 lists `RFC8785Version | ProtobufCanonical | CBORProfile` plus per-domain selection. Pick one. Two canonicalisation domains is two implementations diverging. ADR-6 says "RFC 8785 JCS / Protobuf canonical / CBOR per RFC 8949" — that's three. Pin one, force everything to use it. Multiple canonicalisation domains is the same disease as multiple version pins, just more compact.

### MINOR

**m1-NEW.** §9 Theorem 6 (Pillar-3-Projection-Lifting) is named "cost-free architectural commitment." Cost-free architectural commitments do not exist; either the projection function μ_P3 has implementation cost (then state it) or the theorem is cosmetic.

**m2-NEW.** §10.2 C-A1 / C-A2 owners are "TBD; OPEN — production deployment blocked on assignment per nazarov M-2." This is honest — but it means production deployment is blocked. State that *prominently*, not in a table cell.

**m3-NEW.** §12.2 BreakRegister FSM has 11 states. That's an FSM, not a state machine — it's a graph. State the transition matrix or simplify to {OPEN, AGED, ESCALATED, CLOSED}. 11 states with 4 closure variants is a Goodhart trap waiting to happen (specifically GT2: M-AGGREGATE — operators will mark CLOSED-WAIVED to clear AGED-5 backlog).

**m4-NEW.** §17 "Open issues for Phase 3 Round 2 reviewers" lists 9 instructions for how reviewers should attack v2. Reviewers should attack v2 using their own judgment. Spec authors do not get to scope reviewers. Delete §17.

**m5-NEW.** §11 Versioning Algebra has 7 axes (`component_pin, schema_pin, contract_pin, model_pin, refdata_pin, drr_rule_set_pin, canonicalisation_pin`). v1 was attacked for conflating 5; v2 ships 7. Each is justified individually but the algebra needs a composition lemma proving non-redundancy. Otherwise this is conflation broken into more pieces.

**m6-NEW.** §13 reports "True distinct-PR-unit headcount: ~15 (was claimed 5)." That's a 3x correction on a load-bearing input. Audit the rest of §13's numerics with the same skepticism.

---

## 5. What over-engineering survived this round

**Worst surviving pattern: §5 is a stub.** v1's "6-line per-leaf entries delegate to 7 specialist files" is now "we summarise the load-bearing changes; full content is in the specialist files." Same disease, lighter wrapper. The spec is not a spec until §5 is inlined or the document admits it is a navigation index.

**Runner-up: ADR proliferation.** 12 ADRs is a lot. Each is individually defensible but the ADR-as-escape-valve pattern is exactly the same shape as v1's "qualifying language." Now it has a register and serial numbers, but the structural test is the same: count the ADRs in 6 months. If it grows past 20, the ADR mechanism has become the new tension-box.

**Bronze: §15 disagreement-as-resolution.** Diplomatic format under an ADR costume. Five sub-sections, each "name the conflict → cite ADR → declare resolved." Just delete §15.

**Honourable mention: 7 canonicalisation pin variants.** Multiple canonicalisation domains is conflation broken into more pieces.

---

## 6. Grade

**B−** (was C+).

- **+** B1 closed cleanly: 19 leaves, FORMALIS-16 + 3 ADR-justified additions. My kill list honoured 7/8.
- **+** B3 closed cleanly: L19 reclassified as view; new L19 is ClockAuthority with documented S3-carrier justification.
- **+** Vetoes V1–V14 now have falsifying predicates and CI mechanisms. "No enforcement = wish" is now the explicit ruling.
- **+** C6 collapsed from 8 leaves to 1 (better than my proposed 2). This was the single most important structural cut.
- **+** §11 Versioning Algebra, §12 Operational Floor, §10.2 detection/compensation/blast-radius, §16 ADR register — all real engineering content that was missing in v1.
- **+** ADR-10 tokenised collateral framing rejects DigitalAsset on live-CDM evidence; this is hacker-grade rigour.
- **−** B2 partially closed: enforcement is real (CI hooks), format is diplomatic (§15 performs the banned pattern under an ADR badge).
- **−** M5 unaddressed: no LoC budget anywhere. The spec is 654 lines and growing; every future addition is a free option.
- **−** L13 MoveStream still not promoted to standalone prose. The keystone leaf gets a table row.
- **−** §5 per-leaf section is still a stub pointing at specialist files. Same disease as v1.
- **−** 7 canonicalisation domains (was attacked for 5).

**Path to A:** (i) inline §5 or rename the document, (ii) state the LoC budget, (iii) delete §15 and §17, (iv) promote L13 to its own prose section, (v) cap the ADR register at ≤15 with explicit "further additions require deletion" rule, (vi) pin a single canonicalisation domain.

The bones are right now. The flesh is still committee-speak. v2 earned a B− because the structural cuts I demanded actually happened. v3 can earn an A by doing the boring work of inlining §5 and deleting the meta-layer.

**The most important sentence in v2 is still missing: "every line you keep is a line someone must read."** v2 has 654 lines defending 19 leaves. v3 should have ≤500 lines defending the same 19.

---

**End of geohot R2 review.**
