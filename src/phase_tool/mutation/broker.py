from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import base64
from pathlib import Path
from typing import Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from ..canonical import canonical_bytes, digest_bytes, parse_json_bytes, profile_digest
from ..contracts import load_contract_hook
from ..errors import PhaseError

from ..freeze import FrozenInput
from ..planning import validate_static_plan
from ..registry import RegistrySnapshot, ResolvedContract
from .content_addressed_copy import ContentAddressedCopyFaults, execute_content_addressed_copy
from .exclusive_create import ExclusiveCreateFaults, execute_exclusive_create
from .expected_head_append import AppendRecordFaults, execute_append_record
from .target_authority import TargetRootLock


@dataclass(frozen=True)
class BrokerFaults:
    exclusive_create: ExclusiveCreateFaults | None = None
    append_record: AppendRecordFaults | None = None
    content_addressed_copy: ContentAddressedCopyFaults | None = None
    content_addressed_copy_fail_after_bytes: int | None = None
    mutate_plan_after_intent: bool = False
    before_mechanism: Callable[[Path], None] | None = None
    before_effect: Mapping[int, Callable[[Path], None]] | None = None
    before_effect_lock: Callable[[int, Path], None] | None = None


class EffectBroker:
    """The only boundary allowed to invoke a target mutation mechanism."""

    def __init__(self, registry: RegistrySnapshot) -> None:
        self.registry = registry
        schema = registry.schema_document("https://phase-tool.local/schemas/effect-receipt.schema.json")
        self._receipt_validator = Draft202012Validator(
            schema,
            registry=registry.schema_registry(),
            format_checker=FormatChecker(),
        )

    def _locked_plan_from_evidence(
        self,
        plan: dict[str, object],
        contract: ResolvedContract,
        root_bindings: Mapping[str, Path],
        intent_path: Path,
    ) -> dict[str, object]:
        intent = parse_json_bytes(intent_path.read_bytes())
        run_root = intent_path.parent
        plan_path = run_root / "attachments" / "effect-plan.json"
        if not plan_path.is_file():
            raise PhaseError("broker.plan_attachment_missing")
        plan_bytes = plan_path.read_bytes()
        attached_plan = parse_json_bytes(plan_bytes)
        attachment_digest = digest_bytes(plan_bytes)
        evidence = intent.get("evidence", {})
        if evidence.get("effect_plan_attachment_digest") != attachment_digest:
            raise PhaseError("broker.plan_attachment_mismatch")
        if attached_plan != plan:
            raise PhaseError("broker.plan_attachment_mismatch")
        expected_contract = {"id": contract.document["identity"]["id"], "version": contract.document["identity"]["version"], "package_digest": contract.package_digest}
        if intent.get("contract") != expected_contract:
            raise PhaseError("broker.intent_contract_mismatch")
        operation = intent.get("operation")
        if not isinstance(operation, Mapping) or operation.get("mechanism") != attached_plan.get("mechanism"):
            raise PhaseError("broker.intent_mechanism_mismatch")
        if intent.get("effect_plan_digest") != profile_digest("effect-plan", attached_plan):
            raise PhaseError("broker.intent_plan_mismatch")
        locked_plan = parse_json_bytes(canonical_bytes(attached_plan))
        validate_static_plan(locked_plan, contract, root_bindings, self.registry)
        return locked_plan

    @staticmethod
    def _attached_blob_content(effect: Mapping[str, object], intent_path: Path, intent: Mapping[str, object]) -> bytes:
        blob_digest = effect.get("content_blob_digest")
        if not isinstance(blob_digest, str):
            raise PhaseError("broker.content_blob_missing", str(effect.get("effect_id")))
        evidence = intent.get("evidence", {})
        bound_digests = evidence.get("content_blob_digests") if isinstance(evidence, Mapping) else None
        if not isinstance(bound_digests, list) or blob_digest not in bound_digests:
            raise PhaseError("broker.content_blob_unbound", str(effect.get("effect_id")))
        blob_path = intent_path.parent / "blobs" / blob_digest.split(":", 1)[1]
        if not blob_path.is_file():
            raise PhaseError("broker.content_blob_missing", blob_digest)
        content = blob_path.read_bytes()
        if len(content) != effect["content_length"] or digest_bytes(content) != effect["content_digest"] or digest_bytes(content) != blob_digest:
            raise PhaseError("broker.content_blob_mismatch", blob_digest)
        encoded = effect.get("content_bytes_b64")
        if isinstance(encoded, str):
            inline = base64.b64decode(encoded.encode("ascii"), validate=True)
            if inline != content:
                raise PhaseError("broker.inline_blob_mismatch", str(effect.get("effect_id")))
        return content

    @staticmethod
    def _frozen_blob_content(effect: Mapping[str, object], intent_path: Path, intent: Mapping[str, object]) -> bytes:
        source = effect.get("content_source")
        if not isinstance(source, Mapping) or source.get("kind") != "frozen_input":
            raise PhaseError("broker.content_source_missing", str(effect.get("effect_id")))
        binding_id = source.get("binding_id")
        inputs = intent.get("inputs")
        if not isinstance(inputs, list):
            raise PhaseError("broker.content_source_missing", str(effect.get("effect_id")))
        matches = [item for item in inputs if isinstance(item, Mapping) and item.get("binding_id") == binding_id]
        if len(matches) != 1:
            raise PhaseError("broker.content_source_missing", str(binding_id))
        record = matches[0]
        blob_digest = record.get("blob_digest")
        if not isinstance(blob_digest, str):
            raise PhaseError("broker.content_source_not_frozen", str(binding_id))
        if blob_digest != effect.get("content_digest") or record.get("digest") != effect.get("content_digest"):
            raise PhaseError("broker.content_blob_mismatch", blob_digest)
        blob_path = intent_path.parent / "blobs" / blob_digest.split(":", 1)[1]
        if not blob_path.is_file():
            raise PhaseError("broker.content_blob_missing", blob_digest)
        content = blob_path.read_bytes()
        if len(content) != effect["content_length"] or digest_bytes(content) != effect["content_digest"]:
            raise PhaseError("broker.content_blob_mismatch", blob_digest)
        return content

    def execute(
        self,
        plan: dict[str, object],
        contract: ResolvedContract,
        frozen_inputs: Mapping[str, FrozenInput],
        root_bindings: Mapping[str, Path],
        intent_path: Path,
        operational_lock_root: Path,
        *,
        timestamp: str,
        faults: BrokerFaults | None = None,
        progress_callback: Callable[[list[dict[str, object]]], None] | None = None,
        receipt_sink: list[dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        active = faults or BrokerFaults()
        if not intent_path.is_file():
            raise PhaseError("broker.intent_missing")
        intent = parse_json_bytes(intent_path.read_bytes())
        if intent.get("execution_requested") is not True:
            raise PhaseError("broker.execution_not_requested")
        locked_plan = self._locked_plan_from_evidence(plan, contract, root_bindings, intent_path)
        if active.mutate_plan_after_intent:
            plan["effects"].append(deepcopy(plan["effects"][0]))  # type: ignore[union-attr,index]
        if intent.get("effect_plan_digest") != profile_digest("effect-plan", plan):
            raise PhaseError("broker.plan_changed_after_intent")
        if active.before_mechanism is not None:
            active.before_mechanism(intent_path)
        locked_plan = self._locked_plan_from_evidence(plan, contract, root_bindings, intent_path)
        intent = parse_json_bytes(intent_path.read_bytes())
        if intent.get("execution_requested") is not True:
            raise PhaseError("broker.execution_not_requested")
        effects = locked_plan["effects"]
        if not effects or any(effect["kind"] not in {"exclusive_create", "append_record", "copy_blob"} for effect in effects):
            raise PhaseError("broker.plan_not_executable")
        receipts = receipt_sink if receipt_sink is not None else []
        hook = load_contract_hook(contract)
        candidate = intent.get("candidate", {}).get("storage", {}).get("value")
        for ordinal, effect in enumerate(effects):
            mechanism = effect.get("mechanism", locked_plan["mechanism"])
            entry = self.registry.resolve_mechanism(mechanism)
            descriptor = parse_json_bytes(self.registry.resource_bytes(str(entry["artifact"])))
            if descriptor.get("execution_allowed") is not True:
                raise PhaseError("broker.mechanism_execution_unavailable", str(mechanism["id"]))
            supported = {
                ("mechanism.exclusive_create_v1", "1.0.0"),
                ("mechanism.expected_head_append_v1", "1.0.0"),
                ("content_addressed_copy", "1.0.0"),
            }
            if (mechanism["id"], mechanism["version"]) not in supported:
                raise PhaseError("broker.mechanism_execution_unavailable", str(mechanism["id"]))
            root_id = effect["target"]["root_binding"]
            try:
                target_root = Path(root_bindings[root_id]).resolve(strict=True)
            except KeyError as exc:
                raise PhaseError("plan.root_binding_missing", str(root_id)) from exc
            if active.before_effect_lock is not None:
                active.before_effect_lock(ordinal, intent_path)
            lock_scope = effect.get("lock_scope")
            if isinstance(lock_scope, str):
                context = TargetRootLock(target_root, lock_scope)
            else:
                context = None
            if context is None:
                receipt = self._execute_one(active, candidate, contract, effect, frozen_inputs, hook, intent, intent_path, ordinal, target_root, timestamp)
            else:
                with context:
                    receipt = self._execute_one(active, candidate, contract, effect, frozen_inputs, hook, intent, intent_path, ordinal, target_root, timestamp)
            self._receipt_validator.validate(receipt)
            receipts.append(receipt)
            if progress_callback is not None:
                progress_callback(list(receipts))
            if receipt["status"] != "applied_verified":
                break
        return receipts

    def _execute_one(
        self,
        active: BrokerFaults,
        candidate: object,
        contract: ResolvedContract,
        effect: dict[str, object],
        frozen_inputs: Mapping[str, FrozenInput],
        hook: object | None,
        intent: Mapping[str, object],
        intent_path: Path,
        ordinal: int,
        target_root: Path,
        timestamp: str,
    ) -> dict[str, object]:
        try:
            if hook is not None and hasattr(hook, "before_effect"):
                hook.before_effect(candidate, contract, effect, frozen_inputs, target_root)
            if active.before_effect and ordinal in active.before_effect:
                active.before_effect[ordinal](intent_path)
            if effect.get("content_blob_digest") is not None:
                content = self._attached_blob_content(effect, intent_path, intent)
            elif effect["kind"] == "copy_blob":
                content = self._frozen_blob_content(effect, intent_path, intent)
            elif effect["content_source"]["kind"] == "frozen_input":
                content = self._frozen_blob_content(effect, intent_path, intent)
            else:
                encoded = effect.get("content_bytes_b64")
                if not isinstance(encoded, str):
                    raise PhaseError("broker.content_source_missing", "content_bytes_b64")
                content = base64.b64decode(encoded.encode("ascii"), validate=True)
        except PhaseError as exc:
            if ordinal == 0:
                raise
            unknown = {"known": False, "exists": None, "digest": None, "length": None, "head_token": None}
            return {
                "effect_receipt_version": "1.0",
                "run_id": str(intent.get("run_id")),
                "effect_id": effect["effect_id"],
                "kind": effect["kind"],
                "status": "failed_no_effect",
                "attempted": True,
                "before": unknown,
                "after": unknown,
                "bytes_written": 0,
                "verification_refs": ["broker.preinvocation"],
                "error": {"code": exc.code, "message": str(exc)},
                "started_at": timestamp,
                "finished_at": timestamp,
            }
        if effect["kind"] == "exclusive_create":
            return execute_exclusive_create(
                effect,
                target_root,
                content,
                run_id=str(contract.document.get("_run_id", intent.get("run_id"))),
                timestamp=timestamp,
                faults=active.exclusive_create,
            )
        if effect["kind"] == "append_record":
            return execute_append_record(
                effect,
                target_root,
                content,
                run_id=str(intent.get("run_id")),
                timestamp=timestamp,
                operational_lock_root=intent_path.parent.parent.parent / "locks",
                faults=active.append_record,
            )
        copy_faults = active.content_addressed_copy
        if active.content_addressed_copy_fail_after_bytes is not None:
            copy_faults = ContentAddressedCopyFaults(fail_after_bytes=active.content_addressed_copy_fail_after_bytes)
        return execute_content_addressed_copy(
            effect,
            target_root,
            content,
            run_id=str(intent.get("run_id")),
            timestamp=timestamp,
            faults=copy_faults,
        )
