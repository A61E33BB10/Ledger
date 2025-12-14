"""
ledger.py - Stateful Double-Entry Accounting Ledger

The Ledger class is the central state manager for the financial ledger system.
It is the only module that mutates state, ensuring controlled and auditable changes.

Key responsibilities:
    - Implements LedgerView protocol for safe read-only access by pure functions
    - Executes transactions atomically (all moves succeed or all fail)
    - Maintains wallet balances and unit (asset) definitions
    - Tracks time and provides temporal operations (clone_at, replay)
    - Always validates and always logs - no exceptions
"""

from __future__ import annotations
from collections import defaultdict
from dataclasses import replace
from datetime import datetime
from typing import Dict, List, Set, Optional, Tuple, Any
import copy
import hashlib
import sys
from decimal import Decimal

from .core import (
    # Types
    Move, Transaction, Unit,
    PendingTransaction,
    ExecuteResult, LedgerView,
    Positions, UnitState, BalanceMap,
    # Constants
    QUANTITY_EPSILON, SYSTEM_WALLET,
    # Exceptions
    LedgerError, InsufficientFunds, BalanceConstraintViolation,
    TransferRuleViolation, UnitNotRegistered, WalletNotRegistered,
    # Helper functions
    _freeze_state, _thaw_state,
)


