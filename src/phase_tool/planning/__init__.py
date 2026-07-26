from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from ..candidate import CapturedCandidate
from ..canonical import canonical_bytes, canonical_digest, digest_bytes, parse_json_bytes, profile_digest
from ..errors import PhaseError
from ..freeze import FrozenInput, revalidate_frozen
from ..paths import safe_relative_locator
from ..registry import RegistrySnapshot, ResolvedContract


def _exact(binding: Mapping[str, Any]) -> dict[str, str]:
    return {"id": str(binding["id"]), "version": str(binding["version"]), "package_digest": str(binding["package_digest"])}


def build_idempotency_digests(
    contract: ResolvedContract,
    candidate: CapturedCandidate,
    frozen_inputs: Mapping[str, FrozenInput],
) -> tuple[str, str, str | None]:
    value = parse_json_bytes(candidate.canonical_bytes)
    locator: Any = value.get("target_locator", sorted(value.get("destinations", [])))
    scope = {
        "contract": {
            "id": contract.document["identity"]["id"],
            "version": contract.document["identity"]["version"],
            "package_digest": contract.package_digest,
        },
        "result_locator": locator,
        "operation_intent": contract.document["operation"]["intent"],
    }
    scope_digest = profile_digest("idempotency-scope", scope)
    request_digest = profile_digest(
        "request",
        {
            "scope": scope,
            "candidate_digest": candidate.digest,
            "inputs": [item.intent_record() for _, item in sorted(frozen_inputs.items())],
        },
    )
    return scope_digest, request_digest, value.get("idempotency_key")


def _require_roots(contract: ResolvedContract, root_bindings: Mapping[str, Path]) -> None:
    required = {root["binding_id"] for root in contract.document["write_scope"]["roots"]}
    missing = required.difference(root_bindings)
    if missing:
        raise PhaseError("plan.root_binding_missing", sorted(missing)[0])
    forbidden = set(contract.document["write_scope"]["forbidden_root_bindings"])
    if forbidden.intersection(root_bindings):
        raise PhaseError("plan.forbidden_root_binding", sorted(forbidden.intersection(root_bindings))[0])
    resolved = [Path(root_bindings[item]).resolve(strict=True) for item in required]
    if len(resolved) != len(set(resolved)):
        raise PhaseError("plan.root_binding_collision")


def _ensure_validation_allows_plan(results: list[dict[str, Any]]) -> None:
    for result in results:
        if result["blocking"] and result["phase"] != "post_operation" and result["status"] != "pass":
            raise PhaseError("validation.blocked", result["code"])


