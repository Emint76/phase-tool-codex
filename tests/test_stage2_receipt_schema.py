from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def schema_registry() -> Registry:
    registry = Registry()
    for path in (ROOT / "schemas").glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return registry


def planned_receipt(intent_digest: str | None = "sha256:" + "1" * 64) -> dict:
    return {
        "phase_receipt_version": "1.0",
        "run_id": "stage2-run-001",
        "contract": {"id": "fixture_append.v1", "version": "1.0.0", "package_digest": "sha256:" + "2" * 64},
        "core": {"id": "phase.core", "version": "1.0.0", "package_digest": "sha256:" + "3" * 64},
        "started_at": "2026-07-27T00:00:00Z",
        "finished_at": "2026-07-27T00:00:01Z",
        "terminal_status": "validated_planned",
        "execution_disposition": "not_executed",
        "mutation_attempted": False,
        "result_state": "planned_no_effect",
        "canonical_result": None,
        "validator_results": [load("fixtures/golden/validator-result.valid.json") | {"run_id": "stage2-run-001"}],
        "effect_receipts": [],
        "evidence": {
            "finalization_status": "finalized",
            "intent_digest": intent_digest,
            "receipt_digest_policy_id": "digest.phase_canonical_json_v1",
            "required_attachments_present": True,
            "attachment_digests": ["sha256:" + "4" * 64],
        },
        "retry_disposition": "safe_idempotent_retry",
        "prior_verified_receipt_digest": None,
        "recovery_required": False,
        "blockers": [],
        "exit_code": 0,
    }


def test_validation_only_receipt_is_schema_valid() -> None:
    schema = load("schemas/phase-receipt.schema.json")
    Draft202012Validator(schema, registry=schema_registry(), format_checker=FormatChecker()).validate(planned_receipt())


def test_early_rejection_can_truthfully_have_no_intent() -> None:
    receipt = planned_receipt(intent_digest=None)
    receipt.update(
        terminal_status="rejected",
        result_state="none",
        validator_results=[],
        evidence=receipt["evidence"] | {"finalization_status": "finalized", "required_attachments_present": False, "attachment_digests": []},
        retry_disposition="forbidden",
        blockers=["registry.entry_not_found"],
        exit_code=10,
    )
    schema = load("schemas/phase-receipt.schema.json")
    Draft202012Validator(schema, registry=schema_registry(), format_checker=FormatChecker()).validate(receipt)
