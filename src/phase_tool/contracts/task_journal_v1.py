from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from ..canonical import canonical_bytes, parse_json_bytes
from ..errors import PhaseError
from ..append_codec import append_head_token, stream_head_token
from ..paths import safe_relative_locator

_WIRE_RECORD_TYPES = {
    "open": "task_open",
    "event": "task_event",
    "close": "task_close",
    "correction": "task_correction",
}

_DIGEST_SCHEMA = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
_COMMON_RECORD_PROPERTIES: dict[str, Any] = {
    "task_record_version": {"const": "1.0"},
    "record_type": {"type": "string"},
    "task_id": {"type": "string", "pattern": "^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$"},
    "sequence": {"type": "integer", "minimum": 1},
    "action": {"type": "string"},
    "operation_id": {"type": "string", "minLength": 1},
    "request_digest": _DIGEST_SCHEMA,
    "previous_head": {"oneOf": [{"type": "null"}, _DIGEST_SCHEMA]},
    "event_hash": _DIGEST_SCHEMA,
}
_ACTION_RECORD_PROPERTIES: dict[str, dict[str, Any]] = {
    "open": {
        "original_instruction": {"type": "string"},
        "normalized_goal": {"type": "string"},
    },
    "event": {
        "event_kind": {"type": "string", "minLength": 1},
        "event_payload": {"type": "object"},
    },
    "close": {
        "outcome": {"enum": ["completed", "failed", "partial", "cancelled"]},
    },
    "correction": {
        "target_sequence": {"type": "integer", "minimum": 1},
        "target_event_hash": _DIGEST_SCHEMA,
        "reason": {"type": "string", "minLength": 1},
        "replacement": {"type": "object"},
    },
}
_ACTION_REQUIRED = {
    "open": ["original_instruction"],
    "event": ["event_kind", "event_payload"],
    "close": ["outcome"],
    "correction": ["target_sequence", "target_event_hash", "reason", "replacement"],
}


def _validate_record_shape(record: dict[str, Any]) -> None:
    action = record.get("action")
    if action not in _WIRE_RECORD_TYPES:
        raise PhaseError("task_journal.action_unsupported")
    properties = dict(_COMMON_RECORD_PROPERTIES) | _ACTION_RECORD_PROPERTIES[action]
    properties["action"] = {"const": action}
    properties["record_type"] = {"const": _WIRE_RECORD_TYPES[action]}
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(_COMMON_RECORD_PROPERTIES) + _ACTION_REQUIRED[action],
    }
    if next(Draft202012Validator(schema).iter_errors(record), None) is not None:
        raise PhaseError("task_journal.record_schema_invalid")


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise PhaseError("input.invalid_tail")
    records: list[dict[str, Any]] = []
    offset = 0
    prefix = b""
    task_id = None
    state = "absent"
    for line in data.splitlines(keepends=True):
        value = parse_json_bytes(line.rstrip(b"\n"))
        _validate_record_replay(value, index=len(records) + 1, previous_bytes=prefix, task_id=task_id, state=state)
        expected_hash = _event_hash(value, offset)
        if value.get("event_hash") != expected_hash:
            raise PhaseError("task_journal.hash_mismatch")
        task_id = value["task_id"]
        state = _next_state(state, value["action"])
        records.append(value)
        prefix += line
        offset += len(line)
    return records


def _next_state(state: str, action: str) -> str:
    if action == "open":
        return "open"
    if action == "close":
        return "closed"
    return state


def _validate_record_replay(record: dict[str, Any], *, index: int, previous_bytes: bytes, task_id: str | None, state: str) -> None:
    _validate_record_shape(record)
    action = record.get("action")
    if action not in _WIRE_RECORD_TYPES:
        raise PhaseError("task_journal.action_unsupported")
    if record.get("record_type") != _WIRE_RECORD_TYPES[action]:
        raise PhaseError("task_journal.record_type_mismatch")
    if record.get("sequence") != index:
        raise PhaseError("task_journal.sequence_gap")
    if index == 1 and action != "open":
        raise PhaseError("task_journal.first_record_not_open")
    if index != 1 and action == "open":
        raise PhaseError("task_journal.duplicate_open")
    if task_id is not None and record.get("task_id") != task_id:
        raise PhaseError("task_journal.task_id_mismatch")
    expected_previous = None if not previous_bytes else stream_head_token(previous_bytes)
    if record.get("previous_head") != expected_previous:
        raise PhaseError("task_journal.previous_head_mismatch")
    if action in {"event", "close"} and state != "open":
        raise PhaseError("task_journal.not_open")
    if action == "correction" and state == "absent":
        raise PhaseError("task_journal.not_open")


def _state(records: list[dict[str, Any]]) -> str:
    if not records:
        return "absent"
    status = "open"
    for record in records:
        if record["action"] == "close":
            status = "closed"
    return status


def locator_for(candidate: dict[str, Any]) -> str:
    return safe_relative_locator(f"tasks/{candidate['task_id']}.jsonl")


