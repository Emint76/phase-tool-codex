from __future__ import annotations

import os
from pathlib import Path

import pytest

if os.name != "nt":
    pytest.skip("Windows authority conformance requires Windows", allow_module_level=True)

from phase_tool.mutation.windows import WindowsAuthorityProvider
from tests.mutation.common.conformance import assert_basic_authority_conformance


def test_windows_authority_common_conformance(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    assert_basic_authority_conformance(WindowsAuthorityProvider(), root)
