from __future__ import annotations

import os
from pathlib import Path

import pytest

if os.name == "nt":
    pytest.skip("POSIX authority conformance requires POSIX", allow_module_level=True)

from phase_tool.mutation.posix import PosixAuthorityProvider
from tests.mutation.common.conformance import assert_basic_authority_conformance


def test_posix_authority_common_conformance(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    assert_basic_authority_conformance(PosixAuthorityProvider(), root)
