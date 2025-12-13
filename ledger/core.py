"""
Core types and pure functions for the financial ledger system.

This module provides the foundational data structures and protocols for the ledger:
1. Protocols: LedgerView for read-only ledger access
2. Immutable data structures: Move, PendingTransaction, Transaction, Unit
3. Exceptions: LedgerError and domain-specific error types
4. Type aliases: Positions, BalanceMap, UnitState
5. Transfer rules: Pure validation functions for moves
6. Unit factories: Functions to create standard unit types

All functions in this module are pure and operate on read-only views.
No function can mutate ledger state directly.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
from typing import (
    Dict, List, Set, Optional, Callable, Any, Protocol,
    Tuple, FrozenSet, runtime_checkable
)


# ============================================================================
# CONSTANTS
# ============================================================================

# Reserved wallet for issuance, redemption, and obligation lifecycle.
# The system wallet is exempt from balance validation and can hold any balance.
SYSTEM_WALLET = "system"

# Unit type constants (strings, not enum per design decision).
# These provide clarity and consistency without over-engineering.
UNIT_TYPE_CASH = "CASH"
UNIT_TYPE_STOCK = "STOCK"
UNIT_TYPE_BILATERAL_OPTION = "BILATERAL_OPTION"
UNIT_TYPE_BILATERAL_FORWARD = "BILATERAL_FORWARD"
UNIT_TYPE_DEFERRED_CASH = "DEFERRED_CASH"
UNIT_TYPE_DELTA_HEDGE_STRATEGY = "DELTA_HEDGE_STRATEGY"
UNIT_TYPE_BOND = "BOND"
UNIT_TYPE_FUTURE = "FUTURE"
# Phase 3 unit types
UNIT_TYPE_MARGIN_LOAN = "MARGIN_LOAN"
UNIT_TYPE_STRUCTURED_NOTE = "STRUCTURED_NOTE"
UNIT_TYPE_PORTFOLIO_SWAP = "PORTFOLIO_SWAP"
UNIT_TYPE_AUTOCALLABLE = "AUTOCALLABLE"

# SBL (Securities Borrowing and Lending) unit types
UNIT_TYPE_BORROW_RECORD = "BORROW_RECORD"
UNIT_TYPE_LOCATE = "LOCATE"

# QIS (Quantitative Investment Strategy)
UNIT_TYPE_QIS = "QIS"

# Epsilon for floating point comparisons.
# Quantities with absolute value below this threshold are treated as zero.
QUANTITY_EPSILON = 1e-12

# Default minimum balance for cash units (allows large overdrafts).
DEFAULT_CASH_MIN_BALANCE = -1_000_000_000.0

# Default minimum balance for stock units when short selling is enabled.
DEFAULT_STOCK_SHORT_MIN_BALANCE = -10_000_000.0

# Default decimal precision for stock quantities.
STOCK_DECIMAL_PLACES = 6


# ============================================================================
# TYPE ALIASES
# ============================================================================

# Mapping from wallet ID to quantity held by that wallet for a specific unit.
Positions = Dict[str, float]

# Mapping from unit symbol to quantity held in a single wallet.
BalanceMap = Dict[str, float]

# Internal state for a unit, containing term sheet data, lifecycle information, etc.
UnitState = Dict[str, Any]


# ============================================================================
# PROTOCOLS
# ============================================================================

@runtime_checkable
class LedgerView(Protocol):
    """
    Read-only interface to ledger state.

    This protocol defines the interface that contracts, transfer rules, and
    valuation functions use to query ledger state without the ability to modify it.
    Functions accepting a LedgerView parameter declare their read-only intent.

    This is a type-level guarantee enforced by static type checkers (mypy, pyright).
    Runtime enforcement depends on the implementing class. The Ledger class implements
    this protocol but also provides mutation methods. For testing, FakeView provides
    a truly immutable implementation.
    """

    @property
    def current_time(self) -> datetime:
        """Return the current logical time of the ledger."""
        ...

    def get_balance(self, wallet_id: str, unit_symbol: str) -> float:
        """
        Return the balance of a specific unit in a wallet.

        Returns 0.0 if the wallet or unit does not exist.
        """
        ...

    def get_unit_state(self, unit_symbol: str) -> UnitState:
        """
        Return a copy of the unit's internal state.

        The state dictionary contains term sheet data, lifecycle information,
        and any other unit-specific metadata.
        """
        ...

    def get_positions(self, unit_symbol: str) -> Positions:
        """
        Return all non-zero positions for a unit across all wallets.

        Returns a dictionary mapping wallet IDs to quantities.
        """
        ...

    def list_wallets(self) -> Set[str]:
        """Return the set of all registered wallet IDs."""
        ...

    def get_unit(self, symbol: str) -> 'Unit':
        """Return the Unit object for a given symbol."""
        ...


class SmartContract(Protocol):
    """
    Protocol for lifecycle-aware contracts.

    Contracts check if any events should fire based on:
    - Current time
    - Current prices
    - Unit state

    Contracts receive a LedgerView and return a PendingTransaction directly.
    Use build_transaction() or empty_pending_transaction() to create the return value.
    """

    def check_lifecycle(
        self,
        view: LedgerView,
        symbol: str,
        timestamp: datetime,
        prices: Dict[str, float]
    ) -> 'PendingTransaction':
        """
        Check if lifecycle events should fire.

        Args:
            view: Read-only ledger access
            symbol: Unit symbol to check
            timestamp: Current timestamp
            prices: Current market prices

        Returns:
            PendingTransaction with moves/state updates, or empty if nothing to do.
        """
        ...


# ============================================================================
# ENUMS
# ============================================================================

class ExecuteResult(Enum):
    """
    Outcome of a transaction execution attempt.

    APPLIED: Transaction was successfully validated and applied to the ledger.
    ALREADY_APPLIED: Transaction ID was previously processed (idempotent behavior).
    REJECTED: Transaction failed validation due to insufficient funds, balance
              constraints, or transfer rule violations.
    """
    APPLIED = "applied"
    ALREADY_APPLIED = "already_applied"
    REJECTED = "rejected"


class OriginType(Enum):
    """
    Classification of where a transaction originated.

    Used for audit trails, reconciliation, and regulatory compliance.
    """
    USER_ACTION = "user_action"           # Manual user-initiated transaction
    CONTRACT = "contract"                 # Unit contract (trade execution)
    LIFECYCLE = "lifecycle"               # Automatic lifecycle event (expiry, coupon, etc.)
    SYSTEM = "system"                     # System operations (issuance, initial setup)
    EXTERNAL = "external"                 # External system integration


# ============================================================================
# EXCEPTIONS
# ============================================================================

class LedgerError(Exception):
    """Base exception for all ledger-related errors."""
    pass


class InsufficientFunds(LedgerError):
    """Raised when a move would cause a wallet balance to fall below the unit's minimum."""
    pass


