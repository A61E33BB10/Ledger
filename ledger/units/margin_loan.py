"""
margin_loan.py - Margin Loan Units for Secured Lending

This module provides margin loan unit creation and lifecycle processing:
1. create_margin_loan() - Factory for margin loans with collateral pools
2. compute_collateral_value() - Calculate haircut-adjusted collateral value
3. compute_margin_status() - Check margin ratio, shortfall, and status
4. compute_interest_accrual() - Daily interest accrual on outstanding loan
5. compute_margin_call() - Issue margin call when below maintenance
6. compute_margin_cure() - Cure margin call with additional collateral/payment
7. compute_liquidation() - Forced sale when margin call not met
8. compute_repayment() - Full or partial loan repayment
9. transact() - Event-driven interface for all margin loan events
10. margin_loan_contract() - SmartContract for LifecycleEngine integration

Margin loans represent secured debt with:
- Collateral pool: Multiple assets as collateral
- Haircuts: Asset-specific risk weights (higher haircut = more credit given)
- Margin requirements: Initial (150%) and maintenance (125%) margin levels
- Interest accrual: Daily interest on outstanding loan amount
- Margin calls: Triggered when equity falls below maintenance margin
- Liquidation: Forced sale when margin call deadline passes without cure

Key Formulas:
    collateral_value = sum(quantity * price * haircut for each asset)
    total_debt = loan_amount + accrued_interest
    margin_ratio = collateral_value / total_debt
    shortfall = maintenance_margin * total_debt - collateral_value (if ratio < maintenance)

All functions take LedgerView (read-only) and return immutable results.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from ..core import (
    LedgerView, Move, ContractResult, Unit,
    QUANTITY_EPSILON, UNIT_TYPE_MARGIN_LOAN,
)


# Type aliases
CollateralPool = Dict[str, float]  # asset_symbol -> quantity
HaircutSchedule = Dict[str, float]  # asset_symbol -> haircut (0-1, where 1=full credit)
PriceDict = Dict[str, float]  # asset_symbol -> price


# Margin status constants
MARGIN_STATUS_HEALTHY = "HEALTHY"
MARGIN_STATUS_WARNING = "WARNING"
MARGIN_STATUS_BREACH = "BREACH"
MARGIN_STATUS_LIQUIDATION = "LIQUIDATION"


# ============================================================================
# MARGIN LOAN CREATION
# ============================================================================

def create_margin_loan(
    symbol: str,
    name: str,
    loan_amount: float,
    interest_rate: float,
    collateral: CollateralPool,
    haircuts: HaircutSchedule,
    initial_margin: float,
    maintenance_margin: float,
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
            loan_amount=100000.0,
            interest_rate=0.08,
            collateral={"AAPL": 1000, "MSFT": 500},
            haircuts={"AAPL": 0.70, "MSFT": 0.75},  # 70-75% credit
            initial_margin=1.5,
            maintenance_margin=1.25,
            borrower_wallet="alice",
            lender_wallet="bank",
            currency="USD",
        )
        ledger.register_unit(loan)
    """
    # Validate loan_amount
    if loan_amount <= 0:
        raise ValueError(f"loan_amount must be positive, got {loan_amount}")

    # Validate interest_rate
    if interest_rate < 0:
        raise ValueError(f"interest_rate cannot be negative, got {interest_rate}")

    # Validate margin requirements
    if initial_margin <= 0:
        raise ValueError(f"initial_margin must be positive, got {initial_margin}")
    if maintenance_margin <= 0:
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
        if haircut < 0 or haircut > 1:
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
        if qty < 0:
            raise ValueError(
                f"collateral quantity for {asset} cannot be negative, got {qty}"
            )

    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_MARGIN_LOAN,
        min_balance=-1.0,  # Only borrower (-1) and lender (+1) positions
        max_balance=1.0,
        decimal_places=0,  # Loan is a single unit
        transfer_rule=None,
        _state={
            'loan_amount': loan_amount,
            'interest_rate': interest_rate,
            'accrued_interest': 0.0,
            'collateral': dict(collateral),
            'haircuts': dict(haircuts),
            'initial_margin': initial_margin,
            'maintenance_margin': maintenance_margin,
            'borrower_wallet': borrower_wallet,
            'lender_wallet': lender_wallet,
            'currency': currency,
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
            'margin_call_deadline_days': margin_call_deadline_days,
            'liquidated': False,
            'origination_date': origination_date,
            'last_accrual_date': origination_date,
            'total_interest_paid': 0.0,
            'total_principal_paid': 0.0,
        }
    )


