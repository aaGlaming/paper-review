"""Shared pagination helpers for API list endpoints."""

from __future__ import annotations


def clamp_page_size(value: int, maximum: int = 100) -> int:
    """Clamp a validated positive page size without changing the public default."""
    return min(int(value), int(maximum))


def page_offset(page: int, size: int) -> int:
    """Return the zero-based offset for a one-based page number."""
    return (int(page) - 1) * int(size)
