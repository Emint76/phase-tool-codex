# Hermes canonical mutation routing through Phase

## Boundary

The conforming workflow is: semantic decision by the agent -> deterministic preparation outside the canonical target -> exact contract selection -> direct Phase MCP `phase_execute` -> `phase_inspect` -> six-field verified result. Python, shell, PowerShell, Hermes file tools, and the preparation adapters do not write canonical targets. This policy governs the Hermes workflow; it does not claim to intercept unrelated operating-system processes.

Router and preparation are separate skills. `phase-verified-execution` remains a narrow transport-neutral execution boundary and never creates payloads, roots, or targets. MCP is primary; its CLI runner is diagnostic/CI fallback only when MCP is unavailable or explicitly requested.

## Routing map

| Semantic mutation | Contract |
|---|---|
| New stable file | `file_create.v1@1.0.0` |
| Existing stable path, new bytes | `publish_new_version.v1@1.0.0` |
| Append-only immutable record | `append_stream.v1@1.0.0` |
| Content-addressed object | `content_addressed_publish.v1@1.0.0` |
| Source admission | `source_admission.v1@1.0.0` |
| Knowledge admission | `knowledge_admission.v1@1.0.0` |

The three production-neutral contracts reuse the existing fixed generic candidate validators and bundled mechanisms, but replace fixture-facing contract identity, schema URI, canonical owner/root, and retention policy. This is a semantic production boundary, not a cosmetic alias. Formats and extensions remain opaque bytes.

## Runtime layout and archive placement

A portable product instance uses a dedicated instance parent with this normative layout:

```text
<instance-parent>/
  toolkit/     Git checkout
  archive/     predecessor runtime history
```

Bind the canonical root to `<instance-parent>`, and express every repository target locator with the `toolkit/` prefix, for example `toolkit/docs/item.md`. Never bind the canonical root directly to the Git checkout root when using `publish_new_version.v1@1.0.0`: the contract-owned predecessor archive must resolve to `<instance-parent>/archive/sha256/`, outside `<instance-parent>/toolkit/`.

The evidence root is outside `<instance-parent>`. The preparation root is also outside `<instance-parent>` and disjoint from both the canonical and evidence roots. Archive leaves, receipts, evidence, and preparation artifacts are runtime or history state and do not belong in product Git.

For an installed skill, use the same dedicated-parent rule rather than binding publication directly to the skill's Git or product root. Disposable smoke roots retain archives only until their exact allowlisted root is removed. Evidence remains in its separate normalized external root and is never substituted for the predecessor archive.

## Portable source and Phase-only sync

Repository source of truth is `integrations/hermes/skills/`. To install, prepare each destination file outside `%LOCALAPPDATA%\hermes`, route absent destination leaves through `file_create.v1@1.0.0`, route existing leaves through `publish_new_version.v1@1.0.0`, then execute and inspect each run through MCP. Do not use `copy`, `cp`, `write_file`, Python, or PowerShell against the local skills target. Verify bytes/digests after inspect.

Installed destinations:

- `%LOCALAPPDATA%/hermes/skills/software-development/phase-mutation-router/`
- `%LOCALAPPDATA%/hermes/skills/software-development/phase-mutation-preparation/`
- `%LOCALAPPDATA%/hermes/skills/software-development/phase-verified-execution/`

Use `/reload-skills` to rescan newly added skills. If the current surface cannot reload its startup skill inventory, start a fresh session and ask it to create then version a disposable Markdown file through router -> preparation -> Phase MCP execute -> inspect.
