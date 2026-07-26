# Current Phase Decomposition — Iteration 0.5

Evidence baseline:

- `crab-control-plane` remote `https://github.com/Emint76/crab-control-plane.git`
- branch `main`
- commit `f6c19d50fe1351e3a501be317f1a3424e5e4883f`
- Iteration 0 research commit `9cb1bec117ef4ff6164f84b20a1998398093faca`

Classification describes the current component's future role; it does not claim current code already implements Phase Core.

## 1. Classification vocabulary

- **Phase Core:** universal run/contract/evidence responsibility. No current directory is accepted wholesale as core.
- **Reusable execution mechanism:** deterministic mechanism that can be extracted and tested independently.
- **Operation contract:** domain policy/schema defining a controlled operation.
- **Adapter/skill:** invocation/routing surface around the tool.
- **Domain-specific implementation:** source, knowledge, KB, repo, OpenClaw, or task semantics.
- **Historical wrapper:** topology needed for the present harness but not future core architecture.
- **Remove/replace candidate:** duplicate, hard-coded, misleading, or subsumed surface.

## 2. Admission stack

| Current component | Actual function | Classification | Disposition |
|---|---|---|---|
| `operations/admission/README.md` | Defines Stage 1 package and Stage 2 handoff; explicitly not a runtime | Operation-contract documentation | Preserve concepts; replace Stage bridge with native Phase contracts |
| `schemas/admission_package.schema.json` | Universal envelope for source/knowledge admission package | Operation contract | Split shared admission envelope from source/knowledge contract payloads |
| `schemas/source_capture.v1.schema.json` | Source-capture profile payload | Domain-specific operation contract | Basis for `source_admission.v1`, not core |
| `schemas/knowledge_asset.v1.schema.json` | Knowledge-asset profile payload | Domain-specific operation contract | Basis for `knowledge_admission.v1`, not core |
| `schemas/admission_handoff.v1.schema.json` | Static bridge to prepared Phase3 target/manifest inputs | Historical bridge / replace candidate | Eliminate once Phase contract directly binds candidate, inputs, target and policy |
| `schemas/kb_taxonomy_config.v1.schema.json` | Instance taxonomy config shape | Domain-specific policy contract | Keep outside core under knowledge admission |
| `profiles/source_capture.v1.json` | Admission profile declaration | Operation contract metadata | Convert to contract bundle metadata |
| `profiles/knowledge_asset.v1.json` | Knowledge profile declaration; profile data intentionally opaque | Operation contract metadata | Convert; keep extraction semantics external |
| `placement-policies/registry.v1.json` | Declared placement policy registry | Domain-specific registry | Contract-bundled/instance policy; remove duplicated constants |
| `knowledge-profiles/registry.v1.json` and templates | Instance profile registry interface | Domain-specific implementation/config | Remain instance input; never core registry |
| `examples/stage2/**` | Positive source/knowledge handoff fixtures | Contract tests/fixtures | Migrate to contract conformance fixtures |
| `tests/test_admission_contracts.sh` | Schema/contract tests | Reusable test intent | Rebuild under contract conformance suite |
| `tests/test_stage2_handoff.sh` | Cross-binding and full-example checks | Reusable validation tests + historical bridge tests | Preserve relevant bindings; retire Stage2-only mapping tests later |

## 3. Phase2

