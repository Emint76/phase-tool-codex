from __future__ import annotations

from .canonical import canonical_bytes, digest_bytes, parse_json_bytes, profile_digest
from .errors import PhaseError

CANONICAL_JSONL_CODEC_ID = "canonical-jsonl"
CANONICAL_JSONL_CODEC_VERSION = "1"


def absent_head_token() -> str:
    return profile_digest(
        "append-head",
        {
            "codec_id": CANONICAL_JSONL_CODEC_ID,
            "codec_version": CANONICAL_JSONL_CODEC_VERSION,
            "state": "absent",
            "byte_length": None,
            "record_count": None,
            "stream_digest": None,
        },
    )


def append_head_token(previous_head: str | None, record: bytes, previous_length: int, codec_id: str = CANONICAL_JSONL_CODEC_ID) -> str:
    validate_record_bytes(record)
    return profile_digest(
        "append-head",
        {
            "codec_id": codec_id,
            "codec_version": CANONICAL_JSONL_CODEC_VERSION,
            "previous_head": previous_head,
            "previous_length": previous_length,
            "record_digest": digest_bytes(record),
            "record_length": len(record),
        },
    )


def validate_record_bytes(record: bytes) -> dict[str, object]:
    if not record.endswith(b"\n"):
        raise PhaseError("codec.record_lf_missing")
    if record.endswith(b"\r\n"):
        raise PhaseError("codec.record_crlf_forbidden")
    if record.count(b"\n") != 1:
        raise PhaseError("codec.record_multiple_lines")
    body = record[:-1]
    if not body:
        raise PhaseError("codec.blank_record")
    value = parse_json_bytes(body)
    if not isinstance(value, dict):
        raise PhaseError("codec.record_not_object")
    if canonical_bytes(value) != body:
        raise PhaseError("codec.record_noncanonical")
    return value


def validate_stream_bytes(data: bytes) -> int:
    if data == b"":
        return 0
    if data.endswith(b"\r\n") or b"\r\n" in data:
        raise PhaseError("codec.crlf_forbidden")
    if not data.endswith(b"\n"):
        raise PhaseError("input.invalid_tail")
    count = 0
    for line in data.splitlines(keepends=True):
        validate_record_bytes(line)
        count += 1
    return count


def stream_head_token(data: bytes, codec_id: str = CANONICAL_JSONL_CODEC_ID) -> str:
    record_count = validate_stream_bytes(data)
    return profile_digest(
        "append-head",
        {
            "codec_id": codec_id,
            "codec_version": CANONICAL_JSONL_CODEC_VERSION,
            "state": "present",
            "byte_length": len(data),
            "record_count": record_count,
            "stream_digest": digest_bytes(data),
        },
    )
