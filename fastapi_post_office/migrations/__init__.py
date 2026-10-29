"""Explicit, additive migration helpers; never run automatically at application startup."""

from .v0_2 import upgrade as upgrade_0_2

__all__ = ["upgrade_0_2"]
