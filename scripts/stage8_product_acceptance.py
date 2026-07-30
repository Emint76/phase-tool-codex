from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

NOW = "2026-07-30T12:00:00Z"
SOURCE = "source_admission.v1@1.0.0"
KNOWLEDGE = "knowledge_admission.v1@1.0.0"


def digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def source_candidate(payload: bytes) -> dict[str, Any]:
    return {
        "candidate_version": "1.0",
        "contract": {"id": "source_admission.v1", "version": "1.0.0"},
        "operation_id": "stage8-source-operation",
        "idempotency_key": "stage8-source-operation",
        "logical_source_id": "stage8-source",
        "asset_input": {"binding_id": "asset", "expected_digest": digest(payload), "expected_length": len(payload)},
        "declared_media_type": "text/plain",
        "original_filename": "stage8-source.txt",
        "provenance": {
            "provenance_version": "1.0",
            "origin": {"kind": "external_uri", "locator": "https://example.invalid/stage8-source", "label": "Stage 8 acceptance source"},
            "supplied_by": {"kind": "adapter", "identifier": "adapter.stage8.acceptance"},
        },
        "placement": {"target_root_binding": "admission_result_root", "namespace": "acceptance"},
        "supersedes": None,
        "request_metadata": {"submitted_by": "adapter.stage8.acceptance", "correlation_id": "stage8-source-operation"},
    }


def knowledge_candidate(artifact: bytes, source_binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_version": "1.0",
        "contract": {"id": "knowledge_admission.v1", "version": "1.0.0"},
        "operation_id": "stage8-knowledge-operation",
        "idempotency_key": "stage8-knowledge-operation",
        "logical_knowledge_id": "stage8-knowledge",
        "artifact_input": {"binding_id": "asset", "expected_digest": digest(artifact), "expected_length": len(artifact)},
        "artifact_kind": "document",
        "artifact_format": "application/json",
        "provenance": {
            "provenance_version": "1.0",
            "source_bindings": [source_binding],
            "producer": {"kind": "tool", "identifier": "producer.stage8.acceptance", "version": "1.0.0"},
            "transformation": {
                "identifier": "transform.stage8.acceptance",
                "version": "1.0.0",
                "parameters_digest": digest(b"stage8-parameters"),
            },
        },
        "placement": {"target_root_binding": "admission_result_root", "namespace": "acceptance"},
        "supersedes": None,
        "request_metadata": {"submitted_by": "adapter.stage8.acceptance", "correlation_id": "stage8-knowledge-operation"},
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def cli(phase: Path, operation: str, *, contract: str | None = None, candidate: Path | None = None,
        evidence: Path, run_id: str, payload: Path | None = None, target: Path) -> dict[str, Any]:
    command = [str(phase), operation]
    if contract is not None:
        command += ["--contract", contract, "--candidate", str(candidate), "--input", f"asset={payload}", "--timestamp", NOW]
    command += ["--evidence-root", str(evidence), "--run-id", run_id, "--root", f"admission_result_root={target}"]
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(command, capture_output=True, text=True, env=environment, check=False)
    if completed.returncode != 0:
        raise AssertionError(f"CLI failed: {command!r} rc={completed.returncode} stdout={completed.stdout!r} stderr={completed.stderr!r}")
    if completed.stderr:
        raise AssertionError(f"CLI stderr is not clean: {completed.stderr!r}")
    return json.loads(completed.stdout)


def tool_payload(result: object) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    return json.loads(getattr(result, "content")[0].text)


async def mcp_call(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "phase_tool.mcp_server"], env=environment)
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments)
            if result.isError:
                raise AssertionError(f"MCP tool failed: {result}")
            return tool_payload(result)


def receipt(evidence: Path, run_id: str) -> dict[str, Any]:
    return json.loads((evidence / ".phase" / "runs" / run_id / "receipt.json").read_text(encoding="utf-8"))