class BalanceConstraintViolation(LedgerError):
    """Raised when a move would cause a wallet balance to violate the unit's min/max constraints."""
    pass


class TransferRuleViolation(LedgerError):
    """Raised when a move violates the unit's transfer rule."""
    pass


class UnitNotRegistered(LedgerError):
    """Raised when attempting to operate on a unit that has not been registered with the ledger."""
    pass


class WalletNotRegistered(LedgerError):
    """Raised when attempting to operate on a wallet that has not been registered with the ledger."""
    pass


# ============================================================================
# TRANSACTION ORIGIN
# ============================================================================

@dataclass(frozen=True, slots=True)
class TransactionOrigin:
    """
    Immutable record of a transaction's origin for audit purposes.

    This structured type captures the provenance of every transaction,
    enabling audit trails, reconciliation, and regulatory compliance.

    Attributes:
        origin_type: Classification of the origin source (USER, CONTRACT, LIFECYCLE, etc.)
        source_id: Identifier of the specific source (contract name, user ID, etc.)
        unit_symbol: Symbol of the unit that triggered this (if applicable)
        event_type: Specific event within the source (e.g., "EXPIRY", "SETTLEMENT", "TRADE")
    """
    origin_type: OriginType
    source_id: str
    unit_symbol: Optional[str] = None
    event_type: Optional[str] = None

    def __repr__(self) -> str:
        parts = [f"{self.origin_type.value}:{self.source_id}"]
        if self.unit_symbol:
            parts.append(f"unit={self.unit_symbol}")
        if self.event_type:
            parts.append(f"event={self.event_type}")
        return f"Origin({', '.join(parts)})"


