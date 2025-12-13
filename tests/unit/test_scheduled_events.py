"""
test_scheduled_events.py - Unit Tests for Simplified Scheduled Event System

Tests cover:
1. Event creation and properties
2. EventScheduler scheduling and retrieval
3. Event priority ordering
4. Handler registration and execution
5. Event factory functions
"""

import pytest
from datetime import datetime, timedelta

from ledger.scheduled_events import (
    Event,
    EventScheduler,
    dividend_event,
    coupon_event,
    maturity_event,
    expiry_event,
    settlement_event,
    split_event,
)
from ledger.event_handlers import (
    handle_dividend,
    handle_coupon,
    DEFAULT_HANDLERS,
    create_default_scheduler,
)


class TestEvent:
    """Tests for Event dataclass."""

    def test_event_id_is_deterministic(self):
        """Same content produces same event_id."""
        event1 = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="dividend",
            params=(("amount", "0.25"),),
        )
        event2 = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="dividend",
            params=(("amount", "0.25"),),
        )
        assert event1.event_id == event2.event_id

    def test_different_params_different_id(self):
        """Different params produce different event_id."""
        event1 = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="dividend",
            params=(("amount", "0.25"),),
        )
        event2 = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="dividend",
            params=(("amount", "0.30"),),
        )
        assert event1.event_id != event2.event_id

    def test_different_time_different_id(self):
        """Different trigger_time produces different event_id."""
        event1 = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="dividend",
        )
        event2 = Event(
            trigger_time=datetime(2024, 6, 16),
            symbol="AAPL",
            action="dividend",
        )
        assert event1.event_id != event2.event_id

    def test_event_ordering_by_time(self):
        """Events sort by time first."""
        early = Event(
            trigger_time=datetime(2024, 6, 15, 9, 0),
            priority=30,  # Lower priority
            symbol="AAPL",
            action="dividend",
        )
        late = Event(
            trigger_time=datetime(2024, 6, 15, 10, 0),
            priority=0,  # Higher priority
            symbol="AAPL",
            action="dividend",
        )
        # Early time wins even with lower priority
        assert early < late

    def test_event_ordering_by_priority(self):
        """Events at same time sort by priority."""
        high_priority = Event(
            trigger_time=datetime(2024, 6, 15, 9, 0),
            priority=0,
            symbol="AAPL",
            action="split",
        )
        low_priority = Event(
            trigger_time=datetime(2024, 6, 15, 9, 0),
            priority=30,
            symbol="MSFT",
            action="dividend",
        )
        # Lower priority number = higher priority = comes first
        assert high_priority < low_priority

    def test_params_dict_property(self):
        """params_dict converts tuple to dict."""
        event = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="dividend",
            params=(("amount", "0.25"), ("currency", "USD")),
        )
        assert event.params_dict == {"amount": "0.25", "currency": "USD"}


class TestEventScheduler:
    """Tests for EventScheduler."""

    def test_schedule_and_count(self):
        """Can schedule events and count them."""
        scheduler = EventScheduler()
        event = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="dividend",
        )

        event_id = scheduler.schedule(event)

        assert scheduler.pending_count() == 1
        assert event_id == event.event_id

    def test_get_due_events(self):
        """get_due returns events due at or before timestamp."""
        scheduler = EventScheduler()

        early = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="dividend",
        )
        middle = Event(
            trigger_time=datetime(2024, 6, 20),
            symbol="MSFT",
            action="dividend",
        )
        late = Event(
            trigger_time=datetime(2024, 6, 25),
            symbol="GOOG",
            action="dividend",
        )

        scheduler.schedule(early)
        scheduler.schedule(middle)
        scheduler.schedule(late)

        # Query at June 20
        due = scheduler.get_due(as_of=datetime(2024, 6, 20))
        symbols = [e.symbol for e in due]

        assert "AAPL" in symbols
        assert "MSFT" in symbols
        assert "GOOG" not in symbols

    def test_get_due_removes_events(self):
        """get_due removes returned events from queue."""
        scheduler = EventScheduler()
        event = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="dividend",
        )
        scheduler.schedule(event)

        # First call returns the event
        due = scheduler.get_due(as_of=datetime(2024, 6, 15))
        assert len(due) == 1

        # Second call returns nothing (event already retrieved)
        due = scheduler.get_due(as_of=datetime(2024, 6, 15))
        assert len(due) == 0

    def test_get_due_priority_order(self):
        """Due events are returned in priority order."""
        scheduler = EventScheduler()

        low_priority = Event(
            trigger_time=datetime(2024, 6, 15),
            priority=30,
            symbol="DC1",
            action="settlement",
        )
        high_priority = Event(
            trigger_time=datetime(2024, 6, 15),
            priority=0,
            symbol="AAPL",
            action="split",
        )

        scheduler.schedule(low_priority)
        scheduler.schedule(high_priority)

        due = scheduler.get_due(as_of=datetime(2024, 6, 15))

        # High priority (0) should come first
        assert due[0].symbol == "AAPL"
        assert due[1].symbol == "DC1"

    def test_peek_next(self):
        """peek_next shows next event without removing it."""
        scheduler = EventScheduler()
        event = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="dividend",
        )
        scheduler.schedule(event)

        # Peek doesn't remove
        next_event = scheduler.peek_next()
        assert next_event.symbol == "AAPL"
        assert scheduler.pending_count() == 1

    def test_register_and_execute_handler(self):
        """Can register handler and execute events."""
        scheduler = EventScheduler()

        # Track if handler was called
        called = []

        def test_handler(event, view, prices):
            called.append(event.symbol)
            return None  # Would return PendingTransaction

        scheduler.register("test", test_handler)

        event = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="test",
        )

        scheduler.execute(event, None, {})

        assert "AAPL" in called

    def test_execute_unknown_action_returns_none(self):
        """Executing event with no handler returns None."""
        scheduler = EventScheduler()
        event = Event(
            trigger_time=datetime(2024, 6, 15),
            symbol="AAPL",
            action="unknown_action",
        )

        result = scheduler.execute(event, None, {})
        assert result is None

    def test_schedule_many(self):
        """Can schedule multiple events at once."""
        scheduler = EventScheduler()
        events = [
            Event(trigger_time=datetime(2024, 6, 15), symbol="AAPL", action="dividend"),
            Event(trigger_time=datetime(2024, 6, 16), symbol="MSFT", action="dividend"),
            Event(trigger_time=datetime(2024, 6, 17), symbol="GOOG", action="dividend"),
        ]

        ids = scheduler.schedule_many(events)

        assert len(ids) == 3
        assert scheduler.pending_count() == 3


