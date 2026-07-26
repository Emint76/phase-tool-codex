# ADR: Hard Anti-Control-Plane Boundary

- **Status:** Accepted for Stage 1 specification
- **Decision ID:** ADR-ANTI-CONTROL-PLANE-BOUNDARY
- **Scope:** Phase Core v1 and future change admission
- **Implementation status:** Specification only

## Context

A generic contract engine can easily grow into a workflow/control-plane product. Routing, approvals, scheduling, orchestration, domain registries, arbitrary plugins, remote execution, and agent planning would increase the trusted computing base and obscure the controlled mutation boundary.

Phase Core is a deterministic operation executor, not a general workflow engine.

## Decision

### Allowed Core responsibilities

Only the following responsibility classes are provisionally allowed:

- exact contract/registry resolution;
- candidate capture;
- declared input freeze and digest binding;
- ordered fixed validator phases;
- complete bounded effect-plan validation;
- brokered bundled mutation mechanisms;
- postcondition verification;
- generic idempotency/recovery coordination;
- terminal status and canonical intent/receipt;
- read-only inspection of Core evidence.

Even these surfaces remain provisional until conformance tests and two mutation-bearing implementations confirm common semantics.

### Forbidden Core vocabulary

Core source, schemas, field names, enums, fixtures, and error codes MUST NOT contain or interpret these domain/integration concepts:

```text
task
source
knowledge
KB
taxonomy
profile
Hermes
OpenClaw
Codex
Phase2
Phase3
Phase4
approval
routing
orchestration
```

Generic documentation may mention the prohibited terms only in an explicit negative-test or architecture-boundary section. Core schemas and neutral synthetic contracts may not contain them at all, including property names and enum values.

### Hard-rejected capability classes

The following are rejected from Core v1:

1. **Routing** — deciding which domain contract/adapter should run.
2. **Approvals** — obtaining, authenticating, queueing, or interpreting approval workflow.
3. **Scheduling** — delayed, periodic, retry-queue, or dependency-triggered execution.
4. **Orchestration** — DAGs, multi-run workflows, branching, fan-out/fan-in, step compensation engines.
5. **Taxonomy/profile interpretation** — domain classification or instance configuration semantics.
6. **Registry administration** — install/update/remove/search/resolve dependencies or trust roots dynamically.
7. **Arbitrary plugin execution** — shell/import/path/URL-loaded executable extensions.
8. **Remote execution** — dispatch to remote agents, hosts, containers, services, or queues.
9. **Agent planning** — LLM/tool planning, semantic candidate generation, autonomous review.
10. **Identity/approval authority** — authentication, signing authority, or authorization service.
11. **Observability platform** — global event bus, dashboard, alerting, tracing backend, or analytics database.
12. **General persistence platform** — global control-plane database or canonical index required for correctness.

These capabilities may exist outside Core in adapters, installer/admin tooling, contract-specific producers/validators, external schedulers, or future separately bounded products.

## Rejection gate

A proposal in any hard-rejected class is rejected by default. It cannot enter Core because it is convenient, already exists in Phase2/3/4, is requested by one contract, or reduces adapter code.

A future proposal must provide all evidence below before reconsideration:

1. **Two-implementation proof:** at least two independent mutation-bearing contracts already implement the same semantics; two schemas/design probes are insufficient.
2. **Necessity proof:** show why the capability cannot remain in a contract, adapter, installer, validator, or external service.
3. **Neutrality proof:** no domain/integration vocabulary, branches, identifiers, or error codes enter Core.
4. **Determinism proof:** bounded inputs, outputs, ordering, timeout, retry, and failure semantics.
5. **Security/threat model:** capabilities, target access, trust roots, secrets, network/process boundaries, supply chain.
6. **Evidence/ownership proof:** one canonical result owner and one Phase evidence owner remain unambiguous.
7. **Failure proof:** partial, committed-unverified, indeterminate, crash, and recovery behavior.
8. **Platform proof:** Windows and Linux/WSL tests for every claimed filesystem/process guarantee.
9. **Complexity budget:** API/schema/TCB growth, dependency impact, performance, and maintenance cost.
10. **Independent review:** explicit review finding no control-plane expansion or weaker contract isolation.
11. **Approved ADR:** separate user-approved ADR and migration/deprecation plan.

Failure of any item means the feature remains outside Core.

## Workflow-shaped contract prevention

Operation contracts are bounded single-operation policy bundles. The contract schema must prevent or semantically reject:

- nested contract invocation;
- dynamic contract selection;
- arbitrary step graphs;
- condition expressions that branch to other mechanisms;
- loops, retries, schedules, delays, or callbacks;
- mechanism installation;
- remote endpoint execution;
- child runs as required operation semantics.

A contract may contain an ordered finite effect plan produced before mutation. This is not a workflow: effects use one bound contract/mechanism policy, cannot expand dynamically, and aggregate success requires explicit partial-failure semantics.

## Approval and policy input boundary

A domain validator may validate the structure/digest/binding of a declared review or authorization artifact. Core does not:

- obtain it;
- decide who may approve;
- authenticate the actor unless an external trust mechanism is explicitly bound;
- interpret domain decision vocabulary;
- wait for or route approval;
- infer semantic correctness.

The artifact remains contract input, not a Core subsystem.

## Registry boundary

Core reads one installation-controlled immutable registry snapshot. Registry CRUD, dependency resolution, publisher discovery, trust-root updates, and package installation are outside the operation path.

## Remote and agent boundary

Adapters may run on agent platforms and invoke Phase locally. Core v1 neither embeds an agent nor dispatches remote work. A remote filesystem is not treated as a local durability boundary.

## Conformance gates

| Gate | Stage 1 evidence | Future executable gate |
|---|---|---|
| Vocabulary neutrality | scan Core schemas/synthetic contracts | scan Core source/schema/error catalog |
| One fixed pipeline | append/copy contracts map to same stages | trace/evidence stage sequence equality |
| No workflow language | contract schema lacks graph/loop/callback fields | adversarial contracts rejected |
| No arbitrary code | schema + trust ADR | shell/import/URL/plugin tests |
| Broker-only writes | ownership/effect specifications | denied direct-write tests |
| Minimal evidence | intent/receipt schemas | no mandatory report tree |
| Stable API restraint | provisional schemas | two mutation-bearing implementation proof |

## Universality falsification criteria

The universal Core hypothesis is falsified or must be narrowed if:

- neutral append and copy require different Core lifecycle/state machines;
- one contract requires domain branches in Core;
- common schemas collapse into unrestricted generic dictionaries;
- guarantees must be weakened to a least-common-denominator statement;
- one evidence owner cannot represent truthful partial/indeterminate outcomes for both;
- profile/taxonomy/review interpretation must move into Core;
- generic API/TCB cost exceeds duplicated narrow mechanisms without safety benefit;
- a second mutation-bearing contract cannot use the same mechanism interfaces and terminal model.

Falsification is an acceptable Stage 1/compatibility result; it must not be hidden by adding workflow features.

## Consequences

- Core stays intentionally less convenient than a workflow engine.
- Domain producers/adapters carry routing and policy preparation.
- Installer tooling remains a separate trust boundary.
- Existing Phase wrappers are evidence sources, not mandatory future architecture.
- Stage 2 is blocked until High/Critical risks show a testable Core-local boundary rather than prose-only controls.
