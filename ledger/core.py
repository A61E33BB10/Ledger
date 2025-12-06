"""
Core types and pure functions for the financial ledger system.

This module provides the foundational data structures and protocols for the ledger:
1. Protocols: LedgerView for read-only ledger access
2. Immutable data structures: Move, Transaction, ContractResult, Unit
3. Exceptions: LedgerError and domain-specific error types
4. Type aliases: Positions, BalanceMap, UnitState, StateUpdates
5. Transfer rules: Pure validation functions for moves
6. Unit factories: Functions to create standard unit types

All functions in this module are pure and operate on read-only views.
No function can mutate ledger state directly.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import math
from typing import (
    Dict, List, Set, Optional, Callable, Any, Protocol,
    Tuple, FrozenSet, runtime_checkable
)


# ============================================================================
# CONSTANTS
# ============================================================================

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

# Mapping from unit symbol to state changes to be applied.
StateUpdates = Dict[str, UnitState]


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

    def get_balance(self, wallet: str, unit: str) -> float:
        """
        Return the balance of a specific unit in a wallet.

        Returns 0.0 if the wallet or unit does not exist.
        """
        ...

    def get_unit_state(self, unit: str) -> UnitState:
        """
        Return a copy of the unit's internal state.

        The state dictionary contains term sheet data, lifecycle information,
        and any other unit-specific metadata.
        """
        ...

    def get_positions(self, unit: str) -> Positions:
        """
        Return all non-zero positions for a unit across all wallets.

        Returns a dictionary mapping wallet IDs to quantities.
        """
        ...

    def list_wallets(self) -> Set[str]:
        """Return the set of all registered wallet IDs."""
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
# STATE DELTA
# ============================================================================

@dataclass(frozen=True)
class StateDelta:
    """
    Record of a unit state change for transaction logging and potential rollback.

    Captures the complete before and after state of a unit when its internal
    state is modified. Both old_state and new_state should be immutable objects
    (frozen dataclasses or None).
    """
    unit: str
    old_state: Any  # The state before the change (frozen dataclass or None)
    new_state: Any  # The state after the change (frozen dataclass)


# ============================================================================
# CORE DATA STRUCTURES
# ============================================================================

@dataclass(frozen=True, slots=True)
class Move:
    """
    A single transfer of value between two wallets.

    Attributes:
        source: The wallet ID from which value is debited.
        dest: The wallet ID to which value is credited.
        unit: The unit symbol being transferred.
        quantity: The amount to transfer (must be finite and non-zero).
        contract_id: Identifier of the contract generating this move.
        metadata: Optional additional information about the move.

    This class is immutable (frozen=True) and memory-optimized (slots=True).
    All fields are validated in __post_init__.
    """
    source: str
    dest: str
    unit: str
    quantity: float
    contract_id: str
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.source or not self.source.strip():
            raise ValueError("Move source cannot be empty")
        if not self.dest or not self.dest.strip():
            raise ValueError("Move dest cannot be empty")
        if not self.unit or not self.unit.strip():
            raise ValueError("Move unit cannot be empty")
        if not self.contract_id or not self.contract_id.strip():
            raise ValueError("Move contract_id cannot be empty")
        if not math.isfinite(self.quantity):
            raise ValueError(f"Move quantity must be finite, got {self.quantity}")
        if abs(self.quantity) < QUANTITY_EPSILON:
            raise ValueError("Move quantity is effectively zero")
        if self.source == self.dest:
            raise ValueError("Source and dest must be different")

    def __repr__(self) -> str:
        return f"Move({self.source}→{self.dest}: {self.quantity} {self.unit})"


@dataclass(frozen=True)
class ContractResult:
    """
    Output from a contract execution containing moves and state changes.

    Attributes:
        moves: Tuple of balance transfers to execute. Tuples are used for immutability.
        state_updates: Dictionary mapping unit symbols to their state changes.

    This dataclass is frozen to prevent reassignment of fields. The state_updates
    dictionary itself can technically be mutated, so callers should treat it as
    read-only by convention.
    """
    moves: Tuple[Move, ...] = ()
    state_updates: StateUpdates = field(default_factory=dict)

    def is_empty(self) -> bool:
        """Return True if this result contains no moves and no state updates."""
        return not self.moves and not self.state_updates

    def __repr__(self) -> str:
        return f"ContractResult({len(self.moves)} moves, {list(self.state_updates.keys()) or '{}'})"


@dataclass(frozen=True, slots=True)
class Transaction:
    """
    An atomic, immutable record of ledger state changes.

    Attributes:
        moves: Tuple of value transfers between wallets.
        tx_id: Unique identifier for this transaction.
        timestamp: Logical time when the transaction was created.
        ledger_name: Name of the ledger this transaction belongs to.
        state_deltas: Tuple of unit state changes included in this transaction.
        contract_ids: Set of contract IDs that generated the moves (auto-populated).
        execution_time: Actual time when the transaction was executed (optional).

    This class is immutable (frozen=True) and memory-optimized (slots=True).
    """
    moves: Tuple[Move, ...]
    tx_id: str
    timestamp: datetime
    ledger_name: str
    state_deltas: Tuple[StateDelta, ...] = ()
    contract_ids: FrozenSet[str] = None
    execution_time: Optional[datetime] = None

    def __post_init__(self):
        if not self.moves and not self.state_deltas:
            raise ValueError("Transaction must have moves or state_deltas")
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
            f"│{pad(' Transaction: ' + self.tx_id)}│",
            f"├{bar}┤",
            f"│{pad('   timestamp      : ' + str(self.timestamp))}│",
            f"│{pad('   ledger_name    : ' + self.ledger_name)}│",
            f"│{pad('   execution_time : ' + str(self.execution_time))}│",
            f"│{pad('   contract_ids   : ' + str(set(self.contract_ids)))}│",
            f"├{bar}┤",
            f"│{pad(' Moves (' + str(len(self.moves)) + '):')}│",
        ]
        for i, move in enumerate(self.moves):
            move_str = f"   [{i}] {move.source} → {move.dest}: {move.quantity} {move.unit}"
            lines.append(f"│{pad(move_str)}│")
        if self.state_deltas:
            lines.append(f"├{bar}┤")
            lines.append(f"│{pad(' State Deltas (' + str(len(self.state_deltas)) + '):')}│")
            for delta in self.state_deltas:
                lines.append(f"│{pad('   [' + delta.unit + ']')}│")
                lines.append(f"│{pad('      old: ' + str(delta.old_state))}│")
                lines.append(f"│{pad('      new: ' + str(delta.new_state))}│")
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
    state = view.get_unit_state(move.unit)
    long_wallet = state.get('long_wallet')
    short_wallet = state.get('short_wallet')

    if not long_wallet or not short_wallet:
        raise TransferRuleViolation(
            f"Bilateral unit {move.unit} missing counterparty state"
        )

    # Build set of authorized wallets (includes novation source if present)
    novation_from = state.get('_novation_from')
    authorized = {long_wallet, short_wallet}
    if novation_from:
        authorized.add(novation_from)

    if move.source not in authorized:
        raise TransferRuleViolation(
            f"Bilateral {move.unit}: {move.source} not authorized"
        )
    if move.dest not in authorized:
        raise TransferRuleViolation(
            f"Bilateral {move.unit}: {move.dest} not authorized"
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
        unit_type="CASH",
        decimal_places=decimal_places,
        min_balance=DEFAULT_CASH_MIN_BALANCE,
        _state={'issuer': 'central_bank'}
    )


