from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from ..canonical import canonical_bytes, digest_bytes, parse_json_bytes, profile_digest
from ..errors import PhaseError
from ..evidence import evidence_file_exists, iter_run_artifacts, read_evidence_bytes, validate_intent, validate_receipt, validate_run_id
from ..paths import _platform_path, contained_read_path
from ..planning import validate_static_plan
from ..registry import BundledRegistry, RegistrySnapshot
from ..append_codec import stream_head_token
from ..contracts import load_contract_hook


def _read_canonical(path: Path) -> tuple[Any, str]:
    try:
        data = read_evidence_bytes(path)
    except OSError as exc:
        raise PhaseError("inspection.missing_artifact", str(path.name)) from exc
    try:
        value = parse_json_bytes(data)
    except PhaseError as exc:
        raise PhaseError("inspection.invalid_json", str(path.name)) from exc
    if canonical_bytes(value) != data:
        raise PhaseError("inspection.digest_mismatch", str(path.name))
    return value, digest_bytes(data)


def _validate_progress(progress: Mapping[str, Any], plan: Mapping[str, Any], effect_receipts: list[dict[str, Any]], registry: RegistrySnapshot) -> None:
    schema = registry.schema_document("https://phase-tool.local/schemas/ordered-effect-progress.schema.json")
    Draft202012Validator(schema, registry=registry.schema_registry(), format_checker=FormatChecker()).validate(progress)
    if progress["plan_digest"] != profile_digest("effect-plan", plan):
        raise PhaseError("inspection.progress_plan_mismatch")
    planned_ids = [effect["effect_id"] for effect in plan["effects"]]
    receipt_ids = [receipt["effect_id"] for receipt in effect_receipts]
    if receipt_ids != planned_ids[: len(receipt_ids)]:
        raise PhaseError("inspection.progress_prefix_mismatch")
    if progress["completed_effect_ids"] != receipt_ids:
        raise PhaseError("inspection.progress_prefix_mismatch")
    if progress["not_started_effect_ids"] != planned_ids[len(receipt_ids):]:
        raise PhaseError("inspection.progress_prefix_mismatch")
    receipt_by_id = {receipt["effect_id"]: receipt for receipt in effect_receipts}
    for index, effect_progress in enumerate(progress["effects"]):
        if effect_progress["ordinal"] != index or effect_progress["effect_id"] != planned_ids[index]:
            raise PhaseError("inspection.progress_prefix_mismatch")
        receipt = receipt_by_id.get(effect_progress["effect_id"])
        if receipt is None:
            if effect_progress["state"] != "not_started" or effect_progress["receipt_digest"] is not None or effect_progress["observation_digest"] is not None:
                raise PhaseError("inspection.progress_prefix_mismatch")
            continue
        if effect_progress["receipt_digest"] != profile_digest("effect-receipt", receipt):
            raise PhaseError("inspection.progress_receipt_mismatch")
        observation_digest = profile_digest("effect-observation", {"effect_id": receipt["effect_id"], "after": receipt["after"], "status": receipt["status"]})
        if effect_progress["observation_digest"] != observation_digest:
            raise PhaseError("inspection.progress_observation_mismatch")