| Current component | Actual function | Classification | Disposition |
|---|---|---|---|
| `harness-phase2/README.md` | Documents strict audit profile and repo-native scaffold profile | Historical wrapper documentation | Do not retain Phase number in new architecture |
| `bin/run_phase2_check_layer.sh` | Runs audit-only checks and evidence pack | Reusable validation orchestration fragment | Extract validator runner/check-result model; retire wrapper topology |
| `bin/run_phase2_bundle.sh` | Runs checks, renders static decisions/runtime-ready, emits reports/handoff readiness | Historical scaffold wrapper | Replace with `phase validate/plan` plus contract fixtures |
| `bin/validate_json_against_schema.sh` | Draft 2020-12 validation helper | Reusable execution mechanism | Replace shell wrapper with core schema-validator service |
| `bin/validate_contracts.py` | Validates known contracts/examples | Reusable validator | Generalize to contract bundle validator |
| `bin/check_admission_policy.py` | Validates package/handoff/review hashes, identity, placement, target/manifest bindings | Domain-specific validators with reusable result shape | Split source/knowledge validators into contracts; keep generic hash/binding utilities reusable |
| `bin/check_placement_policy.py` / `validate_policy.py` | Repo-specific policy checks | Domain-specific implementation | Move under source/knowledge contracts |
| `bin/render_apply_plan.py` | Static scaffold renderer, not a decision engine | Historical wrapper / replace candidate | Replace with contract planner/effect-plan generation |
| `bin/run_phase2_conformance.py`, `run_phase2_smoke.py` | Harness-specific conformance/smoke | Reusable test intent | Replace with Phase Core + contract conformance suites |
| `bin/preflight_wrong_root_scan.sh` | Detects wrong-root hazards | Reusable safety check | Recast as core path/run containment tests |
| `bin/emit_phase2_report.py` | Phase2 report surface | Historical/duplicate evidence | Replace with one core evidence envelope |
| `bin/emit_observability_record.py` | Sample JSONL under Phase2 reports | Historical sample | Remove unless observability consumer is proven |
| `policy/*.yaml` | Repo admission/placement policy | Domain-specific contract data | Move into operation contracts; avoid duplicate Python constants |
| `tests/**` | Positive/negative policy, containment, output tests | Mixed | Preserve mechanisms as fixtures; rename away from Phase2 |

Important boundary: generic Phase2 does not consume a concrete admission handoff. Reusing a baseline tied only to repository HEAD is not a substitute for per-run candidate/input binding.

## 4. Phase3

Phase3 contains the strongest reusable execution ideas, but it is not separable core as written.