# ============================================================================
# UNIT STATE CHANGE
# ============================================================================

@dataclass(frozen=True, slots=True)
class UnitStateChange:
    """
    Record of a unit state change for transaction logging and potential rollback.

    Stores complete before/after state snapshots for correctness.
    This enables:
    - Forward replay: apply new_state
    - Backward replay: restore old_state
    - Audit queries: compute changed_fields() on demand

    Attributes:
        unit: Symbol of the unit whose state changed
        old_state: Complete state before the change (dict or None)
        new_state: Complete state after the change (dict)
    """
    unit: str
    old_state: Any  # The state before the change (dict or None)
    new_state: Any  # The state after the change (dict)

    def changed_fields(self) -> Dict[str, Tuple[Any, Any]]:
        """
        Compute fields that differ between old and new state.

        Returns:
            Dict mapping field name to (old_value, new_value) tuples.
            Only includes fields that actually changed.
        """
        old = self.old_state if isinstance(self.old_state, dict) else {}
        new = self.new_state if isinstance(self.new_state, dict) else {}
        changes = {}
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changes[key] = (old_val, new_val)
        return changes


# ============================================================================
# CORE DATA STRUCTURES
# ============================================================================

@dataclass(frozen=True, slots=True)
class Move:
    """
    A single transfer of value between two wallets.

    Attributes:
        quantity: The amount to transfer (must be finite and non-zero).
        unit_symbol: The symbol of the unit being transferred (e.g., "USD", "AAPL").
        source: The wallet ID from which value is debited.
        dest: The wallet ID to which value is credited.
        contract_id: Identifier of the contract generating this move.
        metadata: Optional additional information about the move.

    This class is immutable (frozen=True) and memory-optimized (slots=True).
    All fields are validated in __post_init__.
    """
    quantity: float
    unit_symbol: str
    source: str
    dest: str
    contract_id: str
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.source or not self.source.strip():
            raise ValueError("Move source cannot be empty")
        if not self.dest or not self.dest.strip():
            raise ValueError("Move dest cannot be empty")
        if not self.unit_symbol or not self.unit_symbol.strip():
            raise ValueError("Move unit_symbol cannot be empty")
        if not self.contract_id or not self.contract_id.strip():
            raise ValueError("Move contract_id cannot be empty")
        if not math.isfinite(self.quantity):
            raise ValueError(f"Move quantity must be finite, got {self.quantity}")
        if abs(self.quantity) < QUANTITY_EPSILON:
            raise ValueError("Move quantity is effectively zero")
        if self.source == self.dest:
            raise ValueError("Source and dest must be different")

    def __repr__(self) -> str:
        return f"Move({self.quantity} {self.unit_symbol}: {self.source}→{self.dest})"


