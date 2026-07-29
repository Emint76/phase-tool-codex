from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import __version__
from .candidate import CapturedCandidate, capture_structured
from .canonical import digest_bytes, parse_json_bytes, profile_digest
from .errors import PhaseError
from .evidence import EvidenceStore, operational_lock_path, validate_intent, validate_receipt
from .freeze import FrozenInput, freeze_declared_inputs
from .inspection import inspect_run
from .mutation import BrokerFaults, EffectBroker
from .planning import build_idempotency_digests, build_static_plan, validate_static_plan
from .registry import BundledRegistry, RegistrySnapshot, ResolvedContract
from .validation import ValidatorRunner

CORE_BINDING = {
    "id": "phase.core",
    "version": __version__,
    "package_digest": profile_digest("core-package", {"id": "phase.core", "version": __version__, "capability": "effect_broker_v1"}),
}


class _OperationalFileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream = None

    def __enter__(self) -> "_OperationalFileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.path.open("a+b")
        if os.name == "nt":
            import msvcrt

            self._stream.seek(0)
            msvcrt.locking(self._stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *_exc: object) -> None:
        assert self._stream is not None
        if os.name == "nt":
            import msvcrt

            self._stream.seek(0)
            msvcrt.locking(self._stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
        self._stream.close()


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
    def _check_idempotency(
        store: EvidenceStore,
        key: str | None,
        scope_digest: str,
        request_digest: str,
        root_bindings: Mapping[str, Path],
        *,
        execute: bool,
    ) -> tuple[dict[str, Any], str] | None:
        if key is None:
            return None
        runs_root = store.evidence_root / ".phase" / "runs"
        for path in sorted(runs_root.glob("*/intent.json")):
            if path.parent == store.run_root:
                continue
            intent = parse_json_bytes(path.read_bytes())
            prior = intent.get("idempotency", {})
            if prior.get("key") == key and prior.get("scope_digest") == scope_digest and prior.get("request_digest") != request_digest:
                raise PhaseError("idempotency.same_key_conflict", key)
            if prior.get("key") == key and prior.get("scope_digest") == scope_digest and prior.get("request_digest") == request_digest:
                if not execute:
                    continue
                receipt_path = path.parent / "receipt.json"
                if not receipt_path.is_file():
                    if intent.get("execution_requested") is False:
                        continue
                    raise PhaseError("idempotency.prior_inspection_required", path.parent.name)
                receipt = parse_json_bytes(receipt_path.read_bytes())
                if receipt.get("terminal_status") == "validated_planned":
                    continue
                if receipt.get("terminal_status") != "succeeded_verified":
                    raise PhaseError("idempotency.prior_inspection_required", path.parent.name)
                if receipt.get("evidence", {}).get("finalization_status") != "finalized":
                    raise PhaseError("idempotency.prior_inspection_required", path.parent.name)
                try:
                    inspected = inspect_run(store.evidence_root, path.parent.name, root_bindings=root_bindings)
                except PhaseError as exc:
                    raise PhaseError("idempotency.prior_result_changed", str(exc)) from exc
                if inspected.get("target_verified") is not True:
                    raise PhaseError("idempotency.prior_result_changed", path.parent.name)
                return receipt, profile_digest("receipt", receipt)
        return None

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
        root_identity_digest: str,
        effect_plan_attachment_digest: str,
        content_blob_digests: list[str],
        execution_requested: bool,
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
            "idempotency": {
                "key": key,
                "scope_digest": scope_digest,
                "request_digest": request_digest,
                "root_identity_digest": root_identity_digest,
            },
            "effect_plan_digest": profile_digest("effect-plan", plan),
            "execution_requested": execution_requested,
            "evidence": {
                "effect_plan_attachment_digest": effect_plan_attachment_digest,
                "content_blob_digests": sorted(content_blob_digests),
            },
            "status": "intent_recorded",
        }

    @staticmethod
    def _publish_append_blobs(store: EvidenceStore, plan: dict[str, Any]) -> list[str]:
        blob_digests: list[str] = []
        for effect in plan["effects"]:
            if effect.get("content_blob_digest") is None:
                continue
            encoded = effect.get("content_bytes_b64")
            if not isinstance(encoded, str):
                raise PhaseError("plan.content_inline_missing", str(effect["effect_id"]))
            try:
                content = base64.b64decode(encoded.encode("ascii"), validate=True)
            except ValueError as exc:
                raise PhaseError("plan.content_inline_invalid", str(effect["effect_id"])) from exc
            digest = digest_bytes(content)
            if digest != effect["content_digest"] or len(content) != effect["content_length"]:
                raise PhaseError("plan.content_binding_mismatch", str(effect["effect_id"]))
            if effect.get("content_blob_digest") != digest:
                raise PhaseError("plan.content_blob_digest_mismatch", str(effect["effect_id"]))
            store.write_blob_exact(digest, content)
            blob_digests.append(digest)
        return blob_digests

    @staticmethod
    def _ordered_progress(plan: Mapping[str, Any], effect_receipts: list[dict[str, Any]]) -> dict[str, Any]:
        plan_digest = profile_digest("effect-plan", plan)
        receipt_by_id = {receipt["effect_id"]: receipt for receipt in effect_receipts}
        completed: list[str] = []
        verified: list[str] = []
        not_started: list[str] = []
        failed: str | None = None
        effects: list[dict[str, Any]] = []
        for index, effect in enumerate(plan["effects"]):
            effect_id = effect["effect_id"]
            receipt = receipt_by_id.get(effect_id)
            target = {
                "root_binding": effect["target"]["root_binding"],
                "relative_locator": effect["target"]["relative_locator"],
                "expected_digest": effect["content_digest"],
            }
            if receipt is None:
                not_started.append(effect_id)
                state = "not_started"
                observation_digest = None
                receipt_digest = None
            else:
                completed.append(effect_id)
                status = receipt["status"]
                observation_digest = profile_digest("effect-observation", {"effect_id": effect_id, "after": receipt["after"], "status": status})
                receipt_digest = profile_digest("effect-receipt", receipt)
                if status == "applied_verified":
                    verified.append(effect_id)
                    state = "verified_existing" if receipt.get("bytes_written") == 0 else "applied_new_verified"
                else:
                    state = status
                    failed = failed or effect_id
            effects.append({
                "ordinal": effect.get("ordinal", index),
                "effect_id": effect_id,
                "kind": effect["kind"],
                "mechanism": effect.get("mechanism", plan["mechanism"])["id"],
                "state": state,
                "target": target,
                "receipt_digest": receipt_digest if receipt is not None else None,
                "observation_digest": observation_digest,
            })
        return {
            "progress_version": "1.0",
            "plan_digest": plan_digest,
            "maximum_effects": len(plan["effects"]),
            "completed_effect_ids": completed,
            "verified_effect_ids": verified,
            "failed_effect_id": failed,
            "not_started_effect_ids": not_started,
            "effects": effects,
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

    def _reused_receipt(
        self,
        request: PhaseRequest,
        validator_results: list[dict[str, Any]],
        timestamp: str,
        prior_receipt: Mapping[str, Any],
        prior_receipt_digest: str,
    ) -> dict[str, Any]:
        reused_validators = validator_results or [
            dict(item) | {"run_id": request.run_id, "started_at": timestamp, "finished_at": timestamp}
            for item in prior_receipt["validator_results"]
        ]
        return self._base_receipt(request, reused_validators, timestamp) | {
            "terminal_status": "succeeded_verified",
            "execution_disposition": "reused_existing",
            "mutation_attempted": False,
            "result_state": "verified_result",
            "canonical_result": prior_receipt["canonical_result"],
            "effect_receipts": [],
            "evidence": {
                "finalization_status": "finalized",
                "intent_digest": None,
                "receipt_digest_policy_id": "digest.phase_canonical_json_v1",
                "required_attachments_present": True,
                "attachment_digests": [],
            },
            "retry_disposition": "noop_existing",
            "recovery_required": False,
            "blockers": [],
            "exit_code": 0,
            "prior_verified_receipt_digest": prior_receipt_digest,
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
            "terminal_status": "rejected",
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
        result = {
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
        appended = {
            "operation_identity": observation.get("operation_identity"),
            "request_digest": observation.get("request_digest"),
            "record_identity": observation.get("record_identity"),
            "append_offset": observation.get("append_offset"),
            "record_digest": observation.get("record_digest"),
            "record_length": observation.get("record_length"),
            "resulting_head": observation.get("resulting_head"),
        }
        if all(value is not None for value in appended.values()):
            result["appended_record"] = appended
        return result

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
        result_effect = plan["effects"][-1]
        failed_receipts = [receipt for receipt in effect_receipts if receipt["status"] != "applied_verified"]
        status = failed_receipts[0]["status"] if failed_receipts else ("applied_verified" if len(effect_receipts) == len(plan["effects"]) else "failed_no_effect")
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
        all_effects_verified = status == "applied_verified" and len(effect_receipts) == len(plan["effects"])
        if all_effects_verified and post_verified and not finalization_failed:
            terminal, result_state, exit_code, recovery = "succeeded_verified", "verified_result", 0, False
        elif all_effects_verified:
            terminal, result_state, exit_code, recovery = "committed_unverified", "committed_unverified", 40, True
        else:
            if any(receipt["status"] == "failed_partial" for receipt in effect_receipts):
                terminal, result_state, exit_code, recovery = mapping["failed_partial"]
            elif failed_receipts:
                terminal, result_state, exit_code, recovery = mapping[status]
                if len(effect_receipts) > 1 and any(receipt["after"].get("exists") is True for receipt in effect_receipts[:-1]):
                    terminal, result_state, exit_code, recovery = "failed_partial", "known_partial", 30, True
            elif effect_receipts and any(receipt["status"] == "applied_verified" for receipt in effect_receipts):
                terminal, result_state, exit_code, recovery = "failed_partial", "known_partial", 30, True
            else:
                terminal, result_state, exit_code, recovery = "failed_no_effect", "verified_no_effect", 20, False
        error = failed_receipts[0].get("error") if failed_receipts else None
        blockers = [] if terminal == "succeeded_verified" else [
            "evidence.finalization_failed" if finalization_failed else (error["code"] if error else "verification.incomplete")
        ]
        return self._base_receipt(request, validator_results, timestamp) | {
            "terminal_status": terminal,
            "execution_disposition": "executed",
            "mutation_attempted": any(bool(receipt["attempted"]) for receipt in effect_receipts),
            "result_state": result_state,
            "canonical_result": (
                self._canonical_result(
                    contract,
                    result_effect,
                    dict(effect_receipts[-1]["after"]) | {
                        "operation_identity": effect_receipts[-1].get("operation_identity"),
                        "request_digest": effect_receipts[-1].get("request_digest"),
                        "record_identity": effect_receipts[-1].get("record_identity"),
                        "append_offset": effect_receipts[-1].get("append_offset"),
                        "record_digest": effect_receipts[-1].get("record_digest"),
                        "record_length": effect_receipts[-1].get("record_length"),
                        "resulting_head": effect_receipts[-1].get("resulting_head"),
                    },
                    timestamp,
                )
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
        progress_digest: str | None = None
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
            scope_digest, request_digest, key, root_identity_digest = build_idempotency_digests(contract, candidate, frozen, request.root_bindings)
            idempotency_lock = None
            if key is not None:
                lock_digest = profile_digest("idempotency-lock", {"key": key, "scope_digest": scope_digest})
                idempotency_lock = _OperationalFileLock(operational_lock_path(store.operational_lock_root / "idempotency", lock_digest))
            if idempotency_lock is None:
                return self._run_after_idempotency_binding(
                    request,
                    store,
                    contract,
                    candidate,
                    frozen,
                    validator_results,
                    lifecycle,
                    timestamp,
                    scope_digest,
                    request_digest,
                    key,
                    root_identity_digest,
                    execute,
                    active_faults,
                )
            with idempotency_lock:
                return self._run_after_idempotency_binding(
                    request,
                    store,
                    contract,
                    candidate,
                    frozen,
                    validator_results,
                    lifecycle,
                    timestamp,
                    scope_digest,
                    request_digest,
                    key,
                    root_identity_digest,
                    execute,
                    active_faults,
                )
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

    def _run_after_idempotency_binding(
        self,
        request: PhaseRequest,
        store: EvidenceStore,
        contract: ResolvedContract,
        candidate: CapturedCandidate,
        frozen: Mapping[str, FrozenInput],
        validator_results: list[dict[str, Any]],
        lifecycle: list[str],
        timestamp: str,
        scope_digest: str,
        request_digest: str,
        key: str | None,
        root_identity_digest: str,
        execute: bool,
        active_faults: CoreFaults,
    ) -> PhaseOutcome:
        plan: dict[str, Any] | None = None
        intent: dict[str, Any] | None = None
        effect_receipts: list[dict[str, Any]] = []
        final_validators_published = False
        plan_digest: str | None = None
        attachment_digests: list[str] = []
        progress_digest: str | None = None
        latest_progress: dict[str, Any] | None = None
        runner = ValidatorRunner(self.registry)
        try:
            reused = self._check_idempotency(store, key, scope_digest, request_digest, request.root_bindings, execute=execute)
            if execute and reused is not None:
                receipt = self._reused_receipt(request, [], timestamp, reused[0], reused[1])
                validate_receipt(receipt, self.registry)
                lifecycle.append("receipt")
                store.write_canonical("receipt.json", receipt)
                return PhaseOutcome(request.run_id, receipt["exit_code"], receipt, None, None, tuple(lifecycle), profile_digest("receipt", receipt), None)
            lifecycle.append("validate")
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
                request_digest=request_digest,
            )
            validate_static_plan(plan, contract, request.root_bindings, self.registry)
            content_blob_digests = self._publish_append_blobs(store, plan)
            _, plan_attachment_digest = store.write_canonical("attachments/effect-plan.json", plan)
            attachment_digests.append(plan_attachment_digest)
            plan_digest = profile_digest("effect-plan", plan)
            validator_name = "attachments/pre-validator-results.json" if execute else "attachments/validator-results.json"
            _, validators_digest = store.write_canonical(validator_name, validator_results)
            attachment_digests.append(validators_digest)
            intent = self._intent(
                request,
                contract,
                candidate,
                frozen,
                plan,
                timestamp,
                scope_digest,
                request_digest,
                key,
                root_identity_digest,
                plan_attachment_digest,
                content_blob_digests,
                execute,
            )
            validate_intent(intent, self.registry)
            lifecycle.append("intent")
            intent_path, _ = store.write_canonical("intent.json", intent)
            intent_digest = profile_digest("intent", intent)
            if not execute:
                receipt = self._planned_receipt(request, validator_results, timestamp, intent_digest, attachment_digests)
            else:
                def record_progress(receipts: list[dict[str, object]]) -> None:
                    nonlocal progress_digest, latest_progress
                    if len(plan["effects"]) <= 1:
                        return
                    progress = self._ordered_progress(plan, receipts)  # type: ignore[arg-type]
                    _, digest = store.replace_attachment_canonical("ordered-effect-progress.json", progress)
                    progress_digest = digest
                    latest_progress = progress

                record_progress([])
                lifecycle.append("broker")
                effect_receipts = EffectBroker(self.registry).execute(
                    plan,
                    contract,
                    frozen,
                    request.root_bindings,
                    intent_path,
                    store.operational_lock_root,
                    timestamp=timestamp,
                    faults=active_faults.broker,
                    progress_callback=record_progress,
                    receipt_sink=effect_receipts,
                )
                lifecycle.append("effect")
                _, effects_digest = store.write_canonical("attachments/effect-receipts.json", effect_receipts)
                attachment_digests.append(effects_digest)
                if progress_digest is not None:
                    attachment_digests.append(progress_digest)
                lifecycle.append("verify")
                validator_results = runner.run_post_operation(
                    contract,
                    validator_results,
                    plan,
                    request.root_bindings,
                    run_id=request.run_id,
                    timestamp=timestamp,
                    effect_receipts=effect_receipts,
                    ordered_progress=latest_progress,
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
                incomplete_ordered_prefix = len(effect_receipts) < len(plan["effects"])
                if incomplete_ordered_prefix:
                    try:
                        _, effects_digest = store.write_canonical("attachments/effect-receipts.json", effect_receipts)
                        attachment_digests.append(effects_digest)
                    except (PhaseError, OSError):
                        pass
                    if len(plan["effects"]) > 1:
                        latest_progress = self._ordered_progress(plan, effect_receipts)
                        try:
                            _, progress_digest = store.replace_attachment_canonical("ordered-effect-progress.json", latest_progress)
                            attachment_digests.append(progress_digest)
                        except (PhaseError, OSError):
                            pass
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
                    required_attachments_present=False if incomplete_ordered_prefix else final_validators_published,
                )
                validate_receipt(receipt, self.registry)
                if not lifecycle or lifecycle[-1] != "receipt":
                    lifecycle.append("receipt")
                receipt_digest = None
                if incomplete_ordered_prefix:
                    try:
                        store.write_canonical("receipt.json", receipt)
                        receipt_digest = profile_digest("receipt", receipt)
                    except (PhaseError, OSError):
                        pass
                return PhaseOutcome(
                    request.run_id,
                    receipt["exit_code"],
                    receipt,
                    intent,
                    plan,
                    tuple(lifecycle),
                    receipt_digest,
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
