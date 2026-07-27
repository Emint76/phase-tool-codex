from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from ..canonical import canonical_bytes, parse_json_bytes, profile_digest
from ..errors import PhaseError
from ..freeze import FrozenInput, revalidate_frozen
from ..planning import validate_static_plan
from ..registry import RegistrySnapshot, ResolvedContract
from .exclusive_create import ExclusiveCreateFaults, execute_exclusive_create


@dataclass(frozen=True)
class BrokerFaults:
    exclusive_create: ExclusiveCreateFaults | None = None
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

    def execute(
        self,
        plan: dict[str, object],
        contract: ResolvedContract,
        frozen_inputs: Mapping[str, FrozenInput],
        root_bindings: Mapping[str, Path],
        intent_path: Path,
        *,
        timestamp: str,
        faults: BrokerFaults | None = None,
    ) -> list[dict[str, object]]:
        active = faults or BrokerFaults()
        if not intent_path.is_file():
            raise PhaseError("broker.intent_missing")
        intent = parse_json_bytes(intent_path.read_bytes())
        if intent.get("effect_plan_digest") != profile_digest("effect-plan", plan):
            raise PhaseError("broker.intent_plan_mismatch")
        if active.mutate_plan_after_intent:
            plan["effects"].append(deepcopy(plan["effects"][0]))  # type: ignore[union-attr,index]
        if intent.get("effect_plan_digest") != profile_digest("effect-plan", plan):
            raise PhaseError("broker.plan_changed_after_intent")
        locked_plan = parse_json_bytes(canonical_bytes(plan))
        validate_static_plan(locked_plan, contract, root_bindings, self.registry)
        mechanism = locked_plan["mechanism"]
        entry = self.registry.resolve_mechanism(mechanism)
        descriptor = parse_json_bytes(self.registry.resource_bytes(str(entry["artifact"])))
        if descriptor.get("execution_allowed") is not True:
            raise PhaseError("broker.mechanism_execution_unavailable", str(mechanism["id"]))
        if (mechanism["id"], mechanism["version"]) != ("mechanism.exclusive_create_v1", "1.0.0"):
            raise PhaseError("broker.mechanism_execution_unavailable", str(mechanism["id"]))
        effects = locked_plan["effects"]
        if len(effects) != 1 or effects[0]["kind"] != "exclusive_create":
            raise PhaseError("broker.plan_not_executable")
        effect = effects[0]
        root_id = effect["target"]["root_binding"]
        try:
            target_root = Path(root_bindings[root_id]).resolve(strict=True)
        except KeyError as exc:
            raise PhaseError("plan.root_binding_missing", str(root_id)) from exc
        binding_id = effect["content_source"]["binding_id"]
        try:
            frozen = frozen_inputs[binding_id]
        except KeyError as exc:
            raise PhaseError("broker.content_source_missing", str(binding_id)) from exc
        if frozen.blob_path is None:
            raise PhaseError("broker.content_source_not_frozen", str(binding_id))
        revalidate_frozen(frozen)
        content = frozen.blob_path.read_bytes()
        if active.before_mechanism is not None:
            active.before_mechanism(intent_path)
        receipt = execute_exclusive_create(
            effect,
            target_root,
            content,
            run_id=str(locked_plan["run_id"]),
            timestamp=timestamp,
            faults=active.exclusive_create,
        )
        self._receipt_validator.validate(receipt)
        return [receipt]
