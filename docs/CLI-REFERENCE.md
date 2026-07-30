# CLI Reference

All successful machine-facing commands emit one canonical JSON document on stdout. Diagnostics use stderr.

```text
phase --version
phase doctor
phase contracts list
phase contracts describe --contract <id@version>
phase validate --contract <id@version> --candidate <json> --evidence-root <dir> --run-id <id> [--input NAME=PATH] [--root NAME=PATH]
phase plan --contract <id@version> --candidate <json> --evidence-root <dir> --run-id <id> [--input NAME=PATH] [--root NAME=PATH]
phase execute --contract <id@version> --candidate <json> --evidence-root <dir> --run-id <id> [--input NAME=PATH] [--root NAME=PATH]
phase inspect --evidence-root <dir> --run-id <id> [--root NAME=PATH]
phase mcp serve --stdio
```

`--contract` is an exact registry key such as `source_admission.v1@1.0.0` or `knowledge_admission.v1@1.0.0`; no latest-version or network lookup occurs. Repeat `--input` and `--root` for generic named bindings. Duplicate names are rejected.

`validate` and `plan` run the non-mutating lifecycle and persist their evidence. `execute` uses the same lifecycle with trusted broker execution. `inspect` rereads evidence and reverifies the target.

Use `phase doctor` after installation and `phase contracts list` to discover the installed package's contracts. `phase contracts describe --contract source_admission.v1@1.0.0` returns contract and package metadata directly from the registry.
