from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "integrations" / "hermes" / "skills"


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, SKILLS / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


router = load("phase_mutation_router", "phase-mutation-router/scripts/route_mutation.py")
preparation = load("phase_mutation_preparation", "phase-mutation-preparation/scripts/prepare_phase_mutation.py")
verified = load("phase_verified_execution", "phase-verified-execution/scripts/run_phase_verified.py")


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize(
    ("kind", "exists", "binding"),
    [
        ("create", False, "file_create.v1@1.0.0"),
        ("publish_new_version", True, "publish_new_version.v1@1.0.0"),
        ("append", False, "append_stream.v1@1.0.0"),
        ("content_addressed_publish", False, "content_addressed_publish.v1@1.0.0"),
        ("source_admission", False, "source_admission.v1@1.0.0"),
        ("knowledge_admission", False, "knowledge_admission.v1@1.0.0"),
    ],
)
def test_semantic_router_selects_exact_contract(kind: str, exists: bool, binding: str) -> None:
    decision = router.route_mutation({"mutation_kind": kind, "stable_path_exists": exists})
    assert decision["contract_binding"] == binding
    assert decision["contract_digest"].startswith("sha256:")
    assert len(decision["contract_digest"]) == 71
    assert decision["transport"] == "mcp"
    assert decision["direct_write_allowed"] is False


def test_existing_stable_path_cannot_route_to_create() -> None:
    with pytest.raises(router.RoutingError):
        router.route_mutation({"mutation_kind": "create", "stable_path_exists": True})


def test_unsupported_mutation_fails_closed() -> None:
    with pytest.raises(router.RoutingError, match="unsupported"):
        router.route_mutation({"mutation_kind": "overwrite", "stable_path_exists": True})


@pytest.mark.parametrize("locator", ["/absolute.md", "../escape.md", "a/../b.md", "a\\b.md", "C:/drive.md", "docs/CON.txt", ""])
def test_malformed_locator_is_blocked(tmp_path: Path, locator: str) -> None:
    target = tmp_path / "target"
    target.mkdir()
    with pytest.raises(preparation.PreparationError):
        preparation.prepare_mutation(
            {"mutation_kind": "create", "target_locator": locator, "content_text": "x"},
            canonical_root=target,
            preparation_root=tmp_path / "prep",
            evidence_root=tmp_path / "evidence",
        )


