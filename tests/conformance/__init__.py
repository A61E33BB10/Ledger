"""
Conformance Test Suite

This suite defines the NORMATIVE behavior of the Ledger system.
Any compliant implementation MUST pass these tests.

The tests are organized by invariant:
1. conservation.py - Double-entry accounting invariants
2. atomicity.py - All-or-nothing transaction semantics
3. idempotency.py - Duplicate execution handling
4. determinism.py - Reproducible behavior
5. canonicalization.py - Content-addressable identity
6. temporal.py - Time and event ordering

These tests use hypothesis for property-based testing.
"""
