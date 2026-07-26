from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import __version__
from .candidate import CapturedCandidate, capture_structured
from .canonical import parse_json_bytes, profile_digest
from .errors import PhaseError
from .evidence import EvidenceStore, validate_intent, validate_receipt
from .freeze import FrozenInput, freeze_declared_inputs
from .planning import build_idempotency_digests, build_static_plan, validate_static_plan
from .registry import BundledRegistry, RegistrySnapshot, ResolvedContract
from .validation import ValidatorRunner

CORE_BINDING = {
    "id": "phase.core",
    "version": __version__,
    "package_digest": profile_digest("core-package", {"id": "phase.core", "version": __version__, "capability": "validation_only"}),
}


@dataclass(frozen=True)
class PhaseRequest:
    contract_id: str
    contract_version: str
    contract_digest: str
    candidate_path: Path
    evidence_root: Path
    run_id: str
    input_paths: Mapping[str, Path]
    root_bindings: Mapping[str, Path]
    timestamp: str | None = None
    maximum_candidate_bytes: int = 1_048_576


@dataclass(frozen=True)
class PhaseOutcome:
    run_id: str
    exit_code: int
    receipt: dict[str, Any]
    intent: dict[str, Any] | None
    effect_plan: dict[str, Any] | None
    lifecycle: tuple[str, ...]
    receipt_digest: str
    effect_plan_digest: str | None


