from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, immutable_value, parse_json_bytes, profile_digest_bytes


@dataclass(frozen=True)
class CapturedCandidate:
    input_mode: str
    captured_bytes: bytes
    canonical_bytes: bytes
    digest: str
    length: int
    value: Any


def _read_once(path: Path, maximum_bytes: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(maximum_bytes + 1)
    if len(data) > maximum_bytes:
        from ..errors import PhaseError
        raise PhaseError("candidate.too_large", f"candidate exceeds {maximum_bytes} bytes")
    return data


def capture_structured(path: Path, *, maximum_bytes: int = 1_048_576) -> CapturedCandidate:
    raw = _read_once(path, maximum_bytes)
    parsed = parse_json_bytes(raw, maximum_bytes=maximum_bytes)
    encoded = canonical_bytes(parsed)
    return CapturedCandidate(
        input_mode="structured_json",
        captured_bytes=raw,
        canonical_bytes=encoded,
        digest=profile_digest_bytes("candidate", encoded),
        length=len(encoded),
        value=immutable_value(parsed),
    )


def capture_raw(path: Path, *, maximum_bytes: int = 1_048_576) -> CapturedCandidate:
    raw = _read_once(path, maximum_bytes)
    return CapturedCandidate(
        input_mode="binary_bundle",
        captured_bytes=raw,
        canonical_bytes=raw,
        digest=profile_digest_bytes("candidate", raw),
        length=len(raw),
        value=None,
    )
