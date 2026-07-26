from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from phase_tool.canonical import canonical_bytes, profile_digest, profile_digest_bytes

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT / "fixtures" / "stage2" / "canonical-profile-v1.json").read_text(encoding="utf-8"))


def test_literal_golden_profile_vectors_are_independently_verified() -> None:
    assert VECTORS["profile"] == "phase-canonical-json-v1"
    for vector in VECTORS["vectors"]:
        expected_canonical = bytes.fromhex(vector["canonical_hex"])
        expected_preimage = bytes.fromhex(vector["preimage_hex"])
        assert canonical_bytes(vector["value"]) == expected_canonical
        assert hashlib.sha256(expected_preimage).hexdigest() == vector["digest"].split(":", 1)[1]
        assert profile_digest(vector["domain"], vector["value"]) == vector["digest"]
        assert profile_digest_bytes(vector["domain"], expected_canonical) == vector["digest"]


def test_digest_domains_are_not_interchangeable() -> None:
    value = {"same": "bytes"}
    digests = {profile_digest(domain, value) for domain in ("candidate", "request", "effect-plan", "intent", "receipt")}
    assert len(digests) == 5


@pytest.mark.parametrize("domain", ["", "has space", "é", "UPPER", "a/b"])
def test_invalid_digest_domains_are_rejected(domain: str) -> None:
    with pytest.raises(ValueError):
        profile_digest(domain, {})