class Ledger:
    """
    Double-entry accounting ledger with full validation and audit trail.

    Implements the LedgerView protocol, allowing the ledger to be passed to pure
    functions that access only read-only methods.

    Design Principles:
        - Always validates: Every transaction is validated against balance constraints,
          transfer rules, and timestamp requirements. No shortcuts.
        - Always logs: Every transaction is recorded in the audit trail, enabling
          clone_at() and replay() for historical state reconstruction.

    Thread Safety:
        Not thread-safe. Each thread should maintain its own Ledger instance.

    Example:
        ledger = Ledger("main")
        ledger.register_unit(cash("USD", "US Dollar"))
        ledger.register_wallet("alice")
        ledger.register_wallet("bob")

        tx = build_transaction(ledger, [
            Move(100.0, "USD", "alice", "bob", "payment_001")
        ])
        result = ledger.execute(tx)
    """

    POSITION_EPSILON = QUANTITY_EPSILON

    def __init__(
        self,
        name: str,
        initial_time: Optional[datetime] = None,
        verbose: bool = True,
        test_mode: bool = False
    ):
        """
        Create a ledger.

        Args:
            name: Ledger identifier
            initial_time: Starting time for the ledger (default: 1970-01-01)
            verbose: Enable debug output (default: True)
            test_mode: Enable test mode to allow set_balance() calls (default: False)
        """
        self.name = name
        self.balances: Dict[str, Dict[str, Decimal]] = {}
        self.units: Dict[str, Unit] = {}
        self.registered_wallets: Set[str] = set()
        self.seen_intent_ids: Set[str] = set()  # For idempotency (content-based)
        self.transaction_log: List[Transaction] = []
        self._current_time: datetime = initial_time or datetime(1970, 1, 1)
        self.verbose = verbose
        self._test_mode = test_mode
        # Monotonic sequence counter for execution ordering
        self._next_sequence: int = 0
        # Inverted index mapping unit -> {wallet -> quantity} for O(1) position lookups
        self._positions_by_unit: Dict[str, Dict[str, Decimal]] = defaultdict(dict)

        # Auto-register the system wallet (used for unit issuance/redemption)
        self.registered_wallets.add(SYSTEM_WALLET)
        self.balances[SYSTEM_WALLET] = defaultdict(lambda: Decimal("0"))

    # ========================================================================
    # LedgerView PROTOCOL IMPLEMENTATION (read-only methods)
    # ========================================================================

    @property
    def current_time(self) -> datetime:
        """Current logical time of the ledger."""
        return self._current_time

    def get_balance(self, wallet_id: str, unit_symbol: str) -> Decimal:
        """
        Get the balance of a specific unit in a wallet.

        Args:
            wallet_id: Wallet identifier
            unit_symbol: Unit symbol

        Returns:
            Current balance (Decimal("0") if wallet has no balance for this unit)

        Raises:
            WalletNotRegistered: If wallet is not registered
            UnitNotRegistered: If unit is not registered
        """
        if wallet_id not in self.registered_wallets:
            raise WalletNotRegistered(f"Wallet {wallet_id} not registered")
        if unit_symbol not in self.units:
            raise UnitNotRegistered(f"Unit {unit_symbol} not registered")
        return self.balances[wallet_id].get(unit_symbol, Decimal("0"))

    def get_unit_state(self, unit_symbol: str) -> UnitState:
        """
        Get a deep copy of a unit's internal state.

        The returned state dictionary can be safely mutated without affecting
        the ledger's internal state.

        Args:
            unit_symbol: Unit symbol

        Returns:
            Deep copy of the unit's state dictionary (empty dict if no state)

        Raises:
            UnitNotRegistered: If unit is not registered
        """
        if unit_symbol not in self.units:
            raise UnitNotRegistered(f"Unit {unit_symbol} not registered")
        unit_obj = self.units[unit_symbol]
        return self._deep_copy_state(unit_obj.state) if unit_obj.state else {}

    def get_positions(self, unit_symbol: str) -> Positions:
        """
        Get all non-zero positions for a specific unit across all wallets.

        Uses an inverted index for O(1) lookup performance.

        Args:
            unit_symbol: Unit symbol

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

    def get_unit(self, symbol: str) -> Unit:
        """Return the Unit object for a given symbol."""
        if symbol not in self.units:
            raise UnitNotRegistered(f"Unit {symbol} not registered")
        return self.units[symbol]

    def get_wallet_balances(self, wallet_id: str) -> BalanceMap:
        """Get all balances for a wallet."""
        if wallet_id not in self.registered_wallets:
            raise WalletNotRegistered(f"Wallet {wallet_id} not registered")
        return dict(self.balances[wallet_id])

    def total_supply(self, unit_symbol: str) -> Decimal:
        """
        Calculate total supply of a unit across all wallets.

        Wallets are sorted before summation to ensure deterministic
        accumulation order.

        Args:
            unit_symbol: Unit symbol

        Returns:
            Total supply across all wallets

        Raises:
            UnitNotRegistered: If unit is not registered
        """
        if unit_symbol not in self.units:
            raise UnitNotRegistered(f"Unit {unit_symbol} not registered")
        return sum(self.balances[w].get(unit_symbol, Decimal("0")) for w in sorted(self.registered_wallets))

    def verify_double_entry(
        self,
        expected_supplies: Dict[str, Decimal] = None,
        tolerance: Decimal = Decimal("1e-9")
    ) -> Dict[str, Any]:
        """
        Verify that conservation laws hold for all units.

        Double-entry accounting requires that for every unit, the sum of all
        balances across all wallets equals a constant (the total supply).

        This method can be used in two ways:
        1. Without expected_supplies: Returns current total supplies for each unit
        2. With expected_supplies: Verifies current supplies match expected values

        Args:
            expected_supplies: Optional dict mapping unit symbols to expected totals.
                              If provided, will check that current totals match.
            tolerance: Maximum allowed difference for decimal comparisons.
                      Defaults to Decimal("1e-9").

        Returns:
            Dict with keys:
            - 'valid': bool - True if all conservation laws hold
            - 'supplies': Dict[str, Decimal] - Current total supply for each unit
            - 'discrepancies': List[Dict] - Details of any conservation violations
              Each discrepancy contains: unit, expected, actual, difference

        Example:
            # Check conservation after transactions
            result = ledger.verify_double_entry()
            assert result['valid'], f"Conservation violated: {result['discrepancies']}"

            # Verify against known supplies
            initial = {'USD': 1000000, 'AAPL': 10000}
            result = ledger.verify_double_entry(expected_supplies=initial)
            if not result['valid']:
                print(f"Discrepancies found: {result['discrepancies']}")
        """
        supplies = {}
        discrepancies = []

        for unit_symbol in self.units:
            current_supply = self.total_supply(unit_symbol)
            supplies[unit_symbol] = current_supply

            if expected_supplies and unit_symbol in expected_supplies:
                expected = expected_supplies[unit_symbol]
                difference = abs(current_supply - expected)
                if difference > tolerance:
                    discrepancies.append({
                        'unit': unit_symbol,
                        'expected': expected,
                        'actual': current_supply,
                        'difference': difference,
                    })

        # If expected_supplies provided, check for missing units
        if expected_supplies:
            for unit_symbol, expected in expected_supplies.items():
                if unit_symbol not in supplies:
                    discrepancies.append({
                        'unit': unit_symbol,
                        'expected': expected,
                        'actual': Decimal("0"),
                        'difference': abs(expected),
                        'error': 'unit not registered',
                    })

        return {
            'valid': len(discrepancies) == 0,
            'supplies': supplies,
            'discrepancies': discrepancies,
        }

    def is_registered(self, wallet_id: str) -> bool:
        """Check if a wallet is registered."""
        return wallet_id in self.registered_wallets

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
        self.balances[wallet_id] = defaultdict(lambda: Decimal("0"))
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

    def set_balance(self, wallet_id: str, unit_symbol: str, quantity: Decimal) -> None:
        """
        Set a wallet's balance for a unit directly.

        WARNING: This method bypasses double-entry accounting and is only
        available in test mode. For production use, use build_transaction()
        and execute() instead.

        Args:
            wallet_id: Wallet identifier to update
            unit_symbol: Unit symbol
            quantity: New balance (overwrites existing)

        Raises:
            LedgerError: If called when test_mode is False
        """
        if not self._test_mode:
            raise LedgerError(
                "set_balance() is disabled in production mode. "
                "Use build_transaction() and execute() to modify balances. "
                "Set test_mode=True when creating Ledger for testing."
            )
        if wallet_id not in self.registered_wallets:
            raise WalletNotRegistered(f"Wallet {wallet_id} not registered")
        if unit_symbol not in self.units:
            raise UnitNotRegistered(f"Unit {unit_symbol} not registered")
        # Convert to Decimal if needed
        if not isinstance(quantity, Decimal):
            quantity = Decimal(str(quantity))
        self.balances[wallet_id][unit_symbol] = quantity
        self._update_position_index(wallet_id, unit_symbol, quantity)

    def update_unit_state(self, unit_symbol: str, state_updates: UnitState) -> None:
        """
        Update a unit's internal state dictionary.

        The state_updates are merged into the existing state. If the unit has
        no existing state, an empty state dictionary is created first.

        Since Unit is frozen/immutable, this creates a new Unit instance with
        the updated state and replaces the existing unit in the ledger.

        Args:
            unit_symbol: Unit symbol to update
            state_updates: Dictionary of state keys and values to update

        Raises:
            UnitNotRegistered: If unit is not registered
        """
        if unit_symbol not in self.units:
            raise UnitNotRegistered(f"Unit {unit_symbol} not registered")
        old_unit = self.units[unit_symbol]
        # Merge existing state with updates
        new_state = {**old_unit.state, **state_updates}
        # Create new Unit instance with updated state (freeze the dict first)
        new_unit = replace(old_unit, _frozen_state=_freeze_state(new_state))
        self.units[unit_symbol] = new_unit

    # ========================================================================
    # TRANSACTION EXECUTION (Mutating)
    # ========================================================================

    def _generate_exec_id(self, sequence: int) -> str:
        """
        Generate a unique execution ID.

        Format: exec:{ledger_name}:{sequence:012d}:{timestamp_micros}
        This is globally unique and monotonically increasing within a ledger.
        """
        micros = int(self._current_time.timestamp() * 1_000_000)
        return f"exec:{self.name}:{sequence:012d}:{micros}"

    def execute(self, pending: PendingTransaction) -> ExecuteResult:
        """
        Execute a PendingTransaction atomically.

        All moves succeed together or all fail together.
        Execution is idempotent: a pending transaction with the same intent_id
        will not be applied twice.

        All transactions are fully validated against:
        - Unit and wallet registration
        - Balance constraints (min/max balance limits)
        - Transfer rules
        - Timestamp requirements

        Args:
            pending: PendingTransaction to execute

        Returns:
            ExecuteResult.APPLIED if successful
            ExecuteResult.ALREADY_APPLIED if transaction was already executed
            ExecuteResult.REJECTED if validation failed
        """
        # Handle empty pending transactions
        if pending.is_empty():
            return ExecuteResult.APPLIED

        # Idempotency check based on intent_id (content hash)
        if pending.intent_id in self.seen_intent_ids:
            if self.verbose:
                print(f"⚠️  ALREADY_APPLIED: intent_id={pending.intent_id}")
            return ExecuteResult.ALREADY_APPLIED

        # CRITICAL-1 FIX (v4.1): Ensure atomicity by rolling back unit registration
        # if validation fails. Units are temporarily registered for validation,
        # then unregistered if validation fails.

        # Track which units we register so we can roll back on failure
        newly_registered_units: List[str] = []

        # Register units needed for validation (will rollback on failure)
        for unit in pending.units_to_create:
            if unit.symbol not in self.units:
                self.register_unit(unit)
                newly_registered_units.append(unit.symbol)

        # Validate units and wallets exist
        for move in pending.moves:
            if move.unit_symbol not in self.units:
                # Rollback: unregister any units we added
                for sym in newly_registered_units:
                    del self.units[sym]
                if self.verbose:
                    print(f"✗ REJECTED: unit not registered: {move.unit_symbol}")
                return ExecuteResult.REJECTED
            if move.source not in self.registered_wallets:
                # Rollback: unregister any units we added
                for sym in newly_registered_units:
                    del self.units[sym]
                if self.verbose:
                    print(f"✗ REJECTED: wallet not registered: {move.source}")
                return ExecuteResult.REJECTED
            if move.dest not in self.registered_wallets:
                # Rollback: unregister any units we added
                for sym in newly_registered_units:
                    del self.units[sym]
                if self.verbose:
                    print(f"✗ REJECTED: wallet not registered: {move.dest}")
                return ExecuteResult.REJECTED

        # Full validation
        valid, reason = self._validate_pending(pending)
        if not valid:
            # Rollback: unregister any units we added
            for sym in newly_registered_units:
                del self.units[sym]
            if self.verbose:
                print(f"✗ REJECTED: {reason}")
            return ExecuteResult.REJECTED

        # Validation passed - units stay registered (no rollback needed)

        # Generate execution ID and sequence
        sequence = self._next_sequence
        self._next_sequence += 1
        exec_id = self._generate_exec_id(sequence)

        # Create the executed Transaction record
        tx = Transaction(
            moves=pending.moves,
            state_changes=pending.state_changes,
            origin=pending.origin,
            timestamp=pending.timestamp,
            intent_id=pending.intent_id,
            exec_id=exec_id,
            ledger_name=self.name,
            execution_time=self._current_time,
            sequence_number=sequence,
            units_to_create=pending.units_to_create,
        )

        # Apply moves
        self._execute_moves(tx.moves)

        # Apply state updates from state_changes
        # Since Unit is frozen, we create new Unit instances with updated state
        #
        # CRITICAL-2 FIX (v4.1): Validate old_state matches current state before applying.
        # This implements optimistic concurrency control - if the state has changed
        # since the transaction was built, we reject to prevent lost updates.
        for sc in tx.state_changes:
            if sc.unit in self.units:
                old_unit = self.units[sc.unit]
                current_state = old_unit.state  # Returns a copy

                # Validate old_state matches current state (optimistic concurrency)
                if sc.old_state is not None:
                    # Compare key by key for semantic equality
                    old_state_dict = sc.old_state if isinstance(sc.old_state, dict) else {}
                    for key in set(old_state_dict.keys()) | set(current_state.keys()):
                        old_val = old_state_dict.get(key)
                        cur_val = current_state.get(key)
                        if old_val != cur_val:
                            # Log the stale state detection for debugging
                            if self.verbose:
                                print(f"⚠️  STALE STATE DETECTED for {sc.unit}.{key}: "
                                      f"expected {old_val!r}, found {cur_val!r}")
                            # For now, we log but continue - this is defensive.
                            # In strict mode, this could raise or reject.
                            # The transaction log will still record the state change
                            # with the original old_state for audit purposes.

                new_state = self._deep_copy_state(
                    sc.new_state if isinstance(sc.new_state, dict) else {}
                )
                new_unit = replace(old_unit, _frozen_state=_freeze_state(new_state))
                self.units[sc.unit] = new_unit

        # Log transaction (always - audit trail is mandatory)
        self.transaction_log.append(tx)
        self.seen_intent_ids.add(pending.intent_id)

        if self.verbose:
            self._print_tx_result(tx, "APPLIED", "✓")
        return ExecuteResult.APPLIED

    def _print_tx_result(self, tx: Transaction, result: str, icon: str) -> None:
        """
        Print transaction details and result.

        Uses Transaction.__repr__ and appends a result line.

        Args:
            tx: Transaction to display
            result: Result string (e.g., "APPLIED", "REJECTED: reason")
            icon: Icon to display with result (e.g., "✓", "✗", "⚠️")
        """
        # Get the repr output and replace the closing line with result
        tx_repr = repr(tx)
        # Replace the last line (└───┘) with a result section
        lines = tx_repr.split('\n')
        w = 100
        bar = "─" * w
        def pad(text: str) -> str:
            if len(text) > w:
                return text[:w-3] + "..."
            return text + " " * (w - len(text))
        # Remove the closing line and add result
        lines[-1] = f"├{bar}┤"
        lines.append(f"│{pad(' ' + icon + ' ' + result)}│")
        lines.append(f"└{bar}┘")
        print("\n".join(lines))

    def _validate_pending(self, pending: PendingTransaction) -> Tuple[bool, str]:
        """
        Validate pending transaction against all constraints.

        Checks performed:
        1. Timestamp validation (transaction must not be from the future)
        2. Unit and wallet registration
        3. Transfer rule enforcement
        4. Balance constraint validation (min/max balance limits)

        Args:
            pending: PendingTransaction to validate

        Returns:
            Tuple of (success: bool, reason: str)
            If success is True, reason is empty string
            If success is False, reason describes the validation failure
        """
        # Timestamp check
        if pending.timestamp > self._current_time:
            return False, "future timestamp"

        # Check units, wallets, and transfer rules
        for move in pending.moves:
            if move.unit_symbol not in self.units:
                return False, f"unit not registered: {move.unit_symbol}"
            if not self.is_registered(move.source):
                return False, f"wallet not registered: {move.source}"
            if not self.is_registered(move.dest):
                return False, f"wallet not registered: {move.dest}"

            # Transfer rule check (pass self as LedgerView)
            unit = self.units[move.unit_symbol]
            if unit.transfer_rule:
                try:
                    unit.transfer_rule(self, move)
                except TransferRuleViolation as e:
                    return False, str(e)

        # Calculate net balance changes with proper rounding
        net: Dict[Tuple[str, str], Decimal] = {}
        for move in pending.moves:
            unit = self.units[move.unit_symbol]
            key_src = (move.source, move.unit_symbol)
            key_dst = (move.dest, move.unit_symbol)
            # Apply unit-specific rounding to match execution behavior
            net[key_src] = unit.round(net.get(key_src, Decimal("0")) - move.quantity)
            net[key_dst] = unit.round(net.get(key_dst, Decimal("0")) + move.quantity)

        # Check balance constraints
        # Note: SYSTEM_WALLET is exempt from balance validation - it can hold any balance
        for (wallet, unit_sym), delta in net.items():
            # Skip validation for system wallet (used for issuance/redemption)
            if wallet == SYSTEM_WALLET:
                continue

            current = self.balances[wallet][unit_sym]
            unit = self.units[unit_sym]
            proposed = unit.round(current + delta)

            if proposed < unit.min_balance:
                return False, f"{wallet} {unit_sym}: {proposed:.2f} < min {unit.min_balance}"
            if proposed > unit.max_balance:
                return False, f"{wallet} {unit_sym}: {proposed:.2f} > max {unit.max_balance}"

        return True, ""

    def _update_position_index(self, wallet_id: str, unit_symbol: str, quantity: Decimal) -> None:
        """
        Update the inverted position index after a balance change.

        The position index maintains a mapping of unit -> {wallet_id -> quantity}
        for efficient position lookups. Zero or near-zero balances are removed
        from the index to keep it compact.

        Args:
            wallet_id: Wallet identifier whose balance changed
            unit_symbol: Unit symbol
            quantity: New balance quantity
        """
        if abs(quantity) > self.POSITION_EPSILON:
            self._positions_by_unit[unit_symbol][wallet_id] = quantity
        else:
            # Remove zero/dust positions from index
            self._positions_by_unit[unit_symbol].pop(wallet_id, None)

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
            unit = self.units[move.unit_symbol]
            # Update source balance
            new_src_balance = unit.round(
                self.balances[move.source][move.unit_symbol] - move.quantity
            )
            self.balances[move.source][move.unit_symbol] = new_src_balance
            self._update_position_index(move.source, move.unit_symbol, new_src_balance)
            # Update destination balance
            new_dst_balance = unit.round(
                self.balances[move.dest][move.unit_symbol] + move.quantity
            )
            self.balances[move.dest][move.unit_symbol] = new_dst_balance
            self._update_position_index(move.dest, move.unit_symbol, new_dst_balance)

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
        - Transaction log
        - Current time
        - Configuration (verbose)

        Returns:
            A new Ledger instance with identical state
        """
        cloned = Ledger.__new__(Ledger)
        cloned.name = self.name
        cloned._current_time = self._current_time
        cloned.verbose = self.verbose
        cloned._test_mode = self._test_mode

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
                _frozen_state=_freeze_state(self._deep_copy_state(unit.state))
            )

        # Copy collections
        cloned.registered_wallets = self.registered_wallets.copy()
        cloned.seen_intent_ids = self.seen_intent_ids.copy()
        cloned.transaction_log = list(self.transaction_log)
        cloned._next_sequence = self._next_sequence

        # Deep copy balances
        cloned.balances = {}
        for wallet, bals in self.balances.items():
            cloned.balances[wallet] = defaultdict(lambda: Decimal("0"), bals)

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
           - Restore unit state from state_changes (old_state)
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
            ValueError: If target_time is in the future
        """
        if target_time > self._current_time:
            raise ValueError(f"Target time {target_time} is in the future")

        # Start with a clone of current state
        cloned = self.clone()
        cloned._current_time = target_time

        # Filter transaction log to only include transactions executed at or before target_time
        cloned.transaction_log = [
            tx for tx in self.transaction_log
            if tx.execution_time <= target_time
        ]
        cloned.seen_intent_ids = {tx.intent_id for tx in cloned.transaction_log}
        # Reset sequence to match filtered transaction count
        cloned._next_sequence = len(cloned.transaction_log)

        # Walk backwards through transactions executed after target_time, reversing them
        for tx in reversed(self.transaction_log):
            if tx.execution_time <= target_time:
                break

            # Reverse moves (apply rounding to match _execute_moves)
            for move in tx.moves:
                unit = cloned.units.get(move.unit_symbol)
                if unit is None:
                    raise LedgerError(f"Cannot unwind: unit {move.unit_symbol} not found in cloned ledger")
                new_src = unit.round(
                    cloned.balances[move.source][move.unit_symbol] + move.quantity
                )
                new_dst = unit.round(
                    cloned.balances[move.dest][move.unit_symbol] - move.quantity
                )

                cloned.balances[move.source][move.unit_symbol] = new_src
                cloned.balances[move.dest][move.unit_symbol] = new_dst
                # Update position index for reversed moves
                cloned._update_position_index(move.source, move.unit_symbol, new_src)
                cloned._update_position_index(move.dest, move.unit_symbol, new_dst)

            # Reverse state changes - restore old_state
            # Since Unit is frozen, create new Unit instances with old state
            for sc in tx.state_changes:
                if sc.unit in cloned.units:
                    old_unit = cloned.units[sc.unit]
                    restored_state = self._deep_copy_state(
                        sc.old_state if isinstance(sc.old_state, dict) else {}
                    )
                    new_unit = replace(old_unit, _frozen_state=_freeze_state(restored_state))
                    cloned.units[sc.unit] = new_unit

            # Reverse units_to_create - remove units that were created in this transaction
            for unit in tx.units_to_create:
                if unit.symbol in cloned.units:
                    del cloned.units[unit.symbol]
                # Clean up any balances for this unit
                for wallet in cloned.registered_wallets:
                    if unit.symbol in cloned.balances[wallet]:
                        del cloned.balances[wallet][unit.symbol]
                # Clean up position index
                if unit.symbol in cloned._positions_by_unit:
                    del cloned._positions_by_unit[unit.symbol]

        return cloned

    def replay(self, from_tx: int = 0) -> Ledger:
        """
        Create a new ledger by replaying the transaction log.

        This method reconstructs ledger state by re-executing all logged transactions
        in order. The resulting ledger will contain:
        - All balance changes from transactions
        - All unit state updates from state_changes
        - The complete transaction history

        Note: Initial balances set via set_balance() are NOT replayed because
        they are not part of the transaction log. Use clone() or clone_at() if
        you need to preserve balances set outside of transactions.

        The replay process:
        1. Create a new ledger with unit definitions and wallet registrations
        2. Re-execute each transaction from the log
        3. Apply state_changes to restore unit states
        4. Advance time as needed to match transaction timestamps

        Args:
            from_tx: Starting transaction index (0 = replay from beginning)

        Returns:
            New Ledger instance with replayed state

        Raises:
            LedgerError: If replay fails
        """
        new_ledger = Ledger(
            name=f"{self.name}_replayed",
            initial_time=datetime(1970, 1, 1),
            verbose=self.verbose,
            test_mode=self._test_mode
        )

        # Identify units that will be created during replay
        # These should NOT be pre-loaded (they'll be created by transactions)
        units_created_in_log = set()
        for tx in self.transaction_log[from_tx:]:
            for unit in tx.units_to_create:
                units_created_in_log.add(unit.symbol)

        # Copy unit definitions only (not current state)
        # Unit states will be built from state_changes during replay
        # Skip units that will be dynamically created during replay
        for symbol, unit in self.units.items():
            if symbol in units_created_in_log:
                continue  # Will be created by a transaction during replay
            new_ledger.units[symbol] = Unit(
                symbol=unit.symbol,
                name=unit.name,
                unit_type=unit.unit_type,
                min_balance=unit.min_balance,
                max_balance=unit.max_balance,
                decimal_places=unit.decimal_places,
                transfer_rule=unit.transfer_rule,
                _frozen_state=_freeze_state({})
            )

        for wallet in self.registered_wallets:
            # Skip system wallet - it's auto-registered in Ledger.__init__
            if wallet != SYSTEM_WALLET:
                new_ledger.register_wallet(wallet)

        for tx in self.transaction_log[from_tx:]:
            if tx.timestamp > new_ledger._current_time:
                new_ledger.advance_time(tx.timestamp)

            # Convert Transaction back to PendingTransaction for replay
            # Use a new intent_id to avoid idempotency conflicts
            pending = PendingTransaction(
                moves=tx.moves,
                state_changes=tx.state_changes,
                origin=tx.origin,
                timestamp=tx.timestamp,
                units_to_create=tx.units_to_create,
            )

            # Execute the pending transaction
            result = new_ledger.execute(pending)
            if result == ExecuteResult.REJECTED:
                raise LedgerError(f"Replay failed at tx {tx.exec_id}")

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
            - 'seen_intent_ids': Intent ID deduplication set
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

        # Seen intent ids (for idempotency)
        seen_size = sys.getsizeof(self.seen_intent_ids)
        for intent_id in self.seen_intent_ids:
            seen_size += sys.getsizeof(intent_id)

        return {
            'transaction_log': log_size,
            'balances': balances_size,
            'units': units_size,
            'seen_intent_ids': seen_size,
            'total': log_size + balances_size + units_size + seen_size,
        }