def build_record(candidate: dict[str, Any], *, existing_bytes: bytes, expected_head: str | None, request_digest: str | None = None) -> dict[str, Any]:
    records = _load_records_from_bytes(existing_bytes)
    action = candidate["action"]
    if candidate.get("operation_id") != candidate.get("idempotency_key"):
        raise PhaseError("task_journal.operation_id_mismatch")
    state = _state(records)
    if expected_head is None and records:
        raise PhaseError("task_journal.already_open")
    if action == "open" and records:
        raise PhaseError("task_journal.already_open")
    if action in {"event", "close"} and state != "open":
        raise PhaseError("task_journal.not_open")
    if action == "correction" and state == "absent":
        raise PhaseError("task_journal.not_open")
    sequence = len(records) + 1
    record: dict[str, Any] = {
        "task_record_version": "1.0",
        "record_type": _WIRE_RECORD_TYPES[action],
        "task_id": candidate["task_id"],
        "sequence": sequence,
        "action": action,
        "operation_id": candidate["operation_id"],
        "request_digest": request_digest or "",
        "previous_head": expected_head,
    }
    if action == "open":
        record["original_instruction"] = candidate["original_instruction"]
        if "normalized_goal" in candidate:
            record["normalized_goal"] = candidate["normalized_goal"]
    elif action == "event":
        record["event_kind"] = candidate["event_kind"]
        record["event_payload"] = candidate["event_payload"]
    elif action == "close":
        record["outcome"] = candidate["outcome"]
    elif action == "correction":
        record["target_sequence"] = candidate["target_sequence"]
        record["target_event_hash"] = candidate["target_event_hash"]
        record["reason"] = candidate["reason"]
        record["replacement"] = candidate["replacement"]
    else:
        raise PhaseError("task_journal.action_unsupported")
    return record


def finalize_record(record: dict[str, Any], *, previous_head: str | None, previous_length: int) -> bytes:
    staged = dict(record)
    staged.pop("event_hash", None)
    line_without_hash = canonical_bytes(staged | {"event_hash": ""}) + b"\n"
    event_hash = append_head_token(previous_head, line_without_hash, previous_length, "task_journal.v1")
    final = staged | {"event_hash": event_hash}
    return canonical_bytes(final) + b"\n"


def _event_hash(record: dict[str, Any], previous_length: int) -> str:
    staged = dict(record)
    staged["event_hash"] = ""
    previous = staged.get("previous_head")
    return append_head_token(previous, canonical_bytes(staged) + b"\n", previous_length, "task_journal.v1")


def _load_records_from_bytes(data: bytes) -> list[dict[str, Any]]:
    if not data:
        return []
    if not data.endswith(b"\n"):
        raise PhaseError("input.invalid_tail")
    records = []
    prefix = b""
    task_id = None
    state = "absent"
    for raw_line in data.splitlines(keepends=True):
        line = raw_line.rstrip(b"\n")
        record = parse_json_bytes(line)
        _validate_record_replay(record, index=len(records) + 1, previous_bytes=prefix, task_id=task_id, state=state)
        expected_hash = _event_hash(record, len(prefix))
        if record.get("event_hash") != expected_hash:
            raise PhaseError("task_journal.hash_mismatch")
        task_id = record["task_id"]
        state = _next_state(state, record["action"])
        records.append(record)
        prefix += raw_line
    return records


def validate_candidate(value: dict[str, Any], schema: dict[str, Any]) -> tuple[str, str, Any, Any, list[str]]:
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        return "fail", "candidate.schema_invalid", "schema_valid", errors[0].message, ["candidate.schema_invalid"]
    if value["operation_id"] != value["idempotency_key"]:
        return "fail", "task_journal.operation_id_mismatch", value["idempotency_key"], value["operation_id"], ["task_journal.operation_id_mismatch"]
    return "pass", "validation.pass", "schema_valid", "schema_valid", []


def validate_state(value: dict[str, Any], path: Path) -> tuple[str, str, Any, Any, list[str]]:
    try:
        records = _load_records(path)
    except PhaseError as exc:
        return "fail", exc.code, "valid_stream", "invalid_stream", [exc.code]
    expected = value["expected_head"]
    if expected is None:
        if records:
            return "fail", "target.same_key_conflict", "absent", "present", ["target.same_key_conflict"]
        return "pass", "validation.pass", "absent", "absent", []
    try:
        current = stream_head_token(path.read_bytes())
    except (OSError, PhaseError) as exc:
        code = exc.code if isinstance(exc, PhaseError) else "target.unavailable"
        return "fail", code, expected, None, [code]
    if current != expected:
        return "fail", "freeze.stale_snapshot", expected, current, ["freeze.stale_snapshot"]
    state = _state(records)
    action = value["action"]
    if action in {"event", "close"} and state != "open":
        return "fail", "task_journal.not_open", "open", state, ["task_journal.not_open"]
    if action == "correction" and state == "absent":
        return "fail", "task_journal.not_open", "open_or_closed", state, ["task_journal.not_open"]
    if action == "correction":
        expected_target = (value["task_id"], value["target_sequence"], value["target_event_hash"])
        observed = {
            (record.get("task_id"), record.get("sequence"), record.get("event_hash"))
            for record in records
        }
        if expected_target not in observed:
            return "fail", "task_journal.correction_target_mismatch", expected_target, sorted(observed), ["task_journal.correction_target_mismatch"]
    return "pass", "validation.pass", expected, current, []


def project_task(path: Path) -> dict[str, Any]:
    records = _load_records(path)
    terminal_outcome = None
    for record in records:
        if record["action"] == "close":
            terminal_outcome = record["outcome"]
    return {
        "task_id": records[0]["task_id"] if records else None,
        "status": _state(records),
        "terminal_outcome": terminal_outcome,
        "sequence": len(records),
        "event_count": sum(1 for item in records if item["action"] == "event"),
        "corrections": [
            {
                "sequence": item["sequence"],
                "target_sequence": item["target_sequence"],
                "target_event_hash": item["target_event_hash"],
                "reason": item["reason"],
            }
            for item in records
            if item["action"] == "correction"
        ],
    }