def _compute_intent_id(
    moves: Tuple[Move, ...],
    state_changes: Tuple[UnitStateChange, ...],
    origin: TransactionOrigin,
    units_to_create: Tuple['Unit', ...] = ()
) -> str:
    """
    Compute a deterministic content hash for a transaction's intent.

    This hash is based solely on the semantic content of the transaction
    (moves, state_changes, origin, units_to_create), NOT on timestamps or ledger-specific data.
    Same inputs always produce the same intent_id.

    Used for idempotency checking: prevents duplicate business transactions.
    """
    # Canonicalize moves (sort for determinism)
    sorted_moves = tuple(sorted(
        moves,
        key=lambda m: (m.quantity, m.unit_symbol, m.source, m.dest, m.contract_id)
    ))

    content_parts = []

    # Add origin
    content_parts.append(f"origin:{origin.origin_type.value}:{origin.source_id}")
    if origin.unit_symbol:
        content_parts.append(f"unit:{origin.unit_symbol}")
    if origin.event_type:
        content_parts.append(f"event:{origin.event_type}")

    # Add units to create (sorted by symbol for determinism)
    for unit in sorted(units_to_create, key=lambda u: u.symbol):
        content_parts.append(f"unit_create:{unit.symbol}|{unit.unit_type}")

    # Add moves
    for m in sorted_moves:
        content_parts.append(f"move:{m.quantity}|{m.unit_symbol}|{m.source}|{m.dest}|{m.contract_id}")

    # Add state changes (sorted by unit)
    for sc in sorted(state_changes, key=lambda s: s.unit):
        # Use repr for state to get deterministic string representation
        content_parts.append(f"state_change:{sc.unit}|{repr(sc.old_state)}|{repr(sc.new_state)}")

    content = "|".join(content_parts)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class PendingTransaction:
    """
    A transaction specification before execution - represents INTENT.

    Created by contracts and submitted to the ledger for execution.
    Contains everything needed to describe what should happen, but without
    execution-specific metadata (exec_id, ledger_name, execution_time).

    Lifecycle:
    1. Contract creates PendingTransaction with moves, state_changes, origin, timestamp
    2. intent_id is auto-computed from content (deterministic hash)
    3. Ledger.execute() validates and executes, creating a Transaction record

    Attributes:
        moves: Tuple of value transfers between wallets
        state_changes: Tuple of unit state changes (with old_state and new_state)
        units_to_create: Tuple of Unit objects to register before executing moves
        origin: Who/what created this transaction and why
        timestamp: When this pending transaction was created
        intent_id: Content-addressable hash of the transaction intent (auto-computed)
    """
    moves: Tuple[Move, ...]
    state_changes: Tuple[UnitStateChange, ...]
    origin: TransactionOrigin
    timestamp: datetime
    units_to_create: Tuple['Unit', ...] = ()
    intent_id: str = field(default="")

    def __post_init__(self):
        # Compute intent_id if not provided
        if not self.intent_id:
            computed_id = _compute_intent_id(
                self.moves, self.state_changes, self.origin, self.units_to_create
            )
            object.__setattr__(self, 'intent_id', computed_id)

    def is_empty(self) -> bool:
        """Return True if this pending transaction has no moves, no state deltas, and no units to create."""
        return not self.moves and not self.state_changes and not self.units_to_create

    def __repr__(self) -> str:
        return f"PendingTransaction({len(self.moves)} moves, {len(self.state_changes)} deltas, {self.origin})"


def build_transaction(
    view: LedgerView,
    moves: List[Move],
    state_changes: Optional[List[UnitStateChange]] = None,
    origin: Optional[TransactionOrigin] = None,
    units_to_create: Optional[Tuple['Unit', ...]] = None,
) -> PendingTransaction:
    """
    Build a PendingTransaction from moves and state deltas.

    This is the standard way to create transactions.

    Args:
        view: Read-only ledger view (provides current_time)
        moves: List of moves to include in the transaction
        state_changes: Optional list of UnitStateChange objects representing state changes
        origin: Transaction origin (defaults to CONTRACT origin)
        units_to_create: Optional tuple of Unit objects to register before executing moves

    Returns:
        A PendingTransaction ready for execution

    Example:
        def compute_settlement(view, symbol, price):
            moves = [Move(1000.0, "USD", "alice", "bob", "settlement")]
            old_state = view.get_unit_state(symbol)
            new_state = {**old_state, "settled": True, "settlement_price": price}
            changes = [UnitStateChange(unit=symbol, old_state=old_state, new_state=new_state)]
            return build_transaction(view, moves, changes)
    """
    import copy

    if origin is None:
        origin = TransactionOrigin(
            origin_type=OriginType.CONTRACT,
            source_id="contract",
        )

    # Deep copy state changes to prevent mutation
    copied_changes: Tuple[UnitStateChange, ...] = ()
    if state_changes:
        copied_changes = tuple(
            UnitStateChange(
                unit=sc.unit,
                old_state=copy.deepcopy(sc.old_state),
                new_state=copy.deepcopy(sc.new_state),
            )
            for sc in state_changes
        )

    return PendingTransaction(
        moves=tuple(moves),
        state_changes=copied_changes,
        origin=origin,
        timestamp=view.current_time,
        units_to_create=units_to_create or (),
    )


