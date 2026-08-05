from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Callable

from .authority import TargetAuthority as TargetAuthorityProtocol
from .target_authority import TargetAuthority, TargetRootLock


class LegacyAuthorityProvider:
    """Compatibility adapter for the pre-split mixed authority implementation."""

    def open_authority(
        self,
        root: Path,
        locator: str,
        reparse_detector: Callable[[Path], bool] | None = None,
    ) -> TargetAuthorityProtocol:
        return TargetAuthority(root, locator, reparse_detector)

    def lock_target_root(self, root: Path, scope: str) -> AbstractContextManager[object]:
        return TargetRootLock(root, scope)


LEGACY_AUTHORITY_PROVIDER = LegacyAuthorityProvider()
