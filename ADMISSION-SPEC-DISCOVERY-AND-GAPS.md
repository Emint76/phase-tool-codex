# Admission Stage 6–7 Discovery and Gap Ledger

Status: tracked-only read-only discovery record for the non-executable admission specification baseline. Legacy/design material is evidence, not automatically normative.

## 1. Tracked discovery inventory

### Universal Phase boundary

- `PHASE-CORE-ARCHITECTURE.md`
- `PHASE-CONTRACT-MODEL.md`
- `ADR-CORE-CONTRACT-ADAPTER-OWNERSHIP.md`
- `ADR-CONTRACT-TRUST-REGISTRY.md`
- `ADR-ANTI-CONTROL-PLANE-BOUNDARY.md`
- `STRATEGIC-CORRECTION.md`
- `CURRENT-PHASE-DECOMPOSITION.md`

### Lifecycle, guarantees, and recovery

- `FREEZE-STRATEGIES.md`
- `EFFECT-MECHANISM-SPEC.md`
- `EVIDENCE-MODEL.md`
- `TERMINAL-STATUS-MODEL.md`
- `IDEMPOTENCY-PROTOCOL.md`
- `RECOVERY-CORRECTION-ROLLBACK.md`
- `WRITE-SCOPE-AND-PATH-POLICY.md`
- `PLATFORM-GUARANTEE-MATRIX.md`
- `GUARANTEE-TRACEABILITY.md`
- `CONFORMANCE-SPEC.md`

### Active schemas and Stage 2–5 executable/reference surfaces

- active schemas under `schemas/`, including contract, plan, effect receipt/journal, receipt, and result-reference schemas;
- bundled registry snapshot `src/phase_tool/data/registry.json` read only;
- `fixture_create.v1`, `fixture_append.v1`, `task_journal.v1`, and `fixture_copy.v1` contracts;
- Stage 2–5 deviation records;
- `tests/test_stage3_architecture.py` and Stage 5 copy/race/inspection acceptance behavior;
- `docs/STAGE-5-CONTENT-ADDRESSED-COPY-WALKTHROUGH.md`.

### Admission and legacy/reference surfaces

- `contracts/design-probes/source_admission.v1.example.json`;
- `contracts/design-probes/knowledge_admission.v1.example.json`;
- `contracts/design-probes/README.md`;
- `SOURCE-INVENTORY.md`, `DISCOVERY.md`, `REUSE-MAP.md`, `ARCHITECTURE-PROPOSAL.md`, `REVISED-ROADMAP.md`, `REPOSITORY-TRANSITION-PLAN.md`, `TASK-JOURNAL-CONTRACT-PROPOSAL.md`, and `STAGE-1-INDEPENDENT-REVIEW.md`.

Protected untracked `_sources/`, `.stage5-tmpp/`, `.t/`, `.rar`, and `src/phase_tool.egg-info/` were not used as writable or normative inputs. Historical facts about legacy Phase were taken only from tracked discovery/decomposition records.

## 2. Already normative and reusable

| Existing rule | Normative owner | Admission use |
|---|---|---|
| One universal resolve/capture/freeze/validate/plan/intent/broker/verify/receipt pipeline | Core architecture/contract model | Both contracts use it unchanged. |
| Domain vocabulary and semantics stay outside Core | ownership and anti-control-plane ADRs | Source/knowledge validators remain contract-owned. |
| Exact contract/mechanism identity and immutable registry snapshot | trust-registry ADR | Candidate descriptors pin only mechanisms already present; candidate validators remain explicitly unregistered. |
| Candidate value capture and asset `copy_and_hash` | freeze specification | Candidate and bytes are frozen independently before planning. |
| Static bounded ordered effects; no dynamic work | contract/effect specs | Exactly two effects, fixed before intent. |
| Durable intent before mutation | evidence model | Admission plan and frozen descriptor bytes are intent-bound. |
| Per-effect attempt/observation journal required for multi-effect execution | conformance/effect-journal schema | Recovery never guesses reached subset. |
| Existing terminal statuses and precedence | terminal model | No new admission status family. |
| Same scoped key/same digest reuse only after canonical result plus receipt verification | idempotency protocol | Reuse validates both target objects and Phase evidence. |
| Partial/indeterminate prior run requires inspection | idempotency/recovery specs | Blind retry is forbidden. |
| No automatic rollback; immutable correction/supersession only | recovery/correction spec | No descriptor or blob rewrite. |
| Portable relative locators under installed root bindings; path regex is not the OS security boundary | write/path policy | Caller supplies namespace, never destination. |
| `exclusive_create` and `content_addressed_copy` no-overwrite mechanisms | bundled registry and Stage 3/5 evidence | Future admission can compose them without inventing a new mechanism. |
| Phase receipt and domain result have separate owners | architecture/evidence/result model | Descriptor owns metadata; receipt owns execution evidence. |

