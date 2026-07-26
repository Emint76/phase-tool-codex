# Domain Design Probes

These two JSON documents are deliberately non-executable:

- `source_admission.v1.example.json`;
- `knowledge_admission.v1.example.json`.

Both validate against the same neutral `schemas/phase-contract.schema.json`. Both bind a deferred, unregistered probe mechanism, so a future trust resolver must reject execution.

## Purpose

The probes test whether the contract meta-model can express domain-owned:

- provenance;
- review;
- placement;
- canonical destination;
- destination verification;
- profile and taxonomy selection where relevant.

Those terms may appear in contract instances, candidate schemas, validator IDs, and canonical-domain authority. They must not appear in Core schema vocabulary or Core control flow.

## What passing schema validation proves

Only structural fit:

- exact contract identity can be represented;
- domain inputs can select generic freeze strategies;
- domain validators can be exact registered bindings;
- bounded effects can be selected;
- domain canonical result ownership can be declared;
- Phase receipt/evidence remains common.

## What it does not prove

- executable admission;
- behavioral parity with existing admission paths;
- correct provenance/review/taxonomy/placement policy;
- trust/registry installation;
- platform/path/durability guarantees;
- universal Core;
- permission to mutate any source, knowledge base, or live system.

A future migration must compare contract validation and execution against intended domain behavior with differential tests. Any need to add domain vocabulary or routing/approval/orchestration to Core is evidence against the proposed abstraction.