def build_static_plan(
    contract: ResolvedContract,
    candidate: CapturedCandidate,
    frozen_inputs: Mapping[str, FrozenInput],
    validator_results: list[dict[str, Any]],
    *,
    root_bindings: Mapping[str, Path],
    run_id: str,
    generated_at: str,
) -> dict[str, Any]:
    _require_roots(contract, root_bindings)
    _ensure_validation_allows_plan(validator_results)
    value = parse_json_bytes(candidate.canonical_bytes)
    operation = contract.document["operation"]
    common = {
        "effect_plan_version": "1.0",
        "plan_id": "plan." + canonical_digest({"run_id": run_id, "candidate": candidate.digest})[-16:],
        "run_id": run_id,
        "contract": {"id": contract.document["identity"]["id"], "version": contract.document["identity"]["version"], "package_digest": contract.package_digest},
        "operation_intent": operation["intent"],
        "mechanism": _exact(operation["mechanism"]),
        "write_scope_digest": canonical_digest(contract.document["write_scope"]),
        "generated_at": generated_at,
        "effect_order": "static_predeclared",
    }
    effects: list[dict[str, Any]] = []
    if operation["intent"] == "append":
        expected_locator = contract.document["canonical_result"]["locator_template"].replace("{stream_id}", value["stream_id"])
        locator = safe_relative_locator(value["target_locator"])
        if locator != expected_locator:
            raise PhaseError("plan.locator_template_mismatch", locator)
        content = canonical_bytes(value["record"]) + b"\n"
        expected_head = value["expected_head"]
        kind = "exclusive_create" if expected_head is None else "append_record"
        effects.append({
            "effect_id": "effect.append.001",
            "kind": kind,
            "target": {"root_binding": contract.document["canonical_result"]["root_binding"], "relative_locator": locator},
            "input_binding": None,
            "content_source": {"kind": "captured_candidate", "binding_id": None, "source_digest": candidate.digest},
            "content_digest": digest_bytes(content),
            "content_length": len(content),
            "preconditions": {
                "existence": "absent" if expected_head is None else "present",
                "expected_digest": None,
                "expected_head": expected_head,
                "concurrency_token": expected_head,
            },
            "lock_scope": None if expected_head is None else "stream." + value["stream_id"],
            "durability_policy_id": "file_data_synced",
            "on_failure": "stop_and_classify",
        })
    elif operation["intent"] == "copy":
        frozen = frozen_inputs.get(value["input_binding"])
        if frozen is None:
            raise PhaseError("input.required_missing", value["input_binding"])
        revalidate_frozen(frozen)
        for index, locator_value in enumerate(sorted(value["destinations"]), 1):
            locator = safe_relative_locator(locator_value)
            effects.append({
                "effect_id": f"effect.copy.{index:03d}",
                "kind": "copy_blob",
                "target": {"root_binding": contract.document["canonical_result"]["root_binding"], "relative_locator": locator},
                "input_binding": value["input_binding"],
                "content_source": {"kind": "frozen_input", "binding_id": value["input_binding"], "source_digest": frozen.digest},
                "content_digest": frozen.digest,
                "content_length": frozen.length,
                "preconditions": {"existence": "absent_or_same_digest", "expected_digest": frozen.digest, "expected_head": None, "concurrency_token": None},
                "lock_scope": None,
                "durability_policy_id": "file_and_directory_synced",
                "on_failure": "stop_and_classify",
            })
    else:
        raise PhaseError("plan.operation_unsupported", operation["intent"])
    plan = common | {"effects": effects}
    validate_static_plan(plan, contract, root_bindings, None)
    return plan


def validate_static_plan(
    plan: dict[str, Any],
    contract: ResolvedContract,
    root_bindings: Mapping[str, Path],
    registry: RegistrySnapshot | None,
) -> None:
    _require_roots(contract, root_bindings)
    if registry is not None:
        schema = registry.schema_document("https://phase-tool.local/schemas/effect-plan.schema.json")
        errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(plan), key=lambda error: list(error.path))
        if errors:
            raise PhaseError("plan.schema_invalid", errors[0].message)
    if plan.get("contract") != {"id": contract.document["identity"]["id"], "version": contract.document["identity"]["version"], "package_digest": contract.package_digest}:
        raise PhaseError("plan.contract_mismatch")
    if plan.get("mechanism") != _exact(contract.document["operation"]["mechanism"]):
        raise PhaseError("plan.mechanism_mismatch")
    effects = plan.get("effects", [])
    if len(effects) > contract.document["operation"]["maximum_effects"] or not effects:
        raise PhaseError("plan.incomplete")
    ids = [effect["effect_id"] for effect in effects]
    if len(ids) != len(set(ids)):
        raise PhaseError("plan.duplicate_effect_id")
    locators = [(effect["target"]["root_binding"], effect["target"]["relative_locator"]) for effect in effects]
    if len(locators) != len(set(locators)):
        raise PhaseError("plan.locator_collision")
    allowed = set(contract.document["operation"]["allowed_effects"])
    required_roots = {item["binding_id"] for item in contract.document["write_scope"]["roots"]}
    for effect in effects:
        if effect["kind"] not in allowed:
            raise PhaseError("plan.effect_not_allowed", effect["kind"])
        if effect["target"]["root_binding"] not in required_roots:
            raise PhaseError("plan.root_binding_unknown", effect["target"]["root_binding"])
        safe_relative_locator(effect["target"]["relative_locator"])
        source = effect["content_source"]
        if source["kind"] == "captured_candidate" and source["binding_id"] is not None:
            raise PhaseError("plan.source_binding_mismatch")
        if source["kind"] == "frozen_input" and source["binding_id"] != effect["input_binding"]:
            raise PhaseError("plan.source_binding_mismatch")
