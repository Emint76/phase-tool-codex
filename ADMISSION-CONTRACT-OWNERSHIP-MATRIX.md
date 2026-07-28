# Admission Contract Ownership Matrix Candidate

Status: non-executable Stage 6–7 specification candidate.

Legend: **owns** = authoritative definition; **asserts** = supplies untrusted/bounded input; **enforces** = generic lifecycle enforcement; **executes** = bounded mutation only; **records** = evidence; **contains** = canonical domain authority.

| Responsibility | Caller/adapter | Contract | Core | Broker | Mechanism | Evidence | Canonical result |
|---|---|---|---|---|---|---|---|
| Logical identity | asserts source/knowledge logical ID | **owns** syntax, immutability, conflict/version policy | transports opaque value only | none | none | records candidate/request binding | **contains** logical/result identity |
| Content digest | optional expected assertion | **owns** SHA-256/length predicates and identity projection | freezes input, coordinates validator | passes frozen binding | hashes/read-backs generic bytes | records observed/frozen/effect digests | **contains** verified digest/length and blob binding |
| Candidate validation | submits closed candidate | **owns** field and semantic rules | invokes exact validator generically | none | none | records validator result | none until success |
| Provenance validation — source | asserts origin/supplier metadata | **owns** shape and untrusted/verified distinctions | generic validator lifecycle | none | none | records validator observations | source descriptor **contains** canonical provenance |
| Provenance validation — knowledge | supplies exact source bindings and producer/transformation declarations | **owns** exact source descriptor/blob/receipt revalidation | generic validator lifecycle | none | none | records exact observations | knowledge descriptor **contains** source bindings/provenance |
| Placement | supplies authorized namespace; never locator | **owns** deterministic templates and identity projection | freezes computed plan/write scope | verifies effect target equals plan | resolves only bound root + relative locator | records root/locator observations | **contains** canonical relative locators |
| Record/blob serialization | supplies input bytes only | **owns** `admission_canonical_json_v1`, identity projections, exact codec golden vectors, and canonical descriptor bytes | freezes resulting bytes generically | transports bytes binding | writes bytes without domain interpretation | records content source/digest | descriptor/blob are authoritative bytes |
| Effect ordering | none | declares exact two-effect static order | **enforces** durable intent/journal sequencing and exact-bound `phase.ordered_effect_plan_progress_v1` generic set/state validation | dispatches current ordinal only | never invokes next effect | records marker/receipt/progress sets | no ordering logic |
| Target mutation | none | declares kinds/preconditions/no-replace | authorizes only after intent | **owns** trusted dispatch boundary | **executes** one bounded generic effect | records observation/effect receipt | receives immutable objects |
| Post-verification | none | **owns** domain result and provenance predicates | invokes validators and classifies | rereads/returns generic observation | verifies bytes/target mechanically | records all results | must resolve and match descriptor+blob |
| Terminal classification | receives exact outcome | maps predicates to existing neutral statuses | **owns** deterministic aggregate classifier | reports effect facts only | reports effect facts only | records canonical receipt | does not define Phase status |
| Domain result | consumes/reference | **owns** descriptor schema/authority | carries generic result reference | none | none | references but does not own | **owns** descriptor+blob pair |
| Execution evidence | may render | declares required attachments | **owns** intent/receipt semantics | emits effect receipts | emits observations | **owns** intent, journal, receipt, attachments | contains only run binding, not evidence database |
| Reuse | asks with stable key | **owns** canonical-result-then-receipt predicates | coordinates lookup/inspection | may invoke verification only when needed | verifies existing exact objects generically | exact prior verified receipt required | descriptor/blob must be reverified |
| Correction/versioning | submits new IDs + exact supersedes | **owns** immutable supersession rules | transports relation; no rewrite | none | create-only only | links runs/receipts | new descriptor contains prior reference; old result unchanged |
| Inspection | requests | **owns** domain checks for descriptor/provenance | **owns** read-only lifecycle and aggregate reporting | read-only observation routing if supported | no mutation | supplies intent/journal/receipt | resolved and revalidated, never repaired |

## Domain-specific differences

Only these responsibilities differ between contracts:

- Source provenance validates bounded origin/supplier declarations and observed asset identity.
- Knowledge provenance requires one or more exact source admission result bindings and revalidates each source descriptor, blob, contract, and Phase receipt.
- Source result identity projection includes media type and original filename metadata.
- Knowledge result identity projection includes artifact kind/format and complete source/producer/transformation provenance.
- Both use the same Core lifecycle, root/placement algorithm family, two-effect ordering, broker, mechanisms, terminal model, evidence model, idempotency protocol, and inspection lifecycle.

No source- or knowledge-specific responsibility is assigned to Core, broker, or mechanisms.