def _verify_intent_blobs(run_root: Path, intent: Mapping[str, Any], plan: Mapping[str, Any] | None = None) -> None:
    for item in intent["inputs"]:
        digest = item["blob_digest"]
        if digest is None:
            continue
        blob = run_root / "blobs" / digest.split(":", 1)[1]
        if not evidence_file_exists(blob) or digest_bytes(read_evidence_bytes(blob)) != digest:
            raise PhaseError("inspection.digest_mismatch", blob.name)
    evidence = intent.get("evidence", {})
    for digest in evidence.get("content_blob_digests", []):
        blob = run_root / "blobs" / digest.split(":", 1)[1]
        if not evidence_file_exists(blob) or digest_bytes(read_evidence_bytes(blob)) != digest:
            raise PhaseError("inspection.digest_mismatch", blob.name)
    if plan is None or plan.get("operation_intent") != "publish_new_version":
        return
    inputs = {item["binding_id"]: item for item in intent["inputs"]}
    for effect in plan.get("effects", []):
        source = effect.get("content_source", {})
        if source.get("kind") != "frozen_input":
            continue
        binding_id = source.get("binding_id")
        item = inputs.get(binding_id)
        if item is None or item.get("blob_digest") is None:
            raise PhaseError("inspection.frozen_input_mismatch", str(binding_id))
        blob_digest = item["blob_digest"]
        blob = run_root / "blobs" / blob_digest.split(":", 1)[1]
        data = read_evidence_bytes(blob)
        if (
            item.get("digest") != blob_digest
            or source.get("source_digest") != blob_digest
            or effect.get("content_digest") != blob_digest
            or effect.get("content_length") != len(data)
        ):
            raise PhaseError("inspection.frozen_input_mismatch", str(binding_id))


def _prior_receipt_run_id(runs_root: Path, current_run_id: str, prior_digest: str) -> str:
    for path in iter_run_artifacts(runs_root, "receipt.json"):
        if path.parent.name == current_run_id:
            continue
        try:
            candidate, _ = _read_canonical(path)
        except PhaseError:
            continue
        if profile_digest("receipt", candidate) == prior_digest:
            return path.parent.name
    raise PhaseError("inspection.prior_receipt_missing", prior_digest)


