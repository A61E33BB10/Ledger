"""
lifecycle.py - Lifecycle Engine for Smart Contracts

Orchestrates autonomous execution of smart contracts across the ledger.
Each unit type can have a contract that checks for lifecycle events
such as option expiry, dividend payments, or forward settlement.
"""

from __future__ import annotations
from datetime import datetime
from typing import Dict, List, Protocol, Optional

from .core import LedgerView, ContractResult, Transaction, ExecuteResult, LedgerError
from .ledger import Ledger


class SmartContract(Protocol):
    """
    Protocol for lifecycle-aware contracts.

    Contracts check if any events should fire based on:
    - Current time
    - Current prices
    - Unit state

    Contracts receive a LedgerView and return a ContractResult.
    """

    def check_lifecycle(
        self,
        view: LedgerView,
        symbol: str,
        timestamp: datetime,
        prices: Dict[str, float]
    ) -> ContractResult:
        """
        Check if lifecycle events should fire.

        Args:
            view: Read-only ledger access
            symbol: Unit symbol to check
            timestamp: Current timestamp
            prices: Current market prices

        Returns:
            ContractResult with moves/state updates, or empty if nothing to do.
        """
        ...


class LifecycleEngine:
    """
    Orchestrates smart contract execution across all units.

    Maps unit types to their corresponding smart contracts.
    On each step, iterates all registered units and executes applicable contracts.

    Contracts can be:
    - Objects implementing the SmartContract protocol
    - Callables with signature: (view, symbol, timestamp, prices) -> ContractResult
    """

    def __init__(
        self,
        ledger: Ledger,
        contracts: Optional[Dict[str, SmartContract]] = None
    ):
        self.ledger = ledger
        self.contracts: Dict[str, SmartContract] = contracts or {}

    def register(self, unit_type: str, contract: SmartContract) -> None:
        """Register a contract for a unit type."""
        self.contracts[unit_type] = contract

    def step(
        self,
        timestamp: datetime,
        prices: Dict[str, float]
    ) -> List[Transaction]:
        """
        Advance time and execute all pending lifecycle events.

        Args:
            timestamp: New timestamp
            prices: Current market prices

        Returns:
            List of executed transactions.
        """
        self.ledger.advance_time(timestamp)
        executed = []

        # Sort units for deterministic iteration order (reproducibility)
        for symbol in sorted(self.ledger.units.keys()):
            unit = self.ledger.units[symbol]
            contract = self.contracts.get(unit.unit_type)
            if not contract:
                continue

            # Support both callables and objects with check_lifecycle method
            if hasattr(contract, 'check_lifecycle'):
                result = contract.check_lifecycle(self.ledger, symbol, timestamp, prices)
            else:
                # Assume it's a callable
                result = contract(self.ledger, symbol, timestamp, prices)
            if not result.is_empty():
                exec_result = self.ledger.execute_contract(result)
                if exec_result == ExecuteResult.REJECTED:
                    raise LedgerError(f"Lifecycle event failed for {symbol}: contract execution rejected")
                # Get the most recent transaction if it was logged and applied
                if exec_result == ExecuteResult.APPLIED and self.ledger.transaction_log:
                    executed.append(self.ledger.transaction_log[-1])

        return executed

    def run(
        self,
        timestamps: List[datetime],
        get_prices_at_timestamp,
    ) -> List[Transaction]:
        """
        Run engine through a sequence of timestamps.

        Args:
            timestamps: List of timestamps to process
            get_prices_at_timestamp: Callable(timestamp) -> Dict[str, float]

        Returns:
            All executed transactions.
        """
        all_transactions = []
        for timestamp in timestamps:
            prices = get_prices_at_timestamp(timestamp)
            transactions = self.step(timestamp, prices)
            all_transactions.extend(transactions)
        return all_transactions