| Current component | Actual function | Classification | Disposition |
|---|---|---|---|
| `PHASE3_EXECUTION_CONTRACT.md` | Declares run owner, frozen inputs, staging/apply, reports and exit status | Phase Core principles + historical topology | Extract invariants; do not preserve Phase3 label/paths |
| `bin/run_phase3_bundle.sh` | Monolithic run coordinator across freeze, validation, apply, evidence, reports | Phase Core candidate, requires decomposition | Replace with contract-driven coordinator; no target-kind branches |
| `bin/freeze_phase2_input.py` | Copies/hashes selected Phase2 metadata but leaves runtime package upstream | Reusable freezer fragment with gap | Replace with explicit freeze strategies and truthful guarantees |
| `bin/hash_frozen_input.py` | Produces frozen input inventory/digest | Reusable execution mechanism | Extract; reverify digest before operation |
| `bin/validate_frozen_intake.py` | Checks frozen intake artifacts | Reusable validator | Generalize to input manifest validator |
| `bin/reverify_runtime_ready.py` | Re-hashes mutable upstream before materialization | Reusable precondition check with TOCTOU | Replace by operation from frozen bytes or lock/token revalidation |
| `bin/materialize_phase3_staging.py` | Copies runtime-ready files from upstream into staging | Reusable copy mechanism with TOCTOU | Copy only from frozen/content-addressed input |
| `contracts/execution_target.schema.json` | Hard-coded `phase3_staging`, `repo_admission`, `kb_admission` union | Mixed contract/router | Replace with generic contract identity + target bindings |
| `bin/validate_execution_target.py` | Schema/semantic target/path checks | Reusable target validation + domain branches | Split generic path/binding checks from contract validators |
| `bin/validate_pre_apply.py` | Dispatches pre-apply checks by target kind | Historical hard-coded router | Replace with contract-declared validator pipeline |
| `bin/validate_repo_admission_pre_apply.py` | Repo admission manifest/source/destination checks | Domain-specific implementation | Move to source/knowledge admission contract extensions |
| `bin/validate_kb_admission_pre_apply.py` | Workspace KB integration/manifest/path checks | Domain-specific implementation | Move to admission contracts; no KB in core |
| `contracts/admission_manifest.schema.json` | Repo copy manifest for source/knowledge | Operation contract | Recast as admission effect-plan schema |
| `contracts/kb_admission_manifest.schema.json` | Workspace KB copy manifest | Domain-specific operation contract | Recast under source/knowledge contracts; remove duplicate copy schema |
| `bin/execute_apply.py` | Hard-coded target routing; scaffold check or calls repo/KB libraries | Historical router / replace candidate | Replace with registered mechanism ID selected by contract |
| `bin/repo_admission_lib.py` | Manifest preflight, containment, hash, idempotent copy into repo | Reusable copy mechanism + repo policy | Extract generic content-addressed copy; keep repo path policy in contract |
| `bin/kb_admission_lib.py` | Similar copy into external workspace KB | Reusable copy mechanism + KB policy | Extract common copy; keep KB integration/root policy in contract |
| `bin/collect_declared_scope_evidence.py` | Aggregates declared/observed paths; KB `writes_outside_scope` is declaratively empty | Evidence mechanism with overclaim risk | Replace with broker effect receipts; do not call it OS write audit |
| `bin/validate_post_apply.py` | Validates apply log, declared scope and domain evidence | Reusable verifier runner + hard-coded domain checks | Split core verifier aggregation from contract verifiers |
| `bin/emit_execution_result.py` | Aggregates fixed check names into result | Core result-finalizer concept, schema gap | Generalize and schema-validate; derive checks from contract |
| `bin/emit_phase3_report.py` | Emits canonical Phase3 reports/timestamps | Phase Core evidence concept | Replace with one versioned core evidence schema; avoid duplicate Markdown authority |
| `tests/test_fail_closed_and_evidence.sh` | Failure/reached-step evidence tests | Reusable core tests | Port to core conformance |
| `tests/test_repo_admission*`, `test_kb_admission*` | Copy/admission tests | Domain-contract + mechanism tests | Split generic copy tests from admission policy tests |
| `tests/test_report_shape.sh`, `test_run_dir_invariants.sh` | Evidence/run containment tests | Reusable core tests | Preserve under neutral names |

### Known implementation gaps

- `input.sha256` presence is checked more strongly than complete re-computation immediately before apply.
- Runtime-ready input is not fully copied into frozen input; later code reads mutable upstream.
- TOCTOU exists between `reverify_runtime_ready.py` and `materialize_phase3_staging.py`.
- Repo/KB admission hashes a source while building the copy plan, then later reopens the mutable path for `copyfile`; drift is generally detected only by a post-copy destination hash, after mutation.
- Destination existence/containment/symlink checks are path-based preflight followed by later path-based create/copy, leaving a check-to-use race without descriptor-relative/no-follow primitives or an equivalent lock.
- Sequential multi-file copy can leave partial effects.
- `collect_declared_scope_evidence.py` sets KB `writes_outside_scope: []` declaratively; this is not exhaustive system observation.
- Aggregate Phase3 reports do not have a separate JSON Schema validation boundary.
- `execute_apply.py` branches directly on target kinds and imports domain libraries.

These are reasons to extract mechanisms, not to copy Phase3 wholesale.

## 5. Phase4 and orchestration

| Current component | Actual function | Classification | Disposition |
|---|---|---|---|
| `harness-phase4/PHASE4_WRAPPER_CONTRACT.md` | Defines thin operator wrapper and non-competing outputs | Adapter/skill principle + historical wrapper | Preserve thin/non-owning rule; retire Phase4 layer |
| `harness-phase4/bin/run_phase4_wrapper.sh` | Validates args, invokes Phase3, preserves status, writes wrapper metadata | Adapter/CLI wrapper | Replace with direct Phase Tool invocation by adapters |
| `harness-phase4/tests/test_phase4_wrapper.sh` | Proves no competing canonical outputs | Reusable adapter conformance test | Port to adapter tests |
| `harness-orchestration/ORCHESTRATION_CONTRACT.md` | Crab-safe wrapper for one smoke path; forbids arbitrary selection | Adapter safety contract | Keep only as current legacy adapter boundary |
| `bin/run_repo_native_smoke.sh` | Executes fixed e2e smoke path | Historical wrapper | Replace with test command, not product core |
| `bin/run_crab_approved_live_rollout.sh` | Approved rollout-specific invocation | Domain/live orchestration | Out of Phase Core; separate high-risk contract if ever migrated |
| orchestration tests/runbooks | Wrapper containment and operator instructions | Adapter tests/docs | Preserve while legacy path exists; deprecate after equivalent adapter tests |

