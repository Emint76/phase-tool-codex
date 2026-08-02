#!/usr/bin/env python
"""Fail-closed semantic routing for Hermes filesystem mutations."""
from __future__ import annotations

import argparse
import json
from typing import Any, Mapping


class RoutingError(ValueError):
    pass


_ROUTES = {
    "create": {"contract_binding": "file_create.v1@1.0.0", "contract_digest": "sha256:50e214ab02f6bee74d605239ce7031f827bdcc43745c166244167cf4faa6f1b9", "root_binding": "phase_result_root"},
    "publish_new_version": {"contract_binding": "publish_new_version.v1@1.0.0", "contract_digest": "sha256:86a79002a91cb0a97be784b60029624f3a6f52fa5c839ba37cd64caa2abbf363", "root_binding": "fixture_result_root"},
    "append": {"contract_binding": "append_stream.v1@1.0.0", "contract_digest": "sha256:a381ed6e29255fd17097944a97cc16b0d60c1d097bb3a863d3de5902631ae14b", "root_binding": "phase_result_root"},
    "content_addressed_publish": {"contract_binding": "content_addressed_publish.v1@1.0.0", "contract_digest": "sha256:de6a82667c94a584b0412b924ae8266f4e9d9a47c59131eece128e2ae9b54579", "root_binding": "phase_result_root"},
    "source_admission": {"contract_binding": "source_admission.v1@1.0.0", "contract_digest": "sha256:fa86dd0da4077c648684ad8267bf904b1387c6c09b30f6e689d4516a5493c0f3", "root_binding": "admission_result_root"},
    "knowledge_admission": {"contract_binding": "knowledge_admission.v1@1.0.0", "contract_digest": "sha256:d015367dc85347bd3f36abb6a2ba5158ef1b135f3b4add544bbc94f632cebad8", "root_binding": "admission_result_root"},
}


def route_mutation(intent: Mapping[str, Any]) -> dict[str, Any]:
    kind = intent.get("mutation_kind")
    if not isinstance(kind, str) or kind not in _ROUTES:
        raise RoutingError(f"unsupported mutation kind: {kind!r}; direct write is forbidden")
    exists = intent.get("stable_path_exists")
    if not isinstance(exists, bool):
        raise RoutingError("stable_path_exists must be boolean")
    if kind == "create" and exists:
        raise RoutingError("create is invalid for an existing stable path; use publish_new_version")
    if kind == "publish_new_version" and not exists:
        raise RoutingError("publish_new_version requires an existing stable path")
    return {
        "mutation_kind": kind,
        **_ROUTES[kind],
        "transport": "mcp",
        "lifecycle": ["phase_execute", "phase_inspect"],
        "direct_write_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("intent", help="JSON object")
    args = parser.parse_args()
    try:
        print(json.dumps(route_mutation(json.loads(args.intent)), sort_keys=True))
    except (json.JSONDecodeError, RoutingError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