def inspect_run(
    evidence_root: Path,
    run_id: str,
    registry: RegistrySnapshot | None = None,
    *,
    root_bindings: Mapping[str, Path] | None = None,
    _visited_receipts: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Verify evidence and, for observed results, re-read installation-bound target bytes."""
    validate_run_id(run_id)
    registry = registry or BundledRegistry.load()
    root = Path(_platform_path(Path(evidence_root))).resolve(strict=True)
    run_root = (root / ".phase" / "runs" / run_id).resolve(strict=True)
    expected_parent = (root / ".phase" / "runs").resolve(strict=True)
    try:
        run_root.relative_to(expected_parent)
    except ValueError as exc:
        raise PhaseError("inspection.outside_evidence_root", run_id) from exc
    receipt_path = run_root / "receipt.json"
    if not evidence_file_exists(receipt_path):
        intent, _ = _read_canonical(run_root / "intent.json")
        intent_digest = profile_digest("intent", intent)
        validate_intent(intent, registry)
        plan, _ = _read_canonical(run_root / "attachments" / "effect-plan.json")
        plan_digest = profile_digest("effect-plan", plan)
        if plan_digest != intent["effect_plan_digest"]:
            raise PhaseError("inspection.digest_mismatch", "effect-plan.json")
        if intent.get("evidence", {}).get("effect_plan_attachment_digest") != digest_bytes(canonical_bytes(plan)):
            raise PhaseError("inspection.digest_mismatch", "effect-plan.json")
        _verify_intent_blobs(run_root, intent, plan)
        contract_binding = intent["contract"]
        contract = registry.resolve_contract(
            contract_binding["id"],
            contract_binding["version"],
            contract_binding["package_digest"],
            core_version=intent["core"]["version"],
        )
        state_classification = None
        hook = load_contract_hook(contract)
        if hook is not None and hasattr(hook, "inspect_missing_receipt_result"):
            validate_static_plan(plan, contract, root_bindings or {}, registry)
            state_classification = hook.inspect_missing_receipt_result(plan, root_bindings or {}, registry)
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
            "state_classification": state_classification,
        }
    receipt, _ = _read_canonical(receipt_path)
    receipt_digest = profile_digest("receipt", receipt)
    if receipt_digest in _visited_receipts:
        raise PhaseError("inspection.prior_receipt_cycle", receipt_digest)
    validate_receipt(receipt, registry)
    intent = None
    intent_digest = None
    plan = None
    plan_digest = None
    target_verified: bool | None = None
    contract_result: Any | None = None
    state_classification: str | None = None
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
            planned_ids = [item["effect_id"] for item in plan["effects"]]
            receipt_ids = [item["effect_id"] for item in effect_receipts]
            if receipt_ids != planned_ids[: len(receipt_ids)]:
                raise PhaseError("inspection.effect_receipt_set_mismatch")
            if not isinstance(pre_validators, list):
                raise PhaseError("inspection.validator_results_mismatch")
            progress_path = run_root / "attachments" / "ordered-effect-progress.json"
            if evidence_file_exists(progress_path):
                progress, progress_digest = _read_canonical(progress_path)
                _validate_progress(progress, plan, effect_receipts, registry)
                attachment_digests.add(progress_digest)
            attachment_digests.update({pre_validators_digest, effect_receipts_digest})
        claimed = set(receipt["evidence"]["attachment_digests"])
        if attachment_digests != claimed:
            raise PhaseError("inspection.attachment_set_mismatch")
        _verify_intent_blobs(run_root, intent, plan)
        contract_for_plan = registry.resolve_contract(
            intent["contract"]["id"],
            intent["contract"]["version"],
            intent["contract"]["package_digest"],
            core_version=intent["core"]["version"],
        )
        hook_for_plan = load_contract_hook(contract_for_plan)
        needs_state_classification = (
            receipt["terminal_status"] not in {"succeeded_verified", "validated_planned"}
            or receipt["evidence"]["finalization_status"] != "finalized"
        )
        if needs_state_classification and hook_for_plan is not None and hasattr(hook_for_plan, "inspect_missing_receipt_result"):
            validate_static_plan(plan, contract_for_plan, root_bindings or {}, registry)
            state_classification = hook_for_plan.inspect_missing_receipt_result(plan, root_bindings or {}, registry)
    canonical_result = receipt["canonical_result"]
    if canonical_result is not None:
        contract_binding = receipt["contract"]
        contract = registry.resolve_contract(
            contract_binding["id"],
            contract_binding["version"],
            contract_binding["package_digest"],
            core_version=receipt["core"]["version"],
        )
        roots = root_bindings or {}
        root_id = canonical_result["root_binding"]
        try:
            target_root = Path(roots[root_id])
        except KeyError as exc:
            raise PhaseError("inspection.target_root_missing", root_id) from exc
        try:
            target = contained_read_path(target_root, canonical_result["locator"])
            with open(_platform_path(target), "rb") as stream:
                data = stream.read()
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
        if receipt["execution_disposition"] == "reused_existing":
            prior_digest = receipt.get("prior_verified_receipt_digest")
            if not isinstance(prior_digest, str):
                raise PhaseError("inspection.prior_receipt_missing")
            prior_run_id = _prior_receipt_run_id(root / ".phase" / "runs", run_id, prior_digest)
            prior = inspect_run(
                root,
                prior_run_id,
                registry,
                root_bindings=root_bindings,
                _visited_receipts=_visited_receipts | {receipt_digest},
            )
            if prior.get("terminal_status") != "succeeded_verified" or prior.get("target_verified") is not True or prior.get("contract") != receipt["contract"]:
                raise PhaseError("inspection.prior_receipt_mismatch", prior_run_id)
            contract_result = prior.get("contract_result")
        else:
            hook = load_contract_hook(contract)
            if hook is not None:
                setattr(hook, "_registry", registry)
                contract_result = hook.inspect_result(data, state["digest"], target_root, receipt_digest, registry, evidence_root=root)
                if hasattr(hook, "inspect_receipt_result"):
                    receipt_result = hook.inspect_receipt_result(
                        receipt,
                        plan,
                        target_root,
                        registry,
                        root,
                        root_bindings=root_bindings,
                    )
                    if isinstance(contract_result, dict) and isinstance(receipt_result, dict):
                        contract_result = dict(contract_result) | receipt_result
                    else:
                        contract_result = receipt_result
        target_verified = True
    result = {
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
    if state_classification is not None:
        result["state_classification"] = state_classification
    if contract_result is not None:
        result["contract_result"] = contract_result
    return result
