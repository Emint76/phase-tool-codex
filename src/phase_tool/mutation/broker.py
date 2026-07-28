from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import base64
from pathlib import Path
from typing import Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from ..canonical import canonical_bytes, digest_bytes, parse_json_bytes, profile_digest
from ..errors import PhaseError
from ..freeze import FrozenInput, revalidate_frozen
from ..planning import validate_static_plan
from ..registry import RegistrySnapshot, ResolvedContract
from .content_addressed_copy import ContentAddressedCopyFaults, execute_content_addressed_copy
from .exclusive_create import ExclusiveCreateFaults, execute_exclusive_create
from .expected_head_append import AppendRecordFaults, execute_append_record


@dataclass(frozen=True)
class BrokerFaults:
    exclusive_create: ExclusiveCreateFaults | None = None
    append_record: AppendRecordFaults | None = None
    content_addressed_copy: ContentAddressedCopyFaults | None = None
    mutate_plan_after_intent: bool = False
    before_mechanism: Callable[[Path], None] | None = None


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
    def _append_blob_content(effect: Mapping[str, object], intent_path: Path, intent: Mapping[str, object]) -> bytes:
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
        mechanism = locked_plan["mechanism"]
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
        effects = locked_plan["effects"]
        if len(effects) != 1 or effects[0]["kind"] not in {"exclusive_create", "append_record", "copy_blob"}:
            raise PhaseError("broker.plan_not_executable")
        effect = effects[0]
        root_id = effect["target"]["root_binding"]
        try:
            target_root = Path(root_bindings[root_id]).resolve(strict=True)
        except KeyError as exc:
            raise PhaseError("plan.root_binding_missing", str(root_id)) from exc
        if effect["kind"] == "append_record":
            content = self._append_blob_content(effect, intent_path, intent)
        elif effect["kind"] == "copy_blob":
            content = self._frozen_blob_content(effect, intent_path, intent)
        elif effect["content_source"]["kind"] == "frozen_input":
            binding_id = effect["content_source"]["binding_id"]
            try:
                frozen = frozen_inputs[binding_id]
            except KeyError as exc:
                raise PhaseError("broker.content_source_missing", str(binding_id)) from exc
            if frozen.blob_path is None:
                raise PhaseError("broker.content_source_not_frozen", str(binding_id))
            revalidate_frozen(frozen)
            content = frozen.blob_path.read_bytes()
        else:
            encoded = effect.get("content_bytes_b64")
            if not isinstance(encoded, str):
                raise PhaseError("broker.content_source_missing", "content_bytes_b64")
            content = base64.b64decode(encoded.encode("ascii"), validate=True)
        if effect["kind"] == "exclusive_create":
            receipt = execute_exclusive_create(
                effect,
                target_root,
                content,
                run_id=str(locked_plan["run_id"]),
                timestamp=timestamp,
                faults=active.exclusive_create,
            )
        elif effect["kind"] == "append_record":
            receipt = execute_append_record(
                effect,
                target_root,
                content,
                run_id=str(locked_plan["run_id"]),
                timestamp=timestamp,
                operational_lock_root=operational_lock_root,
                faults=active.append_record,
            )
        else:
            receipt = execute_content_addressed_copy(
                effect,
                target_root,
                content,
                run_id=str(locked_plan["run_id"]),
                timestamp=timestamp,
                faults=active.content_addressed_copy,
            )
        self._receipt_validator.validate(receipt)
        return [receipt]