def empty_pending_transaction(view: LedgerView) -> PendingTransaction:
    """
    Create an empty PendingTransaction (no moves, no state changes).

    Use this when a contract function has nothing to do.

    Args:
        view: Read-only ledger view (provides current_time)

    Returns:
        An empty PendingTransaction
    """
    return PendingTransaction(
        moves=(),
        state_changes=(),
        origin=TransactionOrigin(OriginType.CONTRACT, "noop"),
        timestamp=view.current_time,
    )


@dataclass(frozen=True, slots=True)
class Transaction:
    """
    An executed, immutable record of ledger state changes - represents FACT.

    Created by the ledger when executing a PendingTransaction.
    All fields are guaranteed to be present (no None values for required fields).

    Attributes:
        moves: Tuple of value transfers between wallets
        state_changes: Tuple of unit state changes (with old_state and new_state)
        origin: Who/what created this transaction and why
        timestamp: When the PendingTransaction was created
        intent_id: Content hash from PendingTransaction (for idempotency)
        exec_id: Unique execution identifier (ledger + sequence + time)
        ledger_name: Name of the ledger that executed this
        execution_time: When this was executed and logged
        sequence_number: Monotonic sequence within the ledger (for ordering)
        contract_ids: Set of contract IDs from moves (auto-populated)

    This class is immutable (frozen=True) and memory-optimized (slots=True).
    """
    moves: Tuple[Move, ...]
    state_changes: Tuple[UnitStateChange, ...]
    origin: TransactionOrigin
    timestamp: datetime           # When PendingTransaction was created
    intent_id: str               # Content hash (from PendingTransaction)
    exec_id: str                 # Unique execution instance ID
    ledger_name: str
    execution_time: datetime     # When executed
    sequence_number: int         # Monotonic within ledger
    units_to_create: Tuple['Unit', ...] = ()
    contract_ids: FrozenSet[str] = None

    def __post_init__(self):
        if not self.moves and not self.state_changes and not self.units_to_create:
            raise ValueError("Transaction must have moves, state_changes, or units_to_create")
        if self.contract_ids is None:
            object.__setattr__(
                self, 'contract_ids',
                frozenset(m.contract_id for m in self.moves)
            )

    def __repr__(self) -> str:
        w = 100  # Inner content width
        bar = "─" * w

        def pad(text: str) -> str:
            """Pad or truncate text to exactly w characters."""
            if len(text) > w:
                return text[:w-3] + "..."
            return text + " " * (w - len(text))

        lines = [
            "",
            f"┌{bar}┐",
            f"│{pad(' Transaction: ' + self.exec_id)}│",
            f"├{bar}┤",
            f"│{pad('   intent_id      : ' + self.intent_id)}│",
            f"│{pad('   timestamp      : ' + str(self.timestamp))}│",
            f"│{pad('   ledger_name    : ' + self.ledger_name)}│",
            f"│{pad('   execution_time : ' + str(self.execution_time))}│",
            f"│{pad('   sequence       : ' + str(self.sequence_number))}│",
            f"│{pad('   origin         : ' + str(self.origin))}│",
            f"│{pad('   contract_ids   : ' + str(set(self.contract_ids)))}│",
        ]
        if self.units_to_create:
            lines.append(f"├{bar}┤")
            lines.append(f"│{pad(' Units Created (' + str(len(self.units_to_create)) + '):')}│")
            for unit in self.units_to_create:
                lines.append(f"│{pad('   ' + unit.symbol + ' (' + unit.name + ')')}│")
        lines.append(f"├{bar}┤")
        lines.append(f"│{pad(' Moves (' + str(len(self.moves)) + '):')}│")
        for i, move in enumerate(self.moves):
            move_str = f"   [{i}] {move.quantity} {move.unit_symbol}: {move.source} → {move.dest}"
            lines.append(f"│{pad(move_str)}│")
        if self.state_changes:
            lines.append(f"├{bar}┤")
            lines.append(f"│{pad(' State Changes (' + str(len(self.state_changes)) + '):')}│")
            for sc in self.state_changes:
                lines.append(f"│{pad('   [' + sc.unit + ']')}│")
                changed = sc.changed_fields()
                if changed:
                    for field_name, (old_val, new_val) in changed.items():
                        lines.append(f"│{pad(f'      {field_name}: {old_val!r} → {new_val!r}')}│")
        lines.append(f"└{bar}┘")
        return "\n".join(lines)


