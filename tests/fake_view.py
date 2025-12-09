"""
fake_view.py - Test Helper for LedgerView

Provides a minimal LedgerView implementation for testing contract functions
without requiring a full Ledger instance.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, Set, Optional, Any

from ledger import LedgerView
from ledger.core import Unit


# Type aliases (matching core.py)
Positions = Dict[str, float]
UnitState = Dict[str, Any]


class FakeUnit:
    """Minimal Unit for testing - provides min_balance and max_balance."""
    def __init__(self, symbol: str, min_balance: float = -1_000_000.0, max_balance: float = 1_000_000.0):
        self.symbol = symbol
        self.min_balance = min_balance
        self.max_balance = max_balance


class FakeView:
    """
    Minimal LedgerView implementation for testing contract functions.

    Example:
        view = FakeView(
            balances={'alice': {'USD': 1000, 'AAPL': 10}},
            states={'AAPL': {'issuer': 'AAPL'}},
            time=datetime(2025, 1, 1)
        )

        positions = view.get_positions('AAPL')
        # Returns: {'alice': 10}
    """

    def __init__(
        self,
        balances: Dict[str, Dict[str, float]],
        states: Optional[Dict[str, UnitState]] = None,
        time: Optional[datetime] = None,
        units: Optional[Dict[str, Any]] = None
    ):
        self._balances = balances
        self._states = states or {}
        self._time = time or datetime.now()
        self._units = units or {}

    @property
    def current_time(self) -> datetime:
        return self._time

    def get_balance(self, wallet: str, unit: str) -> float:
        return self._balances.get(wallet, {}).get(unit, 0.0)

    def get_unit_state(self, unit: str) -> UnitState:
        return dict(self._states.get(unit, {}))

    def get_positions(self, unit: str) -> Positions:
        return {
            w: b[unit]
            for w, b in self._balances.items()
            if unit in b and b[unit] != 0
        }

    def list_wallets(self) -> Set[str]:
        return set(self._balances.keys())

    def get_unit(self, symbol: str) -> Any:
        """Return unit or a FakeUnit with default position limits."""
        if symbol in self._units:
            return self._units[symbol]
        # Return a FakeUnit with default futures position limits
        return FakeUnit(symbol)
