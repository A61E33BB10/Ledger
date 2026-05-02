# HALMOS R4 re-verify — deferredSettlement.tex (2129 lines)

**Verdict: PASS_WITH_CHANGES**

All five R4 findings are materially closed. One residual is cosmetic, not blocking.

## F1 — §5.3 PnL at T+1 close: CLOSED

Single canonical formula now boxed at line 550:
`V_t = w_us.own(USD) + w_us.own(XYZ)·P_t(XYZ)`. Substitution table (lines 554–559) gives `V_pre = V_T = 1,000,000.00`, `V_{T+1} = 1,000,200.00`. Headline at line 571: `PnL_{T+1} = +$200.00`. The `V_T = V_pre` equality is now stated explicitly as the fair-exchange identity (line 561). Cpty_virtual exclusion from valuation is justified before the formula, not retrofitted.

## F2 — §6.3 sell PnL: CLOSED

Same canonical formula re-boxed at line 800 with explicit cross-reference to §5.3. The long-to-flat geometry is named (line 803) and the zero PnL is honestly defended: "the firm has no economic XYZ exposure during the open window" (line 803), "PnL is genuinely zero ... because there is nothing to mark" (line 820). Footnote at line 820 redirects the short-sale +$200 case to §7 with SBL composition. No fabricated PnL.

## F3 — §11 numbering-gap note: CLOSED

Line 1875, immediately before the first `\begin{invariant}` block (DS1 at 1877): "**Note on numbering.** The numbering DS1, DS3, DS4, DS7, … reflects pruning during R3 review — DS2, DS5, DS6, DS8, and DS13–DS16 were restated v10.3 invariants moved to the appendix, and the gaps are deliberate." Confirmed: gap explained before reader hits it.

## F4 — Inline glosses for L_15, L_11, L_7^P: CLOSED at first body use

- L_15: line 166 ("data-layer leaf $L_{15}$ (the data-spec \texttt{Obligation} leaf)") and line 178.
- L_11: line 377 ("leaf $L_{11}$ (the data-spec \texttt{ExternalConfirmation} leaf)").
- L_7^P: line 379 ("$L_7^{\mathrm{P}}$ (the data-spec \texttt{PolicyConfiguration} sidecar)").

Residual: the abstract (line 51) mentions `$L_{15}$ leaf` without gloss. Cosmetic only — first body use is glossed, abstract is signposting.

## F5 — Definition 3.2 admits `inception`: CLOSED

Line 188: "Every wallet in $\mathcal{W}$ belongs to exactly one of **four** classes". The fourth class `inception` is defined at line 193 with the v10.3 §2.7 reference, and the constant universe at line 252 is now `W_real ∪ W_cpty_virtual ∪ W_csd_virtual ∪ W_inception`. WalletRegistry sidecar enum at line 212 enumerates all four. StatesHome compliance untouched.

## Halmos test summary

Notation table: present. Define-before-use: tightened on F4. Examples: every formula numerically substituted. Read-six-times: visible in F1/F2 rewrites. Implementable: yes.
