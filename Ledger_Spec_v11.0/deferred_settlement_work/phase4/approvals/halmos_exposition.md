# HALMOS exposition pass — `deferredSettlement.tex` v1.0

**Reviewer:** HALMOS (Phase-4 exposition gate)
**Artefact:** `/home/renaud/A61E33BB10/Ledger_Spec_v11.0/deferredSettlement.tex` (2,151 lines)
**Author:** R. Delloye (KARPATHY sole-authorial Phase-3 deliverable)
**Date:** 2026-05-02

## Verdict: PASS_WITH_CHANGES

The document satisfies the HALMOS hierarchy on form: notation table designed in advance (Defs 3.1–3.3 + glossary §13), structure apparent from TOC, every definition followed by an example (worked buy §5, sell §6), conservation tables sum to zero in print at every step (Tables 5.2, 5.3, 6.1, 5.5, 5.6), nineteen named invariants with severity. Three clarity tests pass: engineer can build (§10), auditor can check (§8.3 five-document chain), risk manager can answer T+1 (boxed formula §5.3 line 574). One load-bearing section is hand-waved and must be rewritten; four smaller findings are remediable in one editing pass.

## Findings (≤5, by descending severity)

### F1 — CRITICAL (§5.3, "PnL at T+1 close", lines 545–589)
The PnL derivation is the single load-bearing numerical claim of the document and it is **not worked**. The text presents three formulas yielding three different $V_{T+1}$ values ($1{,}000{,}400$ then $1{,}000{,}200$ then $995{,}200$), declares one "correct" after the fact, then recovers the headline number via prose ("Adding the \$5{,}000 back gives…"). The asymmetric rule — XYZ-receivable held at mark, USD-payable held at face — is asserted, not derived. **Required fix:** state the valuation rule before the computation, derive each $V$ in one continuous block, let the boxed formula stand alone. F2 follows from this fix.

### F2 — HIGH (§6.3 sell PnL, lines 813–838)
The sell uses the un-disciplined formula §5.3 has just rejected (line 815) and recovers the right answer by sign cancellation. Two pages later the buy and sell ostensibly use "the same algebra"; in fact they use different formulas. Standardise on the boxed §5.3 form for both directions.

### F3 — MEDIUM (§11 invariant numbering, line 1897)
The numbering DS1, DS3, DS4, DS7, DS9, DS10, DS11a/b, DS12, DS17–DS19 has unannounced gaps; the reader reaches §11 with no warning. Gaps are explained on lines 2000–2008 but only after the body. **Fix:** one sentence at the top of §11 ("Twelve primary invariants below; seven restated v10.3 invariants by reference at section end") before the first `\begin{invariant}`.

### F4 — MEDIUM (Symbol-before-definition: $L_{15}$, $L_{11}$, $L_7^{\mathrm{P}}$)
$L_{15}$ first appears in the abstract (line 51) and recurs six times in §1–§3 before its role is unpacked. The glossary entry $L_n$ (line 2086) defines it; on first read the symbol is opaque. **Fix:** at first use, parenthesise once — "the data layer's obligation leaf $L_{15}$" — and likewise for $L_{11}$ and $L_7^{\mathrm{P}}$.

### F5 — LOW (§5.1 Table 5.1: undeclared `inception` wallet class)
Table 5.1 (line 441) introduces a fourth wallet class `inception` ($w_{\mathrm{genesis\_inception}}$) which Definition 3.2 (line 187) does not admit — Def 3.2 closes on three classes. **Fix:** either widen Def 3.2 to four classes (preferred — the v10.3 §2.7 baseline is canonical) or strike the row from Table 5.1 with a v10.3 cite in the caption.

## Sign-off

HALMOS test: 9/11. The two failures concentrate in §5.3 with echo in §6.3. The remainder is publishable as written. Block sign-off until F1+F2 land (≈2 hours of editing); F3–F5 clear in the same pass. A revised §5.3 with a single derived boxed formula lifts the verdict to PASS without further review.

— HALMOS
