from __future__ import annotations

import os
from pathlib import Path

import pytest

if os.name == "nt":
    pytest.skip("POSIX authority conformance requires POSIX", allow_module_level=True)

from phase_tool.mutation.posix import PosixAuthorityProvider
from tests.mutation.common.conformance import assert_basic_authority_conformance
from tests.mutation.common.guarantee_conformance import assert_common_guarantees


def test_posix_authority_common_conformance(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    assert_basic_authority_conformance(PosixAuthorityProvider(), root)


def test_posix_production_profile_common_guarantees(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    provider = PosixAuthorityProvider()
    binding = provider.guarantee_profile_binding()
    assert binding.id == "phase.posix.authority.v1"
    assert_common_guarantees(provider, root)


def test_posix_production_profile_claims_only_executable_conformance_guarantees() -> None:
    from phase_tool.registry import BundledRegistry

    provider = PosixAuthorityProvider()
    profile = BundledRegistry.load().resolve_guarantee_profile(provider.guarantee_profile_binding().as_dict())

    assert profile["classification"] == "production"
    assert set(profile["provided_guarantees"]) == {
        "exclusive_create",
        "readback_verification",
        "cross_process_serialization",
        "namespace_bound_mutation",
        "atomic_replace",
        "namespace_metadata_flush_attempted",
    }
    assert {item["guarantee"] for item in profile["conformance"]} == set(profile["provided_guarantees"])
    assert "process_crash_recovery" not in profile["provided_guarantees"]
