# ADR: Exclusive Write Contour for Managed Information

**Status:** Accepted
**Date:** 2026-08-03
**Implementation status:** Partial
**Related:** `ARCHITECTURE.md`, `ADR-ANTI-CONTROL-PLANE-BOUNDARY.md`

## Context

Phase is intended to conduct and prove managed transitions of information state.

A receipt can prove that a transition passed through Phase. It cannot prove that every change to a resource passed through Phase when the same agent or another system can mutate that resource through a different channel.

Prompt-level instructions such as:

```text
Always write through Phase.
```

are not an enforcement boundary.

If an agent also has writable filesystem access, a mutation-capable shell, direct Git access, a writable database tool, a publication API, or another write-capable MCP server, Phase is only one possible mutation path.

The architectural claim must therefore be limited to a controlled contour in which write authority is technically constrained.

## Decision

For every resource declared to be inside the managed information contour:

> Phase must be the exclusive normal write channel.

Agents may:

- read admitted resources;
- inspect state;
- reason about changes;
- prepare candidates;
- propose information transitions;
- inspect Phase evidence.

Agents must not directly own the write capability for managed resources.

Only Phase mechanisms or effect adapters operating behind the Phase boundary may apply normal mutations.

The promise is:

> All managed changes inside the controlled information contour pass through Phase.

This decision does not claim that Phase controls every information change in every external system.

## Logical Resource Handles

Agents must refer to managed resources by logical identity, for example:

```text
source_store
knowledge_store
task_journal
project_repository
publication_target
```

Agents must not select arbitrary absolute filesystem paths as the authority for a managed transition.

A trusted installation layer resolves a logical resource handle to:

- an exact local root;
- a database capability;
- a repository capability;
- an object-store capability;
- an external service capability;
- another admitted resource authority.

Resolution belongs to host configuration, not to agent reasoning.

## Agent Capability Model

The intended capability split is:

```text
Agent capabilities:
read
inspect
reason
propose

Phase capabilities:
validate
plan
commit
verify
record evidence
```

For managed resources, agents must not have direct access to:

- writable filesystem mounts;
- mutation-capable shell commands;
- direct Git commit, tag, merge, or push operations;
- direct database writes;
- direct document publication;
- direct task or knowledge-store mutation;
- writable third-party MCP tools;
- unrestricted external APIs that can mutate the same canonical state.

Write-capable systems may still exist, but they must operate as admitted Phase mechanisms or effect adapters.

## Transition Coverage

Exclusive capability is insufficient when Phase does not support the transition the agent needs.

The managed contour must provide admitted transitions for all required mutation classes, including where applicable:

- create;
- append;
- update;
- compare-and-swap;
- replace;
- publish;
- archive;
- move;
- rename;
- delete;
- restore;
- relate;
- detach;
- status change;
- metadata change;
- permission change;
- external publication.

When a required transition is not available, the system must fail closed. It must not silently grant the agent a lower-level bypass.

## High-Level Transitions

Agents should normally propose domain transitions rather than low-level storage instructions.

Preferred:

```text
admit this source
admit this knowledge artifact
record this task event
publish this version
establish this relationship
```

Not preferred:

```text
create this directory
write these bytes
append this line
rename this file
```

The Domain Runtime translates the high-level information transition into bounded physical effects.

This prevents Phase from becoming a low-level filesystem proxy and keeps evidence aligned with the actual meaning of the transition.

## Other Tools

Every tool available to an agent must be classified as:

1. read-only;
2. proposal-only;
3. write-capable behind Phase;
4. prohibited for managed resources.

A writable filesystem tool, shell tool, Git tool, database tool, SaaS MCP server, or publication API invalidates the exclusive contour when it can mutate the same resource directly.

The deployment must therefore remove, restrict, or mediate such tools.

## Human Break-Glass Access

An authorized human may require emergency write access when:

- Phase is unavailable;
- a mechanism is defective;
- a resource requires manual recovery;
- safety or continuity requires immediate intervention.

Break-glass access is permitted only as an exceptional process.

It must:

- require explicit human action;
- record the human identity;
- record the reason;
- record the affected resource;
- record the time and scope;
- preserve before and after observations where possible;
- create separate audit evidence;
- trigger subsequent drift inspection and reconciliation.

A break-glass mutation must not be represented as an ordinary successful Phase transition.

## External Changes and Drift

Some managed resources may also be changed by:

- humans;
- IDEs;
- synchronization software;
- backup or restoration systems;
- repository hosting services;
- external APIs;
- administrators;
- legacy automation.

The preferred control is to prevent these writes through capability isolation.

Where prevention is impossible, Phase must treat unexplained change as drift.

Drift means:

```text
observed resource state
!=
latest state proven by Phase
```

with no admitted transition explaining the difference.

Drift must be:

- detected;
- classified;
- recorded;
- reconciled before the resource is considered fully inside the controlled contour again.

## Relationship to MCP

MCP is a transport and discovery protocol. It is not the write-security boundary.

Exposing Phase as an MCP server is useful only when the surrounding agent environment preserves the capability model.

The required model is:

```text
agent
↓ MCP proposal
Phase
↓ admitted mechanism
managed resource
```

The following model is not sufficient:

```text
agent
├── Phase MCP
├── writable filesystem MCP
├── shell
└── direct publication API
```

MCP configuration must therefore be evaluated as part of the installation security boundary.

## Relationship to the Anti-Control-Plane Boundary

Exclusive write ownership does not turn Phase into a workflow engine or agent control plane.

Phase still does not own:

- agent routing;
- scheduling;
- long-running workflow orchestration;
- human approval interfaces;
- multi-agent coordination;
- general remote execution;
- global observability.

External orchestration systems may decide when to propose a transition. Phase decides whether and how that transition can be committed to a managed resource.

## Consequences

### Positive

- Every normal managed change has a Phase intent and receipt.
- Agents cannot silently bypass transition validation.
- Evidence can represent the authoritative history of the managed contour.
- Logical resource identity is separated from physical paths.
- Domain transitions remain higher-level than storage mutations.
- Security and audit claims become technically enforceable rather than prompt-based.

### Costs

- Agent environments require stricter capability configuration.
- Existing writable tools must be removed, restricted, or wrapped.
- Phase must cover every required transition class.
- Missing contracts or mechanisms will block work.
- Host installation configuration becomes part of the trusted computing base.
- Break-glass and reconciliation workflows must be maintained.
- External services may require dedicated Phase effect adapters.

### Risks

- Phase may become a bottleneck if transitions are too low-level.
- Incomplete transition coverage may encourage bypass attempts.
- Incorrect installation configuration may create a false sense of exclusivity.
- A Phase outage may block all managed mutation without a controlled break-glass path.
- Undetected external writes may invalidate evidence completeness.

## Implementation Requirements

The target implementation requires:

1. a logical resource installation registry;
2. opaque or bounded resource handles;
3. read-only agent access to managed resources;
4. exclusive Phase write capabilities;
5. removal or mediation of competing write-capable tools;
6. admitted contracts for every required transition;
7. bounded physical mechanisms;
8. explicit break-glass evidence;
9. drift detection or technical write prevention;
10. installation diagnostics proving the intended capability model.

## Current Implementation Status

The current Phase repository already provides:

- contract-bound transitions;
- durable intent before mutation;
- bounded filesystem mechanisms;
- post-operation verification;
- canonical evidence;
- independent inspection;
- CLI and MCP adapters.

The exclusive write contour is not yet fully enforced by the repository itself.

Current gaps include:

- caller-provided physical root paths;
- no universal logical-resource installation registry;
- no proof that agents lack alternative write-capable tools;
- incomplete transition coverage;
- incomplete break-glass workflow;
- incomplete drift detection;
- filesystem permissions and tool exposure remain deployment responsibilities.

This ADR records the target architectural decision. It must not be read as a claim that all enforcement is already implemented.

## Alternatives Considered

### Prompt-only discipline

Rejected.

An instruction to use Phase does not prevent direct mutation through another tool.

### Phase as one optional write tool

Rejected for managed resources.

This model can produce evidence for individual Phase runs but cannot establish a complete managed transition history.

### Full agent write access plus later logging

Rejected as the primary model.

Post-hoc logs cannot reliably reconstruct exact preconditions, commit-time state, partial effects, or unobserved writes.

### Phase detects every external change but does not own writes

Accepted only as a weaker transitional deployment mode.

Detection is useful, but prevention through exclusive capabilities provides the stronger and preferred guarantee.

## Decision Summary

For resources inside the managed information contour:

```text
Agents propose.
Phase commits.
Evidence proves.
Humans break glass explicitly.
Unexplained external change is drift.
```
