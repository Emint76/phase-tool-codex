from __future__ import annotations

import os

if os.name == "nt":
    from .windows.authority import WindowsAuthorityProvider as HostAuthorityProvider
    from .windows.authority import WindowsTargetAuthority as HostTargetAuthority
    from .windows.authority import WindowsTargetRootLock as HostTargetRootLock
else:
    from .posix.authority import PosixAuthorityProvider as HostAuthorityProvider
    from .posix.authority import PosixTargetAuthority as HostTargetAuthority
    from .posix.authority import PosixTargetRootLock as HostTargetRootLock

__all__ = ["HostAuthorityProvider", "HostTargetAuthority", "HostTargetRootLock"]
