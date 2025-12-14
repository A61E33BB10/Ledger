"""
scheduled_events.py - Minimal Event Scheduler

Simplified event scheduling following expert committee recommendations:
- ~180 lines instead of 1,100+
- Simple heap-based scheduling
- Events are just data, handlers are just functions
- The transaction log IS the audit trail (no separate event status tracking)

Core concepts:
1. Event: Immutable specification of what should happen and when
2. EventScheduler: Simple priority queue for due event retrieval
3. Handlers: Plain functions that process events -> PendingTransaction
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Callable, Any, FrozenSet
import heapq

from .core import LedgerView, PendingTransaction, empty_pending_transaction


# ============================================================================
# EVENT DATA STRUCTURE
# ============================================================================

@dataclass(frozen=True, slots=True)
class Event:
    """
    Immutable scheduled lifecycle event.

    Sorting: by trigger_time, then priority (lower=first), then symbol.

    Attributes:
        trigger_time: When this event should execute
        priority: Execution order within same timestamp (0=first)
        symbol: Unit symbol this event affects
        action: Event type string ("dividend", "coupon", "expiry", etc.)
        params: Event-specific parameters as frozen tuple of (key, value) pairs
    """
    trigger_time: datetime
    priority: int = 0
    symbol: str = ""
    action: str = ""
    params: tuple = ()  # Frozen for hashability: (("key1", "val1"), ("key2", "val2"))

    def __lt__(self, other: 'Event') -> bool:
        """Enable heap ordering: time, then priority, then symbol."""
        if self.trigger_time != other.trigger_time:
            return self.trigger_time < other.trigger_time
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.symbol < other.symbol

    @property
    def params_dict(self) -> Dict[str, Any]:
        """Get params as a dictionary for convenience."""
        return dict(self.params)

    @property
    def event_id(self) -> str:
        """Deterministic ID for deduplication (includes params for uniqueness)."""
        params_str = "|".join(f"{k}={v}" for k, v in sorted(self.params))
        return f"{self.action}:{self.symbol}:{self.trigger_time.isoformat()}:{params_str}"


# ============================================================================
# EVENT SCHEDULER
# ============================================================================

# Handler type: (event, view, prices) -> PendingTransaction
EventHandler = Callable[[Event, LedgerView, Dict[str, Decimal]], PendingTransaction]


class EventScheduler:
    """
    Minimal event scheduler using a priority queue.

    Design:
    - Events are scheduled in advance
    - get_due() returns events ready to execute
    - After execution, the TRANSACTION LOG is the audit trail
    - No separate event status tracking needed
    """

    def __init__(self):
        self._heap: List[Event] = []
        self._handlers: Dict[str, EventHandler] = {}
        self._executed: set = set()  # Track executed event_ids for deduplication

    def register(self, action: str, handler: EventHandler) -> None:
        """Register a handler function for an action type."""
        self._handlers[action] = handler

    def schedule(self, event: Event) -> str:
        """
        Add an event to the pending queue.

        Returns the event_id.
        """
        heapq.heappush(self._heap, event)
        return event.event_id

    def schedule_many(self, events: List[Event]) -> List[str]:
        """Add multiple events efficiently."""
        ids = []
        for event in events:
            ids.append(self.schedule(event))
        return ids

    def get_due(self, as_of: datetime) -> List[Event]:
        """
        Get and remove events due for execution.

        Returns events with trigger_time <= as_of, in execution order.
        Already-executed events are skipped.
        """
        due = []

        while self._heap and self._heap[0].trigger_time <= as_of:
            event = heapq.heappop(self._heap)
            if event.event_id not in self._executed:
                due.append(event)

        return due

    def execute(
        self,
        event: Event,
        view: LedgerView,
        prices: Dict[str, Decimal],
    ) -> Optional[PendingTransaction]:
        """
        Execute a single event via its registered handler.

        Returns PendingTransaction or None if no handler registered.

        Raises:
            Exception: Any exception raised by the handler propagates unchanged.
                       Handlers are expected to be pure functions that either
                       return a valid PendingTransaction or raise an explicit error.
                       Silent failures are forbidden by design.
        """
        handler = self._handlers.get(event.action)
        if not handler:
            return None

        # Execute handler - exceptions propagate (no silent swallowing)
        # This ensures failures are explicit and debuggable
        result = handler(event, view, prices)
        self._executed.add(event.event_id)
        return result

    def step(
        self,
        as_of: datetime,
        view: LedgerView,
        prices: Dict[str, Decimal],
    ) -> List[PendingTransaction]:
        """
        Process all due events and return their transactions.

        This is the main entry point for lifecycle processing.
        """
        transactions = []
        for event in self.get_due(as_of):
            tx = self.execute(event, view, prices)
            if tx is not None and not tx.is_empty():
                transactions.append(tx)
        return transactions

    def pending_count(self) -> int:
        """Number of pending events."""
        return len(self._heap)

    def peek_next(self) -> Optional[Event]:
        """Peek at next scheduled event without removing it."""
        return self._heap[0] if self._heap else None

    def clear_executed(self) -> None:
        """Clear the executed event tracking (for testing/reset)."""
        self._executed.clear()


# ============================================================================
# EVENT FACTORY FUNCTIONS
# ============================================================================

def dividend_event(
    symbol: str,
    ex_date: datetime,
    amount_per_share: Decimal,
    currency: str,
    payment_date: Optional[datetime] = None,
) -> Event:
    """Create a dividend event."""
    return Event(
        trigger_time=ex_date,
        priority=0,  # Record phase
        symbol=symbol,
        action="dividend",
        params=(
            ("amount_per_share", str(amount_per_share)),
            ("currency", currency),
            ("payment_date", payment_date.isoformat() if payment_date else ""),
        ),
    )


def coupon_event(
    bond_symbol: str,
    payment_date: datetime,
    coupon_amount: Decimal,
    currency: str,
) -> Event:
    """Create a bond coupon payment event."""
    return Event(
        trigger_time=payment_date,
        priority=30,  # Payment phase
        symbol=bond_symbol,
        action="coupon",
        params=(
            ("coupon_amount", str(coupon_amount)),
            ("currency", currency),
        ),
    )


def maturity_event(
    bond_symbol: str,
    maturity_date: datetime,
    redemption_price: Decimal,
    currency: str,
) -> Event:
    """Create a bond maturity/redemption event."""
    return Event(
        trigger_time=maturity_date,
        priority=40,  # Settlement phase
        symbol=bond_symbol,
        action="maturity",
        params=(
            ("redemption_price", str(redemption_price)),
            ("currency", currency),
        ),
    )


def expiry_event(
    symbol: str,
    expiry_date: datetime,
    underlying: str,
) -> Event:
    """Create an option/derivative expiry event."""
    return Event(
        trigger_time=expiry_date,
        priority=40,  # Settlement phase
        symbol=symbol,
        action="expiry",
        params=(("underlying", underlying),),
    )


def settlement_event(
    symbol: str,
    settlement_date: datetime,
    underlying: Optional[str] = None,
) -> Event:
    """Create a settlement event (forward, cash, etc.)."""
    params = []
    if underlying:
        params.append(("underlying", underlying))
    return Event(
        trigger_time=settlement_date,
        priority=40,  # Settlement phase
        symbol=symbol,
        action="settlement",
        params=tuple(params),
    )


def split_event(
    symbol: str,
    effective_date: datetime,
    ratio: Decimal,
) -> Event:
    """Create a stock split event."""
    return Event(
        trigger_time=effective_date,
        priority=0,  # Record phase
        symbol=symbol,
        action="split",
        params=(("ratio", str(ratio)),),
    )
