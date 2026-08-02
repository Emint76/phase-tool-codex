#!/usr/bin/env python
"""Verify a prepared Phase request through a replaceable transport adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


_BINDING_RE = re.compile(r"^[A-Za-z0-9._-]+@[0-9]+\.[0-9]+\.[0-9]+$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class VerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PhaseRequest:
    contract: str
    contract_digest: str
    candidate: str
    evidence_root: str
    run_id: str
    inputs: tuple[str, ...]
    roots: tuple[str, ...]
    input_digests: tuple[str, ...] = ()
    timestamp: str | None = None


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    payload: dict[str, object] | None
    stderr: str


class PhaseTransport(Protocol):
    def execute(self, request: PhaseRequest) -> CommandResult:
        ...

    def inspect(self, request: PhaseRequest) -> CommandResult:
        ...


class CliPhaseTransport:
    """CLI adapter. A future MCP adapter can implement the same protocol."""

    def __init__(self, executable: str) -> None:
        self.executable = executable

    def _invoke(self, arguments: Sequence[str]) -> CommandResult:
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        completed = subprocess.run(
            [self.executable, *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
        stdout = completed.stdout.strip()
        payload: dict[str, object] | None = None
        if stdout:
            try:
                decoded = json.loads(stdout)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, dict):
                payload = decoded
        return CommandResult(completed.returncode, payload, completed.stderr.strip())

    def execute(self, request: PhaseRequest) -> CommandResult:
        contract_id, contract_version = request.contract.rsplit("@", 1)
        arguments = [
            "execute",
            "--contract-id",
            contract_id,
            "--contract-version",
            contract_version,
            "--contract-digest",
            request.contract_digest,
            "--candidate",
            request.candidate,
            "--evidence-root",
            request.evidence_root,
            "--run-id",
            request.run_id,
        ]
        for binding in request.inputs:
            arguments.extend(("--input", binding))
        for binding in request.roots:
            arguments.extend(("--root", binding))
        if request.timestamp is not None:
            arguments.extend(("--timestamp", request.timestamp))
        return self._invoke(arguments)

    def inspect(self, request: PhaseRequest) -> CommandResult:
        arguments = [
            "inspect",
            "--evidence-root",
            request.evidence_root,
            "--run-id",
            request.run_id,
        ]
        for binding in request.roots:
            arguments.extend(("--root", binding))
        return self._invoke(arguments)


def _named_path(value: str, option: str, *, file_required: bool) -> str:
    name, separator, raw_path = value.partition("=")
    if not separator or not name or not raw_path:
        raise VerificationError(f"{option} must be NAME=PATH")
    path = os.path.abspath(raw_path)
    exists = os.path.isfile(path) if file_required else os.path.isdir(path)
    if not exists:
        expected = "file" if file_required else "directory"
        raise VerificationError(f"{option} {name!r} does not resolve to an existing {expected}")
    return f"{name}={path}"


def _resolve_phase(explicit: str | None) -> str:
    configured = explicit or os.environ.get("PHASE_BIN")
    if configured:
        resolved = os.path.abspath(configured)
        if not os.path.isfile(resolved):
            raise VerificationError("configured Phase executable does not exist")
        return resolved
    discovered = shutil.which("phase")
    if discovered is None:
        raise VerificationError("phase executable not found; use --phase-bin or PHASE_BIN")
    return discovered


def _loaded_request(path: str) -> dict[str, object]:
    request_path = os.path.abspath(path)
    if not os.path.isfile(request_path):
        raise VerificationError("request must be an existing JSON file")
    try:
        value = json.loads(open(request_path, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"request is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError("request JSON must be an object")
    return value


def _prepared_request(args: argparse.Namespace) -> PhaseRequest:
    if args.request:
        value = _loaded_request(args.request)
        try:
            contract = value["contract_binding"]
            contract_digest = value["contract_digest"]
            candidate_arg = value["candidate_path"]
            evidence_arg = value["evidence_root"]
            run_id = value["run_id"]
            input_values = [f"{name}={path}" for name, path in dict(value["input_paths"]).items()]
            root_values = [f"{name}={path}" for name, path in dict(value["root_bindings"]).items()]
            digest_values = [f"{name}={digest}" for name, digest in dict(value["expected_input_digests"]).items()]
            timestamp = value.get("timestamp")
        except (KeyError, TypeError, ValueError) as exc:
            raise VerificationError(f"request JSON is incomplete: {exc}") from exc
    else:
        required = (args.contract, args.contract_digest, args.candidate, args.evidence_root, args.run_id)
        if any(value is None for value in required):
            raise VerificationError("manual mode requires --contract, --contract-digest, --candidate, --evidence-root, and --run-id")
        contract, contract_digest = args.contract, args.contract_digest
        candidate_arg, evidence_arg, run_id = args.candidate, args.evidence_root, args.run_id
        input_values, root_values, digest_values = args.input, args.root, args.input_digest
        timestamp = args.timestamp
    if not isinstance(contract, str) or not _BINDING_RE.fullmatch(contract):
        raise VerificationError("contract must be an exact <id>@<semver> registry binding")
    if not isinstance(contract_digest, str) or not _DIGEST_RE.fullmatch(contract_digest):
        raise VerificationError("contract digest must be lowercase sha256:<64 hex>")
    candidate = os.path.abspath(str(candidate_arg))
    evidence_root = os.path.abspath(str(evidence_arg))
    if not os.path.isfile(candidate):
        raise VerificationError("candidate must be an existing file")
    if not os.path.isdir(evidence_root):
        raise VerificationError("evidence root must already exist")
    if not isinstance(run_id, str) or not run_id:
        raise VerificationError("run ID must not be empty")
    inputs = tuple(_named_path(value, "--input", file_required=True) for value in input_values)
    roots = tuple(_named_path(value, "--root", file_required=False) for value in root_values)
    if not roots:
        raise VerificationError("at least one existing root binding is required")
    input_digests: list[str] = []
    for value in digest_values:
        name, separator, digest = value.partition("=")
        if not separator or not name or not _DIGEST_RE.fullmatch(digest):
            raise VerificationError("input digest must be NAME=sha256:<64 lowercase hex>")
        input_digests.append(f"{name}={digest}")
    return PhaseRequest(
        contract=contract,
        contract_digest=contract_digest,
        candidate=candidate,
        evidence_root=evidence_root,
        run_id=run_id,
        inputs=inputs,
        roots=roots,
        input_digests=tuple(input_digests),
        timestamp=timestamp if isinstance(timestamp, str) else None,
    )


def _verify_prepared_inputs(request: PhaseRequest) -> None:
    paths = dict(value.split("=", 1) for value in request.inputs)
    digests = dict(value.split("=", 1) for value in request.input_digests)
    if set(paths) != set(digests):
        raise VerificationError("prepared input digest bindings must exactly match input bindings")
    for name, expected in digests.items():
        path = paths.get(name)
        if path is None:
            raise VerificationError(f"prepared digest has no input binding {name!r}")
        digest = "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if digest != expected:
            raise VerificationError(f"prepared input {name!r} changed after preparation")


def _payload(result: CommandResult, command: str) -> dict[str, object]:
    if result.payload is None:
        detail = result.stderr or "stdout was not a JSON object"
        raise VerificationError(f"{command} transport failure: {detail}")
    if result.returncode != 0:
        error = result.payload.get("error") or result.stderr or f"exit {result.returncode}"
        raise VerificationError(f"{command} failed: {error}")
    return result.payload


def run_verified(transport: PhaseTransport, request: PhaseRequest) -> dict[str, object]:
    _verify_prepared_inputs(request)
    execute_result = transport.execute(request)
    _verify_prepared_inputs(request)
    inspect_result = transport.inspect(request)
    executed = _payload(execute_result, "execute")
    inspected = _payload(inspect_result, "inspect")

    if executed.get("success") is not True:
        raise VerificationError("execute did not report success=true")
    if inspected.get("success") is not True:
        raise VerificationError("inspect did not report success=true")
    if inspected.get("target_verified") is not True:
        raise VerificationError("inspect did not report target_verified=true")

    required_equal = ("run_id", "terminal_status", "execution_disposition", "receipt_digest")
    for field in required_equal:
        if executed.get(field) != inspected.get(field):
            raise VerificationError(f"execute/inspect disagreement for {field}")
    if executed.get("run_id") != request.run_id:
        raise VerificationError("Phase returned a different run ID")
    if executed.get("terminal_status") != "succeeded_verified":
        raise VerificationError("terminal status is not succeeded_verified")
    receipt_digest = executed.get("receipt_digest")
    if not isinstance(receipt_digest, str) or not _DIGEST_RE.fullmatch(receipt_digest):
        raise VerificationError("durable receipt digest is absent or invalid")

    return {
        "contract": request.contract,
        "run_id": request.run_id,
        "terminal_status": executed["terminal_status"],
        "execution_disposition": executed["execution_disposition"],
        "receipt_digest": receipt_digest,
        "inspect_status": {
            "success": True,
            "target_verified": True,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-bin")
    parser.add_argument("--request", help="complete phase-request.json emitted by phase-mutation-preparation")
    parser.add_argument("--contract")
    parser.add_argument("--contract-digest")
    parser.add_argument("--candidate")
    parser.add_argument("--evidence-root")
    parser.add_argument("--run-id")
    parser.add_argument("--input", action="append", default=[])
    parser.add_argument("--input-digest", action="append", default=[])
    parser.add_argument("--root", action="append", default=[])
    parser.add_argument("--timestamp")
    return parser


def main() -> int:
    try:
        args = _parser().parse_args()
        request = _prepared_request(args)
        transport = CliPhaseTransport(_resolve_phase(args.phase_bin))
        result = run_verified(transport, request)
    except VerificationError as exc:
        print(f"phase-verified-execution: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
