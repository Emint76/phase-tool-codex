from __future__ import annotations

from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, digest_bytes, parse_json_bytes, profile_digest
from ..errors import PhaseError
from ..evidence import validate_intent, validate_receipt, validate_run_id
from ..registry import BundledRegistry, RegistrySnapshot


def _read_canonical(path: Path) -> tuple[Any, str]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PhaseError("inspection.missing_artifact", str(path.name)) from exc
    try:
        value = parse_json_bytes(data)
    except PhaseError as exc:
        raise PhaseError("inspection.invalid_json", str(path.name)) from exc
    if canonical_bytes(value) != data:
        raise PhaseError("inspection.digest_mismatch", str(path.name))
    return value, digest_bytes(data)


def inspect_run(evidence_root: Path, run_id: str, registry: RegistrySnapshot | None = None) -> dict[str, Any]:
    """Verify a run without opening any write handle."""
    validate_run_id(run_id)
    registry = registry or BundledRegistry.load()
    root = Path(evidence_root).resolve(strict=True)
    run_root = (root / ".phase" / "runs" / run_id).resolve(strict=True)
    expected_parent = (root / ".phase" / "runs").resolve(strict=True)
    try:
        run_root.relative_to(expected_parent)
    except ValueError as exc:
        raise PhaseError("inspection.outside_evidence_root", run_id) from exc
    receipt, _ = _read_canonical(run_root / "receipt.json")
    receipt_digest = profile_digest("receipt", receipt)
    validate_receipt(receipt, registry)
    intent = None
    intent_digest = None
    plan = None
    plan_digest = None
    if receipt["evidence"]["intent_digest"] is not None:
        intent, _ = _read_canonical(run_root / "intent.json")
        intent_digest = profile_digest("intent", intent)
        validate_intent(intent, registry)
        if intent_digest != receipt["evidence"]["intent_digest"]:
            raise PhaseError("inspection.digest_mismatch", "intent.json")
        plan, plan_attachment_digest = _read_canonical(run_root / "attachments" / "effect-plan.json")
        plan_digest = profile_digest("effect-plan", plan)
        if plan_digest != intent["effect_plan_digest"]:
            raise PhaseError("inspection.digest_mismatch", "effect-plan.json")
        validators, validators_digest = _read_canonical(run_root / "attachments" / "validator-results.json")
        if validators != receipt["validator_results"]:
            raise PhaseError("inspection.validator_results_mismatch")
        claimed = set(receipt["evidence"]["attachment_digests"])
        if {plan_attachment_digest, validators_digest} != claimed:
            raise PhaseError("inspection.attachment_set_mismatch")
        for item in intent["inputs"]:
            digest = item["blob_digest"]
            if digest is None:
                continue
            blob = run_root / "blobs" / digest.split(":", 1)[1]
            if not blob.is_file() or digest_bytes(blob.read_bytes()) != digest:
                raise PhaseError("inspection.digest_mismatch", blob.name)
    return {
        "run_id": run_id,
        "terminal_status": receipt["terminal_status"],
        "execution_disposition": receipt["execution_disposition"],
        "mutation_attempted": receipt["mutation_attempted"],
        "result_state": receipt["result_state"],
        "intent_digest": intent_digest,
        "effect_plan_digest": plan_digest,
        "receipt_digest": receipt_digest,
        "contract": receipt["contract"],
        "canonical_profile": "phase-canonical-json-v1",
    }
