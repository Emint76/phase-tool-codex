#!/usr/bin/env python
"""Deterministically prepare Phase requests without mutating canonical targets."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping


def _load_router():
    local = Path(__file__).with_name("route_mutation.py")
    installed = Path(__file__).resolve().parents[2] / "phase-mutation-router" / "scripts" / "route_mutation.py"
    path = local if local.is_file() else installed
    spec = importlib.util.spec_from_file_location("phase_mutation_router_shared", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("phase-mutation-router is not installed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_ROUTER = _load_router()
RoutingError = _ROUTER.RoutingError
route_mutation = _ROUTER.route_mutation


class PreparationError(ValueError):
    pass


_LOCATOR = re.compile(r"^[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_])?(?:/[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_])?)*$")
_RESERVED = re.compile(r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$", re.IGNORECASE)


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _resolved(path: Path) -> Path:
    return path.resolve(strict=False)


def _contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _require_disjoint(canonical: Path, other: Path) -> None:
    canonical_r, other_r = _resolved(canonical), _resolved(other)
    if _contains(canonical_r, other_r) or _contains(other_r, canonical_r):
        raise PreparationError("preparation and evidence roots must remain outside canonical target")


def _require_plain_directory_chain(path: Path) -> None:
    current = Path(path).absolute()
    components = [current]
    components.extend(current.parents)
    for component in reversed(components):
        if not component.exists():
            continue
        stat_result = component.lstat()
        attributes = getattr(stat_result, "st_file_attributes", 0)
        reparse = getattr(stat_result, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if component.is_symlink() or attributes & reparse:
            raise PreparationError("preparation path contains a symlink or reparse component")
        if not component.is_dir():
            raise PreparationError("preparation path component is not a directory")


@contextmanager
def _pin_directory(path: Path):
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = (
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_void_p,
        )
        kernel32.CreateFileW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
        kernel32.CloseHandle.restype = ctypes.c_int
        handle = kernel32.CreateFileW(
            str(Path(path).absolute()),
            0x80,
            0x1 | 0x2,
            None,
            3,
            0x02000000 | 0x00200000,
            None,
        )
        invalid = ctypes.c_void_p(-1).value
        if handle == invalid:
            raise OSError(ctypes.get_last_error(), "cannot pin preparation directory")
        try:
            yield
        finally:
            kernel32.CloseHandle(handle)
    else:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            yield
        finally:
            os.close(descriptor)


def safe_locator(value: Any) -> str:
    if not isinstance(value, str) or not value or not _LOCATOR.fullmatch(value):
        raise PreparationError("target_locator is not a safe relative locator")
    if any(_RESERVED.fullmatch(part) for part in value.split("/")):
        raise PreparationError("target_locator contains a reserved path component")
    return value


def _id(value: Any, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*", value):
        raise PreparationError("operation_id is invalid")
    return value


def _payload_bytes(intent: Mapping[str, Any]) -> bytes:
    has_text = "content_text" in intent
    has_path = "content_path" in intent
    if has_text == has_path:
        raise PreparationError("exactly one of content_text or content_path is required")
    if has_text:
        text = intent["content_text"]
        if not isinstance(text, str):
            raise PreparationError("content_text must be a string")
        data = text.encode("utf-8")
    else:
        source = Path(str(intent["content_path"])).resolve(strict=True)
        if not source.is_file():
            raise PreparationError("content_path must be a regular file")
        data = source.read_bytes()
    return data


def _write_exclusive(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor: int | None = None
    try:
        _require_plain_directory_chain(path.parent)
        with _pin_directory(path.parent):
            _require_plain_directory_chain(path.parent)
            descriptor = os.open(path, flags, 0o400)
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("exclusive preparation write made no progress")
                view = view[written:]
            os.fsync(descriptor)
    finally:
        if descriptor is not None:
            os.close(descriptor)
    path.chmod(0o400)


def prepare_mutation(
    intent: Mapping[str, Any], *, canonical_root: Path, preparation_root: Path, evidence_root: Path
) -> dict[str, Any]:
    canonical_root = Path(canonical_root).resolve(strict=True)
    if not canonical_root.is_dir():
        raise PreparationError("canonical_root must be an existing directory")
    preparation_root, evidence_root = Path(preparation_root), Path(evidence_root)
    _require_disjoint(canonical_root, preparation_root)
    _require_disjoint(canonical_root, evidence_root)
    _require_disjoint(preparation_root, evidence_root)
    preparation_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)
    _require_plain_directory_chain(preparation_root)
    _require_plain_directory_chain(evidence_root)
    _require_disjoint(canonical_root, preparation_root)
    _require_disjoint(canonical_root, evidence_root)
    _require_disjoint(preparation_root, evidence_root)

    kind = intent.get("mutation_kind")
    locator = safe_locator(intent.get("target_locator"))
    target = canonical_root / locator
    exists = target.is_file()
    try:
        route = route_mutation({"mutation_kind": kind, "stable_path_exists": exists})
    except RoutingError as exc:
        raise PreparationError(str(exc)) from exc

    operation_id = _id(intent.get("operation_id"), f"hermes-{kind.replace('_', '-')}")

    candidate: dict[str, Any]
    input_paths: dict[str, str] = {}
    expected_input_digests: dict[str, str] = {}
    payload_data: bytes | None = None
    payload_digest = None
    payload_length = None
    if kind in {"create", "publish_new_version"}:
        data = _payload_bytes(intent)
        payload_data = data
        payload_digest, payload_length = _digest(data), len(data)
        expected_input_digests["payload"] = payload_digest
        candidate = {"operation_id": operation_id, "target_locator": locator, "input_binding": "payload"}
        if kind == "publish_new_version":
            expected = intent.get("expected_current_digest")
            if expected is None:
                expected = _digest(target.read_bytes())
            if not isinstance(expected, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", expected):
                raise PreparationError("expected_current_digest is invalid")
            candidate["expected_current_digest"] = expected
    elif kind == "append":
        stream_id, record_id, record = intent.get("stream_id"), intent.get("record_id"), intent.get("record")
        expected_head = intent.get("expected_head")
        if not isinstance(stream_id, str) or not re.fullmatch(r"[a-z0-9._-]+", stream_id):
            raise PreparationError("stream_id is invalid")
        expected_locator = f"streams/{stream_id}.jsonl"
        if locator != expected_locator:
            raise PreparationError(f"append target_locator must equal contract-derived locator {expected_locator!r}")
        if not isinstance(record_id, str) or not record_id or not isinstance(record, dict):
            raise PreparationError("append requires record_id and object record")
        if expected_head is not None:
            if not exists:
                raise PreparationError("expected_head requires an existing stream")
            input_paths["current_state"] = str(target.resolve())
            expected_input_digests["current_state"] = _digest(target.read_bytes())
        candidate = {"stream_id": stream_id, "target_locator": locator, "record_id": record_id, "expected_head": expected_head, "record": record}
    else:
        raise PreparationError(f"preparation adapter unavailable for {kind!r}; direct write is forbidden")

    identity = {
        "candidate": candidate,
        "payload_digest": payload_digest,
        "payload_length": payload_length,
    }
    token = hashlib.sha256(_canonical(identity)).hexdigest()[:20]
    key = intent.get("idempotency_key", f"hermes-{token}")
    if not isinstance(key, str) or not key:
        raise PreparationError("idempotency_key must be a non-empty string")
    run_id = intent.get("run_id", f"hermes-{kind}-{token}")
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
        raise PreparationError("run_id is invalid")
    candidate["idempotency_key"] = key

    request_root = preparation_root / f"request-{token}"
    _require_plain_directory_chain(preparation_root)
    try:
        request_root.mkdir()
    except FileExistsError as exc:
        raise PreparationError("prepared request directory already exists; use a fresh preparation root") from exc
    _require_plain_directory_chain(request_root)
    candidate_path = request_root / "candidate.json"
    _write_exclusive(candidate_path, _canonical(candidate))
    if payload_data is not None:
        payload_path = request_root / "payload.bin"
        _write_exclusive(payload_path, payload_data)
        input_paths["payload"] = str(payload_path.resolve())
    request = {
        "contract_binding": route["contract_binding"],
        "contract_digest": route["contract_digest"],
        "candidate": candidate,
        "candidate_path": str(candidate_path.resolve()),
        "evidence_root": str(evidence_root.resolve()),
        "run_id": run_id,
        "input_paths": input_paths,
        "expected_input_digests": expected_input_digests,
        "root_bindings": {route["root_binding"]: str(canonical_root)},
        "transport": "mcp",
        "lifecycle": ["phase_execute", "phase_inspect"],
        "payload_digest": payload_digest,
        "payload_length": payload_length,
    }
    request_path = request_root / "phase-request.json"
    _write_exclusive(request_path, _canonical(request))
    return request | {"prepared_request_path": str(request_path.resolve())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intent", type=Path, required=True)
    parser.add_argument("--canonical-root", type=Path, required=True)
    parser.add_argument("--preparation-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        intent = json.loads(args.intent.read_text(encoding="utf-8"))
        print(json.dumps(prepare_mutation(intent, canonical_root=args.canonical_root, preparation_root=args.preparation_root, evidence_root=args.evidence_root), sort_keys=True))
    except (OSError, json.JSONDecodeError, PreparationError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
