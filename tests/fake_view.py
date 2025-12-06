"""
fake_view.py - Test Helper for LedgerView

Provides a minimal LedgerView implementation for testing contract functions
without requiring a full Ledger instance.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, Set, Optional, Any

from ledger import LedgerView


# Type aliases (matching core.py)
Positions = Dict[str, float]
UnitState = Dict[str, Any]


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
        time: Optional[datetime] = None
    ):
        self._balances = balances
        self._states = states or {}
        self._time = time or datetime.now()

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