class TestEventFactoryFunctions:
    """Tests for event factory functions."""

    def test_dividend_event(self):
        """dividend_event creates correct event."""
        event = dividend_event(
            symbol="AAPL",
            ex_date=datetime(2024, 6, 15),
            amount_per_share=0.25,
            currency="USD",
        )

        assert event.action == "dividend"
        assert event.symbol == "AAPL"
        assert event.trigger_time == datetime(2024, 6, 15)
        assert event.priority == 0  # Record phase
        assert event.params_dict["amount_per_share"] == "0.25"
        assert event.params_dict["currency"] == "USD"

    def test_coupon_event(self):
        """coupon_event creates correct event."""
        event = coupon_event(
            bond_symbol="CORP_5Y",
            payment_date=datetime(2024, 6, 15),
            coupon_amount=25.0,
            currency="USD",
        )

        assert event.action == "coupon"
        assert event.symbol == "CORP_5Y"
        assert event.priority == 30  # Payment phase

    def test_maturity_event(self):
        """maturity_event creates correct event."""
        event = maturity_event(
            bond_symbol="CORP_5Y",
            maturity_date=datetime(2029, 12, 15),
            redemption_price=1000.0,
            currency="USD",
        )

        assert event.action == "maturity"
        assert event.priority == 40  # Settlement phase
        assert event.params_dict["redemption_price"] == "1000.0"

    def test_expiry_event(self):
        """expiry_event creates correct event with underlying."""
        event = expiry_event(
            symbol="AAPL_CALL_150",
            expiry_date=datetime(2024, 12, 20),
            underlying="AAPL",
        )

        assert event.action == "expiry"
        assert event.priority == 40  # Settlement phase
        assert event.params_dict["underlying"] == "AAPL"

    def test_settlement_event(self):
        """settlement_event creates correct event."""
        event = settlement_event(
            symbol="FWD_AAPL",
            settlement_date=datetime(2024, 12, 20),
            underlying="AAPL",
        )

        assert event.action == "settlement"
        assert event.priority == 40

    def test_split_event(self):
        """split_event creates correct event."""
        event = split_event(
            symbol="AAPL",
            effective_date=datetime(2024, 8, 1),
            ratio=4.0,
        )

        assert event.action == "split"
        assert event.priority == 0  # Record phase
        assert event.params_dict["ratio"] == "4.0"


class TestDefaultScheduler:
    """Tests for default scheduler creation."""

    def test_create_default_scheduler(self):
        """create_default_scheduler registers all default handlers."""
        scheduler = create_default_scheduler()

        # Check all default handlers are registered
        assert "dividend" in scheduler._handlers
        assert "coupon" in scheduler._handlers
        assert "maturity" in scheduler._handlers
        assert "expiry" in scheduler._handlers
        assert "settlement" in scheduler._handlers
        assert "split" in scheduler._handlers

    def test_default_handlers_dict(self):
        """DEFAULT_HANDLERS contains all handler functions."""
        assert "dividend" in DEFAULT_HANDLERS
        assert "coupon" in DEFAULT_HANDLERS
        assert "maturity" in DEFAULT_HANDLERS
        assert "expiry" in DEFAULT_HANDLERS
        assert "settlement" in DEFAULT_HANDLERS
        assert "split" in DEFAULT_HANDLERS
