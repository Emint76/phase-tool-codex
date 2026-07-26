from __future__ import annotations


class PhaseError(Exception):
    """Fail-closed error with a stable machine-readable code."""

    def __init__(self, code: str, message: str | None = None, *, details: dict | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(f"{code}: {message or code}")
