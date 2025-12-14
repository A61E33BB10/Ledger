"""
lifecycle_engine.py - Lifecycle Engine

Combines scheduled events and smart contract polling into a unified lifecycle engine.

Execution order each step():
1. Advance ledger time
2. Process scheduled events (in priority order)
3. Run smart contract polling (discovery)
4. Repeat until no more events fire (cascading effects)

The transaction log is the audit trail - no separate event status tracking needed.
"""

from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Callable

from .core import (
    LedgerView, PendingTransaction, Transaction,
    ExecuteResult, LedgerError,
    SmartContract,
)
from .ledger import Ledger
from .scheduled_events import Event, EventScheduler
from .event_handlers import create_default_scheduler


class LifecycleEngine:
    """
    Lifecycle engine combining scheduled events and smart contract polling.

    Features:
    - Scheduled event processing with proper sequencing
    - Smart contract polling for event discovery
    - Cascading event support (repeat until stable)
    - Full audit trail via transaction log
    """

    def __init__(
        self,
        ledger: Ledger,
        scheduler: Optional[EventScheduler] = None,
        contracts: Optional[Dict[str, SmartContract]] = None,
    ):
        """
        Initialize lifecycle engine.

        Args:
            ledger: The ledger to operate on
            scheduler: Event scheduler (created with default handlers if not provided)
            contracts: Smart contracts for polling (unit_type -> contract)
        """
        self.ledger = ledger
        self.scheduler = scheduler or create_default_scheduler()
        self.contracts: Dict[str, SmartContract] = contracts or {}

        # Configuration
        self.max_passes = 10  # Safety limit for cascading events
        self.verbose = ledger.verbose

    def register(self, unit_type: str, contract: SmartContract) -> None:
        """
        Register a smart contract for a unit type.

        Args:
            unit_type: Type of unit (e.g., "STOCK", "BOND", "DELTA_HEDGE_STRATEGY")
            contract: SmartContract implementation (callable or object with check_lifecycle)
        """
        self.contracts[unit_type] = contract

    def schedule(self, event: Event) -> str:
        """
        Schedule an event for future execution.

        Args:
            event: Event to schedule

        Returns:
            Event ID
        """
        return self.scheduler.schedule(event)

    def schedule_many(self, events: List[Event]) -> List[str]:
        """Schedule multiple events."""
        return self.scheduler.schedule_many(events)

    def step(
        self,
        timestamp: datetime,
        prices: Dict[str, Decimal],
    ) -> List[Transaction]:
        """
        Advance time and execute all pending lifecycle events.

        Processing order:
        1. Advance ledger time
        2. Process scheduled events (in priority order)
        3. Run smart contract polling (discovery)
        4. Repeat until no more events fire

        Args:
            timestamp: New timestamp
            prices: Current market prices

        Returns:
            List of executed transactions
        """
        self.ledger.advance_time(timestamp)
        executed: List[Transaction] = []

        for pass_num in range(self.max_passes):
            pass_executed: List[Transaction] = []

            # Phase 1: Process scheduled events
            scheduled_txs = self._process_scheduled_events(timestamp, prices)
            pass_executed.extend(scheduled_txs)

            # Phase 2: Smart contract polling
            polling_txs = self._process_smart_contracts(timestamp, prices)
            pass_executed.extend(polling_txs)

            executed.extend(pass_executed)

            # If no events fired this pass, we're done
            if not pass_executed:
                break

        return executed

    def _process_scheduled_events(
        self,
        timestamp: datetime,
        prices: Dict[str, Decimal],
    ) -> List[Transaction]:
        """Process all scheduled events due at or before timestamp."""
        executed: List[Transaction] = []

        # Get pending transactions from scheduler
        pending_txs = self.scheduler.step(timestamp, self.ledger, prices)

        for pending_tx in pending_txs:
            if pending_tx.is_empty():
                continue

            if self.verbose:
                print(f"[SCHEDULED] Executing event transaction")

            exec_result = self.ledger.execute(pending_tx)

            if exec_result == ExecuteResult.APPLIED and self.ledger.transaction_log:
                executed.append(self.ledger.transaction_log[-1])

        return executed

    def _process_smart_contracts(
        self,
        timestamp: datetime,
        prices: Dict[str, Decimal],
    ) -> List[Transaction]:
        """Run smart contract polling for event discovery."""
        executed: List[Transaction] = []

        # Sort units for deterministic iteration order
        for symbol in sorted(self.ledger.units.keys()):
            unit = self.ledger.units[symbol]
            contract = self.contracts.get(unit.unit_type)

            if not contract:
                continue

            # Support both callables and objects with check_lifecycle method
            if hasattr(contract, 'check_lifecycle'):
                pending = contract.check_lifecycle(self.ledger, symbol, timestamp, prices)
            else:
                pending = contract(self.ledger, symbol, timestamp, prices)

            if not isinstance(pending, PendingTransaction):
                raise LedgerError(
                    f"Contract for {symbol} must return PendingTransaction, got {type(pending)}"
                )

            if pending.is_empty():
                continue

            exec_result = self.ledger.execute(pending)

            if exec_result == ExecuteResult.REJECTED:
                raise LedgerError(f"Lifecycle event failed for {symbol}: contract execution rejected")

            if exec_result == ExecuteResult.APPLIED and self.ledger.transaction_log:
                executed.append(self.ledger.transaction_log[-1])

        return executed

    def run(
        self,
        timestamps: List[datetime],
        get_prices_at_timestamp: Callable[[datetime], Dict[str, Decimal]],
    ) -> List[Transaction]:
        """
        Run engine through a sequence of timestamps.

        Args:
            timestamps: List of timestamps to process
            get_prices_at_timestamp: Callable returning prices for a timestamp

        Returns:
            All executed transactions
        """
        all_transactions: List[Transaction] = []

        for timestamp in timestamps:
            prices = get_prices_at_timestamp(timestamp)
            transactions = self.step(timestamp, prices)
            all_transactions.extend(transactions)

        return all_transactions

    # ========================================================================
    # QUERY METHODS
    # ========================================================================

    def pending_event_count(self) -> int:
        """Get count of pending scheduled events."""
        return self.scheduler.pending_count()

    def peek_next_event(self) -> Optional[Event]:
        """Peek at the next scheduled event."""
        return self.scheduler.peek_next()
