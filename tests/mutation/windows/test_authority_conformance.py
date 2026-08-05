from __future__ import annotations

import os
from pathlib import Path

import pytest

if os.name != "nt":
    pytest.skip("Windows authority conformance requires Windows", allow_module_level=True)

from phase_tool.mutation.windows import WindowsAuthorityProvider
from tests.mutation.common.conformance import assert_basic_authority_conformance
from tests.mutation.common.guarantee_conformance import assert_common_guarantees


def test_windows_authority_common_conformance(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    assert_basic_authority_conformance(WindowsAuthorityProvider(), root)


def test_windows_compatibility_profile_guarantees(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    provider = WindowsAuthorityProvider()
    binding = provider.guarantee_profile_binding()
    assert binding.id == "phase.windows.authority.v1"
    assert_common_guarantees(provider, root)


def test_windows_compatibility_profile_does_not_claim_unsupported_guarantees() -> None:
    from phase_tool.registry import BundledRegistry

    provider = WindowsAuthorityProvider()
    profile = BundledRegistry.load().resolve_guarantee_profile(provider.guarantee_profile_binding().as_dict())

    assert profile["classification"] == "compatibility"
    assert profile["provided_guarantees"] == [
        "exclusive_create",
        "readback_verification",
        "cross_process_serialization",
    ]
    assert not {
        "namespace_bound_mutation",
        "atomic_replace",
        "namespace_metadata_flush_attempted",
        "process_crash_recovery",
    } & set(profile["provided_guarantees"])