# ============================================================================
# COLLATERAL VALUE CALCULATION
# ============================================================================

def compute_collateral_value(
    view: LedgerView,
    loan_symbol: str,
    prices: PriceDict,
) -> float:
    """
    Calculate the haircut-adjusted collateral value.

    The collateral value is the sum of each asset's market value multiplied
    by its haircut factor. This gives the "credit value" of the collateral
    that can be borrowed against.

    Args:
        view: Read-only ledger access
        loan_symbol: Symbol of the margin loan unit
        prices: Dictionary mapping asset symbols to current market prices

    Returns:
        Total haircut-adjusted collateral value in loan currency.
        Missing prices are treated as zero (asset not counted).

    Example:
        # Collateral: 1000 AAPL @ $150, haircut 0.70
        # Collateral: 500 MSFT @ $300, haircut 0.75
        # Value = 1000 * 150 * 0.70 + 500 * 300 * 0.75
        #       = 105,000 + 112,500 = 217,500
        value = compute_collateral_value(view, "LOAN_001", prices)
    """
    state = view.get_unit_state(loan_symbol)
    collateral = state.get('collateral', {})
    haircuts = state.get('haircuts', {})

    total_value = 0.0
    for asset, quantity in collateral.items():
        price = prices.get(asset, 0.0)
        haircut = haircuts.get(asset, 0.0)
        asset_value = quantity * price * haircut
        total_value += asset_value

    return total_value


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

    This function calculates the margin ratio (collateral value / total debt)
    and determines if the loan is healthy, in warning territory, or in breach
    of margin requirements.

    IMPORTANT - Race Condition Prevention:
        This function includes pending interest accrued since the last
        accrual date in the total_debt calculation. This prevents the
        margin call timing vs accrual race condition where:

        1. EOD margin check runs with stale accrued_interest
        2. Overnight interest accrues
        3. Next morning actual ratio is in breach

        By calculating pending interest internally, the margin status
        always reflects the true debt position at view.current_time.

        Callers should still run compute_interest_accrual() to persist
        the accrued interest to state, but margin checks will be accurate
        even if accrual has not been persisted yet.

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
    state = view.get_unit_state(loan_symbol)

    # Check if liquidated
    if state.get('liquidated', False):
        return {
            'collateral_value': 0.0,
            'total_debt': 0.0,
            'margin_ratio': 0.0,
            'initial_margin': state.get('initial_margin', 0.0),
            'maintenance_margin': state.get('maintenance_margin', 0.0),
            'status': MARGIN_STATUS_LIQUIDATION,
            'shortfall': 0.0,
            'excess': 0.0,
            'pending_interest': 0.0,
        }

    loan_amount = state.get('loan_amount', 0.0)
    accrued_interest = state.get('accrued_interest', 0.0)
    initial_margin = state.get('initial_margin', 1.5)
    maintenance_margin = state.get('maintenance_margin', 1.25)
    interest_rate = state.get('interest_rate', 0.0)
    last_accrual_date = state.get('last_accrual_date')

    # Calculate pending interest since last accrual to prevent race condition
    # where margin check runs before interest accrual is persisted
    pending_interest = 0.0
    if (
        last_accrual_date is not None
        and view.current_time is not None
        and loan_amount > QUANTITY_EPSILON
        and interest_rate > 0
    ):
        time_delta = view.current_time - last_accrual_date
        days_elapsed = time_delta.total_seconds() / 86400.0
        if days_elapsed > 0:
            pending_interest = loan_amount * (interest_rate / 365.0) * days_elapsed

    # Calculate values
    collateral_value = compute_collateral_value(view, loan_symbol, prices)
    total_debt = loan_amount + accrued_interest + pending_interest

    # Handle zero debt case
    if total_debt < QUANTITY_EPSILON:
        return {
            'collateral_value': collateral_value,
            'total_debt': 0.0,
            'margin_ratio': float('inf'),
            'initial_margin': initial_margin,
            'maintenance_margin': maintenance_margin,
            'status': MARGIN_STATUS_HEALTHY,
            'shortfall': 0.0,
            'excess': collateral_value,
            'pending_interest': 0.0,
        }

    margin_ratio = collateral_value / total_debt

    # Determine status
    if margin_ratio >= initial_margin:
        status = MARGIN_STATUS_HEALTHY
        shortfall = 0.0
        excess = collateral_value - (maintenance_margin * total_debt)
    elif margin_ratio >= maintenance_margin:
        status = MARGIN_STATUS_WARNING
        shortfall = 0.0
        excess = collateral_value - (maintenance_margin * total_debt)
    else:
        # Check if margin call deadline has passed
        margin_call_deadline = state.get('margin_call_deadline')
        if margin_call_deadline and view.current_time >= margin_call_deadline:
            status = MARGIN_STATUS_LIQUIDATION
        else:
            status = MARGIN_STATUS_BREACH
        shortfall = (maintenance_margin * total_debt) - collateral_value
        excess = 0.0

    return {
        'collateral_value': collateral_value,
        'total_debt': total_debt,
        'margin_ratio': margin_ratio,
        'initial_margin': initial_margin,
        'maintenance_margin': maintenance_margin,
        'status': status,
        'shortfall': shortfall,
        'excess': excess,
        'pending_interest': pending_interest,
    }


