from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, digest_bytes, parse_json_bytes, profile_digest
from ..errors import PhaseError
from ..evidence import validate_intent, validate_receipt, validate_run_id
from ..paths import contained_read_path
from ..registry import BundledRegistry, RegistrySnapshot
from ..append_codec import stream_head_token


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


def _verify_intent_blobs(run_root: Path, intent: Mapping[str, Any]) -> None:
    for item in intent["inputs"]:
        digest = item["blob_digest"]
        if digest is None:
            continue
        blob = run_root / "blobs" / digest.split(":", 1)[1]
        if not blob.is_file() or digest_bytes(blob.read_bytes()) != digest:
            raise PhaseError("inspection.digest_mismatch", blob.name)
    evidence = intent.get("evidence", {})
    for digest in evidence.get("content_blob_digests", []):
        blob = run_root / "blobs" / digest.split(":", 1)[1]
        if not blob.is_file() or digest_bytes(blob.read_bytes()) != digest:
            raise PhaseError("inspection.digest_mismatch", blob.name)


def inspect_run(
    evidence_root: Path,
    run_id: str,
    registry: RegistrySnapshot | None = None,
    *,
    root_bindings: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    """Verify evidence and, for observed results, re-read installation-bound target bytes."""
    validate_run_id(run_id)
    registry = registry or BundledRegistry.load()
    root = Path(evidence_root).resolve(strict=True)
    run_root = (root / ".phase" / "runs" / run_id).resolve(strict=True)
    expected_parent = (root / ".phase" / "runs").resolve(strict=True)
    try:
        run_root.relative_to(expected_parent)
    except ValueError as exc:
        raise PhaseError("inspection.outside_evidence_root", run_id) from exc
    receipt_path = run_root / "receipt.json"
    if not receipt_path.is_file():
        intent, _ = _read_canonical(run_root / "intent.json")
        intent_digest = profile_digest("intent", intent)
        validate_intent(intent, registry)
        plan, _ = _read_canonical(run_root / "attachments" / "effect-plan.json")
        plan_digest = profile_digest("effect-plan", plan)
        if plan_digest != intent["effect_plan_digest"]:
            raise PhaseError("inspection.digest_mismatch", "effect-plan.json")
        _verify_intent_blobs(run_root, intent)
        return {
            "run_id": run_id,
            "terminal_status": None,
            "execution_disposition": None,
            "mutation_attempted": None,
            "result_state": None,
            "intent_digest": intent_digest,
            "effect_plan_digest": plan_digest,
            "receipt_digest": None,
            "contract": intent["contract"],
            "canonical_profile": "phase-canonical-json-v1",
            "target_verified": None,
            "receipt_present": False,
            "intent_present": True,
            "inspection_required": True,
        }
    receipt, _ = _read_canonical(receipt_path)
    receipt_digest = profile_digest("receipt", receipt)
    validate_receipt(receipt, registry)
    intent = None
    intent_digest = None
    plan = None
    plan_digest = None
    target_verified: bool | None = None
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
        attachment_digests = {plan_attachment_digest, validators_digest}
        if receipt["effect_receipts"]:
            pre_validators, pre_validators_digest = _read_canonical(run_root / "attachments" / "pre-validator-results.json")
            effect_receipts, effect_receipts_digest = _read_canonical(run_root / "attachments" / "effect-receipts.json")
            if effect_receipts != receipt["effect_receipts"]:
                raise PhaseError("inspection.effect_receipts_mismatch")
            if [item["effect_id"] for item in effect_receipts] != [item["effect_id"] for item in plan["effects"]]:
                raise PhaseError("inspection.effect_receipt_set_mismatch")
            if not isinstance(pre_validators, list):
                raise PhaseError("inspection.validator_results_mismatch")
            attachment_digests.update({pre_validators_digest, effect_receipts_digest})
        claimed = set(receipt["evidence"]["attachment_digests"])
        if attachment_digests != claimed:
            raise PhaseError("inspection.attachment_set_mismatch")
        _verify_intent_blobs(run_root, intent)
    canonical_result = receipt["canonical_result"]
    if canonical_result is not None:
        roots = root_bindings or {}
        root_id = canonical_result["root_binding"]
        try:
            target_root = Path(roots[root_id])
        except KeyError as exc:
            raise PhaseError("inspection.target_root_missing", root_id) from exc
        try:
            target = contained_read_path(target_root, canonical_result["locator"])
            data = target.read_bytes()
        except (OSError, PhaseError) as exc:
            raise PhaseError("inspection.target_mismatch", canonical_result["locator"]) from exc
        state = canonical_result["state"]
        appended = canonical_result.get("appended_record")
        if appended is not None:
            if not receipt["effect_receipts"] or receipt["effect_receipts"][0].get("kind") != "append_record":
                raise PhaseError("inspection.append_evidence_missing")
            effect_receipt = receipt["effect_receipts"][0]
            for key in ("operation_identity", "request_digest", "record_identity", "append_offset", "record_digest", "record_length", "resulting_head"):
                if effect_receipt.get(key) != appended.get(key):
                    raise PhaseError("inspection.append_evidence_mismatch", key)
            offset = appended["append_offset"]
            length = appended["record_length"]
            end = offset + length
            if len(data) < end or digest_bytes(data[offset:end]) != appended["record_digest"]:
                raise PhaseError("inspection.target_mismatch", canonical_result["locator"])
            if stream_head_token(data[:end]) != appended["resulting_head"]:
                raise PhaseError("inspection.target_mismatch", canonical_result["locator"])
            stream_head_token(data)
        elif receipt["effect_receipts"] and receipt["effect_receipts"][0].get("kind") == "append_record":
            raise PhaseError("inspection.append_evidence_missing")
        elif state["exists"] is not True or digest_bytes(data) != state["digest"] or len(data) != state["length"]:
            raise PhaseError("inspection.target_mismatch", canonical_result["locator"])
        target_verified = True
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
        "target_verified": target_verified,
        "receipt_present": True,
        "intent_present": intent is not None,
        "inspection_required": False,
    }