class PhaseCore:
    """One validation-only pipeline. It has no target mutation API."""

    def __init__(self, registry: RegistrySnapshot | None = None) -> None:
        self.registry = registry or BundledRegistry.load()

    @staticmethod
    def _timestamp(request: PhaseRequest) -> str:
        return request.timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _check_root_separation(request: PhaseRequest) -> Path:
        evidence = Path(request.evidence_root).resolve(strict=False)
        for name, root_value in request.root_bindings.items():
            root = Path(root_value).resolve(strict=True)
            try:
                evidence.relative_to(root)
            except ValueError:
                pass
            else:
                raise PhaseError("evidence.overlaps_target_root", name)
            try:
                root.relative_to(evidence)
            except ValueError:
                pass
            else:
                raise PhaseError("evidence.overlaps_target_root", name)
        return evidence

    @staticmethod
    def _requested_binding(request: PhaseRequest) -> dict[str, str]:
        return {"id": request.contract_id, "version": request.contract_version, "package_digest": request.contract_digest}

    @staticmethod
    def _check_idempotency(store: EvidenceStore, key: str | None, scope_digest: str, request_digest: str) -> None:
        if key is None:
            return
        runs_root = store.evidence_root / ".phase" / "runs"
        for path in sorted(runs_root.glob("*/intent.json")):
            if path.parent == store.run_root:
                continue
            intent = parse_json_bytes(path.read_bytes())
            prior = intent.get("idempotency", {})
            if prior.get("key") == key and prior.get("scope_digest") == scope_digest and prior.get("request_digest") != request_digest:
                raise PhaseError("idempotency.same_key_conflict", key)

    def _intent(
        self,
        request: PhaseRequest,
        contract: ResolvedContract,
        candidate: CapturedCandidate,
        frozen: Mapping[str, FrozenInput],
        plan: dict[str, Any],
        timestamp: str,
        scope_digest: str,
        request_digest: str,
        key: str | None,
    ) -> dict[str, Any]:
        return {
            "phase_intent_version": "1.0",
            "run_id": request.run_id,
            "created_at": timestamp,
            "core": CORE_BINDING,
            "registry_snapshot_digest": contract.registry_snapshot_digest,
            "contract": self._requested_binding(request),
            "candidate": {
                "input_mode": candidate.input_mode,
                "digest": candidate.digest,
                "length": candidate.length,
                "storage": {"mode": "inline", "value": parse_json_bytes(candidate.canonical_bytes), "attachment_digest": None},
            },
            "inputs": [item.intent_record() for _, item in sorted(frozen.items())],
            "write_scope_digest": plan["write_scope_digest"],
            "operation": {"intent": contract.document["operation"]["intent"], "mechanism": plan["mechanism"]},
            "idempotency": {"key": key, "scope_digest": scope_digest, "request_digest": request_digest},
            "effect_plan_digest": profile_digest("effect-plan", plan),
            "status": "intent_recorded",
        }

    def _success_receipt(
        self,
        request: PhaseRequest,
        validator_results: list[dict[str, Any]],
        timestamp: str,
        intent_digest: str,
        attachment_digests: list[str],
    ) -> dict[str, Any]:
        return {
            "phase_receipt_version": "1.0",
            "run_id": request.run_id,
            "contract": self._requested_binding(request),
            "core": CORE_BINDING,
            "started_at": timestamp,
            "finished_at": timestamp,
            "terminal_status": "validated_planned",
            "execution_disposition": "not_executed",
            "mutation_attempted": False,
            "result_state": "planned_no_effect",
            "canonical_result": None,
            "validator_results": validator_results,
            "effect_receipts": [],
            "evidence": {
                "finalization_status": "finalized",
                "intent_digest": intent_digest,
                "receipt_digest_policy_id": "digest.phase_canonical_json_v1",
                "required_attachments_present": True,
                "attachment_digests": sorted(attachment_digests),
            },
            "retry_disposition": "safe_idempotent_retry",
            "prior_verified_receipt_digest": None,
            "recovery_required": False,
            "blockers": [],
            "exit_code": 0,
        }

    def _rejection_receipt(
        self,
        request: PhaseRequest,
        validator_results: list[dict[str, Any]],
        timestamp: str,
        blocker: str,
    ) -> dict[str, Any]:
        blockers = sorted({item for result in validator_results for item in result.get("blockers", [])}) or [blocker]
        return {
            "phase_receipt_version": "1.0",
            "run_id": request.run_id,
            "contract": self._requested_binding(request),
            "core": CORE_BINDING,
            "started_at": timestamp,
            "finished_at": timestamp,
            "terminal_status": "rejected",
            "execution_disposition": "not_executed",
            "mutation_attempted": False,
            "result_state": "none",
            "canonical_result": None,
            "validator_results": validator_results,
            "effect_receipts": [],
            "evidence": {
                "finalization_status": "finalized",
                "intent_digest": None,
                "receipt_digest_policy_id": "digest.phase_canonical_json_v1",
                "required_attachments_present": False,
                "attachment_digests": [],
            },
            "retry_disposition": "forbidden",
            "prior_verified_receipt_digest": None,
            "recovery_required": False,
            "blockers": blockers,
            "exit_code": 10,
        }

    def run(self, request: PhaseRequest) -> PhaseOutcome:
        timestamp = self._timestamp(request)
        evidence_root = self._check_root_separation(request)
        store = EvidenceStore(evidence_root, request.run_id)
        lifecycle: list[str] = []
        validator_results: list[dict[str, Any]] = []
        try:
            lifecycle.append("resolve")
            contract = self.registry.resolve_contract(
                request.contract_id,
                request.contract_version,
                request.contract_digest,
                core_version=__version__,
            )
            lifecycle.append("capture")
            candidate = capture_structured(Path(request.candidate_path), maximum_bytes=request.maximum_candidate_bytes)
            lifecycle.append("freeze")
            frozen = freeze_declared_inputs(
                contract.document,
                parse_json_bytes(candidate.canonical_bytes),
                request.input_paths,
                request.root_bindings,
                store.blob_root,
                frozen_at=timestamp,
                maximum_structured_bytes=request.maximum_candidate_bytes,
            )
            lifecycle.append("validate")
            validator_results = ValidatorRunner(self.registry).run(
                contract,
                candidate,
                frozen,
                root_bindings=request.root_bindings,
                run_id=request.run_id,
                timestamp=timestamp,
            )
            lifecycle.append("plan")
            plan = build_static_plan(
                contract,
                candidate,
                frozen,
                validator_results,
                root_bindings=request.root_bindings,
                run_id=request.run_id,
                generated_at=timestamp,
            )
            validate_static_plan(plan, contract, request.root_bindings, self.registry)
            scope_digest, request_digest, key = build_idempotency_digests(contract, candidate, frozen)
            self._check_idempotency(store, key, scope_digest, request_digest)
            _, plan_attachment_digest = store.write_canonical("attachments/effect-plan.json", plan)
            plan_digest = profile_digest("effect-plan", plan)
            _, validators_digest = store.write_canonical("attachments/validator-results.json", validator_results)
            intent = self._intent(request, contract, candidate, frozen, plan, timestamp, scope_digest, request_digest, key)
            validate_intent(intent, self.registry)
            lifecycle.append("intent")
            store.write_canonical("intent.json", intent)
            intent_digest = profile_digest("intent", intent)
            receipt = self._success_receipt(request, validator_results, timestamp, intent_digest, [plan_attachment_digest, validators_digest])
            validate_receipt(receipt, self.registry)
            lifecycle.append("receipt")
            store.write_canonical("receipt.json", receipt)
            receipt_digest = profile_digest("receipt", receipt)
            return PhaseOutcome(request.run_id, 0, receipt, intent, plan, tuple(lifecycle), receipt_digest, plan_digest)
        except PhaseError as exc:
            receipt = self._rejection_receipt(request, validator_results, timestamp, exc.code)
            validate_receipt(receipt, self.registry)
            store.write_canonical("receipt.json", receipt)
            receipt_digest = profile_digest("receipt", receipt)
            return PhaseOutcome(request.run_id, receipt["exit_code"], receipt, None, None, tuple(lifecycle + ["receipt"]), receipt_digest, None)