## 6. Disposable apply and rollback surfaces

| Current component | Actual function | Classification | Disposition |
|---|---|---|---|
| `docs/CONTROLLED_DISPOSABLE_APPLY_CONTRACT.md` | Bounded OpenClaw disposable copy/create operation with evidence | Operation contract + domain policy | Candidate future `openclaw_disposable_apply.v1`, not core |
| `harness-openclaw-disposable-apply/bin/run_controlled_disposable_apply.sh` | Validates target/plan, writes disposable target, emits evidence/plans | Reusable effect ideas + domain-specific wrapper | Extract generic preflight/effect receipts; keep OpenClaw policy in contract |
| `schemas/apply_*.schema.json`, `target_refs.schema.json` | Disposable apply/evidence schemas | Operation contract | Keep under future domain contract; align with core evidence envelope |
| `tests/test_controlled_disposable_apply.sh` | Safety/containment/refusal tests | Domain contract tests + reusable effect tests | Split accordingly |
| `docs/ROLLBACK_MODEL.md` | Model/handoff only; explicitly no rollback execution | Operation-policy documentation | Keep as policy input; never advertise as reusable rollback mechanism |
| live-precheck/execution-prep surfaces referenced by rollback model | Validate/normalize records, do not execute rollback | Historical preparation wrappers | Keep outside core; possible future separate rollback contract |

## 7. Skills and adapters observed in live OpenClaw

| Current component | Classification | Future role |
|---|---|---|
| `phase-execution-skill` | Adapter/skill | Invoke Phase Tool with exact contract ID; no embedded execution logic |
| `admission-router-skill` | Adapter/skill + domain routing | Select source/knowledge contract; routing decision remains outside core |
| `source-admission` | Domain adapter/skill | Prepare `source_admission.v1` candidate and invoke core |
| `knowledge-admission` | Domain adapter/skill | Prepare `knowledge_admission.v1` candidate/profile refs and invoke core |
| `admission-skill-stack-v1.yaml` | Adapter compatibility registry | Replace manual hashes with package/version compatibility checks; not core source of truth |
| `.runtime/phase-python/` | Existing runtime implementation surface | Input to later migration analysis; not accepted as new core without conformance tests |

## 8. Consolidated disposition

### Extract into Phase Core

- contract resolution/version binding;
- contained run/evidence ownership;
- candidate capture;
- truthful freeze strategies and hashing;
- ordered validator runner;
- effect planner/broker;
- generic append/copy/create mechanisms;
- post-verification orchestration;
- result/evidence finalization and terminal status.

### Keep as contracts/domain extensions

- task lifecycle and correction semantics;
- source/knowledge package/review/provenance;
- KB placement, taxonomy and profile registration;
- OpenClaw disposable/live target safety;
- repo/workspace-specific path policy.

### Retain temporarily as legacy compatibility

- Phase2/3/4 entrypoints;
- Stage2 handoff bridge;
- Crab orchestration wrapper;
- current skills/registry/runtime.

### Replace/deprecate after parity

- hard-coded `target_kind` dispatch;
- duplicated repo/KB copy implementations and manifest schemas;
- Phase2 static scaffold decision artifacts;
- competing/redundant report surfaces;
- manual hash registries as sole compatibility proof;
- wrapper numbering as product architecture.

No legacy component is removed until a contract-driven replacement passes fixture parity, negative tests, evidence comparison, and an explicit deprecation decision.
