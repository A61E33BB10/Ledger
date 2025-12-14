"""
bond.py - Bond Unit with Coupon Processing and Redemption

A Bond has:
    face_value, coupon_schedule (List[Coupon]), maturity_date, currency,
    issuer_wallet, issue_date, day_count_convention

On coupon payment_date: Create DeferredCash units for each bondholder
On maturity_date: Pay face_value directly (no DeferredCash)

Dirty Price = Clean Price + Accrued Interest

~300 lines. One file. No unnecessary abstractions.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date
from typing import Dict, List, Tuple, FrozenSet
from decimal import Decimal
import math

from ..core import (
    LedgerView, Move, PendingTransaction, Unit, UnitStateChange,
    build_transaction, empty_pending_transaction,
    UNIT_TYPE_BOND, QUANTITY_EPSILON, SYSTEM_WALLET,
    _freeze_state,
)
from .deferred_cash import create_deferred_cash_unit


# =============================================================================
# COUPON DATACLASS
# =============================================================================

@dataclass(frozen=True, slots=True)
class Coupon:
    """A scheduled coupon payment."""
    payment_date: datetime
    amount: Decimal  # per bond
    currency: str

    def __post_init__(self):
        # Convert amount to Decimal if it's not already
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
        if self.amount <= Decimal("0"):
            raise ValueError("amount must be positive")

    @property
    def key(self) -> str:
        return self.payment_date.date().isoformat()


# =============================================================================
# PURE FUNCTIONS
# =============================================================================

def year_fraction(start: date, end: date, convention: str) -> Decimal:
    """
    Calculate year fraction. Supports: "30/360", "ACT/360", "ACT/365".
    """
    if convention == "30/360":
        y1, m1, d1 = start.year, start.month, min(start.day, 30)
        y2, m2, d2 = end.year, end.month, min(end.day, 30)
        days = 360 * (y2 - y1) + 30 * (m2 - m1) + (d2 - d1)
        return Decimal(days) / Decimal("360")
    elif convention == "ACT/360":
        return Decimal((end - start).days) / Decimal("360")
    elif convention == "ACT/365":
        return Decimal((end - start).days) / Decimal("365")
    else:
        raise ValueError(f"Unknown day count convention: {convention}")


def compute_accrued_interest(
    coupon_amount: Decimal,
    last_coupon_date: date,
    next_coupon_date: date,
    settlement_date: date,
    day_count_convention: str,
) -> Decimal:
    """Accrued = coupon_amount * (days since last / days in period)."""
    # Ensure coupon_amount is Decimal
    coupon_amount = Decimal(str(coupon_amount))

    if settlement_date <= last_coupon_date:
        return Decimal("0")
    if settlement_date >= next_coupon_date:
        return coupon_amount

    accrued_frac = year_fraction(last_coupon_date, settlement_date, day_count_convention)
    period_frac = year_fraction(last_coupon_date, next_coupon_date, day_count_convention)

    if period_frac < Decimal(str(QUANTITY_EPSILON)):
        return Decimal("0")
    return coupon_amount * (accrued_frac / period_frac)


# =============================================================================
# COUPON ENTITLEMENT
# =============================================================================

@dataclass(frozen=True, slots=True)
class CouponEntitlement:
    """Instruction to create a DeferredCash unit for a coupon payment."""
    symbol: str
    amount: Decimal
    currency: str
    payment_date: datetime
    payer_wallet: str
    payee_wallet: str


def compute_coupon_entitlements(
    coupon: Coupon,
    today: date,
    positions: Dict[str, Decimal],
    processed: FrozenSet[str],
    issuer: str,
    bond_symbol: str,
) -> Tuple[List[CouponEntitlement], FrozenSet[str]]:
    """Compute coupon entitlements on payment_date. Pure function."""
    coupon_key = coupon.key

    if coupon_key in processed:
        return [], processed
    if today < coupon.payment_date.date():
        return [], processed

    # Ensure coupon amount is Decimal
    coupon_amount = Decimal(str(coupon.amount))

    entitlements = []
    for wallet, quantity in sorted(positions.items()):
        if wallet == issuer or quantity <= Decimal(str(QUANTITY_EPSILON)):
            continue
        entitlements.append(CouponEntitlement(
            symbol=f"COUPON_{bond_symbol}_{coupon_key}_{wallet}",
            amount=quantity * coupon_amount,
            currency=coupon.currency,
            payment_date=coupon.payment_date,
            payer_wallet=issuer,
            payee_wallet=wallet,
        ))

    return entitlements, processed | {coupon_key}


# =============================================================================
# UNIT CREATION
# =============================================================================

def create_bond_unit(
    symbol: str,
    name: str,
    face_value: Decimal,
    maturity_date: datetime,
    currency: str,
    issuer_wallet: str,
    issue_date: datetime,
    coupon_schedule: List[Coupon],
    day_count_convention: str = "30/360",
) -> Unit:
    """Create a bond unit. coupon_schedule is REQUIRED (no auto-generation)."""
    # Convert face_value to Decimal if it's not already
    if not isinstance(face_value, Decimal):
        face_value = Decimal(str(face_value))

    if face_value <= Decimal("0"):
        raise ValueError(f"face_value must be positive, got {face_value}")
    if not issuer_wallet or not issuer_wallet.strip():
        raise ValueError("issuer_wallet cannot be empty")
    if day_count_convention not in ("30/360", "ACT/360", "ACT/365"):
        raise ValueError(f"Unknown day_count_convention: {day_count_convention}")

    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_BOND,
        min_balance=Decimal("0"),
        max_balance=Decimal('inf'),
        decimal_places=6,
        _frozen_state=_freeze_state({
            'face_value': face_value,
            'coupon_schedule': coupon_schedule,
            'maturity_date': maturity_date,
            'currency': currency,
            'issuer_wallet': issuer_wallet,
            'issue_date': issue_date,
            'day_count_convention': day_count_convention,
            'next_coupon_index': 0,
            'processed_coupons': [],
            'redeemed': False,
        })
    )


# =============================================================================
# LIFECYCLE FUNCTIONS
# =============================================================================

def process_coupons(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
) -> PendingTransaction:
    """Process coupons: create DeferredCash entitlements for each bondholder."""
    state = view.get_unit_state(symbol)

    if state.get('redeemed'):
        return empty_pending_transaction(view)

    schedule: List[Coupon] = state.get('coupon_schedule', [])
    if not schedule:
        return empty_pending_transaction(view)

    issuer = state.get('issuer_wallet')
    if not issuer:
        raise ValueError(f"Bond {symbol} has no issuer_wallet defined")

    positions = view.get_positions(symbol)
    today = timestamp.date()
    processed = frozenset(state.get('processed_coupons', []))

    all_entitlements: List[CouponEntitlement] = []
    new_processed = processed

    for coupon in schedule:
        entitlements, new_processed = compute_coupon_entitlements(
            coupon, today, positions, new_processed, issuer, symbol
        )
        all_entitlements.extend(entitlements)

    if not all_entitlements:
        return empty_pending_transaction(view)

    moves: List[Move] = []
    units_to_create: List[Unit] = []

    for ent in all_entitlements:
        dc_unit = create_deferred_cash_unit(
            symbol=ent.symbol,
            amount=ent.amount,
            currency=ent.currency,
            payment_date=ent.payment_date,
            payer_wallet=ent.payer_wallet,
            payee_wallet=ent.payee_wallet,
            reference=f"{symbol}_coupon_{ent.symbol}",
        )
        units_to_create.append(dc_unit)
        moves.append(Move(
            quantity=Decimal("1"),
            unit_symbol=ent.symbol,
            source=SYSTEM_WALLET,
            dest=ent.payee_wallet,
            contract_id=f'coupon_entitlement_{ent.symbol}',
        ))

    new_state = {**state, 'processed_coupons': list(new_processed)}
    state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes, units_to_create=tuple(units_to_create))


def compute_redemption(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
) -> PendingTransaction:
    """Redeem bond at maturity - pay face_value directly (no DeferredCash)."""
    state = view.get_unit_state(symbol)

    if state.get('redeemed'):
        return empty_pending_transaction(view)

    maturity = state['maturity_date']
    if timestamp < maturity:
        return empty_pending_transaction(view)

    face_value = Decimal(str(state['face_value']))
    currency = state['currency']
    issuer = state['issuer_wallet']
    positions = view.get_positions(symbol)

    moves: List[Move] = []
    for wallet, quantity in sorted(positions.items()):
        if wallet == issuer or quantity <= Decimal(str(QUANTITY_EPSILON)):
            continue
        moves.append(Move(
            quantity=quantity * face_value,
            unit_symbol=currency,
            source=issuer,
            dest=wallet,
            contract_id=f'bond_redemption_{symbol}_{wallet}',
        ))

    if not moves:
        return empty_pending_transaction(view)

    new_state = {**state, 'redeemed': True}
    state_changes = [UnitStateChange(unit=symbol, old_state=state, new_state=new_state)]

    return build_transaction(view, moves, state_changes)


# =============================================================================
# TRADING
# =============================================================================

def transact(
    view: LedgerView,
    symbol: str,
    seller: str,
    buyer: str,
    qty: Decimal,
    clean_price: Decimal,
) -> PendingTransaction:
    """Execute a bond trade at dirty price (clean + accrued interest)."""
    # Ensure parameters are Decimal
    qty = Decimal(str(qty))
    clean_price = Decimal(str(clean_price))

    if qty <= Decimal("0"):
        raise ValueError(f"qty must be positive, got {qty}")
    if clean_price.is_infinite() or clean_price.is_nan() or clean_price <= Decimal("0"):
        raise ValueError(f"clean_price must be positive and finite, got {clean_price}")
    if seller == buyer:
        raise ValueError("seller and buyer must be different")

    state = view.get_unit_state(symbol)
    currency = state['currency']
    coupon_schedule: List[Coupon] = state.get('coupon_schedule', [])
    day_count = state.get('day_count_convention', '30/360')
    issue_date: datetime = state['issue_date']
    settlement_date = view.current_time.date()

    # Find last and next coupon dates
    last_coupon_date = issue_date.date()
    next_coupon_date = None
    next_coupon_amount = Decimal("0")

    for coupon in coupon_schedule:
        cpn_date = coupon.payment_date.date()
        if cpn_date <= settlement_date:
            last_coupon_date = cpn_date
        elif next_coupon_date is None:
            next_coupon_date = cpn_date
            next_coupon_amount = Decimal(str(coupon.amount))

    # Calculate accrued interest
    if next_coupon_date and next_coupon_amount > Decimal("0"):
        accrued = compute_accrued_interest(
            next_coupon_amount, last_coupon_date, next_coupon_date,
            settlement_date, day_count
        )
    else:
        accrued = Decimal("0")

    dirty_price = clean_price + accrued
    total_payment = qty * dirty_price

    # Check seller has enough bonds
    unit = view.get_unit(symbol)
    seller_balance = view.get_balance(seller, symbol)
    if seller_balance - qty < unit.min_balance - Decimal(str(QUANTITY_EPSILON)):
        raise ValueError(f"Insufficient bonds: {seller} has {seller_balance}, needs {qty}")

    moves = [
        Move(qty, symbol, seller, buyer, f'bond_{symbol}_bonds'),
        Move(total_payment, currency, buyer, seller, f'bond_{symbol}_cash'),
    ]
    return build_transaction(view, moves)


# =============================================================================
# SMART CONTRACT
# =============================================================================

def bond_contract(
    view: LedgerView,
    symbol: str,
    timestamp: datetime,
    prices: Dict[str, Decimal],
) -> PendingTransaction:
    """SmartContract for LifecycleEngine: process coupons and redemption."""
    state = view.get_unit_state(symbol)

    if state.get('redeemed'):
        return empty_pending_transaction(view)

    # Check maturity first
    if timestamp >= state['maturity_date']:
        return compute_redemption(view, symbol, timestamp)

    # Check coupons
    return process_coupons(view, symbol, timestamp)