# ============================================================================
# INTEREST ACCRUAL
# ============================================================================

def compute_interest_accrual(
    view: LedgerView,
    loan_symbol: str,
    days: float,
) -> ContractResult:
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
        ContractResult with state updates (no moves).
        Returns empty result if loan is liquidated or days <= 0.

    Raises:
        ValueError: If days is negative.

    Example:
        # Accrue 30 days of interest on $100,000 @ 8%
        # Interest = 100000 * 0.08 / 365 * 30 = $657.53
        result = compute_interest_accrual(view, "LOAN_001", 30)
        ledger.execute_contract(result)
    """
    if days < 0:
        raise ValueError(f"days cannot be negative, got {days}")

    if days < QUANTITY_EPSILON:
        return ContractResult()

    state = view.get_unit_state(loan_symbol)

    if state.get('liquidated', False):
        return ContractResult()

    loan_amount = state.get('loan_amount', 0.0)
    if loan_amount < QUANTITY_EPSILON:
        return ContractResult()  # No loan to accrue on

    interest_rate = state.get('interest_rate', 0.0)
    current_accrued = state.get('accrued_interest', 0.0)

    # Simple interest calculation: P * r * t (annual rate / 365 for daily)
    new_interest = loan_amount * (interest_rate / 365.0) * days
    total_accrued = current_accrued + new_interest

    state_updates = {
        loan_symbol: {
            **state,
            'accrued_interest': total_accrued,
            'last_accrual_date': view.current_time,
        }
    }

    return ContractResult(moves=(), state_updates=state_updates)


# ============================================================================
# MARGIN CALL
# ============================================================================

def compute_margin_call(
    view: LedgerView,
    loan_symbol: str,
    prices: PriceDict,
) -> ContractResult:
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
        ContractResult with state updates setting margin_call_amount and
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
        return ContractResult()

    # Already has an active margin call
    if state.get('margin_call_deadline') is not None:
        return ContractResult()

    margin_status = compute_margin_status(view, loan_symbol, prices)

    if margin_status['status'] not in (MARGIN_STATUS_BREACH, MARGIN_STATUS_LIQUIDATION):
        return ContractResult()

    shortfall = margin_status['shortfall']
    deadline_days = state.get('margin_call_deadline_days', 3)
    deadline = view.current_time + timedelta(days=deadline_days)

    state_updates = {
        loan_symbol: {
            **state,
            'margin_call_amount': shortfall,
            'margin_call_deadline': deadline,
        }
    }

    return ContractResult(moves=(), state_updates=state_updates)


# ============================================================================
# MARGIN CURE
# ============================================================================

def compute_margin_cure(
    view: LedgerView,
    loan_symbol: str,
    cure_amount: float,
    prices: Optional[PriceDict] = None,
) -> ContractResult:
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
        ContractResult with:
        - moves: Cash transfer from borrower to lender
        - state_updates: Reduced debt and potentially cleared margin call

    Raises:
        ValueError: If cure_amount <= 0 or exceeds total debt.

    Example:
        # Cure margin call with $10,000 payment
        result = compute_margin_cure(view, "LOAN_001", 10000.0)
        ledger.execute_contract(result)
    """
    if cure_amount <= 0:
        raise ValueError(f"cure_amount must be positive, got {cure_amount}")

    state = view.get_unit_state(loan_symbol)

    if state.get('liquidated', False):
        raise ValueError("Cannot cure a liquidated loan")

    loan_amount = state.get('loan_amount', 0.0)
    accrued_interest = state.get('accrued_interest', 0.0)
    total_debt = loan_amount + accrued_interest

    if cure_amount > total_debt + QUANTITY_EPSILON:
        raise ValueError(
            f"cure_amount ({cure_amount}) exceeds total_debt ({total_debt})"
        )

    borrower = state['borrower_wallet']
    lender = state['lender_wallet']
    currency = state['currency']

    # Apply payment: first to accrued interest, then to principal
    interest_payment = min(cure_amount, accrued_interest)
    principal_payment = cure_amount - interest_payment

    new_accrued = accrued_interest - interest_payment
    new_loan_amount = loan_amount - principal_payment
    total_interest_paid = state.get('total_interest_paid', 0.0) + interest_payment
    total_principal_paid = state.get('total_principal_paid', 0.0) + principal_payment

    # Generate cash move
    moves = [
        Move(
            source=borrower,
            dest=lender,
            unit=currency,
            quantity=cure_amount,
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
    }

    # If cure brings debt to zero, clear margin call
    if new_loan_amount + new_accrued < QUANTITY_EPSILON:
        new_state['margin_call_amount'] = 0.0
        new_state['margin_call_deadline'] = None
    elif prices is not None:
        # Check if margin is restored
        # Create a temporary state to check margin status
        temp_state = dict(new_state)
        # We need to manually compute since we can't update the view
        collateral_value = 0.0
        collateral = temp_state.get('collateral', {})
        haircuts = temp_state.get('haircuts', {})
        for asset, quantity in collateral.items():
            price = prices.get(asset, 0.0)
            haircut = haircuts.get(asset, 0.0)
            collateral_value += quantity * price * haircut

        new_total_debt = new_loan_amount + new_accrued
        if new_total_debt > QUANTITY_EPSILON:
            margin_ratio = collateral_value / new_total_debt
            maintenance_margin = temp_state.get('maintenance_margin', 1.25)
            if margin_ratio >= maintenance_margin:
                new_state['margin_call_amount'] = 0.0
                new_state['margin_call_deadline'] = None
    else:
        # Clear margin call if it was paid down significantly
        # (caller should verify with prices)
        if new_state.get('margin_call_amount', 0.0) > 0:
            new_margin_call = max(0, new_state['margin_call_amount'] - cure_amount)
            new_state['margin_call_amount'] = new_margin_call
            if new_margin_call < QUANTITY_EPSILON:
                new_state['margin_call_deadline'] = None

    state_updates = {loan_symbol: new_state}

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


# ============================================================================
# LIQUIDATION
# ============================================================================

def compute_liquidation(
    view: LedgerView,
    loan_symbol: str,
    prices: PriceDict,
    sale_proceeds: float,
) -> ContractResult:
    """
    Liquidate the loan by selling collateral and settling the debt.

    When a margin call is not cured by the deadline, the lender liquidates
    the collateral to recover the debt. The sale_proceeds are applied to
    the debt, and any surplus is returned to the borrower.

    Args:
        view: Read-only ledger access
        loan_symbol: Symbol of the margin loan unit
        prices: Dictionary mapping asset symbols to liquidation prices
        sale_proceeds: Total cash received from selling collateral

    Returns:
        ContractResult with:
        - moves: Cash flows for debt settlement and any surplus to borrower
        - state_updates: Marks loan as liquidated, clears collateral

    Raises:
        ValueError: If loan not in liquidation status or already liquidated,
                    or if sale_proceeds is negative.

    Example:
        # Liquidate collateral that sold for $80,000
        result = compute_liquidation(view, "LOAN_001", prices, 80000.0)
        ledger.execute_contract(result)
        # Debt paid from proceeds, any surplus to borrower
    """
    if sale_proceeds < 0:
        raise ValueError(f"sale_proceeds cannot be negative, got {sale_proceeds}")

    state = view.get_unit_state(loan_symbol)

    if state.get('liquidated', False):
        raise ValueError("Loan is already liquidated")

    margin_status = compute_margin_status(view, loan_symbol, prices)

    # Allow liquidation if in breach/liquidation status or if explicitly forced
    # (In practice, should verify margin_call_deadline has passed)
    if margin_status['status'] not in (MARGIN_STATUS_BREACH, MARGIN_STATUS_LIQUIDATION):
        # Check if deadline has passed
        deadline = state.get('margin_call_deadline')
        if deadline is None or view.current_time < deadline:
            raise ValueError(
                "Cannot liquidate: loan is not in liquidation status"
            )

    borrower = state['borrower_wallet']
    lender = state['lender_wallet']
    currency = state['currency']
    loan_amount = state.get('loan_amount', 0.0)
    accrued_interest = state.get('accrued_interest', 0.0)
    total_debt = loan_amount + accrued_interest

    moves: List[Move] = []

    if sale_proceeds >= total_debt:
        # Full debt recovery
        if total_debt > QUANTITY_EPSILON:
            moves.append(Move(
                source=borrower,
                dest=lender,
                unit=currency,
                quantity=total_debt,
                contract_id=f'liquidation_debt_{loan_symbol}',
            ))

        # Surplus to borrower (conceptually from lender who held proceeds)
        surplus = sale_proceeds - total_debt
        if surplus > QUANTITY_EPSILON:
            moves.append(Move(
                source=lender,
                dest=borrower,
                unit=currency,
                quantity=surplus,
                contract_id=f'liquidation_surplus_{loan_symbol}',
            ))
    else:
        # Partial debt recovery - shortfall becomes bad debt (tracked as deficiency)
        if sale_proceeds > QUANTITY_EPSILON:
            moves.append(Move(
                source=borrower,
                dest=lender,
                unit=currency,
                quantity=sale_proceeds,
                contract_id=f'liquidation_partial_{loan_symbol}',
            ))

    # Mark as liquidated
    # IMPORTANT: Always zero out loan_amount and accrued_interest on liquidation.
    # Any deficiency (sale_proceeds < total_debt) is tracked as bad_debt, not as
    # outstanding loan balances. This prevents phantom debt from accruing interest
    # if compute_interest_accrual() is called after liquidation.
    deficiency = max(0.0, total_debt - sale_proceeds)
    state_updates = {
        loan_symbol: {
            **state,
            'loan_amount': 0.0,
            'accrued_interest': 0.0,
            'collateral': {},  # Collateral has been sold
            'liquidated': True,
            'liquidation_date': view.current_time,
            'liquidation_proceeds': sale_proceeds,
            'liquidation_deficiency': deficiency,  # Track bad debt separately
            'margin_call_amount': 0.0,
            'margin_call_deadline': None,
        }
    }

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


# ============================================================================
# REPAYMENT
# ============================================================================

def compute_repayment(
    view: LedgerView,
    loan_symbol: str,
    repayment_amount: float,
) -> ContractResult:
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
        ContractResult with:
        - moves: Cash transfer from borrower to lender
        - state_updates: Reduced loan_amount and accrued_interest

    Raises:
        ValueError: If repayment_amount <= 0 or exceeds total debt,
                    or if loan is already liquidated.

    Example:
        # Full repayment of $100,000 loan + $500 interest
        result = compute_repayment(view, "LOAN_001", 100500.0)
        ledger.execute_contract(result)
    """
    if repayment_amount <= 0:
        raise ValueError(f"repayment_amount must be positive, got {repayment_amount}")

    state = view.get_unit_state(loan_symbol)

    if state.get('liquidated', False):
        raise ValueError("Cannot repay a liquidated loan")

    loan_amount = state.get('loan_amount', 0.0)
    accrued_interest = state.get('accrued_interest', 0.0)
    total_debt = loan_amount + accrued_interest

    if total_debt < QUANTITY_EPSILON:
        raise ValueError("No outstanding debt to repay")

    if repayment_amount > total_debt + QUANTITY_EPSILON:
        raise ValueError(
            f"repayment_amount ({repayment_amount}) exceeds total_debt ({total_debt})"
        )

    borrower = state['borrower_wallet']
    lender = state['lender_wallet']
    currency = state['currency']

    # Apply payment: first to accrued interest, then to principal
    interest_payment = min(repayment_amount, accrued_interest)
    principal_payment = repayment_amount - interest_payment

    new_accrued = accrued_interest - interest_payment
    new_loan_amount = loan_amount - principal_payment
    total_interest_paid = state.get('total_interest_paid', 0.0) + interest_payment
    total_principal_paid = state.get('total_principal_paid', 0.0) + principal_payment

    # Generate cash move
    moves = [
        Move(
            source=borrower,
            dest=lender,
            unit=currency,
            quantity=repayment_amount,
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
    }

    # Clear margin call if loan is fully repaid
    if new_loan_amount + new_accrued < QUANTITY_EPSILON:
        new_state['margin_call_amount'] = 0.0
        new_state['margin_call_deadline'] = None

    state_updates = {loan_symbol: new_state}

    return ContractResult(moves=tuple(moves), state_updates=state_updates)


# ============================================================================
# ADD COLLATERAL
# ============================================================================

def compute_add_collateral(
    view: LedgerView,
    loan_symbol: str,
    asset: str,
    quantity: float,
    prices: Optional[PriceDict] = None,
) -> ContractResult:
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
        ContractResult with state updates adding to collateral pool.
        Does not generate moves (asset transfer handled separately).

    Raises:
        ValueError: If quantity <= 0, asset has no haircut defined,
                    or loan is liquidated.

    Example:
        # Pledge 500 additional shares of AAPL
        result = compute_add_collateral(view, "LOAN_001", "AAPL", 500)
        ledger.execute_contract(result)
    """
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")

    state = view.get_unit_state(loan_symbol)

    if state.get('liquidated', False):
        raise ValueError("Cannot add collateral to a liquidated loan")

    haircuts = state.get('haircuts', {})
    if asset not in haircuts:
        raise ValueError(f"No haircut defined for asset {asset}")

    collateral = dict(state.get('collateral', {}))
    current_qty = collateral.get(asset, 0.0)
    collateral[asset] = current_qty + quantity

    new_state = {
        **state,
        'collateral': collateral,
    }

    # Check if margin call is cured
    if prices is not None and state.get('margin_call_deadline') is not None:
        collateral_value = 0.0
        for a, q in collateral.items():
            price = prices.get(a, 0.0)
            haircut = haircuts.get(a, 0.0)
            collateral_value += q * price * haircut

        loan_amount = state.get('loan_amount', 0.0)
        accrued_interest = state.get('accrued_interest', 0.0)
        total_debt = loan_amount + accrued_interest

        if total_debt > QUANTITY_EPSILON:
            margin_ratio = collateral_value / total_debt
            maintenance_margin = state.get('maintenance_margin', 1.25)
            if margin_ratio >= maintenance_margin:
                new_state['margin_call_amount'] = 0.0
                new_state['margin_call_deadline'] = None

    state_updates = {loan_symbol: new_state}

    return ContractResult(moves=(), state_updates=state_updates)


# ============================================================================
# TRANSACTION INTERFACE
# ============================================================================

def transact(
    view: LedgerView,
    symbol: str,
    event_type: str,
    event_date: datetime,
    **kwargs
) -> ContractResult:
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
        ContractResult with moves and state_updates, or empty result
        if event_type is unknown or required parameters are missing.

    Example:
        # Accrue 30 days of interest
        result = transact(view, "LOAN_001", "INTEREST_ACCRUAL", event_date, days=30)

        # Check for margin call
        result = transact(view, "LOAN_001", "MARGIN_CALL", event_date, prices=prices)

        # Cure margin call
        result = transact(view, "LOAN_001", "MARGIN_CURE", event_date, cure_amount=10000)

        # Full repayment
        result = transact(view, "LOAN_001", "REPAYMENT", event_date, repayment_amount=100500)
    """
    if event_type == 'INTEREST_ACCRUAL':
        days = kwargs.get('days')
        if days is None:
            return ContractResult()
        return compute_interest_accrual(view, symbol, days)

    elif event_type == 'MARGIN_CALL':
        prices = kwargs.get('prices')
        if prices is None:
            return ContractResult()
        return compute_margin_call(view, symbol, prices)

    elif event_type == 'MARGIN_CURE':
        cure_amount = kwargs.get('cure_amount')
        if cure_amount is None:
            return ContractResult()
        prices = kwargs.get('prices')
        return compute_margin_cure(view, symbol, cure_amount, prices)

    elif event_type == 'LIQUIDATION':
        prices = kwargs.get('prices')
        sale_proceeds = kwargs.get('sale_proceeds')
        if prices is None or sale_proceeds is None:
            return ContractResult()
        return compute_liquidation(view, symbol, prices, sale_proceeds)

    elif event_type == 'REPAYMENT':
        repayment_amount = kwargs.get('repayment_amount')
        if repayment_amount is None:
            return ContractResult()
        return compute_repayment(view, symbol, repayment_amount)

    elif event_type == 'ADD_COLLATERAL':
        asset = kwargs.get('asset')
        quantity = kwargs.get('quantity')
        if asset is None or quantity is None:
            return ContractResult()
        prices = kwargs.get('prices')
        return compute_add_collateral(view, symbol, asset, quantity, prices)

    else:
        return ContractResult()  # Unknown event type


# ============================================================================
# SMART CONTRACT
# ============================================================================

def margin_loan_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, float]
) -> ContractResult:
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
        ContractResult with margin call if loan is below maintenance,
        or empty result if loan is healthy or already has active margin call.
    """
    state = view.get_unit_state(symbol)

    if state.get('liquidated', False):
        return ContractResult()

    # Check if we should issue a margin call
    if state.get('margin_call_deadline') is None:
        # No active margin call - check if we need to issue one
        return compute_margin_call(view, symbol, prices)

    return ContractResult()
