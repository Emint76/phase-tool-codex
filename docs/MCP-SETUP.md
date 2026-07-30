# MCP Setup

Phase Tool uses the official stable Python MCP SDK in the bounded range `mcp>=1.26,<2`. Stage 8 supports local stdio only; HTTP, OAuth, MCP Apps, and remote deployment are outside scope.

Start the server with either equivalent command:

```console
phase mcp serve --stdio
phase-mcp
```

The server's stdout is reserved for MCP protocol messages. SDK diagnostics and logs go to stderr.

## Hermes

The following registration shape was verified against local `hermes mcp add --help`:

```console
hermes mcp add phase-tool --command phase-mcp
```

Then use Hermes's normal MCP list/test/configuration commands for its installed version. Platform configuration may differ; local CLI help and the official Hermes documentation are authoritative.

## Generic stdio client configuration

Clients that accept JSON-style stdio definitions generally use:

```json
{
  "command": "phase-mcp",
  "args": []
}
```

For clients whose exact command syntax has not been locally verified, including OpenClaw on this machine, consult that platform's installed help or official documentation rather than copying an unverified command.

## Universal tools

- `phase_contracts_list()`
- `phase_contract_describe(contract_binding=...)`
- `phase_validate(contract_binding=..., candidate={...}, ...)`
- `phase_plan(contract_binding=..., candidate={...}, ...)`
- `phase_execute(contract_binding=..., candidate={...}, ...)`
- `phase_inspect(run_id=..., ...)`

There are no source- or knowledge-specific MCP tools.
