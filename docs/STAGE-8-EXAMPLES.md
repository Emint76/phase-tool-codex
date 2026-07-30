# Stage 8 Universal Examples

Both admissions use the same CLI verb and the same MCP tool. Candidate schema details are discoverable with `phase contracts describe` and are not duplicated in adapters.

## Source Admission

Prepare `source.json` according to the installed `source_admission.v1@1.0.0` candidate schema and bind its asset:

```console
phase contracts describe --contract source_admission.v1@1.0.0
phase validate --contract source_admission.v1@1.0.0 --candidate source.json --input asset=source.txt --root admission_result_root=./results --evidence-root ./evidence --run-id source-validate
phase execute --contract source_admission.v1@1.0.0 --candidate source.json --input asset=source.txt --root admission_result_root=./results --evidence-root ./evidence --run-id source-execute
phase inspect --evidence-root ./evidence --run-id source-execute --root admission_result_root=./results
```

The MCP equivalent calls the universal tool:

```json
{
  "tool": "phase_execute",
  "arguments": {
    "contract_binding": "source_admission.v1@1.0.0",
    "candidate": {"candidate_version": "1.0"},
    "input_paths": {"asset": "source.txt"},
    "root_bindings": {"admission_result_root": "results"},
    "evidence_root": "evidence",
    "run_id": "source-execute"
  }
}
```

The abbreviated candidate above illustrates transport shape only; obtain all required fields from `phase_contract_describe` or `phase contracts describe`.

## Knowledge Admission

Knowledge provenance binds an already verified Source result and its Phase receipt. Use the exact installed contract:

```console
phase contracts describe --contract knowledge_admission.v1@1.0.0
phase plan --contract knowledge_admission.v1@1.0.0 --candidate knowledge.json --input asset=knowledge-artifact.json --root admission_result_root=./results --evidence-root ./evidence --run-id knowledge-plan
phase execute --contract knowledge_admission.v1@1.0.0 --candidate knowledge.json --input asset=knowledge-artifact.json --root admission_result_root=./results --evidence-root ./evidence --run-id knowledge-execute
phase inspect --evidence-root ./evidence --run-id knowledge-execute --root admission_result_root=./results
```

For MCP, call `phase_execute` with `contract_binding="knowledge_admission.v1@1.0.0"`; no knowledge-specific tool exists.