## 3. Confirmed specification gaps before this candidate

1. No chosen canonical admission result architecture among separate blob+descriptor, package, or blob-only models.
2. No exact source or knowledge candidate schema.
3. No normative separation of content, logical, operation, result, and locator identities.
4. No generic canonical placement formula independent of a concrete KB layout.
5. No canonical source/knowledge descriptor schema or exact cross-domain result reference.
6. No minimal provenance model separating caller assertions from Phase observations.
7. No exact knowledge-to-source binding resistant to arbitrary caller-provided source IDs.
8. No explicit v1 policy for same logical identity with changed content/provenance or immutable supersession.
9. No review policy deciding whether admission v1 requires review.
10. Active effect plans bind one mechanism at plan level, while blob+descriptor admission requires two ordered effects with per-effect mechanism identity.
11. Runtime deliberately rejects multi-effect execution until a durable journal protocol exists; existing specification did not give admission-specific maximum/order/recovery behavior.
12. No canonical all-effects progress representation covering completed, verified, failed, and not-started effects.
13. No resolution of the descriptor/final-receipt digest cycle.
14. No admission ownership matrix or end-to-end guarantee traceability.
15. Design probes reference deferred schemas/mechanisms and include review/profile/taxonomy assumptions that are not executable definitions.

## 4. Legacy/reference findings not promoted automatically

Tracked decomposition records show that legacy Phase used source-capture and knowledge-asset packages, review decisions, placement registries, knowledge profiles, taxonomy configuration, Stage 2 handoff, and repo/KB-specific manifests. They also record mutable-upstream TOCTOU, sequential partial copy, duplicated report surfaces, and hard-coded target routing.

This candidate does **not** inherit:

- review as mandatory workflow;
- source family, profile, taxonomy, formulation, PCR, cosmetics, or KB placement fields;
- Stage 2→3 handoff topology;
- repo/KB target-kind routing;
- caller-provided destination manifests;
- automatic rollback or transaction claims;
- legacy evidence trees as domain metadata authority.

Only reusable invariants—exact bindings, frozen bytes, static effects, no overwrite, verified digest, truthful partial state, and thin adapters—are retained.

## 5. Candidate resolution of gaps

- Architecture: ordered immutable blob then immutable descriptor (Option A).
- Neutral extension: candidate per-effect mechanism plan and progress schemas, maximum two effects, no active schema/runtime change.
- Source: closed candidate/provenance/result/result-reference schemas and immutable identity/conflict/supersession policy.
- Knowledge: closed candidate/provenance/result/result-reference/source-binding schemas; at least one inspected exact source result is required.
- Placement: contract-computed relative locators under installation-bound `admission_result_root`.
- Ownership: descriptor is canonical metadata/provenance authority; blob is byte authority; receipt is execution evidence.
- Versioning: new logical and result IDs plus exact `supersedes`; no in-place correction.
- Review: omitted from v1; any future requirement is a versioned contract input validated structurally outside Core.
- Receipt cycle: descriptor carries run ID only; final result reference is computed after receipt finalization and is not a third target effect.
