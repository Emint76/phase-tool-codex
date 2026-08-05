from __future__ import annotations

from dataclasses import dataclass

from .mutation.authority import AuthorityProvider
from .mutation.legacy_authority import LegacyAuthorityProvider


@dataclass(frozen=True)
class Installation:
    authority_provider: AuthorityProvider


def host_installation() -> Installation:
    """Build the explicit host installation configuration at one composition boundary."""

    return Installation(authority_provider=LegacyAuthorityProvider())
