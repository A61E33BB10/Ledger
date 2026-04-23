# FORMALIS Completeness Checklist: v10.26 -> v10.3

## Version
- Source: v10.26 (6,820 lines, 167 pages)
- Target: v10.3 (7,314 lines, 177 pages)
- Delta: +494 lines, +10 pages (new subsection only; no deletions)

## 1. Content Preservation Verification

| v10.26 Section | Label | Present in v10.3 | Verified |
|---|---|---|---|
| Section 1: Introduction | `sec:intro` | YES | OK |
| Section 2: Closed Ledger System | `sec:ledger` | YES | OK |
| Section 3: Unit Store | `sec:unit-store` | YES | OK |
| Section 4: Portfolio Valuation | `sec:valuation` | YES | OK |
| Section 5: Smart Contracts | `sec:contracts` | YES | OK (+ cross-ref added) |
| Section 6: Managed Accounts | `sec:managed` | YES | OK |
| Section 7: Lifecycle Management | `sec:lifecycle` | YES | OK |
| Section 8: Balance Sheet Substantiation | `sec:substantiation` | YES | OK |
| Section 9: Implementation | `sec:implementation` | YES | OK |
| Section 10: Settlement Layer | `sec:settlement` | YES | OK |
| Section 11: CDM Integration | `sec:cdm` | YES | OK |
| Section 12: Invariants | `sec:invariants` | YES | OK |
| Section 13: Regulatory | `sec:regulatory` | YES | OK |
| Section 14: Temporal.io | `sec:temporal` | YES | OK (+ cross-ref added) |
| Section 15: GPM and SBL | `sec:gpm` | YES | OK |
| Section 16: Scope and Limitations | `sec:scope-limitations` | YES | OK |
| Section 17: Conclusion | `sec:conclusion` | YES | OK |
| Section 18: FAQ | `sec:faq` | YES | OK |
| Appendix A: CDM Type Mapping | - | YES | OK |
| Appendix B: Property Test Catalogue | - | YES | OK |
| Appendix C: Reconciliation Taxonomy | - | YES | OK |
| Appendix D: Pricing Coordination | - | YES | OK |
| Appendix E: Glossary | - | YES | OK |
| Appendix F: CDM Developer's Guide | `app:cdm-walkthrough` | YES | OK |
| - Layer 1-6 walkthrough | - | YES | OK |
| - Mapping table | - | YES | OK |
| - Structured note example | `sec:cdm-structured-note` | YES | OK |
| - Tokenized securities | `sec:cdm-tokenized` | YES | OK |
| **NEW: Date Handling** | `sec:cdm-dates` | YES | **NEW** |
| Appendix G: Inventory Verification | `app:invariant-verification` | YES | OK |
| Appendix H: EU SBL Example | `app:eu-sbl-example` | YES | OK |
| Appendix I: US SBL Example | - | YES | OK |

## 2. Changes Made (exhaustive list)

### 2a. Version string
- Line 41: `v10.26` -> `v10.3`

### 2b. New subsection inserted
- Location: After tokenized securities subsection (was line 5732-5735 in v10.26), before Appendix G (Available Inventory)
- Label: `sec:cdm-dates`
- Title: "Date Handling in CDM: Types, Conventions, and Schedule Generation"
- Content: 494 lines of new material

### 2c. Cross-references added (two locations)
1. **Section 5 (IRS move schedule)**: Added parenthetical "(see Section X for CDM date types and day count conventions)" to the day count fraction bullet point
2. **Section 14 (Bond Coupon Payments)**: Added sentence about CDM date adjustment machinery with reference to `sec:cdm-dates`

### 2d. No deletions
- Zero lines removed from v10.26 content
- All existing labels, cross-references, and content preserved verbatim

## 3. New Section Content Verification

