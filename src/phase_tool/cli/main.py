from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from jsonschema import Draft202012Validator, FormatChecker

from ..canonical import canonical_bytes, profile_digest
from ..core import PhaseCore, PhaseRequest
from ..errors import PhaseError
from ..inspection import inspect_run
from ..registry import BundledRegistry


def _binding(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("binding must be NAME=PATH")
    name, raw_path = value.split("=", 1)
    if not name or not raw_path:
        raise argparse.ArgumentTypeError("binding must be NAME=PATH")
    return name, Path(raw_path)


def _write(value: object) -> None:
    registry = BundledRegistry.load()
    schema = registry.schema_document("https://phase-tool.local/schemas/stage3-command-result.schema.json")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)
    sys.stdout.buffer.write(canonical_bytes(value) + b"\n")


def _add_pipeline_arguments(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    parser.add_argument("--contract-id", required=required)
    parser.add_argument("--contract-version", required=required)
    parser.add_argument("--contract-digest", required=required)
    parser.add_argument("--candidate", type=Path, required=required)
    parser.add_argument("--evidence-root", type=Path, required=required)
    parser.add_argument("--run-id", required=required)
    parser.add_argument("--input", action="append", default=[], type=_binding)
    parser.add_argument("--root", action="append", default=[], type=_binding)
    parser.add_argument("--timestamp")
    parser.add_argument("--maximum-candidate-bytes", type=int, default=1_048_576)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="phase", description="Phase Tool Stage 3 brokered mutation CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "plan"):
        command = subparsers.add_parser(name)
        _add_pipeline_arguments(command)
    execute = subparsers.add_parser("execute")
    _add_pipeline_arguments(execute, required=False)
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--evidence-root", type=Path, required=True)
    inspect.add_argument("--run-id", required=True)
    inspect.add_argument("--root", action="append", default=[], type=_binding)
    return parser


def _envelope(
    command: str,
    *,
    success: bool,
    run_id: str | None,
    terminal_status: str | None,
    execution_disposition: str | None,
    mutation_attempted: bool,
    effect_plan_digest: str | None,
    intent_digest: str | None,
    receipt_digest: str | None,
    blockers: list[str],
    error: str | None,
    exit_code: int,
) -> dict[str, object]:
    return {
        "stage3_command_result_version": "1.0",
        "command": command,
        "success": success,
        "run_id": run_id,
        "terminal_status": terminal_status,
        "execution_disposition": execution_disposition,
        "mutation_attempted": mutation_attempted,
        "effect_plan_digest": effect_plan_digest,
        "intent_digest": intent_digest,
        "receipt_digest": receipt_digest,
        "blockers": blockers,
        "error": error,
        "exit_code": exit_code,
    }


def _pipeline(args: argparse.Namespace, *, execute: bool) -> int:
    roots = dict(args.root)
    inputs = dict(args.input)
    if len(roots) != len(args.root) or len(inputs) != len(args.input):
        raise PhaseError("cli.duplicate_binding")
    request = PhaseRequest(
        contract_id=args.contract_id,
        contract_version=args.contract_version,
        contract_digest=args.contract_digest,
        candidate_path=args.candidate,
        evidence_root=args.evidence_root,
        run_id=args.run_id,
        input_paths=inputs,
        root_bindings=roots,
        timestamp=args.timestamp,
        maximum_candidate_bytes=args.maximum_candidate_bytes,
    )
    outcome = PhaseCore().run(request, execute=execute)
    blockers = outcome.receipt["blockers"]
    output = _envelope(
        args.command,
        success=outcome.exit_code == 0,
        run_id=outcome.run_id,
        terminal_status=outcome.receipt["terminal_status"],
        execution_disposition=outcome.receipt["execution_disposition"],
        mutation_attempted=outcome.receipt["mutation_attempted"],
        effect_plan_digest=outcome.effect_plan_digest,
        intent_digest=profile_digest("intent", outcome.intent) if outcome.intent is not None else None,
        receipt_digest=outcome.receipt_digest,
        blockers=blockers,
        error=None if outcome.exit_code == 0 else blockers[0],
        exit_code=outcome.exit_code,
    )
    _write(output)
    return outcome.exit_code


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "execute" and args.contract_id is None:
        output = _envelope(
            "execute",
            success=False,
            run_id=None,
            terminal_status=None,
            execution_disposition=None,
            mutation_attempted=False,
            effect_plan_digest=None,
            intent_digest=None,
            receipt_digest=None,
            blockers=["mutation_execution_unavailable_in_stage_2"],
            error="mutation_execution_unavailable_in_stage_2",
            exit_code=64,
        )
        _write(output)
        return 64
    try:
        if args.command in {"validate", "plan", "execute"}:
            return _pipeline(args, execute=args.command == "execute")
        if args.command == "inspect":
            roots = dict(args.root)
            if len(roots) != len(args.root):
                raise PhaseError("cli.duplicate_binding")
            inspected = inspect_run(args.evidence_root, args.run_id, root_bindings=roots)
            _write(_envelope(
                "inspect",
                success=True,
                run_id=inspected["run_id"],
                terminal_status=inspected["terminal_status"],
                execution_disposition=inspected["execution_disposition"],
                mutation_attempted=inspected["mutation_attempted"],
                effect_plan_digest=inspected["effect_plan_digest"],
                intent_digest=inspected["intent_digest"],
                receipt_digest=inspected["receipt_digest"],
                blockers=[],
                error=None,
                exit_code=0,
            ))
            return 0
    except (PhaseError, OSError, ValueError) as exc:
        code = exc.code if isinstance(exc, PhaseError) else "cli.failure"
        _write(_envelope(
            args.command,
            success=False,
            run_id=None,
            terminal_status=None,
            execution_disposition=None,
            mutation_attempted=False,
            effect_plan_digest=None,
            intent_digest=None,
            receipt_digest=None,
            blockers=[code],
            error=code,
            exit_code=10,
        ))
        return 10
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