def test_create_preparation_is_outside_target_and_does_not_mutate_it(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    canary = target / "canary.bin"
    canary.write_bytes(b"unchanged")
    before = [(p.relative_to(target).as_posix(), p.read_bytes()) for p in target.rglob("*") if p.is_file()]

    request = preparation.prepare_mutation(
        {"mutation_kind": "create", "target_locator": "docs/item.md", "content_text": "# one\n", "operation_id": "create-doc"},
        canonical_root=target,
        preparation_root=tmp_path / "prep",
        evidence_root=tmp_path / "evidence",
    )

    after = [(p.relative_to(target).as_posix(), p.read_bytes()) for p in target.rglob("*") if p.is_file()]
    assert after == before
    assert Path(request["input_paths"]["payload"]).read_bytes() == b"# one\n"
    assert request["candidate"]["target_locator"] == "docs/item.md"
    assert request["payload_digest"] == sha(b"# one\n")
    assert request["payload_length"] == 6
    assert Path(request["prepared_request_path"]).is_relative_to(tmp_path / "prep")
    assert not Path(request["prepared_request_path"]).is_relative_to(target)
    assert not Path(request["evidence_root"]).is_relative_to(target)


def test_publish_preparation_hashes_current_without_writing_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    current = target / "docs" / "item.md"
    current.parent.mkdir(parents=True)
    current.write_bytes(b"old\x00bytes")
    before = current.read_bytes()

    request = preparation.prepare_mutation(
        {"mutation_kind": "publish_new_version", "target_locator": "docs/item.md", "content_text": "new\n"},
        canonical_root=target,
        preparation_root=tmp_path / "prep",
        evidence_root=tmp_path / "evidence",
    )

    assert current.read_bytes() == before
    assert request["contract_binding"] == "publish_new_version.v1@1.0.0"
    assert request["candidate"]["expected_current_digest"] == sha(before)
    assert Path(request["input_paths"]["payload"]).read_bytes() == b"new\n"


def test_preparation_and_evidence_must_be_disjoint_from_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    for prep, evidence in ((target / "prep", tmp_path / "e"), (tmp_path / "p", target / "evidence")):
        with pytest.raises(preparation.PreparationError, match="outside canonical"):
            preparation.prepare_mutation(
                {"mutation_kind": "create", "target_locator": "x.md", "content_text": "x"},
                canonical_root=target,
                preparation_root=prep,
                evidence_root=evidence,
            )


def test_dedicated_instance_parent_layout_needs_no_phase_core_change(tmp_path: Path) -> None:
    instance_parent = tmp_path / "instance"
    toolkit = instance_parent / "toolkit"
    toolkit.mkdir(parents=True)
    preparation_root = tmp_path / "external-preparation"
    evidence_root = tmp_path / "external-evidence"

    request = preparation.prepare_mutation(
        {
            "mutation_kind": "create",
            "target_locator": "toolkit/docs/item.md",
            "content_text": "portable\n",
            "operation_id": "create-portable-doc",
        },
        canonical_root=instance_parent,
        preparation_root=preparation_root,
        evidence_root=evidence_root,
    )

    assert request["candidate"]["target_locator"] == "toolkit/docs/item.md"
    assert request["root_bindings"] == {"phase_result_root": str(instance_parent.resolve())}
    assert Path(request["prepared_request_path"]).is_relative_to(preparation_root)
    assert Path(request["evidence_root"]).is_relative_to(evidence_root)
    assert not preparation_root.resolve().is_relative_to(instance_parent.resolve())
    assert not evidence_root.resolve().is_relative_to(instance_parent.resolve())
    assert not preparation_root.resolve().is_relative_to(evidence_root.resolve())
    assert not evidence_root.resolve().is_relative_to(preparation_root.resolve())
    assert not (toolkit / "docs" / "item.md").exists()


def test_append_preparation_never_direct_writes_stream(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    request = preparation.prepare_mutation(
        {"mutation_kind": "append", "target_locator": "streams/a.jsonl", "stream_id": "a", "record_id": "r1", "record": {"x": 1}, "expected_head": None},
        canonical_root=target,
        preparation_root=tmp_path / "prep",
        evidence_root=tmp_path / "evidence",
    )
    assert request["contract_binding"] == "append_stream.v1@1.0.0"
    assert not (target / "streams" / "a.jsonl").exists()
    assert request["input_paths"] == {}


def test_append_preparation_rejects_locator_not_derived_from_stream_id(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    with pytest.raises(preparation.PreparationError, match="contract-derived locator"):
        preparation.prepare_mutation(
            {"mutation_kind": "append", "target_locator": "logs/a.jsonl", "stream_id": "a", "record_id": "r1", "record": {"x": 1}, "expected_head": None},
            canonical_root=target,
            preparation_root=tmp_path / "prep",
            evidence_root=tmp_path / "evidence",
        )


def test_default_identity_binds_exact_payload_bytes(tmp_path: Path) -> None:
    first_target = tmp_path / "first-target"
    second_target = tmp_path / "second-target"
    first_target.mkdir()
    second_target.mkdir()
    first = preparation.prepare_mutation(
        {"mutation_kind": "create", "target_locator": "same.md", "content_text": "first"},
        canonical_root=first_target,
        preparation_root=tmp_path / "first-prep",
        evidence_root=tmp_path / "first-evidence",
    )
    second = preparation.prepare_mutation(
        {"mutation_kind": "create", "target_locator": "same.md", "content_text": "second"},
        canonical_root=second_target,
        preparation_root=tmp_path / "second-prep",
        evidence_root=tmp_path / "second-evidence",
    )
    assert first["payload_digest"] != second["payload_digest"]
    assert first["candidate"]["idempotency_key"] != second["candidate"]["idempotency_key"]
    assert first["run_id"] != second["run_id"]


def test_default_identity_depends_on_bytes_not_source_path(tmp_path: Path) -> None:
    first_target = tmp_path / "first-target"
    second_target = tmp_path / "second-target"
    first_target.mkdir()
    second_target.mkdir()
    first_source = tmp_path / "first.bin"
    second_source = tmp_path / "second.bin"
    first_source.write_bytes(b"exact\x00bytes")
    second_source.write_bytes(b"exact\x00bytes")
    first = preparation.prepare_mutation(
        {"mutation_kind": "create", "target_locator": "same.bin", "content_path": str(first_source)},
        canonical_root=first_target,
        preparation_root=tmp_path / "first-prep",
        evidence_root=tmp_path / "first-evidence",
    )
    second = preparation.prepare_mutation(
        {"mutation_kind": "create", "target_locator": "same.bin", "content_path": str(second_source)},
        canonical_root=second_target,
        preparation_root=tmp_path / "second-prep",
        evidence_root=tmp_path / "second-evidence",
    )
    assert first["candidate"]["idempotency_key"] == second["candidate"]["idempotency_key"]
    assert first["run_id"] == second["run_id"]


def test_preparation_outputs_complete_exclusive_request(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    prep_root = tmp_path / "prep"
    intent = {"mutation_kind": "create", "target_locator": "item.md", "content_text": "exact"}
    request = preparation.prepare_mutation(
        intent,
        canonical_root=target,
        preparation_root=prep_root,
        evidence_root=tmp_path / "evidence",
    )
    persisted = json.loads(Path(request["prepared_request_path"]).read_text(encoding="utf-8"))
    route = router.route_mutation({"mutation_kind": "create", "stable_path_exists": False})
    assert persisted["contract_digest"] == route["contract_digest"]
    assert persisted["candidate_path"] == request["candidate_path"]
    assert persisted["expected_input_digests"] == {"payload": request["payload_digest"]}
    assert Path(request["candidate_path"]).parent.name.startswith("request-")
    with pytest.raises(preparation.PreparationError, match="already exists"):
        preparation.prepare_mutation(
            intent,
            canonical_root=target,
            preparation_root=prep_root,
            evidence_root=tmp_path / "evidence",
        )


def test_preparation_blocks_request_directory_substitution_before_leaf_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "target"
    target.mkdir()
    original = preparation._write_exclusive
    attacked = False

    def substitute_parent(path: Path, data: bytes) -> None:
        nonlocal attacked
        if not attacked:
            attacked = True
            path.parent.rmdir()
            if os.name == "nt":
                completed = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(path.parent), str(target)],
                    capture_output=True,
                    check=False,
                )
                assert completed.returncode == 0, completed.stderr
            else:
                path.parent.symlink_to(target, target_is_directory=True)
        original(path, data)

    monkeypatch.setattr(preparation, "_write_exclusive", substitute_parent)
    with pytest.raises((OSError, preparation.PreparationError)):
        preparation.prepare_mutation(
            {"mutation_kind": "create", "target_locator": "item.md", "content_text": "exact"},
            canonical_root=target,
            preparation_root=tmp_path / "prep",
            evidence_root=tmp_path / "evidence",
        )
    assert not (target / "candidate.json").exists()


class FakeTransport:
    def __init__(self, *, inspect_verified: bool = True) -> None:
        self.calls: list[str] = []
        self.inspect_verified = inspect_verified

    def execute(self, request):
        self.calls.append("execute")
        return verified.CommandResult(0, {"success": True, "run_id": request.run_id, "terminal_status": "succeeded_verified", "execution_disposition": "executed", "receipt_digest": "sha256:" + "1" * 64}, "")

    def inspect(self, request):
        self.calls.append("inspect")
        return verified.CommandResult(0, {"success": True, "run_id": request.run_id, "terminal_status": "succeeded_verified", "execution_disposition": "executed", "receipt_digest": "sha256:" + "1" * 64, "target_verified": self.inspect_verified}, "")


def phase_request() -> object:
    return verified.PhaseRequest("file_create.v1@1.0.0", "sha256:" + "2" * 64, "candidate.json", "evidence", "run-1", (), ("phase_result_root=target",))


def test_verified_execution_always_executes_then_inspects() -> None:
    transport = FakeTransport()
    result = verified.run_verified(transport, phase_request())
    assert transport.calls == ["execute", "inspect"]
    assert result["inspect_status"] == {"success": True, "target_verified": True}


def test_unverified_inspect_is_never_success() -> None:
    transport = FakeTransport(inspect_verified=False)
    with pytest.raises(verified.VerificationError):
        verified.run_verified(transport, phase_request())
    assert transport.calls == ["execute", "inspect"]


def test_verified_execution_rejects_changed_prepared_input_before_execute(tmp_path: Path) -> None:
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"changed")
    transport = FakeTransport()
    request = verified.PhaseRequest(
        "file_create.v1@1.0.0",
        "sha256:" + "2" * 64,
        "candidate.json",
        "evidence",
        "run-1",
        (f"payload={payload}",),
        ("phase_result_root=target",),
        ("payload=sha256:" + "0" * 64,),
    )
    with pytest.raises(verified.VerificationError, match="changed after preparation"):
        verified.run_verified(transport, request)
    assert transport.calls == []


def test_verified_execution_requires_digest_for_every_prepared_input(tmp_path: Path) -> None:
    payload = tmp_path / "payload.bin"
    payload.write_bytes(b"unbound")
    transport = FakeTransport()
    request = verified.PhaseRequest(
        "file_create.v1@1.0.0",
        "sha256:" + "2" * 64,
        "candidate.json",
        "evidence",
        "run-1",
        (f"payload={payload}",),
        ("phase_result_root=target",),
        (),
    )
    with pytest.raises(verified.VerificationError, match="digest bindings must exactly match input bindings"):
        verified.run_verified(transport, request)
    assert transport.calls == []


def test_direct_mcp_procedure_rehashes_inputs_immediately_before_inspect() -> None:
    skill = (SKILLS / "phase-verified-execution" / "SKILL.md").read_text(encoding="utf-8")
    assert "Immediately before `phase_inspect`, hash every named input again" in skill


def test_primary_transport_policy_is_mcp() -> None:
    source = (SKILLS / "phase-mutation-router" / "scripts" / "route_mutation.py").read_text(encoding="utf-8")
    assert '"transport": "mcp"' in source
    skill = (SKILLS / "phase-mutation-router" / "SKILL.md").read_text(encoding="utf-8")
    assert "CLI fallback" in skill
    assert "only when MCP" in skill


def test_registry_exposes_production_neutral_contracts() -> None:
    from phase_tool.registry import BundledRegistry
    bindings = BundledRegistry.load().contract_bindings()
    assert {
        "file_create.v1@1.0.0",
        "append_stream.v1@1.0.0",
        "content_addressed_publish.v1@1.0.0",
    }.issubset(bindings)
    for name in ("file_create.v1@1.0.0", "append_stream.v1@1.0.0", "content_addressed_publish.v1@1.0.0"):
        binding = bindings[name]
        contract = BundledRegistry.load().resolve_contract(binding["id"], binding["version"], binding["package_digest"], core_version="1.0.0")
        assert contract.document["canonical_result"]["root_binding"] == "phase_result_root"
        assert "fixture://" not in contract.document["candidate"]["schema_ref"]
        assert contract.document["evidence"]["retention_policy_id"] != "retention.fixture_v1"