### Part 1: Type Taxonomy
- [x] `date` primitive explained
- [x] `Period` with Rosetta source and condition
- [x] `Offset` extending Period, with DayTypeEnum
- [x] `BusinessDayConventionEnum` full listing (FOLLOWING, MODFOLLOWING, PRECEDING, MODPRECEDING, FRN, NEAREST, NONE, NotApplicable)
- [x] `BusinessCenters` with choice condition
- [x] `BusinessDayAdjustments` combining convention + centres
- [x] `AdjustableDate` with metadata key, choice condition
- [x] `RelativeDateOffset` extending Offset
- [x] `AdjustableOrRelativeDate` with required choice condition
- [x] `CalculationPeriodFrequency` extending Frequency, with RollConventionEnum and FpML validation rules
- [x] `RollConventionEnum` listing (EOM, FRN, IMM, _1.._30, MON..SUN, etc.)
- [x] `DayCountFractionEnum` full listing (14 values)
- [x] `YearFraction` dispatched function shown (ACT/360 and 30/360 formula)
- [x] `DateRange`, `DateList` container types
- [x] Resolution functions: `ResolveAdjustableDate`, `AddBusinessDays`, `IsBusinessDay`
- [x] Resolution chain: 3-step process explained

### Part 2: Worked Examples
- [x] Example 1: 5Y USD SOFR IRS
  - [x] Effective date as RelativeDateOffset (T+2 USNY)
  - [x] Fixed leg CalculationPeriodFrequency (6M, roll day 3)
  - [x] Floating leg CalculationPeriodFrequency (3M, roll day 3)
  - [x] Termination date as AdjustableDate
  - [x] Generated schedule table (10 payment dates with adjustments)
  - [x] Year fraction computation (30/360 and ACT/360)
  - [x] Connection to IRS move schedule in Section 5
- [x] Example 2: NVDA American equity option
  - [x] Expiry as AdjustableDate (NONE convention, exchange rules)
  - [x] Settlement as RelativeDateOffset (T+1 ExchangeBusiness)
  - [x] DayTypeEnum -> ExchangeBusiness explained
- [x] Gotchas list (6 items):
  1. Omitting business centres
  2. Calendar vs business days
  3. End-of-month roll convention
  4. Multi-calendar intersection (joint holiday)
  5. Stub periods
  6. 30/360 vs ACT/360 ($11,111 error on $50M)

### Part 3: Cross-references
- [x] From IRS move schedule (Section 5) -> sec:cdm-dates
- [x] From Bond Coupon Payments (Section 14) -> sec:cdm-dates
- [x] Internal: sec:cdm-dates references sec:contracts, sec:temporal-scheduler, sec:settlement

## 4. Compilation Results

- **Errors**: 0
- **Undefined references**: 0
- **Warnings**: 6 (all pre-existing font shape warnings for T1/cmr/m/scit)
- **Page count**: 177 pages (was 167 in v10.26)
- **Three passes**: stable (no rerun needed)

## 5. Source Verification

All Rosetta type definitions and enum values were extracted from the actual CDM source files:
- `base-datetime-type.rosetta` — types: AdjustableDate, RelativeDateOffset, AdjustableOrRelativeDate, BusinessDayAdjustments, BusinessCenters, Period, Offset, CalculationPeriodFrequency, DateRange, DateList, PeriodicDates
- `base-datetime-enum.rosetta` — enums: BusinessDayConventionEnum, BusinessCenterEnum, DayTypeEnum, PeriodEnum, PeriodExtendedEnum, RollConventionEnum
- `base-datetime-func.rosetta` — functions: ResolveAdjustableDate, AddBusinessDays, IsBusinessDay, IsHoliday, IsWeekend, BusinessCenterHolidaysMultiple, AddDays, DateDifference
- `base-datetime-daycount-enum.rosetta` — enum: DayCountFractionEnum (14 values)
- `base-datetime-daycount-func.rosetta` — functions: YearFraction dispatched implementations, DayCountBasis

No type names, field names, cardinalities, or conditions were invented. All match the source files at `/home/renaud/A61E33BB10/ISDA/common-domain-model/rosetta-source/src/main/rosetta/`.

## Verdict: PASS

All v10.26 content is preserved. The new subsection is correctly inserted within Appendix F after the tokenized securities subsection. Cross-references are bidirectional. Compilation is clean.
