from __future__ import annotations

import inspect
import os
from pathlib import Path

from phase_tool.installation import host_installation
from phase_tool.mutation import authority as common_authority
from phase_tool.mutation import target_authority as compatibility_authority


def test_common_authority_module_is_platform_neutral() -> None:
    source = inspect.getsource(common_authority) + inspect.getsource(compatibility_authority)

    assert "ctypes" not in source
    assert "fcntl" not in source
    assert "os.name" not in source


def test_platform_implementations_keep_foreign_primitives_isolated() -> None:
    package_root = Path(common_authority.__file__).parent
    posix_source = (package_root / "posix" / "authority.py").read_text(encoding="utf-8")
    windows_source = (package_root / "windows" / "authority.py").read_text(encoding="utf-8")

    assert "ctypes" not in posix_source
    assert "WinDLL" not in posix_source
    assert "fcntl" not in windows_source
    assert "dir_fd=" not in windows_source


def test_authority_backend_selection_has_one_composition_selector() -> None:
    package_root = Path(common_authority.__file__).parent
    authority_modules = [
        package_root / "authority.py",
        package_root / "target_authority.py",
        package_root / "platform.py",
        package_root / "posix" / "authority.py",
        package_root / "windows" / "authority.py",
    ]
    selectors = [
        path.relative_to(package_root).as_posix()
        for path in authority_modules
        if "os.name" in path.read_text(encoding="utf-8")
    ]

    assert selectors == ["platform.py"]


def test_host_installation_selects_one_physical_platform_provider(tmp_path: Path) -> None:
    installation = host_installation()
    expected_module = "phase_tool.mutation.windows.authority" if os.name == "nt" else "phase_tool.mutation.posix.authority"

    assert installation.authority_provider.__class__.__module__ == expected_module
    root = tmp_path / "root"
    root.mkdir()
    authority = installation.authority_provider.open_authority(root, "nested/item.bin")
    try:
        assert authority.__class__.__module__ == expected_module
    finally:
        authority.close()
