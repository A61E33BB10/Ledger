"""
margin_loan.py - Margin Loan Units for Secured Lending

This module provides margin loan unit creation and lifecycle processing using
a pure function architecture with explicit inputs.

ARCHITECTURE (Pure Function Pattern):
=====================================

1. FROZEN DATACLASSES (explicit inputs):
   - MarginLoanTerms: Immutable term sheet (set at creation, never changes)
   - MarginLoanState: Immutable state snapshot (changes over lifecycle)

2. PURE CALCULATION FUNCTIONS (calculate_*):
   - Take all inputs explicitly as parameters
   - No LedgerView, no hidden state
   - Trivially testable, stress-testable
   - Example: calculate_collateral_value(collateral, prices, haircuts) -> float

3. ADAPTER FUNCTIONS (load_margin_loan):
   - Extract state from LedgerView once
   - Convert to typed frozen dataclasses
   - The ONLY place that touches LedgerView for reads

4. CONVENIENCE FUNCTIONS (compute_*):
   - Combine loading + pure calculation + result building
   - Take (view, symbol, ...) for API flexibility
   - Internally call load_margin_loan() then calculate_*()

Key Formulas:
    collateral_value = sum(quantity * price * haircut for each asset)
    total_debt = loan_amount + accrued_interest
    margin_ratio = collateral_value / total_debt
    shortfall = maintenance_margin * total_debt - collateral_value (if ratio < maintenance)
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple, Mapping

from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange,
    QUANTITY_EPSILON, UNIT_TYPE_MARGIN_LOAN,
    build_transaction, empty_pending_transaction,
    _freeze_state,
)


# Type aliases
CollateralPool = Dict[str, Decimal]  # asset_symbol -> quantity
HaircutSchedule = Dict[str, Decimal]  # asset_symbol -> haircut (0-1, where 1=full credit)
PriceDict = Dict[str, Decimal]  # asset_symbol -> price


# Margin status constants
MARGIN_STATUS_HEALTHY = "HEALTHY"
MARGIN_STATUS_WARNING = "WARNING"
MARGIN_STATUS_BREACH = "BREACH"
MARGIN_STATUS_LIQUIDATION = "LIQUIDATION"


# ============================================================================
# FROZEN DATACLASSES - Explicit Inputs for Pure Functions
# ============================================================================

@dataclass(frozen=True, slots=True)
class MarginLoanTerms:
    """
    Immutable term sheet for a margin loan - set at creation, never changes.

    This dataclass captures everything from the loan agreement that is fixed
    at origination. These values define the contract but do not change over
    the loan's lifecycle.

    All fields are explicit - no hidden state. Pure functions take this
    as a parameter, making all dependencies visible in the function signature.
    """
    interest_rate: Decimal        # Annual interest rate (e.g., 0.08 for 8%)
    initial_margin: Decimal       # Required margin at origination (e.g., 1.5 for 150%)
    maintenance_margin: Decimal   # Required margin to avoid calls (e.g., 1.25 for 125%)
    haircuts: Mapping[str, Decimal]  # asset -> haircut factor (0-1, where 1=full credit)
    margin_call_deadline_days: int  # Days to cure a margin call
    currency: str               # Settlement currency
    borrower_wallet: str        # Who owes the debt
    lender_wallet: str          # Who is owed

    def __post_init__(self):
        """Convert float values to Decimal to ensure type consistency."""
        # Convert Decimal fields that might be passed as float
        if not isinstance(self.interest_rate, Decimal):
            object.__setattr__(self, 'interest_rate', Decimal(str(self.interest_rate)))
        if not isinstance(self.initial_margin, Decimal):
            object.__setattr__(self, 'initial_margin', Decimal(str(self.initial_margin)))
        if not isinstance(self.maintenance_margin, Decimal):
            object.__setattr__(self, 'maintenance_margin', Decimal(str(self.maintenance_margin)))

        # Convert haircuts dict values to Decimal
        needs_conversion = False
        for k, v in self.haircuts.items():
            if not isinstance(v, Decimal):
                needs_conversion = True
                break

        if needs_conversion:
            haircuts_converted = {}
            for k, v in self.haircuts.items():
                haircuts_converted[k] = v if isinstance(v, Decimal) else Decimal(str(v))
            object.__setattr__(self, 'haircuts', haircuts_converted)


@dataclass(frozen=True, slots=True)
class MarginLoanState:
    """
    Immutable snapshot of margin loan lifecycle state at a point in time.

    This dataclass captures everything that changes over the loan's lifecycle.
    Each state change creates a NEW instance (value semantics).

    Combined with MarginLoanTerms, this provides all inputs needed for any
    margin loan calculation - no hidden state, no LedgerView queries.
    """
    loan_amount: Decimal               # Current outstanding principal (reduces with payments)
    collateral: Mapping[str, Decimal]  # asset -> quantity pledged
    accrued_interest: Decimal          # Accumulated unpaid interest
    last_accrual_date: Optional[datetime]  # When interest was last calculated
    margin_call_amount: Decimal        # Amount needed to cure (0 if none)
    margin_call_deadline: Optional[datetime]  # Deadline to cure
    liquidated: bool                 # Whether loan has been liquidated
    origination_date: Optional[datetime]  # When loan was created
    total_interest_paid: Decimal       # Cumulative interest paid
    total_principal_paid: Decimal      # Cumulative principal paid
    # Liquidation details (only set after liquidation)
    liquidation_date: Optional[datetime] = None
    liquidation_proceeds: Optional[Decimal] = None
    liquidation_deficiency: Optional[Decimal] = None

    def __post_init__(self):
        """Convert float values to Decimal to ensure type consistency."""
        # Convert Decimal fields that might be passed as float
        if not isinstance(self.loan_amount, Decimal):
            object.__setattr__(self, 'loan_amount', Decimal(str(self.loan_amount)))
        if not isinstance(self.accrued_interest, Decimal):
            object.__setattr__(self, 'accrued_interest', Decimal(str(self.accrued_interest)))
        if not isinstance(self.margin_call_amount, Decimal):
            object.__setattr__(self, 'margin_call_amount', Decimal(str(self.margin_call_amount)))
        if not isinstance(self.total_interest_paid, Decimal):
            object.__setattr__(self, 'total_interest_paid', Decimal(str(self.total_interest_paid)))
        if not isinstance(self.total_principal_paid, Decimal):
            object.__setattr__(self, 'total_principal_paid', Decimal(str(self.total_principal_paid)))

        # Convert optional Decimal fields
        if self.liquidation_proceeds is not None and not isinstance(self.liquidation_proceeds, Decimal):
            object.__setattr__(self, 'liquidation_proceeds', Decimal(str(self.liquidation_proceeds)))
        if self.liquidation_deficiency is not None and not isinstance(self.liquidation_deficiency, Decimal):
            object.__setattr__(self, 'liquidation_deficiency', Decimal(str(self.liquidation_deficiency)))

        # Convert collateral dict values to Decimal
        needs_conversion = False
        for k, v in self.collateral.items():
            if not isinstance(v, Decimal):
                needs_conversion = True
                break

        if needs_conversion:
            collateral_converted = {}
            for k, v in self.collateral.items():
                collateral_converted[k] = v if isinstance(v, Decimal) else Decimal(str(v))
            object.__setattr__(self, 'collateral', collateral_converted)


@dataclass(frozen=True, slots=True)
class MarginStatusResult:
    """
    Immutable result of margin status calculation.

    Contains all outputs from assess_margin() in a typed, frozen structure.
    No Dict[str, Any] - all fields are explicit and typed.
    """
    collateral_value: Decimal
    total_debt: Decimal
    margin_ratio: Decimal
    initial_margin: Decimal
    maintenance_margin: Decimal
    status: str  # HEALTHY, WARNING, BREACH, LIQUIDATION
    shortfall: Decimal
    excess: Decimal
    pending_interest: Decimal

    def __post_init__(self):
        """Convert float values to Decimal to ensure type consistency."""
        # Convert Decimal fields that might be passed as float
        if not isinstance(self.collateral_value, Decimal):
            object.__setattr__(self, 'collateral_value', Decimal(str(self.collateral_value)))
        if not isinstance(self.total_debt, Decimal):
            object.__setattr__(self, 'total_debt', Decimal(str(self.total_debt)))
        if not isinstance(self.margin_ratio, Decimal):
            object.__setattr__(self, 'margin_ratio', Decimal(str(self.margin_ratio)))
        if not isinstance(self.initial_margin, Decimal):
            object.__setattr__(self, 'initial_margin', Decimal(str(self.initial_margin)))
        if not isinstance(self.maintenance_margin, Decimal):
            object.__setattr__(self, 'maintenance_margin', Decimal(str(self.maintenance_margin)))
        if not isinstance(self.shortfall, Decimal):
            object.__setattr__(self, 'shortfall', Decimal(str(self.shortfall)))
        if not isinstance(self.excess, Decimal):
            object.__setattr__(self, 'excess', Decimal(str(self.excess)))
        if not isinstance(self.pending_interest, Decimal):
            object.__setattr__(self, 'pending_interest', Decimal(str(self.pending_interest)))


# ============================================================================
# ADAPTER FUNCTIONS - Bridge Between LedgerView and Pure Functions
# ============================================================================

def load_margin_loan(view: LedgerView, symbol: str) -> Tuple[MarginLoanTerms, MarginLoanState]:
    """
    Load a margin loan from ledger state as typed frozen dataclasses.

    This is the ONLY function that reads from LedgerView for margin loan
    calculations. All pure calculation functions take the returned
    dataclasses as explicit parameters.

    Args:
        view: Read-only ledger access
        symbol: Margin loan unit symbol

    Returns:
        Tuple of (MarginLoanTerms, MarginLoanState) - both frozen/immutable

    Example:
        terms, state = load_margin_loan(view, "LOAN_001")
        value = calculate_collateral_value(state.collateral, prices, terms.haircuts)
    """
    raw = view.get_unit_state(symbol)

    terms = MarginLoanTerms(
        interest_rate=Decimal(str(raw.get('interest_rate', 0.0))),
        initial_margin=Decimal(str(raw.get('initial_margin', 1.5))),
        maintenance_margin=Decimal(str(raw.get('maintenance_margin', 1.25))),
        haircuts={k: Decimal(str(v)) for k, v in raw.get('haircuts', {}).items()},
        margin_call_deadline_days=raw.get('margin_call_deadline_days', 3),
        currency=raw.get('currency', 'USD'),
        borrower_wallet=raw.get('borrower_wallet', ''),
        lender_wallet=raw.get('lender_wallet', ''),
    )

    state = MarginLoanState(
        loan_amount=Decimal(str(raw.get('loan_amount', 0.0))),
        collateral={k: Decimal(str(v)) for k, v in raw.get('collateral', {}).items()},
        accrued_interest=Decimal(str(raw.get('accrued_interest', 0.0))),
        last_accrual_date=raw.get('last_accrual_date'),
        margin_call_amount=Decimal(str(raw.get('margin_call_amount', 0.0))),
        margin_call_deadline=raw.get('margin_call_deadline'),
        liquidated=raw.get('liquidated', False),
        origination_date=raw.get('origination_date'),
        total_interest_paid=Decimal(str(raw.get('total_interest_paid', 0.0))),
        total_principal_paid=Decimal(str(raw.get('total_principal_paid', 0.0))),
        liquidation_date=raw.get('liquidation_date'),
        liquidation_proceeds=Decimal(str(raw.get('liquidation_proceeds'))) if raw.get('liquidation_proceeds') is not None else None,
        liquidation_deficiency=Decimal(str(raw.get('liquidation_deficiency'))) if raw.get('liquidation_deficiency') is not None else None,
    )

    return terms, state


def to_state_dict(terms: MarginLoanTerms, state: MarginLoanState) -> Dict[str, Any]:
    """
    Convert typed dataclasses back to state dict for ledger storage.

    This is the inverse of load_margin_loan() - used when building
    PendingTransaction.state_updates.

    Args:
        terms: Immutable loan terms
        state: Current loan state

    Returns:
        Dictionary suitable for state_updates in PendingTransaction
    """
    return {
        'loan_amount': state.loan_amount,
        'interest_rate': terms.interest_rate,
        'initial_margin': terms.initial_margin,
        'maintenance_margin': terms.maintenance_margin,
        'haircuts': dict(terms.haircuts),
        'margin_call_deadline_days': terms.margin_call_deadline_days,
        'currency': terms.currency,
        'borrower_wallet': terms.borrower_wallet,
        'lender_wallet': terms.lender_wallet,
        'collateral': dict(state.collateral),
        'accrued_interest': state.accrued_interest,
        'last_accrual_date': state.last_accrual_date,
        'margin_call_amount': state.margin_call_amount,
        'margin_call_deadline': state.margin_call_deadline,
        'liquidated': state.liquidated,
        'origination_date': state.origination_date,
        'total_interest_paid': state.total_interest_paid,
        'total_principal_paid': state.total_principal_paid,
        'liquidation_date': state.liquidation_date,
        'liquidation_proceeds': state.liquidation_proceeds,
        'liquidation_deficiency': state.liquidation_deficiency,
    }


# ============================================================================
# PURE CALCULATION FUNCTIONS - No LedgerView, All Inputs Explicit
# ============================================================================

def calculate_collateral_value(
    collateral: Mapping[str, Decimal],
    prices: Mapping[str, Decimal],
    haircuts: Mapping[str, Decimal],
) -> Decimal:
    """
    Calculate haircut-adjusted collateral value.

    PURE FUNCTION - All inputs explicit, no hidden state.

    This is the core collateral valuation formula:
        value = sum(quantity * price * haircut for each asset)

    Args:
        collateral: Asset -> quantity mapping (what's pledged)
        prices: Asset -> price mapping (current market prices)
        haircuts: Asset -> haircut factor mapping (0-1, where 1=full credit)

    Returns:
        Total haircut-adjusted collateral value.

    Raises:
        ValueError: if any collateral asset is missing price or haircut.

    Example:
        # Stress test with 10% more conservative haircuts
        stressed_haircuts = {k: v * Decimal("0.9") for k, v in haircuts.items()}
        stressed_value = calculate_collateral_value(collateral, prices, stressed_haircuts)
    """
    total_value = Decimal("0")
    for asset, quantity in collateral.items():
        if asset not in prices:
            raise ValueError(f"Missing price for collateral asset '{asset}'")
        if asset not in haircuts:
            raise ValueError(f"Missing haircut for collateral asset '{asset}'")
        price = prices[asset]
        haircut = haircuts[asset]
        total_value += quantity * price * haircut
    return total_value


def calculate_pending_interest(
    loan_amount: Decimal,
    interest_rate: Decimal,
    last_accrual_date: Optional[datetime],
    current_time: Optional[datetime],
) -> Decimal:
    """
    Calculate interest accrued since last accrual date.

    PURE FUNCTION - All inputs explicit, no hidden state.

    This prevents race conditions where margin checks run before interest
    accrual is persisted. By calculating pending interest on-the-fly,
    all debt calculations reflect the true position.

    Args:
        loan_amount: Outstanding principal
        interest_rate: Annual interest rate (e.g., 0.08 for 8%)
        last_accrual_date: When interest was last calculated
        current_time: Current timestamp

    Returns:
        Pending interest amount (Decimal("0") if no time elapsed or zero rate)
    """
    # Convert to Decimal if needed for robustness
    if not isinstance(loan_amount, Decimal):
        loan_amount = Decimal(str(loan_amount))
    if not isinstance(interest_rate, Decimal):
        interest_rate = Decimal(str(interest_rate))

    if (
        last_accrual_date is None
        or current_time is None
        or loan_amount <= QUANTITY_EPSILON
        or interest_rate <= Decimal("0")
    ):
        return Decimal("0")

    time_delta = current_time - last_accrual_date
    days_elapsed = Decimal(str(time_delta.total_seconds())) / Decimal("86400")

    if days_elapsed <= 0:
        return Decimal("0")

    return loan_amount * (interest_rate / Decimal("365")) * days_elapsed


def calculate_total_debt(
    terms: MarginLoanTerms,
    state: MarginLoanState,
    current_time: Optional[datetime],
) -> Decimal:
    """
    Calculate total debt including pending interest.

    PURE FUNCTION - All inputs explicit.

    Args:
        terms: Loan terms (for interest rate)
        state: Current state (for loan_amount, accrued interest, last accrual date)
        current_time: For calculating pending interest

    Returns:
        loan_amount + accrued_interest + pending_interest
    """
    pending = calculate_pending_interest(
        loan_amount=state.loan_amount,
        interest_rate=terms.interest_rate,
        last_accrual_date=state.last_accrual_date,
        current_time=current_time,
    )

    return state.loan_amount + state.accrued_interest + pending


def calculate_margin_status(
    terms: MarginLoanTerms,
    state: MarginLoanState,
    prices: Mapping[str, Decimal],
    current_time: Optional[datetime],
) -> MarginStatusResult:
    """
    Compute margin status from explicit inputs.

    PURE FUNCTION - All inputs explicit, no LedgerView.

    This is the core margin assessment logic:
    1. Calculate collateral value with haircuts
    2. Calculate total debt (including pending interest)
    3. Compute margin ratio
    4. Determine status (HEALTHY/WARNING/BREACH/LIQUIDATION)

    Args:
        terms: Immutable loan terms
        state: Current loan state snapshot
        prices: Current market prices
        current_time: For pending interest and deadline checking

    Returns:
        MarginStatusResult with all margin metrics

    Example:
        # Stress test with different prices
        terms, state = load_margin_loan(view, symbol)
        stressed_prices = {k: v * Decimal("0.8") for k, v in prices.items()}
        result = calculate_margin_status(terms, state, stressed_prices, now)
    """
    # Check if liquidated
    if state.liquidated:
        return MarginStatusResult(
            collateral_value=Decimal("0"),
            total_debt=Decimal("0"),
            margin_ratio=Decimal("0"),
            initial_margin=terms.initial_margin,
            maintenance_margin=terms.maintenance_margin,
            status=MARGIN_STATUS_LIQUIDATION,
            shortfall=Decimal("0"),
            excess=Decimal("0"),
            pending_interest=Decimal("0"),
        )

    # Calculate pending interest
    pending_interest = calculate_pending_interest(
        loan_amount=state.loan_amount,
        interest_rate=terms.interest_rate,
        last_accrual_date=state.last_accrual_date,
        current_time=current_time,
    )

    # Calculate values
    collateral_value = calculate_collateral_value(
        state.collateral, prices, terms.haircuts
    )
    total_debt = state.loan_amount + state.accrued_interest + pending_interest

    # Handle zero debt case
    if total_debt < QUANTITY_EPSILON:
        return MarginStatusResult(
            collateral_value=collateral_value,
            total_debt=Decimal("0"),
            margin_ratio=Decimal("Infinity"),
            initial_margin=terms.initial_margin,
            maintenance_margin=terms.maintenance_margin,
            status=MARGIN_STATUS_HEALTHY,
            shortfall=Decimal("0"),
            excess=collateral_value,
            pending_interest=Decimal("0"),
        )

    margin_ratio = collateral_value / total_debt

    # Determine status
    if margin_ratio >= terms.initial_margin:
        status = MARGIN_STATUS_HEALTHY
        shortfall = Decimal("0")
        excess = collateral_value - (terms.maintenance_margin * total_debt)
    elif margin_ratio >= terms.maintenance_margin:
        status = MARGIN_STATUS_WARNING
        shortfall = Decimal("0")
        excess = collateral_value - (terms.maintenance_margin * total_debt)
    else:
        # Check if margin call deadline has passed
        if state.margin_call_deadline and current_time and current_time >= state.margin_call_deadline:
            status = MARGIN_STATUS_LIQUIDATION
        else:
            status = MARGIN_STATUS_BREACH
        shortfall = (terms.maintenance_margin * total_debt) - collateral_value
        excess = Decimal("0")

    return MarginStatusResult(
        collateral_value=collateral_value,
        total_debt=total_debt,
        margin_ratio=margin_ratio,
        initial_margin=terms.initial_margin,
        maintenance_margin=terms.maintenance_margin,
        status=status,
        shortfall=shortfall,
        excess=excess,
        pending_interest=pending_interest,
    )


def calculate_interest_accrual(
    terms: MarginLoanTerms,
    state: MarginLoanState,
    days: Decimal,
) -> Tuple[Decimal, Decimal]:
    """
    Calculate interest accrual for a number of days.

    PURE FUNCTION - All inputs explicit.

    Args:
        terms: Loan terms (for interest rate)
        state: Current state (for loan_amount)
        days: Number of days to accrue

    Returns:
        Tuple of (new_interest_amount, total_accrued_after)
    """
    # Convert to Decimal if needed for robustness
    if not isinstance(days, Decimal):
        days = Decimal(str(days))

    if days <= Decimal("0") or state.liquidated:
        return Decimal("0"), state.accrued_interest

    if state.loan_amount < QUANTITY_EPSILON:
        return Decimal("0"), state.accrued_interest

    # Simple interest: P * r * t
    new_interest = state.loan_amount * (terms.interest_rate / Decimal("365")) * days
    total_accrued = state.accrued_interest + new_interest

    return new_interest, total_accrued


# ============================================================================
# MARGIN LOAN CREATION
# ============================================================================

def create_margin_loan(
    symbol: str,
    name: str,
    loan_amount: Decimal,
    interest_rate: Decimal,
    collateral: CollateralPool,
    haircuts: HaircutSchedule,
    initial_margin: Decimal,
    maintenance_margin: Decimal,
    borrower_wallet: str,
    lender_wallet: str,
    currency: str,
    origination_date: Optional[datetime] = None,
    margin_call_deadline_days: int = 3,
) -> Unit:
    """
    Create a margin loan unit representing secured debt.

    A margin loan allows a borrower to borrow funds against a pool of collateral
    assets. The loan has ongoing interest accrual, and margin requirements that
    must be maintained. If the collateral value falls below the maintenance
    margin, a margin call is issued requiring the borrower to either add
    collateral or repay part of the loan.

    Args:
        symbol: Unique loan identifier (e.g., "LOAN_001")
        name: Human-readable loan name
        loan_amount: Principal amount borrowed (must be positive)
        interest_rate: Annual interest rate (e.g., 0.08 for 8%)
        collateral: Dictionary mapping asset symbols to quantities pledged
        haircuts: Dictionary mapping asset symbols to haircut values (0-1).
                  A haircut of 0.95 means 95% of the asset value is counted.
                  A haircut of 0.50 means only 50% of the asset value is counted.
        initial_margin: Minimum margin ratio at origination (e.g., 1.5 for 150%)
        maintenance_margin: Minimum margin ratio to avoid margin call (e.g., 1.25 for 125%)
        borrower_wallet: Wallet receiving the loan and pledging collateral
        lender_wallet: Wallet providing the loan funds
        currency: Settlement currency (e.g., "USD")
        origination_date: Loan origination date (optional)
        margin_call_deadline_days: Days to cure a margin call (default: 3)

    Returns:
        Unit configured for margin loan with lifecycle support.
        The unit stores margin loan state including:
        - loan_amount: outstanding principal
        - interest_rate: annual rate
        - accrued_interest: accumulated unpaid interest
        - collateral: asset -> quantity mapping
        - haircuts: asset -> haircut factor mapping
        - initial_margin: required margin at origination
        - maintenance_margin: required margin to avoid calls
        - borrower_wallet: who owes the debt
        - lender_wallet: who is owed
        - currency: loan currency
        - margin_call_amount: amount needed to cure (0 if none)
        - margin_call_deadline: deadline to cure margin call
        - liquidated: whether loan has been liquidated

    Raises:
        ValueError: If loan_amount <= 0, interest_rate < 0, margins invalid,
                    wallets empty/identical, or haircuts out of range [0, 1].

    Example:
        loan = create_margin_loan(
            symbol="LOAN_001",
            name="Margin Loan #1",
            loan_amount=Decimal("100000"),
            interest_rate=Decimal("0.08"),
            collateral={"AAPL": Decimal("1000"), "MSFT": Decimal("500")},
            haircuts={"AAPL": Decimal("0.70"), "MSFT": Decimal("0.75")},  # 70-75% credit
            initial_margin=Decimal("1.5"),
            maintenance_margin=Decimal("1.25"),
            borrower_wallet="alice",
            lender_wallet="bank",
            currency="USD",
        )
        ledger.register_unit(loan)
    """
    # Validate loan_amount
    if loan_amount <= Decimal("0"):
        raise ValueError(f"loan_amount must be positive, got {loan_amount}")

    # Validate interest_rate
    if interest_rate < Decimal("0"):
        raise ValueError(f"interest_rate cannot be negative, got {interest_rate}")

    # Validate margin requirements
    if initial_margin <= Decimal("0"):
        raise ValueError(f"initial_margin must be positive, got {initial_margin}")
    if maintenance_margin <= Decimal("0"):
        raise ValueError(f"maintenance_margin must be positive, got {maintenance_margin}")
    if maintenance_margin > initial_margin:
        raise ValueError(
            f"maintenance_margin ({maintenance_margin}) cannot exceed "
            f"initial_margin ({initial_margin})"
        )

    # Validate wallets
    if not borrower_wallet or not borrower_wallet.strip():
        raise ValueError("borrower_wallet cannot be empty")
    if not lender_wallet or not lender_wallet.strip():
        raise ValueError("lender_wallet cannot be empty")
    if borrower_wallet == lender_wallet:
        raise ValueError("borrower_wallet and lender_wallet must be different")

    # Validate currency
    if not currency or not currency.strip():
        raise ValueError("currency cannot be empty")

    # Validate haircuts
    for asset, haircut in haircuts.items():
        if haircut < Decimal("0") or haircut > Decimal("1"):
            raise ValueError(
                f"haircut for {asset} must be in [0, 1], got {haircut}"
            )

    # Validate collateral has corresponding haircuts
    for asset in collateral:
        if asset not in haircuts:
            raise ValueError(
                f"collateral asset {asset} has no corresponding haircut"
            )

    # Validate collateral quantities
    for asset, qty in collateral.items():
        if qty < Decimal("0"):
            raise ValueError(
                f"collateral quantity for {asset} cannot be negative, got {qty}"
            )

    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_MARGIN_LOAN,
        min_balance=Decimal("-1"),  # Only borrower (-1) and lender (+1) positions
        max_balance=Decimal("1"),
        decimal_places=0,  # Loan is a single unit
        transfer_rule=None,
        _frozen_state=_freeze_state({
            'loan_amount': loan_amount,
            'interest_rate': interest_rate,
            'accrued_interest': Decimal("0"),
            'collateral': dict(collateral),
            'haircuts': dict(haircuts),
            'initial_margin': initial_margin,
            'maintenance_margin': maintenance_margin,
            'borrower_wallet': borrower_wallet,
            'lender_wallet': lender_wallet,
            'currency': currency,
            'margin_call_amount': Decimal("0"),
            'margin_call_deadline': None,
            'margin_call_deadline_days': margin_call_deadline_days,
            'liquidated': False,
            'origination_date': origination_date,
            'last_accrual_date': origination_date,
            'total_interest_paid': Decimal("0"),
            'total_principal_paid': Decimal("0"),
        })
    )


# ============================================================================
# ADAPTER FUNCTION (delegates to pure function)
# ============================================================================

def _calculate_pending_interest(
    state: Dict[str, Any],
    current_time: Optional[datetime],
) -> Decimal:
    """
    Adapter function - delegates to pure calculate_pending_interest().

    This wrapper accepts raw state dicts for flexibility. Prefer using
    calculate_pending_interest() directly with explicit parameters.

    Note: loan_amount in state already represents the current outstanding
    principal (it is reduced when payments are made), so we use it directly.
    """
    # loan_amount is already the outstanding principal - it gets reduced
    # when principal payments are made (see compute_repayment, compute_margin_cure)
    loan_amount = state.get('loan_amount', Decimal("0"))
    if not isinstance(loan_amount, Decimal):
        loan_amount = Decimal(str(loan_amount))

    interest_rate = state.get('interest_rate', Decimal("0"))
    if not isinstance(interest_rate, Decimal):
        interest_rate = Decimal(str(interest_rate))

    return calculate_pending_interest(
        loan_amount=loan_amount,
        interest_rate=interest_rate,
        last_accrual_date=state.get('last_accrual_date'),
        current_time=current_time,
    )


# ============================================================================
# COLLATERAL VALUE CALCULATION
# ============================================================================

def compute_collateral_value(
    view: LedgerView,
    loan_symbol: str,
    prices: PriceDict,
) -> Decimal:
    """
    Calculate the haircut-adjusted collateral value.

    This is a convenience function that loads state and calls the pure
    calculate_collateral_value() function.

    For stress testing with different haircuts, use the pure function directly:
        terms, state = load_margin_loan(view, symbol)
        stressed_haircuts = {k: v * Decimal("0.9") for k, v in terms.haircuts.items()}
        value = calculate_collateral_value(state.collateral, prices, stressed_haircuts)

    Args:
        view: Read-only ledger access
        loan_symbol: Symbol of the margin loan unit
        prices: Dictionary mapping asset symbols to current market prices

    Returns:
        Total haircut-adjusted collateral value in loan currency.
        Missing prices are treated as zero (asset not counted).

    Example:
        value = compute_collateral_value(view, "LOAN_001", prices)
    """
    terms, state = load_margin_loan(view, loan_symbol)
    return calculate_collateral_value(state.collateral, prices, terms.haircuts)


# ============================================================================
# MARGIN STATUS CALCULATION
# ============================================================================

def compute_margin_status(
    view: LedgerView,
    loan_symbol: str,
    prices: PriceDict,
) -> Dict[str, Any]:
    """
    Compute the current margin status of the loan.

    This is a convenience function that loads state and calls the pure
    calculate_margin_status() function, then converts the result to a dict.

    For stress testing with different parameters, use the pure function directly:
        terms, state = load_margin_loan(view, symbol)
        stressed_prices = {k: v * Decimal("0.8") for k, v in prices.items()}
        result = calculate_margin_status(terms, state, stressed_prices, now)

    Args:
        view: Read-only ledger access
        loan_symbol: Symbol of the margin loan unit
        prices: Dictionary mapping asset symbols to current market prices

    Returns:
        Dictionary containing:
        - collateral_value: Haircut-adjusted collateral value
        - total_debt: loan_amount + accrued_interest (including pending)
        - margin_ratio: collateral_value / total_debt (or inf if no debt)
        - initial_margin: Required initial margin ratio
        - maintenance_margin: Required maintenance margin ratio
        - status: One of HEALTHY, WARNING, BREACH, LIQUIDATION
        - shortfall: Amount needed to cure breach (0 if healthy)
        - excess: Excess collateral value above maintenance (0 if breach)
        - pending_interest: Interest accrued since last_accrual_date

    Example:
        status = compute_margin_status(view, "LOAN_001", prices)
        if status["status"] == "BREACH":
            print(f"Margin call! Shortfall: ${status['shortfall']:.2f}")
    """
    terms, state = load_margin_loan(view, loan_symbol)
    result = calculate_margin_status(terms, state, prices, view.current_time)

    # Convert frozen dataclass to dict for dict-based API consumers
    return {
        'collateral_value': result.collateral_value,
        'total_debt': result.total_debt,
        'margin_ratio': result.margin_ratio,
        'initial_margin': result.initial_margin,
        'maintenance_margin': result.maintenance_margin,
        'status': result.status,
        'shortfall': result.shortfall,
        'excess': result.excess,
        'pending_interest': result.pending_interest,
    }


# ============================================================================
# INTEREST ACCRUAL
# ============================================================================

def compute_interest_accrual(
    view: LedgerView,
    loan_symbol: str,
    days: Decimal,
) -> PendingTransaction:
    """
    Accrue interest on the outstanding loan balance.

    Interest accrues daily using simple interest calculation:
    daily_interest = loan_amount * (interest_rate / 365) * days

    This function only updates the accrued_interest state - it does not
    generate any cash moves. Interest is paid upon repayment or liquidation.

    Args:
        view: Read-only ledger access
        loan_symbol: Symbol of the margin loan unit
        days: Number of days to accrue interest for

    Returns:
        PendingTransaction with state updates (no moves).
        Returns empty result if loan is liquidated or days <= 0.

    Raises:
        ValueError: If days is negative.

    Example:
        # Accrue 30 days of interest on $100,000 @ 8%
        # Interest = 100000 * 0.08 / 365 * 30 = $657.53
        result = compute_interest_accrual(view, "LOAN_001", Decimal("30"))
        ledger.execute(result)
    """
    # Convert to Decimal if passed as int or float
    if not isinstance(days, Decimal):
        days = Decimal(str(days))

    if days < Decimal("0"):
        raise ValueError(f"days cannot be negative, got {days}")

    if days < QUANTITY_EPSILON:
        return empty_pending_transaction(view)

    state = view.get_unit_state(loan_symbol)

    if state.get('liquidated', False):
        return empty_pending_transaction(view)

    loan_amount = state.get('loan_amount', Decimal("0"))
    if not isinstance(loan_amount, Decimal):
        loan_amount = Decimal(str(loan_amount))
    if loan_amount < QUANTITY_EPSILON:
        return empty_pending_transaction(view)  # No loan to accrue on

    interest_rate = state.get('interest_rate', Decimal("0"))
    if not isinstance(interest_rate, Decimal):
        interest_rate = Decimal(str(interest_rate))
    current_accrued = state.get('accrued_interest', Decimal("0"))
    if not isinstance(current_accrued, Decimal):
        current_accrued = Decimal(str(current_accrued))

    # Simple interest calculation: P * r * t (annual rate / 365 for daily)
    new_interest = loan_amount * (interest_rate / Decimal("365")) * days
    total_accrued = current_accrued + new_interest

    new_state = {
        **state,
        'accrued_interest': total_accrued,
        'last_accrual_date': view.current_time,
    }
    state_changes = [UnitStateChange(unit=loan_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, [], state_changes)


# ============================================================================
# MARGIN CALL
# ============================================================================

def compute_margin_call(
    view: LedgerView,
    loan_symbol: str,
    prices: PriceDict,
) -> PendingTransaction:
    """
    Issue a margin call if the loan is below maintenance margin.

    When collateral value falls below maintenance_margin * total_debt, a margin
    call is issued requiring the borrower to either:
    1. Add collateral to bring margin ratio above maintenance
    2. Repay part of the loan to reduce debt
    3. Face liquidation after the deadline

    Note on Interest Accrual:
        This function delegates to compute_margin_status(), which internally
        calculates pending interest since the last accrual date. This prevents
        the race condition where EOD margin checks pass but overnight interest
        accrual pushes the loan into breach. The margin check sees the true
        debt position at view.current_time regardless of when interest was
        last persisted to state.

        Best practice: Run compute_interest_accrual() before margin checks
        to keep state current, but margin calls will be correct either way.

    Args:
        view: Read-only ledger access
        loan_symbol: Symbol of the margin loan unit
        prices: Dictionary mapping asset symbols to current market prices

    Returns:
        PendingTransaction with state updates setting margin_call_amount and
        margin_call_deadline. Returns empty result if margin is adequate
        or loan is already liquidated.

    Example:
        result = compute_margin_call(view, "LOAN_001", prices)
        if result.state_updates:
            deadline = result.state_updates["LOAN_001"]["margin_call_deadline"]
            print(f"Margin call issued! Cure by {deadline}")
    """
    state = view.get_unit_state(loan_symbol)

    if state.get('liquidated', False):
        return empty_pending_transaction(view)

    # Already has an active margin call
    if state.get('margin_call_deadline') is not None:
        return empty_pending_transaction(view)

    margin_status = compute_margin_status(view, loan_symbol, prices)

    if margin_status['status'] not in (MARGIN_STATUS_BREACH, MARGIN_STATUS_LIQUIDATION):
        return empty_pending_transaction(view)

    shortfall = margin_status['shortfall']
    deadline_days = state.get('margin_call_deadline_days', 3)
    deadline = view.current_time + timedelta(days=deadline_days)

    new_state = {
        **state,
        'margin_call_amount': shortfall,
        'margin_call_deadline': deadline,
    }
    state_changes = [UnitStateChange(unit=loan_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, [], state_changes)


# ============================================================================
# MARGIN CURE
# ============================================================================

def compute_margin_cure(
    view: LedgerView,
    loan_symbol: str,
    cure_amount: Decimal,
    prices: Optional[PriceDict] = None,
) -> PendingTransaction:
    """
    Cure a margin call by making a cash payment to reduce debt.

    The borrower can cure a margin call by paying down the loan. This reduces
    the total debt and may bring the margin ratio back above maintenance level.

    Args:
        view: Read-only ledger access
        loan_symbol: Symbol of the margin loan unit
        cure_amount: Cash amount to apply toward debt (must be positive)
        prices: Optional prices to verify cure is sufficient (not required)

    Returns:
        PendingTransaction with:
        - moves: Cash transfer from borrower to lender
        - state_updates: Reduced debt and potentially cleared margin call

    Raises:
        ValueError: If cure_amount <= 0 or exceeds total debt.

    Example:
        # Cure margin call with $10,000 payment
        result = compute_margin_cure(view, "LOAN_001", Decimal("10000"))
        ledger.execute(result)
    """
    # Convert to Decimal if passed as float
    if not isinstance(cure_amount, Decimal):
        cure_amount = Decimal(str(cure_amount))

    if cure_amount <= Decimal("0"):
        raise ValueError(f"cure_amount must be positive, got {cure_amount}")

    state = view.get_unit_state(loan_symbol)

    if state.get('liquidated', False):
        raise ValueError("Cannot cure a liquidated loan")

    loan_amount = state.get('loan_amount', Decimal("0"))
    if not isinstance(loan_amount, Decimal):
        loan_amount = Decimal(str(loan_amount))
    accrued_interest = state.get('accrued_interest', Decimal("0"))
    if not isinstance(accrued_interest, Decimal):
        accrued_interest = Decimal(str(accrued_interest))

    # CRITICAL FIX: Include pending interest in total debt calculation
    # to ensure cure amount properly accounts for all accrued interest
    pending_interest = _calculate_pending_interest(state, view.current_time)
    total_debt = loan_amount + accrued_interest + pending_interest

    # Allow small tolerance for floating point conversion differences
    if cure_amount > total_debt + Decimal("0.01"):
        raise ValueError(
            f"cure_amount ({cure_amount}) exceeds total_debt ({total_debt})"
        )

    borrower = state['borrower_wallet']
    lender = state['lender_wallet']
    currency = state['currency']

    # Apply payment: first to pending interest, then accrued interest, then principal
    # This ensures all interest (both persisted and pending) is paid before principal
    total_interest = accrued_interest + pending_interest
    interest_payment = min(cure_amount, total_interest)
    principal_payment = cure_amount - interest_payment

    # Pending interest is paid but not yet in accrued_interest state
    # We add it to accrued_interest, then subtract the full interest payment
    new_accrued = (accrued_interest + pending_interest) - interest_payment
    new_loan_amount = loan_amount - principal_payment
    total_interest_paid_old = state.get('total_interest_paid', Decimal("0"))
    if not isinstance(total_interest_paid_old, Decimal):
        total_interest_paid_old = Decimal(str(total_interest_paid_old))
    total_principal_paid_old = state.get('total_principal_paid', Decimal("0"))
    if not isinstance(total_principal_paid_old, Decimal):
        total_principal_paid_old = Decimal(str(total_principal_paid_old))
    total_interest_paid = total_interest_paid_old + interest_payment
    total_principal_paid = total_principal_paid_old + principal_payment

    # Generate cash move
    moves = [
        Move(
            quantity=cure_amount,
            unit_symbol=currency,
            source=borrower,
            dest=lender,
            contract_id=f'margin_cure_{loan_symbol}',
        )
    ]

    # Update state
    new_state = {
        **state,
        'loan_amount': new_loan_amount,
        'accrued_interest': new_accrued,
        'total_interest_paid': total_interest_paid,
        'total_principal_paid': total_principal_paid,
        'last_accrual_date': view.current_time,  # Update accrual date since we rolled in pending interest
    }

    # If cure brings debt to zero, clear margin call
    if new_loan_amount + new_accrued < QUANTITY_EPSILON:
        new_state['margin_call_amount'] = Decimal("0")
        new_state['margin_call_deadline'] = None
    elif prices is not None:
        # Check if margin is restored
        # Create a temporary state to check margin status
        temp_state = dict(new_state)
        # Use pure function for collateral calculation
        collateral = temp_state.get('collateral', {})
        # Convert collateral to Decimal if needed
        collateral_decimal = {}
        for k, v in collateral.items():
            collateral_decimal[k] = v if isinstance(v, Decimal) else Decimal(str(v))
        haircuts = temp_state.get('haircuts', {})
        haircuts_decimal = {}
        for k, v in haircuts.items():
            haircuts_decimal[k] = v if isinstance(v, Decimal) else Decimal(str(v))
        collateral_value = calculate_collateral_value(collateral_decimal, prices, haircuts_decimal)

        new_total_debt = new_loan_amount + new_accrued
        if new_total_debt > QUANTITY_EPSILON:
            margin_ratio = collateral_value / new_total_debt
            maintenance_margin = temp_state.get('maintenance_margin', Decimal("1.25"))
            if not isinstance(maintenance_margin, Decimal):
                maintenance_margin = Decimal(str(maintenance_margin))
            if margin_ratio >= maintenance_margin:
                new_state['margin_call_amount'] = Decimal("0")
                new_state['margin_call_deadline'] = None
    else:
        # Clear margin call if it was paid down significantly
        # (caller should verify with prices)
        margin_call_amount = new_state.get('margin_call_amount', Decimal("0"))
        if not isinstance(margin_call_amount, Decimal):
            margin_call_amount = Decimal(str(margin_call_amount))
        if margin_call_amount > Decimal("0"):
            new_margin_call = max(Decimal("0"), margin_call_amount - cure_amount)
            new_state['margin_call_amount'] = new_margin_call
            if new_margin_call < QUANTITY_EPSILON:
                new_state['margin_call_deadline'] = None

    state_changes = [UnitStateChange(unit=loan_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


# ============================================================================
# LIQUIDATION
# ============================================================================

def compute_liquidation(
    view: LedgerView,
    loan_symbol: str,
    prices: PriceDict,
    sale_proceeds: Decimal,
) -> PendingTransaction:
    """
    Liquidate the loan by selling collateral and settling the debt.

    When a margin call is not cured by the deadline, the lender liquidates
    the collateral to recover the debt. The sale_proceeds are applied to
    the debt, and any surplus is returned to the borrower.

    CRITICAL - Borrower Rights Protection:
        Liquidation is ONLY allowed when margin status is LIQUIDATION, which
        means the margin_call_deadline has passed and the borrower failed to cure.

        BREACH status means the borrower is below maintenance margin but the
        cure deadline has NOT passed yet. Liquidating during BREACH violates
        the borrower's contractual right to cure within the deadline period.

        Status transitions:
        - HEALTHY/WARNING: Above maintenance margin, no liquidation
        - BREACH: Below maintenance, deadline NOT passed, NO liquidation allowed
        - LIQUIDATION: Below maintenance, deadline PASSED, liquidation allowed

    Args:
        view: Read-only ledger access
        loan_symbol: Symbol of the margin loan unit
        prices: Dictionary mapping asset symbols to liquidation prices
        sale_proceeds: Total cash received from selling collateral

    Returns:
        PendingTransaction with:
        - moves: Cash flows for debt settlement and any surplus to borrower
        - state_updates: Marks loan as liquidated, clears collateral

    Raises:
        ValueError: If loan not in LIQUIDATION status (deadline must have passed),
                    if already liquidated, or if sale_proceeds is negative.

    Example:
        # Liquidate collateral that sold for $80,000 (after deadline passed)
        result = compute_liquidation(view, "LOAN_001", prices, Decimal("80000"))
        ledger.execute(result)
        # Debt paid from proceeds, any surplus to borrower
    """
    # Convert to Decimal if passed as float
    if not isinstance(sale_proceeds, Decimal):
        sale_proceeds = Decimal(str(sale_proceeds))

    if sale_proceeds < Decimal("0"):
        raise ValueError(f"sale_proceeds cannot be negative, got {sale_proceeds}")

    state = view.get_unit_state(loan_symbol)

    if state.get('liquidated', False):
        raise ValueError("Loan is already liquidated")

    margin_status = compute_margin_status(view, loan_symbol, prices)

    # CRITICAL FIX: Only allow liquidation when deadline has passed
    # BREACH status means deadline has NOT passed - borrower still has cure rights
    # LIQUIDATION status means deadline HAS passed - liquidation is allowed
    if margin_status['status'] != MARGIN_STATUS_LIQUIDATION:
        raise ValueError(
            f"Cannot liquidate: loan status is {margin_status['status']}. "
            f"Liquidation only allowed when status is LIQUIDATION (deadline passed)."
        )

    borrower = state['borrower_wallet']
    lender = state['lender_wallet']
    currency = state['currency']
    loan_amount = state.get('loan_amount', Decimal("0"))
    if not isinstance(loan_amount, Decimal):
        loan_amount = Decimal(str(loan_amount))
    accrued_interest = state.get('accrued_interest', Decimal("0"))
    if not isinstance(accrued_interest, Decimal):
        accrued_interest = Decimal(str(accrued_interest))

    # CRITICAL FIX: Include pending interest in total debt calculation
    # to ensure lenders receive full accrued-but-not-persisted interest
    pending_interest = _calculate_pending_interest(state, view.current_time)
    total_debt = loan_amount + accrued_interest + pending_interest

    moves: List[Move] = []

    if sale_proceeds >= total_debt:
        # Full debt recovery
        if total_debt > QUANTITY_EPSILON:
            moves.append(Move(
                quantity=total_debt,
                unit_symbol=currency,
                source=borrower,
                dest=lender,
                contract_id=f'liquidation_debt_{loan_symbol}',
            ))

        # Surplus to borrower (conceptually from lender who held proceeds)
        surplus = sale_proceeds - total_debt
        if surplus > QUANTITY_EPSILON:
            moves.append(Move(
                quantity=surplus,
                unit_symbol=currency,
                source=lender,
                dest=borrower,
                contract_id=f'liquidation_surplus_{loan_symbol}',
            ))
    else:
        # Partial debt recovery - shortfall becomes bad debt (tracked as deficiency)
        if sale_proceeds > QUANTITY_EPSILON:
            moves.append(Move(
                quantity=sale_proceeds,
                unit_symbol=currency,
                source=borrower,
                dest=lender,
                contract_id=f'liquidation_partial_{loan_symbol}',
            ))

    # Mark as liquidated
    # IMPORTANT: Always zero out loan_amount and accrued_interest on liquidation.
    # Any deficiency (sale_proceeds < total_debt) is tracked as bad_debt, not as
    # outstanding loan balances. This prevents phantom debt from accruing interest
    # if compute_interest_accrual() is called after liquidation.
    deficiency = max(Decimal("0"), total_debt - sale_proceeds)
    new_state = {
        **state,
        'loan_amount': Decimal("0"),
        'accrued_interest': Decimal("0"),
        'collateral': {},  # Collateral has been sold
        'liquidated': True,
        'liquidation_date': view.current_time,
        'liquidation_proceeds': sale_proceeds,
        'liquidation_deficiency': deficiency,  # Track bad debt separately
        'margin_call_amount': Decimal("0"),
        'margin_call_deadline': None,
    }
    state_changes = [UnitStateChange(unit=loan_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


# ============================================================================
# REPAYMENT
# ============================================================================

def compute_repayment(
    view: LedgerView,
    loan_symbol: str,
    repayment_amount: Decimal,
) -> PendingTransaction:
    """
    Process full or partial loan repayment.

    The borrower can repay the loan at any time. Payment is applied first
    to accrued interest, then to principal. A full repayment clears the
    loan entirely.

    Args:
        view: Read-only ledger access
        loan_symbol: Symbol of the margin loan unit
        repayment_amount: Amount to repay (must be positive)

    Returns:
        PendingTransaction with:
        - moves: Cash transfer from borrower to lender
        - state_updates: Reduced loan_amount and accrued_interest

    Raises:
        ValueError: If repayment_amount <= 0 or exceeds total debt,
                    or if loan is already liquidated.

    Example:
        # Full repayment of $100,000 loan + $500 interest
        result = compute_repayment(view, "LOAN_001", Decimal("100500"))
        ledger.execute(result)
    """
    # Convert to Decimal if passed as float
    if not isinstance(repayment_amount, Decimal):
        repayment_amount = Decimal(str(repayment_amount))

    if repayment_amount <= Decimal("0"):
        raise ValueError(f"repayment_amount must be positive, got {repayment_amount}")

    state = view.get_unit_state(loan_symbol)

    if state.get('liquidated', False):
        raise ValueError("Cannot repay a liquidated loan")

    loan_amount = state.get('loan_amount', Decimal("0"))
    if not isinstance(loan_amount, Decimal):
        loan_amount = Decimal(str(loan_amount))
    accrued_interest = state.get('accrued_interest', Decimal("0"))
    if not isinstance(accrued_interest, Decimal):
        accrued_interest = Decimal(str(accrued_interest))

    # CRITICAL FIX: Include pending interest in total debt calculation
    # to ensure lenders receive full accrued-but-not-persisted interest on repayment
    pending_interest = _calculate_pending_interest(state, view.current_time)
    total_debt = loan_amount + accrued_interest + pending_interest

    if total_debt < QUANTITY_EPSILON:
        raise ValueError("No outstanding debt to repay")

    # Allow small tolerance for floating point conversion differences
    if repayment_amount > total_debt + Decimal("0.01"):
        raise ValueError(
            f"repayment_amount ({repayment_amount}) exceeds total_debt ({total_debt})"
        )

    borrower = state['borrower_wallet']
    lender = state['lender_wallet']
    currency = state['currency']

    # Apply payment: first to pending interest, then accrued interest, then principal
    # This ensures all interest (both persisted and pending) is paid before principal
    total_interest = accrued_interest + pending_interest
    interest_payment = min(repayment_amount, total_interest)
    principal_payment = repayment_amount - interest_payment

    # Pending interest is paid but not yet in accrued_interest state
    # We add it to accrued_interest, then subtract the full interest payment
    new_accrued = (accrued_interest + pending_interest) - interest_payment
    new_loan_amount = loan_amount - principal_payment
    total_interest_paid_old = state.get('total_interest_paid', Decimal("0"))
    if not isinstance(total_interest_paid_old, Decimal):
        total_interest_paid_old = Decimal(str(total_interest_paid_old))
    total_principal_paid_old = state.get('total_principal_paid', Decimal("0"))
    if not isinstance(total_principal_paid_old, Decimal):
        total_principal_paid_old = Decimal(str(total_principal_paid_old))
    total_interest_paid = total_interest_paid_old + interest_payment
    total_principal_paid = total_principal_paid_old + principal_payment

    # Generate cash move
    moves = [
        Move(
            quantity=repayment_amount,
            unit_symbol=currency,
            source=borrower,
            dest=lender,
            contract_id=f'repayment_{loan_symbol}',
        )
    ]

    # Update state
    new_state = {
        **state,
        'loan_amount': new_loan_amount,
        'accrued_interest': new_accrued,
        'total_interest_paid': total_interest_paid,
        'total_principal_paid': total_principal_paid,
        'last_accrual_date': view.current_time,  # Update accrual date since we rolled in pending interest
    }

    # Clear margin call if loan is fully repaid
    if new_loan_amount + new_accrued < QUANTITY_EPSILON:
        new_state['margin_call_amount'] = Decimal("0")
        new_state['margin_call_deadline'] = None

    state_changes = [UnitStateChange(unit=loan_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


# ============================================================================
# ADD COLLATERAL
# ============================================================================

def compute_add_collateral(
    view: LedgerView,
    loan_symbol: str,
    asset: str,
    quantity: Decimal,
    prices: Optional[PriceDict] = None,
) -> PendingTransaction:
    """
    Add collateral to the loan to improve margin ratio.

    The borrower can pledge additional assets as collateral to cure a margin
    call or improve their margin position.

    Args:
        view: Read-only ledger access
        loan_symbol: Symbol of the margin loan unit
        asset: Asset symbol to add as collateral
        quantity: Quantity of asset to pledge (must be positive)
        prices: Optional prices to check if margin call is cured

    Returns:
        PendingTransaction with state updates adding to collateral pool.
        Does not generate moves (asset transfer handled separately).

    Raises:
        ValueError: If quantity <= 0, asset has no haircut defined,
                    or loan is liquidated.

    Example:
        # Pledge 500 additional shares of AAPL
        result = compute_add_collateral(view, "LOAN_001", "AAPL", Decimal("500"))
        ledger.execute(result)
    """
    # Convert to Decimal if passed as float
    if not isinstance(quantity, Decimal):
        quantity = Decimal(str(quantity))

    if quantity <= Decimal("0"):
        raise ValueError(f"quantity must be positive, got {quantity}")

    state = view.get_unit_state(loan_symbol)

    if state.get('liquidated', False):
        raise ValueError("Cannot add collateral to a liquidated loan")

    haircuts = state.get('haircuts', {})
    if asset not in haircuts:
        raise ValueError(f"No haircut defined for asset {asset}")

    collateral = dict(state.get('collateral', {}))
    current_qty = collateral.get(asset, Decimal("0"))
    if not isinstance(current_qty, Decimal):
        current_qty = Decimal(str(current_qty))
    collateral[asset] = current_qty + quantity

    new_state = {
        **state,
        'collateral': collateral,
    }

    # Check if margin call is cured
    if prices is not None and state.get('margin_call_deadline') is not None:
        # Use pure function for collateral calculation
        # Convert collateral and haircuts to Decimal if needed
        collateral_decimal = {}
        for k, v in collateral.items():
            collateral_decimal[k] = v if isinstance(v, Decimal) else Decimal(str(v))
        haircuts_decimal = {}
        for k, v in haircuts.items():
            haircuts_decimal[k] = v if isinstance(v, Decimal) else Decimal(str(v))
        collateral_value = calculate_collateral_value(collateral_decimal, prices, haircuts_decimal)

        loan_amount = state.get('loan_amount', Decimal("0"))
        if not isinstance(loan_amount, Decimal):
            loan_amount = Decimal(str(loan_amount))
        accrued_interest = state.get('accrued_interest', Decimal("0"))
        if not isinstance(accrued_interest, Decimal):
            accrued_interest = Decimal(str(accrued_interest))
        # Include pending interest to prevent race condition where margin call
        # is incorrectly cleared when pending interest would keep ratio below maintenance
        pending_interest = _calculate_pending_interest(state, view.current_time)
        total_debt = loan_amount + accrued_interest + pending_interest

        if total_debt > QUANTITY_EPSILON:
            margin_ratio = collateral_value / total_debt
            maintenance_margin = state.get('maintenance_margin', Decimal("1.25"))
            if not isinstance(maintenance_margin, Decimal):
                maintenance_margin = Decimal(str(maintenance_margin))
            if margin_ratio >= maintenance_margin:
                new_state['margin_call_amount'] = Decimal("0")
                new_state['margin_call_deadline'] = None

    state_changes = [UnitStateChange(unit=loan_symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, [], state_changes)


# ============================================================================
# TRANSACTION INTERFACE
# ============================================================================

def transact(
    view: LedgerView,
    symbol: str,
    event_type: str,
    event_date: datetime,
    **kwargs
) -> PendingTransaction:
    """
    Generate moves and state updates for a margin loan lifecycle event.

    This is the unified entry point for all margin loan lifecycle events,
    routing to the appropriate handler based on event_type.

    Args:
        view: Read-only ledger access
        symbol: Margin loan symbol
        event_type: Type of event:
            - INTEREST_ACCRUAL: Accrue interest (requires 'days')
            - MARGIN_CALL: Check/issue margin call (requires 'prices')
            - MARGIN_CURE: Cure margin call (requires 'cure_amount')
            - LIQUIDATION: Liquidate loan (requires 'prices', 'sale_proceeds')
            - REPAYMENT: Repay loan (requires 'repayment_amount')
            - ADD_COLLATERAL: Add collateral (requires 'asset', 'quantity')
        event_date: When the event occurs
        **kwargs: Event-specific parameters

    Returns:
        PendingTransaction with moves and state_updates, or empty result
        if event_type is unknown or required parameters are missing.

    Example:
        # Accrue 30 days of interest
        result = transact(view, "LOAN_001", "INTEREST_ACCRUAL", event_date, days=30)

        # Check for margin call
        result = transact(view, "LOAN_001", "MARGIN_CALL", event_date, prices=prices)

        # Cure margin call
        result = transact(view, "LOAN_001", "MARGIN_CURE", event_date, cure_amount=10000)

        # Full repayment
        result = transact(view, "LOAN_001", "REPAYMENT", event_date, repayment_amount=Decimal("100500"))
    """
    if event_type == 'INTEREST_ACCRUAL':
        days = kwargs.get('days')
        if days is None:
            raise ValueError(f"Missing 'days' parameter for INTEREST_ACCRUAL event on {symbol}")
        return compute_interest_accrual(view, symbol, days)

    elif event_type == 'MARGIN_CALL':
        prices = kwargs.get('prices')
        if prices is None:
            raise ValueError(f"Missing 'prices' parameter for MARGIN_CALL event on {symbol}")
        return compute_margin_call(view, symbol, prices)

    elif event_type == 'MARGIN_CURE':
        cure_amount = kwargs.get('cure_amount')
        if cure_amount is None:
            raise ValueError(f"Missing 'cure_amount' parameter for MARGIN_CURE event on {symbol}")
        prices = kwargs.get('prices')
        return compute_margin_cure(view, symbol, cure_amount, prices)

    elif event_type == 'LIQUIDATION':
        prices = kwargs.get('prices')
        sale_proceeds = kwargs.get('sale_proceeds')
        if prices is None:
            raise ValueError(f"Missing 'prices' parameter for LIQUIDATION event on {symbol}")
        if sale_proceeds is None:
            raise ValueError(f"Missing 'sale_proceeds' parameter for LIQUIDATION event on {symbol}")
        return compute_liquidation(view, symbol, prices, sale_proceeds)

    elif event_type == 'REPAYMENT':
        repayment_amount = kwargs.get('repayment_amount')
        if repayment_amount is None:
            raise ValueError(f"Missing 'repayment_amount' parameter for REPAYMENT event on {symbol}")
        return compute_repayment(view, symbol, repayment_amount)

    elif event_type == 'ADD_COLLATERAL':
        asset = kwargs.get('asset')
        quantity = kwargs.get('quantity')
        if asset is None:
            raise ValueError(f"Missing 'asset' parameter for ADD_COLLATERAL event on {symbol}")
        if quantity is None:
            raise ValueError(f"Missing 'quantity' parameter for ADD_COLLATERAL event on {symbol}")
        prices = kwargs.get('prices')
        return compute_add_collateral(view, symbol, asset, quantity, prices)

    else:
        raise ValueError(f"Unknown event type '{event_type}' for margin loan {symbol}")


# ============================================================================
# SMART CONTRACT
# ============================================================================

def margin_loan_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, Decimal]
) -> PendingTransaction:
    """
    SmartContract function for automatic margin loan processing.

    This function provides the SmartContract interface required by LifecycleEngine.
    It automatically checks margin status and issues margin calls when needed.

    Args:
        view: Read-only ledger access
        symbol: Margin loan symbol to process
        timestamp: Current time for date checking
        prices: Price data for collateral assets

    Returns:
        PendingTransaction with margin call if loan is below maintenance,
        or empty result if loan is healthy or already has active margin call.
    """
    state = view.get_unit_state(symbol)

    if state.get('liquidated', False):
        return empty_pending_transaction(view)

    # Check if we should issue a margin call
    if state.get('margin_call_deadline') is None:
        # No active margin call - check if we need to issue one
        return compute_margin_call(view, symbol, prices)

    return empty_pending_transaction(view)