# Type alias for transfer rule functions.
# Transfer rules validate moves and raise TransferRuleViolation if invalid.
TransferRule = Callable[[LedgerView, Move], None]


@dataclass
class Unit:
    """
    Definition of a tradeable unit (asset type) in the ledger.

    Attributes:
        symbol: Short identifier for the unit (e.g., "USD", "AAPL").
        name: Human-readable name for the unit.
        unit_type: Category of the unit (CASH, SECURITY, OPTION, FORWARD, etc.).
        min_balance: Minimum allowed balance in any wallet (negative values allow shorting).
        max_balance: Maximum allowed balance in any wallet.
        decimal_places: Number of decimal places for rounding (None = no rounding).
        transfer_rule: Optional function to validate moves involving this unit.
        _state: Internal state dictionary for term sheets, lifecycle data, etc.
    """
    symbol: str
    name: str
    unit_type: str
    min_balance: float = 0.0
    max_balance: float = float('inf')
    decimal_places: Optional[int] = None
    transfer_rule: Optional[TransferRule] = None
    _state: Optional[UnitState] = None

    def round(self, value: float) -> float:
        """
        Round a value to this unit's decimal precision.

        Returns the value unchanged if decimal_places is None.
        """
        if self.decimal_places is None:
            return value
        return round(value, self.decimal_places)


# ============================================================================
# TRANSFER RULES
# ============================================================================

def bilateral_transfer_rule(view: LedgerView, move: Move) -> None:
    """
    Enforce that only the original counterparties can hold positions in a bilateral unit.

    This rule restricts transfers to only occur between the two wallets specified
    in the unit's state as 'long_wallet' and 'short_wallet'. Transfers to or from
    any other wallet are rejected.

    During novation (transfer of a contract to a new counterparty), a temporary
    '_novation_from' entry in the unit state grants the transferring wallet
    permission to participate in the move.

    Raises:
        TransferRuleViolation: If the unit is missing counterparty state or if
                               either the source or destination wallet is not authorized.
    """
    state = view.get_unit_state(move.unit_symbol)
    long_wallet = state.get('long_wallet')
    short_wallet = state.get('short_wallet')

    if not long_wallet or not short_wallet:
        raise TransferRuleViolation(
            f"Bilateral unit {move.unit_symbol} missing counterparty state"
        )

    # Build set of authorized wallets (includes novation source if present)
    novation_from = state.get('_novation_from')
    authorized = {long_wallet, short_wallet}
    if novation_from:
        authorized.add(novation_from)

    if move.source not in authorized:
        raise TransferRuleViolation(
            f"Bilateral {move.unit_symbol}: {move.source} not authorized"
        )
    if move.dest not in authorized:
        raise TransferRuleViolation(
            f"Bilateral {move.unit_symbol}: {move.dest} not authorized"
        )




# ============================================================================
# UNIT FACTORIES
# ============================================================================

def cash(symbol: str, name: str, decimal_places: int = 2) -> Unit:
    """
    Create a cash currency unit.

    Args:
        symbol: Currency code (e.g., "USD", "EUR").
        name: Full name of the currency (e.g., "US Dollar").
        decimal_places: Number of decimal places for amounts (default: 2).

    Returns:
        A Unit configured for cash with a large negative minimum balance
        to allow overdrafts.
    """
    return Unit(
        symbol=symbol,
        name=name,
        unit_type=UNIT_TYPE_CASH,
        decimal_places=decimal_places,
        min_balance=DEFAULT_CASH_MIN_BALANCE,
        _state={'issuer': 'central_bank'}
    )