def descriptor(target: Path, reference: dict[str, Any]) -> tuple[dict[str, Any], bytes]:
    raw = target.joinpath(*reference["locator"].split("/")).read_bytes()
    return json.loads(raw), raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tmp-root", type=Path, required=True)
    parser.add_argument("--phase", type=Path)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    allowed = (repository / ".stage8-tmp").resolve()
    root = args.tmp_root.resolve()
    if root == allowed or allowed not in root.parents:
        raise AssertionError("--tmp-root must be a child of repository .stage8-tmp")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    phase = args.phase or repository / ".venv" / "Scripts" / ("phase.exe" if os.name == "nt" else "phase")

    target = root / "target"
    target.mkdir()
    evidence = root / "evidence"
    payloads = root / "payloads"
    candidates = root / "candidates"

    source_bytes = b"Stage 8 universal source payload\n"
    source_path = payloads / "source.txt"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(source_bytes)
    source_value = source_candidate(source_bytes)
    source_candidate_path = candidates / "source.json"
    write_json(source_candidate_path, source_value)

    cli_source = cli(phase, "execute", contract=SOURCE, candidate=source_candidate_path, evidence=evidence,
                     run_id="source-cli", payload=source_path, target=target)
    cli_source_inspect = cli(phase, "inspect", evidence=evidence, run_id="source-cli", target=target)
    mcp_source = asyncio.run(mcp_call("phase_execute", {
        "contract_binding": SOURCE,
        "candidate": source_value,
        "evidence_root": str(evidence),
        "run_id": "source-mcp",
        "input_paths": {"asset": str(source_path)},
        "root_bindings": {"admission_result_root": str(target)},
        "timestamp": NOW,
    }))
    mcp_source_inspect = asyncio.run(mcp_call("phase_inspect", {
        "evidence_root": str(evidence), "run_id": "source-mcp",
        "root_bindings": {"admission_result_root": str(target)},
    }))

    source_receipt = receipt(evidence, "source-cli")
    source_descriptor, source_descriptor_bytes = descriptor(target, source_receipt["canonical_result"])
    source_binding = {
        "binding_version": "1.0",
        "source_result_id": source_descriptor["source_result_id"],
        "logical_source_id": source_descriptor["logical_source_id"],
        "source_content_digest": source_descriptor["content_digest"],
        "source_blob_locator": source_descriptor["blob_locator"],
        "source_descriptor_digest": digest(source_descriptor_bytes),
        "source_descriptor_locator": source_descriptor["descriptor_locator"],
        "source_contract": {"id": "source_admission.v1", "version": "1.0.0"},
        "source_phase_receipt": {"run_id": "source-cli", "receipt_digest": cli_source["receipt_digest"]},
    }

    artifact = b'{"stage":8,"surface":"universal"}\n'
    artifact_path = payloads / "knowledge.json"
    artifact_path.write_bytes(artifact)
    knowledge_value = knowledge_candidate(artifact, source_binding)
    knowledge_candidate_path = candidates / "knowledge.json"
    write_json(knowledge_candidate_path, knowledge_value)

    cli_knowledge = cli(phase, "execute", contract=KNOWLEDGE, candidate=knowledge_candidate_path, evidence=evidence,
                        run_id="knowledge-cli", payload=artifact_path, target=target)
    cli_knowledge_inspect = cli(phase, "inspect", evidence=evidence, run_id="knowledge-cli", target=target)
    mcp_knowledge = asyncio.run(mcp_call("phase_execute", {
        "contract_binding": KNOWLEDGE,
        "candidate": knowledge_value,
        "evidence_root": str(evidence),
        "run_id": "knowledge-mcp",
        "input_paths": {"asset": str(artifact_path)},
        "root_bindings": {"admission_result_root": str(target)},
        "timestamp": NOW,
    }))
    mcp_knowledge_inspect = asyncio.run(mcp_call("phase_inspect", {
        "evidence_root": str(evidence), "run_id": "knowledge-mcp",
        "root_bindings": {"admission_result_root": str(target)},
    }))

    source_mcp_receipt = receipt(evidence, "source-mcp")
    knowledge_cli_receipt = receipt(evidence, "knowledge-cli")
    knowledge_mcp_receipt = receipt(evidence, "knowledge-mcp")
    source_mcp_descriptor, _ = descriptor(target, source_mcp_receipt["canonical_result"])
    knowledge_descriptor, _ = descriptor(target, knowledge_cli_receipt["canonical_result"])
    knowledge_mcp_descriptor, _ = descriptor(target, knowledge_mcp_receipt["canonical_result"])
    equivalence = {
        "source_result_id": source_descriptor["source_result_id"] == source_mcp_descriptor["source_result_id"],
        "knowledge_result_id": knowledge_descriptor["knowledge_result_id"] == knowledge_mcp_descriptor["knowledge_result_id"],
        "canonical_artifact_digest": knowledge_descriptor["artifact_digest"] == digest(artifact),
        "receipt_semantics": all(item["terminal_status"] == "succeeded_verified" for item in (source_receipt, source_mcp_receipt, knowledge_cli_receipt, knowledge_mcp_receipt)),
        "inspection_semantics": all(item["target_verified"] is True for item in (cli_source_inspect, mcp_source_inspect, cli_knowledge_inspect, mcp_knowledge_inspect)),
    }
    summary = {
        "success": all(equivalence.values()),
        "scenario_count": 8,
        "cli": {"source": cli_source, "source_inspect": cli_source_inspect, "knowledge": cli_knowledge, "knowledge_inspect": cli_knowledge_inspect},
        "mcp": {"source": mcp_source, "source_inspect": mcp_source_inspect, "knowledge": mcp_knowledge, "knowledge_inspect": mcp_knowledge_inspect},
        "equivalence": equivalence,
        "identities": {
            "source_result_id": source_descriptor["source_result_id"],
            "knowledge_result_id": knowledge_descriptor["knowledge_result_id"],
            "artifact_digest": knowledge_descriptor["artifact_digest"],
        },
    }
    write_json(root / "stage8-product-acceptance-summary.json", summary)
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
