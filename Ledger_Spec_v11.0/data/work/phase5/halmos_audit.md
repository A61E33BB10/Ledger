# HALMOS Audit Report — `ledger_data_v1.0.tex`

**Auditor:** HALMOS (Phase 5 Round 1)
**Document:** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/data/ledger_data_v1.0.tex`
**Lines:** 1,660. **PDF:** 49 pages. **Date:** 2026-04-30.
**Verdict:** **CONDITIONAL — three blockers, ship-after-fix**

---

## 1. File-Level Counts (Task 3)

| Check | Required | Actual | Pass |
|---|---|---|---|
| `\begin{theorem}`         | 6  | 6  | YES |
| `\begin{proposition}`     | 15 | 15 | YES |
| `\begin{definition}`      | ≥19| 23 | YES |
| `\section{...}`           | 19 | 19 | YES |
| Bibliography present      | yes| yes| YES |
| Glossary entries          | —  | 34 | OK  |

All mechanical counts pass.

---

## 2. CRITICAL Findings (Blockers)

### CRIT-1. Notation collision: `$C_n$` overloaded across two distinct families

The §2.1 prefix table promises `$C_n$` denotes the **StatesHome structural index** ($n=1,\ldots,12$, per the Ledger).
In §2.3 (line 170) and throughout (e.g. line 447 "(StatesHome $C_2$)"), `$C_n$` is used in this StatesHome sense.

But §3.2 (lines 207–214) and the §3.3 catalogue table (lines 231–249) introduce a **second, incompatible** family also called `$C_n$`: the six **mutation-discipline classes** `$C_1$ Definitions, $C_2$ Shared Status, $C_3$ Per-Position State, $C_4$ Observations, $C_5$ Effects, $C_6$ Provenance`.

The collision is direct:
- `$C_1$` = (a) StatesHome "monotone-carrier", (b) mutation class "Definitions" (members L1, L2, L3, L4, L7P, L8, L19).
- `$C_2$` = (a) StatesHome "per-class structural sum=0", (b) mutation class "Shared Status" (member L5 only).
- `$C_4$` = (a) StatesHome "capability-scoped reads", (b) mutation class "Observations" (members L9–L12).

The `$C_2$` clash is especially confusing on line 447, where the well-formedness predicate of L_{13} cites "(StatesHome $C_2$)" meaning the structural sum index, but L_{13} is itself in mutation class $C_5$, not $C_2$. The prefix table at line 132 lists only the StatesHome meaning; the mutation-class meaning of $C_n$ is **not** declared in §2.1. **HALMOS Principle 4 violation (notation design).**

**Fix:** rename mutation classes to e.g. `$\mathcal{D}_1, \ldots, \mathcal{D}_6$` (Discipline class) or `$\mathrm{Cls}_n$`, and update the §3.2 catalogue table column "Class". Add the new prefix to §2.1.

**Severity:** CRITICAL. The reader cannot follow the body without disambiguating two meanings of $C_2$.

### CRIT-2. Phantom leaves $L_{20}$ and $L_{21}$ used without ever being defined

§2.1 states `$L_n$` ranges over $n=1,\ldots,19$. The taxonomy in §3.3 enumerates exactly nineteen leaves. Yet the body uses `$L_{20}$` and `$L_{21}$` in load-bearing positions:

- Line 198 (taxonomy intro): "the version pin $L_{21}$" — an aside introducing $L_{21}$ in a parenthetical without ever defining it.
- Line 994 ($U_5$ unconditional guarantee): "Idempotency on $L_{20}$-tokened payloads" — the very name of an unconditional guarantee.
- Line 1020 (C-A_5 row): "Version-pin freeze; $L_{21}$ axis update".
- Line 1103 (CDM cross-walk): "Rule-set version pinned per $L_{21}$ axis".
- Line 1365 (lineage cursor): "$L_{13} \oplus L_{12} \oplus \ldots \oplus L_{21} \oplus \text{capabilities}$".
- Line 1536 (ADR-6 row): "$L_{21}$ / $B_{10}$".

Additionally, line 509 ($L_{17}$ workflow): "rule-set version is L21-pinned" — bare `L21` (not even math-italic), worse.

A reader scanning §2.1 and the catalogue learns there are only 19 leaves; encountering $L_{20}, L_{21}$ in normative positions is a gross HALMOS Rule 5 violation (define before use) and a structural inconsistency. From context $L_{20}$ is the idempotency-token sidecar and $L_{21}$ is the version-pin sidecar, both promised in the §3.1 sentence "relegated to a versioned sidecar (the policy partition $L_7^{\mathrm{P}}$, the version pin $L_{21}$)" — but this is an aside, not a definition, and $L_{20}$ has no such mention.

**Fix:** either (i) extend the taxonomy to 21 leaves with proper §4.x sub-sections for $L_{20}$ and $L_{21}$ (and update §2.1, the abstract, the §3.3 catalogue, the §3.4 collapse table to match), or (ii) demote $L_{20}/L_{21}$ to non-leaf sidecar names and rename them throughout (e.g. `IdempotencyTokenSidecar`, `VersionPinSidecar`). Option (ii) is consistent with the §3.4 collapse statement that IdempotencyToken was "Folded as field". Recommend **option (ii)** plus rewording every `L_{20}/L_{21}` mention to use the sidecar's word-name.

**Severity:** CRITICAL. The taxonomy explicitly closes at 19; using $L_{20}, L_{21}$ undermines the central count.

### CRIT-3. The `$N_n$` data-quality family is announced but never defined

§2.1 (line 127) declares "`$N_n$` Minimum data-quality requirement". No section ever enumerates the $N$-list, and no $N$-table appears. Yet the body uses:

- `$N_8$` (line 326, $L_2$ well-formedness; line 1018, C-A_3 row),
- `$N_{12}$` (line 1017, C-A_2 compensation),
- `$N_{8.2}$` (line 1539, ADR-9), and
- `$N_{\mathrm{handler}}$` (line 767, line 895, line 897, line 1587 — the obligation-liveness bound).

Note the conflation: `$N_8$` (numeric) vs `$N_{\mathrm{handler}}$` (word-subscripted) appear to be two entirely different families that the prefix table cannot disambiguate. `$N_{\mathrm{handler}}$` is the handler-delay bound from Theorem 3 (Obligation Liveness); `$N_8$` is a multi-vendor reconciliation gate; they share notation but not meaning.

Additionally line 239 in the catalogue table ("$L_9$ Bitemporal stream with **N8 aggregation gate**") writes the symbol bare, not in math.

**Fix:** add a §2.x table enumerating the $N_n$ minimum-data-quality requirements (at minimum $N_8$ multi-vendor consensus and $N_{12}$ HSM kill-switch). Rename `$N_{\mathrm{handler}}$` to a non-conflicting symbol such as `$\delta_{\mathrm{handler}}$` or `$\tau_{\mathrm{h}}$`. Resolve `$N_{8.2}$` as either an $N_8$ sub-clause with explicit name or a typo for $N_{8b}$.

**Severity:** CRITICAL. Theorem 3 statement uses an undefined symbol.

---

## 3. HIGH-Severity Findings

### HIGH-1. $L_{16}$ ReferenceMaster is structurally underspecified

§4 promises eight uniform fields per leaf: (a) carrier+well-formedness, (b) type design, (c) workflow shape, (d) CDM cross-walk, (e) invariants $\Phi$, (f) laws $\Lambda$, (g) reconciliation pair, (h) realism anchor. Counts across the document show 18 of 19 leaves provide all eight; **$L_{16}$ provides only (a) and a handwave "Notes" paragraph**.

§4.20 (lines 493–500) gives:
- (a) Definition: yes (3-line carrier).
- (b) Type design: missing.
- (c) Workflow shape: missing.
- (d) CDM cross-walk: present in Notes but not in the §4-template format.
- (e) $\Phi$ invariants: **none** (the only leaf without a single $\Phi$).
- (f) $\Lambda$ laws: missing.
- (g) Reconciliation pair: text says "follow the pattern of $L_3$" — not concrete.
- (h) Realism anchor: missing.

Line 500 also contains the dangling reference "matthias\_v2 \S B" (see HIGH-3).

**Fix:** rewrite §4.20 to the §4-template, or split $L_{16}$ into per-table sub-sections with the eight fields per sub-table.

**Severity:** HIGH. The taxonomy claim "every leaf has uniform fields" is falsified by $L_{16}$.

### HIGH-2. `Th-4` referenced after the document explicitly splits it into `Th-4a` and `Th-4b`

§2.1 (line 121): "$\mathrm{Th}\textrm{-}n$ Compositional theorem ($n=1,\ldots,6$, with $\mathrm{Th}\textrm{-}4$ split into $4a$, $4b$)" — explicit notation discipline.
§7 splits Theorem 4 into Th-4a (Substantiation Definition, line 904) and Th-4b (Cache Coherence, line 912).

But §10 Table~\ref{tab:cdm-strategic} row 1 (line 1060) writes "Th-1 / Th-2 / **Th-4** share dependency" — bare Th-4.

**Fix:** replace bare Th-4 with the appropriate Th-4a or Th-4b (Th-4b given the cache-coherence dependency context).

**Severity:** HIGH. Inconsistent with self-declared notation.

### HIGH-3. Three dangling cross-document references not resolvable from the published document

The document repeatedly cites named external/sibling files that are not in the bibliography and not promised in scope:

- Line 296 (§4 intro): "Deeper drilling into each leaf is in **the specialist files cited in the source register**" — no source register is in this document.
- Line 500 ($L_{16}$ Notes): "each table inside $L_{16}$ has its own per-table cross-walk in **matthias\_v2 \S B**".
- Line 974 (§7 DAG): "The full graph is in **formalis\_v2 \S 6.0**".

These appear to be Phase-2/3 working-paper names that survived into the v1.0 deliverable. A reader of v1.0 alone cannot resolve them; HALMOS Principle 6 (read-six-times) has not eliminated them.

**Fix:** for each reference, either (i) inline the content needed to make this document self-sufficient, or (ii) replace with a stable bibliography entry (`\bibitem`) and add the corresponding `\cite{...}`.

**Severity:** HIGH. Self-sufficiency of the published document is broken.

---

## 4. MEDIUM-Severity Findings

### MED-1. Sentences in `\begin{definition}` bodies start with `$L_n$`

Every per-leaf definition body opens with the symbol — line 302 `$L_1$ is a map keyed by ...`, line 326 `$L_2$ is a bitemporal map ...`, etc. (lines 302, 326, 335, 344, 353, 362, 371, 385, 394, 403, 422, 431, 447, 456, 476, 497, 506, 515, 528). **HALMOS Rule 2 violation** ("Never start a sentence with a symbol").

The bracket title `[$L_1$ Carrier and well-formedness]` partially mitigates this in printed form, but Halmos's rule applies to the body sentence itself.

**Fix:** open with "The leaf $L_1$ is a map ..." or "Carrier: $L_1$ is the map ...". One-word prefix per definition.

**Severity:** MEDIUM. Style infraction, not a comprehension blocker, but hits the Halmos Test directly.

### MED-2. Glossary missing several load-bearing technical terms

Glossary has 34 entries. Body uses without defining: **GADT** (lines 434, 680, 1494; load-bearing — Th-5 witness type), **Datalog** (line 1365 — implementation hint for lineage cursor), **Buggify** (line 1387 — chaos test method), **mutmut** / **cosmic-ray** (line 1386), **Hamiltonian Monte Carlo** (line 762 — the $\Lambda_{12}$ sampler).

**GLEIF, AcadiaSoft, triResolve, Heston** are commercial / industry names whose absence from the glossary is borderline acceptable, but a reader without industry context is helped.

**Fix:** add at minimum **GADT** and **Datalog** to the glossary; consider adding **HMC**, **Buggify**, **mutmut**.

**Severity:** MEDIUM. HALMOS Test #4 (every term defined before use): partial fail.

### MED-3. `$L_{18}$ BreakRegister` reconciliation pair is a reference-only stub

Line 522 ($L_{18}$): "Reconciliation pair. Per-leaf reconciliation cadence (cf. Table~\ref{tab:reconciliation})". Looking at Table~\ref{tab:reconciliation} (lines 1162–1175), there is **no row for $L_{18}$** — the table ends at $L_{17}$. So the reference is dangling: $L_{18}$ has no reconciliation pair declared anywhere, contradicting §4's promise of (g) per leaf.

**Fix:** either add a row for $L_{18}$ to the reconciliation matrix, or state explicitly "internal break (no external reconciliation source applicable)" with a justification.

**Severity:** MEDIUM. Halmos completeness check fails for one leaf.

### MED-4. `$L_7^{\mathrm{P}}$` workflow shape and reconciliation pair use non-template prose

Lines 379 ($L_7^{\mathrm{P}}$): the `\paragraph{Bootstrap.}` precedes the `\textbf{Workflow shape.}` block. The eight-field §4 template names "Bootstrap" nowhere; this is an additional ad-hoc field. Minor.

**Fix:** either fold "Bootstrap" into the §4 template (as field (i)) or move the bootstrap material into the Type Design or Workflow Shape paragraphs.

**Severity:** MEDIUM-LOW. Cosmetic but breaks template uniformity.

### MED-5. `realism budget axiom RB-3` mentioned in proof of Theorem 3 but never tabled

Line 901 (Theorem 3 proof): "the unbounded variant is reclassified as realism-budget axiom RB-3 (cf.~$\Lambda_{13}$)". §9 (Realism Budget) tables U_1..U_8 and C-A_1..C-A_13; there is no `RB-n` family. The §2.1 prefix table does not list `RB-`.

**Fix:** rename to the appropriate `C-A_n` (likely C-A_? for unbounded-horizon assumption) or add an `RB-` family to the §2.1 prefix table.

**Severity:** MEDIUM. A theorem proof appeals to an unindexed object.

---

## 5. LOW-Severity Findings

- **LOW-1.** Line 239 (catalogue table $L_9$): "with N8 aggregation gate" — bare alphanumeric, not `$N_8$`. Inconsistent with rest of document.
- **LOW-2.** Line 509 ($L_{17}$): "rule-set version is L21-pinned" — bare `L21`, not `$L_{21}$`. Compounds CRIT-2.
- **LOW-3.** Line 1227: "The policy is L21-pinned per kind" — same bare-alphanumeric issue.
- **LOW-4.** Line 165 (def of bitemporal modes): the phrase "Both modes are first-class" reads cleanly but the prior sentence "Neither mode is derivable from the other" is followed without a connector — minor flow issue.
- **LOW-5.** Lambda_1 footer line 780: "of the fifteen laws, eleven are witnessed directly, three ... are witnessed via composition ... and one ... is genuinely unwitnessed" — count is 11 + 3 + 1 = 15. OK. But text says "$\Lambda_4$, $\Lambda_8$, $\Lambda_{13}$" are the three composition-witnessed; matches §6 declarations. OK.
- **LOW-6.** Line 1387: `\texttt{temporal-test-server} + Buggify` — Buggify is FoundationDB's tool, not Temporal's. Not wrong but potentially confusing in context.

---

## 6. Completeness Audit (Task 2)

### 6.1 Nineteen-Leaf Taxonomy

The 19 leaves match Phase 2 v3 §4.4 exactly:

| Leaf | Defined §1/§3 | Class C1-C6 | CDM cross-walk | Workflow / ingress | Recon pair |
|---|---|---|---|---|---|
| L1 ProductTerms | YES (line 301) | C1 | YES | YES | YES |
| L2 InstrumentMaster | YES (325) | C1 | YES | YES | YES |
| L3 PartyLEI | YES (334) | C1 | YES | YES | YES |
| L4 CalendarConvention | YES (343) | C1 | YES | YES | YES |
| L5 UnitStatus | YES (352) | C2 | YES | YES | YES |
| L6 PositionState | YES (361) | C3 | YES | YES | YES |
| L7P PolicyConfiguration | YES (370) | C1 | YES | YES | YES |
| L8 LegalAgreement | YES (384) | C1 | YES | YES | YES |
| L9 RawMarketObservation | YES (393) | C4 | YES | YES | YES |
| L10 LifecycleOracle | YES (402) | C4 | YES | YES | YES |
| L11 ExternalConfirmation | YES (421) | C4 | YES | YES | YES |
| L12 CalibratedMarketObject | YES (430) | C4 | YES | YES | YES |
| L13 MoveStream | YES (446) | C5 | YES | YES | YES |
| L14 ValuationRecord | YES (455) | C5 | YES | YES | YES |
| L15 Obligation | YES (475) | C5 | YES | YES | YES |
| L16 ReferenceMaster | partial (496) | C6 | partial | **MISSING** | "follow L3 pattern" (vague) |
| L17 RegulatorySubmission | YES (505) | C5 | YES | YES | YES |
| L18 BreakRegister | YES (514) | C5 | YES | YES | **MISSING from table** (HIGH-1, MED-3) |
| L19 ClockAuthority | YES (527) | C1 | YES | YES | YES |

**Material gap:** $L_{16}$ underspecified (HIGH-1); $L_{18}$ reconciliation row missing from Table~\ref{tab:reconciliation} (MED-3).

### 6.2 Indexed Families

| Family | Promised | Found | Pass |
|---|---|---|---|
| Th-1..Th-6 (with Th-4 split into 4a/4b) | 7 environments | 6 theorems + 1 definition (Th-4a is `Balance-Sheet Projection` definition) | YES |
| $\Lambda_1..\Lambda_{15}$ | 15 propositions | 15 | YES |
| $B_1..B_{17}$ | 17 boundaries | 17 (table row count) | YES |
| C-A_1..C-A_{13} | 13 conditional assumptions | 13 (table row count) | YES |
| $V_1..V_{14}$ | 14 vetoes | 14 (table row count) | YES |
| $\mathrm{GT}_1..\mathrm{GT}_5$ | 5 Goodhart traps | 5 (table row count) | YES |
| ADR-1..ADR-12 | 12 ADRs | 12 (table row count) | YES |
| $U_1..U_8$ | 8 unconditional | 8 | YES |
| $P_1..P_{10}$ | 10 principles | 10 | YES |

All indexed families are present at correct cardinality.

### 6.3 Theorem dependency chain

§7.7 (line 974) names nine axioms `A-$\Lambda_n$`, five lemmas `Lm-$\Lambda_n$`, seven theorems. Names are introduced as one-shot in this paragraph and never elaborated; the "full graph is in formalis\_v2 \S 6.0" — see HIGH-3 (dangling reference).

---

## 7. Halmos Test Summary

| Test | Result |
|---|---|
| Notation table exists, designed in advance | PARTIAL (CRIT-1, CRIT-3) |
| Define before use | FAIL (CRIT-2 L_{20}/L_{21}, CRIT-3 N_n, MED-2 GADT/Datalog, MED-5 RB-3) |
| Examples for every definition | YES (worked restatement at line 562 etc.) |
| Structure apparent from TOC | YES |
| Read six times | NO (dangling refs to working papers, sentence-starts violations) |
| Implementable from this document alone | NO (HIGH-3, dangling specialist files) |

**Halmos verdict:** the document is 90% there but fails the self-sufficiency test on three named axes.

---

## 8. Verdict

**CONDITIONAL — three blockers (CRIT-1, CRIT-2, CRIT-3) must be fixed before ship; one HIGH (HIGH-1, $L_{16}$) and one HIGH (HIGH-3, dangling refs) must also be addressed.**

Counts by severity:
- CRITICAL: 3
- HIGH: 3
- MEDIUM: 5
- LOW: 6

Top three issues to fix first:
1. **CRIT-1** Notation collision $C_n$ (mutation class vs StatesHome index) — affects readability of every per-leaf section and every well-formedness predicate.
2. **CRIT-2** Phantom leaves $L_{20}, L_{21}$ used in load-bearing positions (an unconditional guarantee, an ADR, a CDM cross-walk row) without ever being defined; contradicts the central "nineteen leaves" claim.
3. **CRIT-3** $N_n$ data-quality family announced in §2.1 but never tabled; conflated with $N_{\mathrm{handler}}$ (different family); a theorem proof appeals to an undefined symbol.

After these are fixed (and HIGH-1 / HIGH-3 addressed), a v1.1 ships cleanly. The skeleton, the indexed families, the proofs, and the operational floor matrices are sound.

---

*Audit performed against `ledger_data_v1.0.tex` SHA at 2026-04-30 20:30 (1660 lines, 132,951 bytes).*
