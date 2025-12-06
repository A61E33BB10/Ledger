"""
ledger.py - Stateful Double-Entry Accounting Ledger

The Ledger class is the central state manager for the financial ledger system.
It is the only module that mutates state, ensuring controlled and auditable changes.

Key responsibilities:
    - Implements LedgerView protocol for safe read-only access by pure functions
    - Executes transactions atomically (all moves succeed or all fail)
    - Maintains wallet balances and unit (asset) definitions
    - Tracks time and provides temporal operations (clone_at, replay)
    - Provides performance modes (fast_mode, no_log) for different use cases
"""

from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set, Optional, Tuple
import copy
import hashlib
import sys

from .core import (
    # Types
    Move, Transaction, ContractResult, Unit,
    ExecuteResult, LedgerView, StateDelta,
    Positions, UnitState, BalanceMap,
    # Constants
    QUANTITY_EPSILON,
    # Exceptions
    LedgerError, InsufficientFunds, BalanceConstraintViolation,
    TransferRuleViolation, UnitNotRegistered, WalletNotRegistered,
)


class Ledger:
    """
    High-performance double-entry accounting ledger.

    Implements the LedgerView protocol, allowing the ledger to be passed to pure
    functions that access only read-only methods.

    Performance Modes:
        fast_mode=True: Skip validation checks for approximately 30% performance gain.
            Skipped validations include:
            - Balance constraint checks (min/max balance limits)
            - Transfer rule enforcement
            - Timestamp validation

            Note: Wallet and unit registration are always validated, even in fast_mode.

            WARNING: Invalid transactions will corrupt state silently in fast_mode.
            Use this mode only when all inputs are trusted (e.g., replaying verified
            transaction logs).

        no_log=True: Disable transaction logging for approximately 25% performance gain.
            Consequences:
            - clone_at() and replay() will raise LedgerError
            - No audit trail is maintained

            Use this mode for simulations or scenarios where historical state
            reconstruction is not required.

        Combined modes: Using both fast_mode and no_log provides approximately 2x
        performance improvement over full validation and logging.

    Thread Safety:
        Not thread-safe. Each thread should maintain its own Ledger instance.

    Example:
        ledger = Ledger("main", fast_mode=True, no_log=True)
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        tx = ledger.create_transaction([
            Move("alice", "bob", "USD", 100.0, "payment_001")
        ])
        result = ledger.execute(tx)
    """

    POSITION_EPSILON = QUANTITY_EPSILON

    def __init__(
        self,
        name: str,
        initial_time: Optional[datetime] = None,
        verbose: bool = True,
        fast_mode: bool = False,
        no_log: bool = False
    ):
        self.name = name
        self.balances: Dict[str, Dict[str, float]] = {}
        self.units: Dict[str, Unit] = {}
        self.registered_wallets: Set[str] = set()
        self.seen_tx_ids: Set[str] = set()
        self.transaction_log: List[Transaction] = []
        self._current_time: datetime = initial_time or datetime(1970, 1, 1)
        self.verbose = verbose
        self.fast_mode = fast_mode
        self.no_log = no_log
        # Inverted index mapping unit -> {wallet -> quantity} for O(1) position lookups
        self._positions_by_unit: Dict[str, Dict[str, float]] = defaultdict(dict)

    # ========================================================================
    # LedgerView PROTOCOL IMPLEMENTATION (read-only methods)
    # ========================================================================

    @property
    def current_time(self) -> datetime:
        """Current logical time of the ledger."""
        return self._current_time

    def get_balance(self, wallet: str, unit: str) -> float:
        """
        Get the balance of a specific unit in a wallet.

        Args:
            wallet: Wallet identifier
            unit: Unit symbol

        Returns:
            Current balance (0.0 if wallet has no balance for this unit)

        Raises:
            WalletNotRegistered: If wallet is not registered
            UnitNotRegistered: If unit is not registered
        """
        if wallet not in self.registered_wallets:
            raise WalletNotRegistered(f"Wallet {wallet} not registered")
        if unit not in self.units:
            raise UnitNotRegistered(f"Unit {unit} not registered")
        return self.balances[wallet].get(unit, 0.0)

    def get_unit_state(self, unit_symbol: str) -> UnitState:
        """
        Get a deep copy of a unit's internal state.

        The returned state dictionary can be safely mutated without affecting
        the ledger's internal state.

        Args:
            unit_symbol: Symbol of the unit

        Returns:
            Deep copy of the unit's state dictionary (empty dict if no state)

        Raises:
            UnitNotRegistered: If unit is not registered
        """
        if unit_symbol not in self.units:
            raise UnitNotRegistered(f"Unit {unit_symbol} not registered")
        unit = self.units[unit_symbol]
        return self._deep_copy_state(unit._state) if unit._state else {}

    def get_positions(self, unit_symbol: str) -> Positions:
        """
        Get all non-zero positions for a specific unit across all wallets.

        Uses an inverted index for O(1) lookup performance.

        Args:
            unit_symbol: Symbol of the unit

        Returns:
            Dictionary mapping wallet IDs to their non-zero balances for this unit
        """
        return dict(self._positions_by_unit.get(unit_symbol, {}))

    def list_wallets(self) -> Set[str]:
        """List all registered wallet IDs."""
        return self.registered_wallets.copy()

    def list_units(self) -> List[str]:
        """List all registered unit symbols."""
        return sorted(self.units.keys())

    def get_wallet_balances(self, wallet: str) -> BalanceMap:
        """Get all balances for a wallet."""
        if wallet not in self.registered_wallets:
            raise WalletNotRegistered(f"Wallet {wallet} not registered")
        return dict(self.balances[wallet])

    def total_supply(self, unit: str) -> float:
        """
        Calculate total supply of a unit across all wallets.

        Wallets are sorted before summation to ensure deterministic float
        accumulation order.

        Args:
            unit: Unit symbol

        Returns:
            Total supply across all wallets

        Raises:
            UnitNotRegistered: If unit is not registered
        """
        if unit not in self.units:
            raise UnitNotRegistered(f"Unit {unit} not registered")
        return sum(self.balances[w].get(unit, 0.0) for w in sorted(self.registered_wallets))

    def is_registered(self, wallet: str) -> bool:
        """Check if a wallet is registered."""
        return wallet in self.registered_wallets

    # ========================================================================
    # TIME MANAGEMENT
    # ========================================================================

    def advance_time(self, new_time: datetime) -> None:
        """
        Advance the ledger's logical clock to a new time.

        Time can only move forward, never backward.

        Args:
            new_time: The new current time

        Raises:
            ValueError: If new_time is before the current time
        """
        if new_time < self._current_time:
            raise ValueError(
                f"Cannot move time backwards: {new_time} < {self._current_time}"
            )
        self._current_time = new_time

    # ========================================================================
    # REGISTRATION (Mutating)
    # ========================================================================

    def register_wallet(self, wallet_id: str) -> str:
        """
        Register a new wallet in the ledger.

        Args:
            wallet_id: Unique identifier for the wallet

        Returns:
            The wallet_id that was registered

        Raises:
            ValueError: If wallet is already registered
        """
        if wallet_id in self.registered_wallets:
            raise ValueError(f"Wallet {wallet_id} already registered")
        self.registered_wallets.add(wallet_id)
        self.balances[wallet_id] = defaultdict(float)
        return wallet_id

    def register_unit(self, unit: Unit) -> None:
        """
        Register a new unit (asset type) in the ledger.

        If verbose mode is enabled, prints registration confirmation with unit details.

        Args:
            unit: The Unit to register

        Raises:
            ValueError: If unit symbol is already registered
        """
        if unit.symbol in self.units:
            raise ValueError(f"Unit {unit.symbol} already registered")
        self.units[unit.symbol] = unit
        if self.verbose:
            rule_str = f", rule={unit.transfer_rule.__name__}" if unit.transfer_rule else ""
            print(f"📝 Registered: {unit.symbol} ({unit.name}) [{unit.unit_type}]{rule_str}")

    def set_balance(self, wallet: str, unit: str, quantity: float) -> None:
        """
        Set a wallet's balance for a unit directly.

        WARNING: This method bypasses double-entry accounting. It directly sets
        a balance without a corresponding contra-entry. Use only for:
        - Initial setup / seeding test scenarios
        - External system integrations where the contra-entry is elsewhere
        - Correcting errors (with proper audit trail)

        For normal operations, use transactions via execute() which maintain
        double-entry invariants (every credit has a corresponding debit).

        Args:
            wallet: Wallet to update
            unit: Unit symbol
            quantity: New balance (overwrites existing)
        """
        if wallet not in self.registered_wallets:
            raise WalletNotRegistered(f"Wallet {wallet} not registered")
        if unit not in self.units:
            raise UnitNotRegistered(f"Unit {unit} not registered")
        self.balances[wallet][unit] = quantity
        self._update_position_index(wallet, unit, quantity)

    def update_unit_state(self, unit_symbol: str, state_updates: UnitState) -> None:
        """
        Update a unit's internal state dictionary.

        The state_updates are merged into the existing state. If the unit has
        no existing state, an empty state dictionary is created first.

        Args:
            unit_symbol: Symbol of the unit to update
            state_updates: Dictionary of state keys and values to update

        Raises:
            UnitNotRegistered: If unit is not registered
        """
        if unit_symbol not in self.units:
            raise UnitNotRegistered(f"Unit {unit_symbol} not registered")
        unit = self.units[unit_symbol]
        if unit._state is None:
            unit._state = {}
        unit._state.update(state_updates)

    # ========================================================================
    # TRANSACTION EXECUTION (Mutating)
    # ========================================================================

    def _deterministic_tx_id(self, moves: Tuple[Move, ...]) -> str:
        """
        Generate a deterministic transaction ID from move contents.

        The ID is derived from a SHA-256 hash of:
        - Current ledger time
        - Ledger name
        - All move details (source, dest, unit, quantity, contract_id)

        This ensures reproducibility: identical inputs produce identical IDs.

        Args:
            moves: Tuple of moves to hash

        Returns:
            16-character hex string (first 16 chars of SHA-256 hash)
        """
        content = f"{self._current_time.isoformat()}:{self.name}:"
        for m in moves:
            content += f"{m.source},{m.dest},{m.unit},{m.quantity},{m.contract_id};"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def create_transaction(
        self,
        moves: List[Move],
        tx_id: Optional[str] = None
    ) -> Transaction:
        """
        Create a new transaction with the current ledger time as timestamp.

        If no tx_id is provided, a deterministic ID is generated from:
        - Current timestamp
        - Ledger name
        - Move details (source, dest, unit, quantity, contract_id)

        This ensures reproducibility: identical inputs produce identical transaction IDs.

        Args:
            moves: List of moves to include in the transaction
            tx_id: Optional custom transaction ID (auto-generated if not provided)

        Returns:
            A new Transaction object
        """
        moves_tuple = tuple(moves)
        return Transaction(
            moves=moves_tuple,
            tx_id=tx_id or self._deterministic_tx_id(moves_tuple),
            timestamp=self._current_time,
            ledger_name=self.name
        )

    def execute(
        self,
        tx: Transaction,
        fast_mode: Optional[bool] = None
    ) -> ExecuteResult:
        """
        Execute a transaction atomically.

        All moves in the transaction succeed together or all fail together.
        Execution is idempotent: a transaction with the same tx_id will not
        be applied twice.

        Validation behavior:
        - Units and wallets are always validated, regardless of fast_mode
        - In normal mode: balance constraints, transfer rules, and timestamps are validated
        - In fast_mode: balance constraints, transfer rules, and timestamps are skipped

        Args:
            tx: Transaction to execute
            fast_mode: Override ledger's fast_mode setting for this transaction

        Returns:
            ExecuteResult.APPLIED if successful
            ExecuteResult.ALREADY_APPLIED if transaction was already executed
            ExecuteResult.REJECTED if validation failed
        """
        use_fast_mode = fast_mode if fast_mode is not None else self.fast_mode

        # Idempotency check
        if tx.tx_id in self.seen_tx_ids:
            if self.verbose:
                self._print_tx_result(tx, "ALREADY_APPLIED", "⚠️")
            return ExecuteResult.ALREADY_APPLIED

        # Record execution time
        object.__setattr__(tx, 'execution_time', self._current_time)

        # Always validate units and wallets exist (even in fast mode)
        for move in tx.moves:
            if move.unit not in self.units:
                if self.verbose:
                    self._print_tx_result(tx, f"REJECTED: unit not registered: {move.unit}", "✗")
                return ExecuteResult.REJECTED
            if move.source not in self.registered_wallets:
                if self.verbose:
                    self._print_tx_result(tx, f"REJECTED: wallet not registered: {move.source}", "✗")
                return ExecuteResult.REJECTED
            if move.dest not in self.registered_wallets:
                if self.verbose:
                    self._print_tx_result(tx, f"REJECTED: wallet not registered: {move.dest}", "✗")
                return ExecuteResult.REJECTED

        # Full validation (skip in fast mode)
        if not use_fast_mode:
            valid, reason = self._validate_transaction(tx)
            if not valid:
                if self.verbose:
                    self._print_tx_result(tx, f"REJECTED: {reason}", "✗")
                return ExecuteResult.REJECTED

        # Apply moves
        self._execute_moves(tx.moves)

        # Log transaction
        if not self.no_log:
            self.transaction_log.append(tx)
        self.seen_tx_ids.add(tx.tx_id)

        if self.verbose:
            self._print_tx_result(tx, "APPLIED", "✓")
        return ExecuteResult.APPLIED

    def _print_tx_result(self, tx: Transaction, result: str, icon: str) -> None:
        """
        Print transaction details and result in a formatted Unicode box.

        Displays transaction metadata, moves, state deltas, and execution result
        in a 100-character wide box with Unicode border characters.

        Args:
            tx: Transaction to display
            result: Result string (e.g., "APPLIED", "REJECTED: reason")
            icon: Icon to display with result (e.g., "✓", "✗", "⚠️")
        """
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
            f"│{pad(' Transaction: ' + tx.tx_id)}│",
            f"├{bar}┤",
            f"│{pad('   timestamp      : ' + str(tx.timestamp))}│",
            f"│{pad('   ledger_name    : ' + tx.ledger_name)}│",
            f"│{pad('   execution_time : ' + str(tx.execution_time))}│",
            f"│{pad('   contract_ids   : ' + str(set(tx.contract_ids)))}│",
            f"├{bar}┤",
            f"│{pad(' Moves (' + str(len(tx.moves)) + '):')}│",
        ]
        for i, move in enumerate(tx.moves):
            move_str = f"   [{i}] {move.source} → {move.dest}: {move.quantity} {move.unit}"
            lines.append(f"│{pad(move_str)}│")
        if tx.state_deltas:
            lines.append(f"├{bar}┤")
            lines.append(f"│{pad(' State Deltas (' + str(len(tx.state_deltas)) + '):')}│")
            for delta in tx.state_deltas:
                lines.append(f"│{pad('   [' + delta.unit + ']')}│")
                lines.append(f"│{pad('      old: ' + str(delta.old_state))}│")
                lines.append(f"│{pad('      new: ' + str(delta.new_state))}│")
        lines.append(f"├{bar}┤")
        lines.append(f"│{pad(' ' + icon + ' ' + result)}│")
        lines.append(f"└{bar}┘")
        print("\n".join(lines))

    def execute_contract(self, result: ContractResult) -> ExecuteResult:
        """
        Execute a ContractResult atomically.

        Execution order:
        1. Execute moves (if any)
        2. Apply state updates (if moves succeeded or there are no moves)

        If moves fail validation, state updates are not applied.

        State changes are captured as StateDelta objects containing deep copies
        of both old and new state. This ensures the transaction log contains
        immutable snapshots that won't be corrupted by later mutations.

        Args:
            result: ContractResult containing moves and state updates

        Returns:
            ExecuteResult.APPLIED if successful
            ExecuteResult.ALREADY_APPLIED or ExecuteResult.REJECTED if moves failed
        """
        if result.is_empty():
            return ExecuteResult.APPLIED

        # Capture state changes with deep copies
        # Deep copying ensures transaction log contains immutable snapshots
        state_deltas = []
        for unit_symbol, updates in result.state_updates.items():
            old_state = self.get_unit_state(unit_symbol)  # Already a deep copy
            new_state = self._deep_copy_state({**old_state, **updates})
            state_deltas.append(StateDelta(
                unit=unit_symbol,
                old_state=old_state,
                new_state=new_state
            ))

        # Execute moves with state deltas attached
        if result.moves:
            moves_tuple = tuple(result.moves)
            tx = Transaction(
                moves=moves_tuple,
                tx_id=self._deterministic_tx_id(moves_tuple),
                timestamp=self._current_time,
                ledger_name=self.name,
                state_deltas=tuple(state_deltas)
            )
            exec_result = self.execute(tx)
            if exec_result != ExecuteResult.APPLIED:
                return exec_result
        elif state_deltas and not self.no_log:
            # State-only update (no moves) - generate ID from state deltas
            state_content = f"{self._current_time.isoformat()}:{self.name}:state:"
            for delta in state_deltas:
                state_content += f"{delta.unit};"
            tx_id = hashlib.sha256(state_content.encode()).hexdigest()[:16]
            tx = Transaction(
                moves=(),
                tx_id=tx_id,
                timestamp=self._current_time,
                ledger_name=self.name,
                state_deltas=tuple(state_deltas)
            )
            self.transaction_log.append(tx)
            self.seen_tx_ids.add(tx.tx_id)

        # Apply state updates
        for unit_symbol, updates in result.state_updates.items():
            self.update_unit_state(unit_symbol, updates)

        return ExecuteResult.APPLIED

    def _validate_transaction(self, tx: Transaction) -> Tuple[bool, str]:
        """
        Validate transaction against all constraints.

        Checks performed:
        1. Timestamp validation (transaction must not be from the future)
        2. Unit and wallet registration
        3. Transfer rule enforcement
        4. Balance constraint validation (min/max balance limits)

        Args:
            tx: Transaction to validate

        Returns:
            Tuple of (success: bool, reason: str)
            If success is True, reason is empty string
            If success is False, reason describes the validation failure
        """
        # Timestamp check
        if tx.timestamp > self._current_time:
            return False, "future timestamp"

        # Check units, wallets, and transfer rules
        for move in tx.moves:
            if move.unit not in self.units:
                return False, f"unit not registered: {move.unit}"
            if not self.is_registered(move.source):
                return False, f"wallet not registered: {move.source}"
            if not self.is_registered(move.dest):
                return False, f"wallet not registered: {move.dest}"

            # Transfer rule check (pass self as LedgerView)
            unit = self.units[move.unit]
            if unit.transfer_rule:
                try:
                    unit.transfer_rule(self, move)
                except TransferRuleViolation as e:
                    return False, str(e)

        # Calculate net balance changes with proper rounding
        net: Dict[Tuple[str, str], float] = {}
        for move in tx.moves:
            unit = self.units[move.unit]
            key_src = (move.source, move.unit)
            key_dst = (move.dest, move.unit)
            # Apply unit-specific rounding to match execution behavior
            net[key_src] = unit.round(net.get(key_src, 0.0) - move.quantity)
            net[key_dst] = unit.round(net.get(key_dst, 0.0) + move.quantity)

        # Check balance constraints
        for (wallet, unit_sym), delta in net.items():
            current = self.balances[wallet][unit_sym]
            unit = self.units[unit_sym]
            proposed = unit.round(current + delta)

            if proposed < unit.min_balance:
                return False, f"{wallet} {unit_sym}: {proposed:.2f} < min {unit.min_balance}"
            if proposed > unit.max_balance:
                return False, f"{wallet} {unit_sym}: {proposed:.2f} > max {unit.max_balance}"

        return True, ""

    def _update_position_index(self, wallet: str, unit_symbol: str, quantity: float) -> None:
        """
        Update the inverted position index after a balance change.

        The position index maintains a mapping of unit -> {wallet -> quantity}
        for efficient position lookups. Zero or near-zero balances are removed
        from the index to keep it compact.

        Args:
            wallet: Wallet whose balance changed
            unit_symbol: Unit symbol
            quantity: New balance quantity
        """
        if abs(quantity) > self.POSITION_EPSILON:
            self._positions_by_unit[unit_symbol][wallet] = quantity
        else:
            # Remove zero/dust positions from index
            self._positions_by_unit[unit_symbol].pop(wallet, None)

    def _execute_moves(self, moves) -> None:
        """
        Apply all moves to wallet balances and update the position index.

        For each move:
        1. Subtract quantity from source wallet
        2. Add quantity to destination wallet
        3. Apply unit-specific rounding
        4. Update position index for both wallets

        Args:
            moves: Iterable of Move objects to execute
        """
        for move in moves:
            unit = self.units[move.unit]
            # Update source balance
            new_src_balance = unit.round(
                self.balances[move.source][move.unit] - move.quantity
            )
            self.balances[move.source][move.unit] = new_src_balance
            self._update_position_index(move.source, move.unit, new_src_balance)
            # Update destination balance
            new_dst_balance = unit.round(
                self.balances[move.dest][move.unit] + move.quantity
            )
            self.balances[move.dest][move.unit] = new_dst_balance
            self._update_position_index(move.dest, move.unit, new_dst_balance)

    # ========================================================================
    # LEDGER OPERATIONS
    # ========================================================================

    @staticmethod
    def _deep_copy_state(state: Optional[UnitState]) -> Optional[UnitState]:
        """
        Recursively deep copy unit state dictionary.

        Args:
            state: State dictionary to copy, or None

        Returns:
            Deep copy of the state, or None if input was None
        """
        if state is None:
            return None
        return copy.deepcopy(state)

    def clone(self) -> Ledger:
        """
        Create a deep copy of this ledger.

        All state is fully independent: modifications to the clone will not
        affect the original ledger, and vice versa.

        Cloned state includes:
        - All unit definitions and their internal state
        - All wallet registrations and balances
        - Transaction log (if logging is enabled)
        - Current time
        - Configuration (verbose, fast_mode, no_log)

        Returns:
            A new Ledger instance with identical state
        """
        cloned = Ledger.__new__(Ledger)
        cloned.name = self.name
        cloned._current_time = self._current_time
        cloned.verbose = self.verbose
        cloned.fast_mode = self.fast_mode
        cloned.no_log = self.no_log

        # Deep copy units (including nested state)
        cloned.units = {}
        for symbol, unit in self.units.items():
            cloned.units[symbol] = Unit(
                symbol=unit.symbol,
                name=unit.name,
                unit_type=unit.unit_type,
                min_balance=unit.min_balance,
                max_balance=unit.max_balance,
                decimal_places=unit.decimal_places,
                transfer_rule=unit.transfer_rule,
                _state=self._deep_copy_state(unit._state)
            )

        # Copy collections
        cloned.registered_wallets = self.registered_wallets.copy()
        cloned.seen_tx_ids = self.seen_tx_ids.copy()
        cloned.transaction_log = list(self.transaction_log)

        # Deep copy balances
        cloned.balances = {}
        for wallet, bals in self.balances.items():
            cloned.balances[wallet] = defaultdict(float, bals)

        # Deep copy position index
        cloned._positions_by_unit = defaultdict(dict)
        for unit_symbol, positions in self._positions_by_unit.items():
            cloned._positions_by_unit[unit_symbol] = dict(positions)

        return cloned

    def clone_at(self, target_time: datetime) -> Ledger:
        """
        Create a deep copy of this ledger as it existed at a specific past time.

        This method reconstructs historical state using an unwind algorithm:
        1. Clone the current ledger state
        2. Walk backward through all transactions executed after target_time
        3. Reverse each transaction's effects:
           - Restore balances (add to source, subtract from destination)
           - Restore unit state from state_deltas (old_state)
        4. Filter transaction log to only include transactions up to target_time

        The algorithm correctly handles:
        - Initial balances set via set_balance() (preserved in current state)
        - Only reversing logged transactions
        - Using execution_time (when applied) rather than timestamp (when created)

        Args:
            target_time: The point in time to reconstruct

        Returns:
            A new Ledger instance with state as it was at target_time

        Raises:
            LedgerError: If no_log=True (cannot reconstruct without transaction log)
            ValueError: If target_time is in the future
        """
        if self.no_log:
            raise LedgerError("Cannot reconstruct: no_log=True")
        if target_time > self._current_time:
            raise ValueError(f"Target time {target_time} is in the future")

        # Start with a clone of current state
        cloned = self.clone()
        cloned._current_time = target_time

        # Filter transaction log to only include transactions executed at or before target_time
        cloned.transaction_log = [
            tx for tx in self.transaction_log
            if (tx.execution_time or tx.timestamp) <= target_time
        ]
        cloned.seen_tx_ids = {tx.tx_id for tx in cloned.transaction_log}

        # Walk backwards through transactions executed after target_time, reversing them
        for tx in reversed(self.transaction_log):
            effective_time = tx.execution_time or tx.timestamp
            if effective_time <= target_time:
                break

            # Reverse moves (apply rounding to match _execute_moves)
            for move in tx.moves:
                unit = cloned.units.get(move.unit)
                if unit is None:
                    raise LedgerError(f"Cannot unwind: unit {move.unit} not found in cloned ledger")
                new_src = unit.round(
                    cloned.balances[move.source][move.unit] + move.quantity
                )
                new_dst = unit.round(
                    cloned.balances[move.dest][move.unit] - move.quantity
                )

                cloned.balances[move.source][move.unit] = new_src
                cloned.balances[move.dest][move.unit] = new_dst
                # Update position index for reversed moves
                cloned._update_position_index(move.source, move.unit, new_src)
                cloned._update_position_index(move.dest, move.unit, new_dst)

            # Reverse state deltas - restore old_state
            for delta in tx.state_deltas:
                if delta.unit in cloned.units:
                    cloned.units[delta.unit]._state = self._deep_copy_state(
                        delta.old_state if isinstance(delta.old_state, dict) else {}
                    )

        return cloned

    def replay(
        self,
        from_tx: int = 0,
        fast_mode: bool = True,
        no_log: bool = False
    ) -> Ledger:
        """
        Create a new ledger by replaying the transaction log.

        This method reconstructs ledger state by re-executing all logged transactions
        in order. The resulting ledger will contain:
        - All balance changes from transactions
        - All unit state updates from state_deltas
        - The complete transaction history (unless no_log=True)

        Note: Initial balances set via set_balance() are NOT replayed because
        they are not part of the transaction log. Use clone() or clone_at() if
        you need to preserve balances set outside of transactions.

        The replay process:
        1. Create a new ledger with unit definitions and wallet registrations
        2. Re-execute each transaction from the log
        3. Apply state_deltas to restore unit states
        4. Advance time as needed to match transaction timestamps

        Args:
            from_tx: Starting transaction index (0 = replay from beginning)
            fast_mode: Skip validation during replay (default: True)
            no_log: Don't log transactions in the new ledger (default: False)

        Returns:
            New Ledger instance with replayed state

        Raises:
            LedgerError: If no_log=True on source ledger, or if replay fails
        """
        if self.no_log:
            raise LedgerError("Cannot replay: no_log=True")

        new_ledger = Ledger(
            name=f"{self.name}_replayed",
            initial_time=datetime(1970, 1, 1),
            verbose=self.verbose,
            fast_mode=fast_mode,
            no_log=no_log
        )

        # Copy unit definitions only (not current state)
        # Unit states will be built from state_deltas during replay
        for symbol, unit in self.units.items():
            new_ledger.units[symbol] = Unit(
                symbol=unit.symbol,
                name=unit.name,
                unit_type=unit.unit_type,
                min_balance=unit.min_balance,
                max_balance=unit.max_balance,
                decimal_places=unit.decimal_places,
                transfer_rule=unit.transfer_rule,
                _state={}
            )

        for wallet in self.registered_wallets:
            new_ledger.register_wallet(wallet)

        for tx in self.transaction_log[from_tx:]:
            if tx.timestamp > new_ledger._current_time:
                new_ledger.advance_time(tx.timestamp)

            # Execute moves
            result = new_ledger.execute(tx, fast_mode=fast_mode)
            if result == ExecuteResult.REJECTED:
                raise LedgerError(f"Replay failed at tx {tx.tx_id}")

            # Apply state_deltas to restore unit states
            # The new_state from each delta represents the state after this transaction
            for delta in tx.state_deltas:
                if delta.unit in new_ledger.units:
                    new_ledger.units[delta.unit]._state = self._deep_copy_state(
                        delta.new_state if isinstance(delta.new_state, dict) else {}
                    )

        return new_ledger

    def get_memory_stats(self) -> Dict[str, int]:
        """
        Estimate memory consumption of ledger data structures.

        Provides approximate memory usage in bytes for major components.
        Useful for monitoring memory growth in long-running simulations.

        Note: These are estimates using sys.getsizeof(), which may not capture
        all overhead or deeply nested objects.

        Returns:
            Dictionary with byte estimates for each component:
            - 'transaction_log': Transaction log memory usage
            - 'balances': Wallet balance storage
            - 'units': Unit definitions
            - 'seen_tx_ids': Transaction ID deduplication set
            - 'total': Sum of all components
        """
        # Transaction log size
        log_size = sys.getsizeof(self.transaction_log)
        for tx in self.transaction_log:
            log_size += sys.getsizeof(tx)
            for move in tx.moves:
                log_size += sys.getsizeof(move)

        # Balances
        balances_size = sys.getsizeof(self.balances)
        for wallet, bals in self.balances.items():
            balances_size += sys.getsizeof(wallet) + sys.getsizeof(bals)
            for unit, qty in bals.items():
                balances_size += sys.getsizeof(unit) + sys.getsizeof(qty)

        # Units
        units_size = sys.getsizeof(self.units)
        for symbol, unit in self.units.items():
            units_size += sys.getsizeof(symbol) + sys.getsizeof(unit)

        # Seen tx ids
        seen_size = sys.getsizeof(self.seen_tx_ids)
        for tx_id in self.seen_tx_ids:
            seen_size += sys.getsizeof(tx_id)

        return {
            'transaction_log': log_size,
            'balances': balances_size,
            'units': units_size,
            'seen_tx_ids': seen_size,
            'total': log_size + balances_size + units_size + seen_size,
        }
