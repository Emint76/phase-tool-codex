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
from .mutation import BrokerFaults, EffectBroker
from .planning import build_idempotency_digests, build_static_plan, validate_static_plan
from .registry import BundledRegistry, RegistrySnapshot, ResolvedContract
from .validation import ValidatorRunner

CORE_BINDING = {
    "id": "phase.core",
    "version": __version__,
    "package_digest": profile_digest("core-package", {"id": "phase.core", "version": __version__, "capability": "effect_broker_v1"}),
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
class CoreFaults:
    broker: BrokerFaults | None = None
    fail_receipt_write: bool = False


@dataclass(frozen=True)
class PhaseOutcome:
    run_id: str
    exit_code: int
    receipt: dict[str, Any]
    intent: dict[str, Any] | None
    effect_plan: dict[str, Any] | None
    lifecycle: tuple[str, ...]
    receipt_digest: str | None
    effect_plan_digest: str | None


class PhaseCore:
    """One lifecycle coordinator; canonical target writes belong only to EffectBroker."""

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

    def _base_receipt(
        self,
        request: PhaseRequest,
        validator_results: list[dict[str, Any]],
        timestamp: str,
    ) -> dict[str, Any]:
        return {
            "phase_receipt_version": "1.0",
            "run_id": request.run_id,
            "contract": self._requested_binding(request),
            "core": CORE_BINDING,
            "started_at": timestamp,
            "finished_at": timestamp,
            "validator_results": validator_results,
            "prior_verified_receipt_digest": None,
        }

    def _planned_receipt(
        self,
        request: PhaseRequest,
        validator_results: list[dict[str, Any]],
        timestamp: str,
        intent_digest: str,
        attachment_digests: list[str],
    ) -> dict[str, Any]:
        return self._base_receipt(request, validator_results, timestamp) | {
            "terminal_status": "validated_planned",
            "execution_disposition": "not_executed",
            "mutation_attempted": False,
            "result_state": "planned_no_effect",
            "canonical_result": None,
            "effect_receipts": [],
            "evidence": {
                "finalization_status": "finalized",
                "intent_digest": intent_digest,
                "receipt_digest_policy_id": "digest.phase_canonical_json_v1",
                "required_attachments_present": True,
                "attachment_digests": sorted(attachment_digests),
            },
            "retry_disposition": "safe_idempotent_retry",
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
        *,
        intent_digest: str | None = None,
        attachment_digests: list[str] | None = None,
    ) -> dict[str, Any]:
        blockers = sorted({item for result in validator_results for item in result.get("blockers", [])}) or [blocker]
        return self._base_receipt(request, validator_results, timestamp) | {
            "terminal_status": "aborted" if intent_digest else "rejected",
            "execution_disposition": "not_executed",
            "mutation_attempted": False,
            "result_state": "none",
            "canonical_result": None,
            "effect_receipts": [],
            "evidence": {
                "finalization_status": "finalized",
                "intent_digest": intent_digest,
                "receipt_digest_policy_id": "digest.phase_canonical_json_v1",
                "required_attachments_present": bool(attachment_digests),
                "attachment_digests": sorted(attachment_digests or []),
            },
            "retry_disposition": "forbidden",
            "recovery_required": False,
            "blockers": blockers,
            "exit_code": 10,
        }

    @staticmethod
    def _canonical_result(contract: ResolvedContract, effect: Mapping[str, Any], observation: Mapping[str, Any], timestamp: str) -> dict[str, Any] | None:
        if observation.get("known") is not True or observation.get("exists") is not True:
            return None
        return {
            "reference_version": "1.0",
            "owner_id": contract.document["canonical_result"]["owner_id"],
            "root_binding": effect["target"]["root_binding"],
            "locator": effect["target"]["relative_locator"],
            "contract": {
                "id": contract.document["identity"]["id"],
                "version": contract.document["identity"]["version"],
                "package_digest": contract.package_digest,
            },
            "authority_rule": contract.document["canonical_result"]["authority_rule"],
            "state": {
                "exists": True,
                "digest": observation.get("digest"),
                "length": observation.get("length"),
                "head_token": observation.get("head_token"),
            },
            "observed_at": timestamp,
        }

    def _executed_receipt(
        self,
        request: PhaseRequest,
        contract: ResolvedContract,
        plan: Mapping[str, Any],
        validator_results: list[dict[str, Any]],
        effect_receipts: list[dict[str, Any]],
        timestamp: str,
        intent_digest: str,
        attachment_digests: list[str],
        *,
        finalization_failed: bool,
        required_attachments_present: bool = True,
    ) -> dict[str, Any]:
        effect = plan["effects"][0]
        effect_receipt = effect_receipts[0]
        status = effect_receipt["status"]
        post_verified = all(
            result["status"] == "pass"
            for result in validator_results
            if result["phase"] == "post_operation" and result["blocking"]
        )
        mapping = {
            "failed_no_effect": ("failed_no_effect", "verified_no_effect", 20, False),
            "failed_partial": ("failed_partial", "known_partial", 30, True),
            "applied_unverified": ("committed_unverified", "committed_unverified", 40, True),
            "indeterminate": ("indeterminate", "indeterminate", 50, True),
        }
        if status == "applied_verified" and post_verified and not finalization_failed:
            terminal, result_state, exit_code, recovery = "succeeded_verified", "verified_result", 0, False
        elif status == "applied_verified":
            terminal, result_state, exit_code, recovery = "committed_unverified", "committed_unverified", 40, True
        else:
            terminal, result_state, exit_code, recovery = mapping[status]
        error = effect_receipt.get("error")
        blockers = [] if terminal == "succeeded_verified" else [
            "evidence.finalization_failed" if finalization_failed else (error["code"] if error else "verification.incomplete")
        ]
        return self._base_receipt(request, validator_results, timestamp) | {
            "terminal_status": terminal,
            "execution_disposition": "executed",
            "mutation_attempted": bool(effect_receipt["attempted"]),
            "result_state": result_state,
            "canonical_result": (
                self._canonical_result(contract, effect, effect_receipt["after"], timestamp)
                if terminal in {"succeeded_verified", "committed_unverified"}
                else None
            ),
            "effect_receipts": effect_receipts,
            "evidence": {
                "finalization_status": "failed" if finalization_failed else "finalized",
                "intent_digest": intent_digest,
                "receipt_digest_policy_id": "digest.phase_canonical_json_v1",
                "required_attachments_present": required_attachments_present,
                "attachment_digests": sorted(attachment_digests),
            },
            "retry_disposition": "forbidden" if recovery else "safe_idempotent_retry",
            "recovery_required": recovery,
            "blockers": blockers,
            "exit_code": exit_code,
        }

    def run(self, request: PhaseRequest, *, execute: bool = False, faults: CoreFaults | None = None) -> PhaseOutcome:
        timestamp = self._timestamp(request)
        evidence_root = self._check_root_separation(request)
        store = EvidenceStore(evidence_root, request.run_id)
        lifecycle: list[str] = []
        validator_results: list[dict[str, Any]] = []
        plan: dict[str, Any] | None = None
        intent: dict[str, Any] | None = None
        contract: ResolvedContract | None = None
        effect_receipts: list[dict[str, Any]] = []
        final_validators_published = False
        plan_digest: str | None = None
        attachment_digests: list[str] = []
        active_faults = faults or CoreFaults()
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
            runner = ValidatorRunner(self.registry)
            validator_results = runner.run(
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
            attachment_digests.append(plan_attachment_digest)
            plan_digest = profile_digest("effect-plan", plan)
            validator_name = "attachments/pre-validator-results.json" if execute else "attachments/validator-results.json"
            _, validators_digest = store.write_canonical(validator_name, validator_results)
            attachment_digests.append(validators_digest)
            intent = self._intent(request, contract, candidate, frozen, plan, timestamp, scope_digest, request_digest, key)
            validate_intent(intent, self.registry)
            lifecycle.append("intent")
            intent_path, _ = store.write_canonical("intent.json", intent)
            intent_digest = profile_digest("intent", intent)
            if not execute:
                receipt = self._planned_receipt(request, validator_results, timestamp, intent_digest, attachment_digests)
            else:
                lifecycle.append("broker")
                effect_receipts = EffectBroker(self.registry).execute(
                    plan,
                    contract,
                    frozen,
                    request.root_bindings,
                    intent_path,
                    timestamp=timestamp,
                    faults=active_faults.broker,
                )
                lifecycle.append("effect")
                _, effects_digest = store.write_canonical("attachments/effect-receipts.json", effect_receipts)
                attachment_digests.append(effects_digest)
                lifecycle.append("verify")
                validator_results = runner.run_post_operation(
                    contract,
                    validator_results,
                    plan,
                    request.root_bindings,
                    run_id=request.run_id,
                    timestamp=timestamp,
                )
                _, final_validators_digest = store.write_canonical("attachments/validator-results.json", validator_results)
                attachment_digests.append(final_validators_digest)
                final_validators_published = True
                receipt = self._executed_receipt(
                    request,
                    contract,
                    plan,
                    validator_results,
                    effect_receipts,
                    timestamp,
                    intent_digest,
                    attachment_digests,
                    finalization_failed=active_faults.fail_receipt_write,
                )
            validate_receipt(receipt, self.registry)
            lifecycle.append("receipt")
            if not active_faults.fail_receipt_write:
                store.write_canonical("receipt.json", receipt)
            receipt_digest = None if active_faults.fail_receipt_write else profile_digest("receipt", receipt)
            return PhaseOutcome(request.run_id, receipt["exit_code"], receipt, intent, plan, tuple(lifecycle), receipt_digest, plan_digest)
        except (PhaseError, OSError) as exc:
            intent_digest = profile_digest("intent", intent) if intent is not None else None
            if effect_receipts and intent_digest is not None and contract is not None and plan is not None:
                receipt = self._executed_receipt(
                    request,
                    contract,
                    plan,
                    validator_results,
                    effect_receipts,
                    timestamp,
                    intent_digest,
                    attachment_digests,
                    finalization_failed=True,
                    required_attachments_present=final_validators_published,
                )
                validate_receipt(receipt, self.registry)
                if not lifecycle or lifecycle[-1] != "receipt":
                    lifecycle.append("receipt")
                return PhaseOutcome(
                    request.run_id,
                    receipt["exit_code"],
                    receipt,
                    intent,
                    plan,
                    tuple(lifecycle),
                    None,
                    plan_digest,
                )
            if isinstance(exc, OSError):
                raise
            receipt = self._rejection_receipt(
                request,
                validator_results,
                timestamp,
                exc.code,
                intent_digest=intent_digest,
                attachment_digests=attachment_digests,
            )
            validate_receipt(receipt, self.registry)
            store.write_canonical("receipt.json", receipt)
            receipt_digest = profile_digest("receipt", receipt)
            return PhaseOutcome(request.run_id, receipt["exit_code"], receipt, intent, plan, tuple(lifecycle + ["receipt"]), receipt_digest, plan_digest)
