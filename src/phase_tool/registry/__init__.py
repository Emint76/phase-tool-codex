from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from importlib import resources as package_resources
from types import MappingProxyType
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from ..canonical import canonical_bytes, canonical_digest, digest_bytes, parse_json_bytes
from ..errors import PhaseError

_REGISTRY_RESOURCE = "registry.json"


def _semver(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", value)
    if not match:
        raise PhaseError("registry.invalid_semver", value)
    return tuple(int(part) for part in match.groups())


@dataclass(frozen=True)
class ResolvedContract:
    document: dict[str, Any]
    package_digest: str
    registry_snapshot_digest: str
    entry: Mapping[str, Any]


class RegistrySnapshot:
    """An in-memory immutable registry snapshot. It never performs external lookup."""

    def __init__(self, document: dict[str, Any], resources: Mapping[str, bytes]) -> None:
        frozen_document = parse_json_bytes(canonical_bytes(document))
        self._document = frozen_document
        self._resources = MappingProxyType({str(name): bytes(data) for name, data in resources.items()})
        self.digest = canonical_digest(frozen_document)
        if frozen_document.get("registry_snapshot_version") != "1.0":
            raise PhaseError("registry.unsupported_snapshot")
        if not isinstance(frozen_document.get("entries"), list):
            raise PhaseError("registry.invalid_snapshot")

    @classmethod
    def from_document(cls, document: dict[str, Any], resources: Mapping[str, bytes]) -> "RegistrySnapshot":
        return cls(deepcopy(document), resources)

    def to_document(self) -> dict[str, Any]:
        return json.loads(canonical_bytes(self._document).decode("utf-8"))

    def contract_bindings(self) -> dict[str, dict[str, str]]:
        return {
            f"{entry['id']}@{entry['version']}": {
                "id": entry["id"],
                "version": entry["version"],
                "package_digest": entry["package_digest"],
            }
            for entry in self._document["entries"]
            if entry.get("kind") == "contract"
        }

    def resource_bytes(self, name: str) -> bytes:
        try:
            return self._resources[name]
        except KeyError as exc:
            raise PhaseError("registry.resource_missing", name) from exc

    def _trusted_roots(self) -> set[str]:
        return {
            item["id"]
            for item in self._document.get("trust_roots", [])
            if item.get("enabled") is True and item.get("kind") == "bundled_digest_allowlist"
        }

    def _verify_entry(self, entry: dict[str, Any]) -> None:
        if entry.get("mutable") is not False:
            raise PhaseError("registry.mutable_reference", entry.get("id", "unknown"))
        if entry.get("trust_root_id") not in self._trusted_roots():
            raise PhaseError("registry.untrusted", entry.get("id", "unknown"))
        artifact = entry.get("artifact")
        expected = entry.get("artifact_digest")
        if not isinstance(artifact, str) or digest_bytes(self.resource_bytes(artifact)) != expected:
            raise PhaseError("registry.digest_mismatch", entry.get("id", "unknown"))
        package_artifacts = entry.get("package_artifacts")
        if package_artifacts is not None:
            verified: list[dict[str, str]] = []
            for item in package_artifacts:
                actual = digest_bytes(self.resource_bytes(item["resource"]))
                if actual != item["digest"]:
                    raise PhaseError("registry.digest_mismatch", item["resource"])
                verified.append({"resource": item["resource"], "digest": actual})
            package = {"profile": "phase_contract_package_v1", "artifacts": verified}
            if canonical_digest(package) != entry.get("package_digest"):
                raise PhaseError("registry.digest_mismatch", entry.get("id", "unknown"))

    def _exact_entries(self, *, kind: str, identifier: str, version: str, package_digest: str) -> list[dict[str, Any]]:
        return [
            entry
            for entry in self._document["entries"]
            if entry.get("kind") == kind
            and entry.get("id") == identifier
            and entry.get("version") == version
            and entry.get("package_digest") == package_digest
        ]

    def _resolve_binding(self, *, kind: str, binding: Mapping[str, Any], capability: str) -> dict[str, Any]:
        matches = self._exact_entries(
            kind=kind,
            identifier=str(binding["id"]),
            version=str(binding["version"]),
            package_digest=str(binding["package_digest"]),
        )
        if not matches:
            identity_matches = [
                entry
                for entry in self._document["entries"]
                if entry.get("kind") == kind
                and entry.get("id") == binding["id"]
                and entry.get("version") == binding["version"]
                and entry.get("package_digest") == binding["package_digest"]
            ]
            if identity_matches and any(entry.get("capability") != capability for entry in identity_matches):
                raise PhaseError("registry.capability_mismatch", str(binding["id"]))
            raise PhaseError("registry.entry_not_found", str(binding["id"]))
        if len(matches) != 1:
            raise PhaseError("registry.entry_ambiguous", str(binding["id"]))
        entry = matches[0]
        if entry.get("capability") != capability:
            raise PhaseError("registry.capability_mismatch", str(binding["id"]))
        self._verify_entry(entry)
        return entry

    def _schema_entry(self, schema_ref: str, digest: str | None = None) -> dict[str, Any]:
        matches = [
            entry
            for entry in self._document["entries"]
            if entry.get("kind") == "schema"
            and entry.get("schema_ref") == schema_ref
            and (digest is None or entry.get("artifact_digest") == digest)
        ]
        if not matches:
            raise PhaseError("registry.entry_not_found", schema_ref)
        if len(matches) != 1:
            raise PhaseError("registry.entry_ambiguous", schema_ref)
        self._verify_entry(matches[0])
        if digest is not None and digest_bytes(self.resource_bytes(matches[0]["artifact"])) != digest:
            raise PhaseError("registry.digest_mismatch", schema_ref)
        return matches[0]

    def schema_document(self, schema_ref: str, digest: str | None = None) -> dict[str, Any]:
        entry = self._schema_entry(schema_ref, digest)
        return parse_json_bytes(self.resource_bytes(entry["artifact"]))

    def schema_registry(self) -> Registry:
        registry = Registry()
        for entry in self._document["entries"]:
            if entry.get("kind") != "schema":
                continue
            self._verify_entry(entry)
            schema = parse_json_bytes(self.resource_bytes(entry["artifact"]))
            registry = registry.with_resource(entry["schema_ref"], Resource.from_contents(schema))
        return registry

    def resolve_contract(self, identifier: str, version: str, package_digest: str, *, core_version: str) -> ResolvedContract:
        matches = self._exact_entries(kind="contract", identifier=identifier, version=version, package_digest=package_digest)
        if not matches:
            raise PhaseError("registry.entry_not_found", f"{identifier}@{version}")
        if len(matches) != 1:
            raise PhaseError("registry.entry_ambiguous", f"{identifier}@{version}")
        entry = matches[0]
        self._verify_entry(entry)
        contract = parse_json_bytes(self.resource_bytes(entry["artifact"]))
        if contract.get("identity", {}).get("id") != identifier or contract.get("identity", {}).get("version") != version:
            raise PhaseError("registry.identity_mismatch", identifier)

        compatibility = contract["identity"]["core_compatibility"]
        current = _semver(core_version)
        if current < _semver(compatibility["minimum"]) or current >= _semver(compatibility["maximum_exclusive"]):
            raise PhaseError("contract.core_incompatible", core_version)

        contract_schema = self.schema_document("https://phase-tool.local/schemas/phase-contract.schema.json")
        Draft202012Validator.check_schema(contract_schema)
        errors = sorted(Draft202012Validator(contract_schema, format_checker=FormatChecker()).iter_errors(contract), key=lambda item: list(item.path))
        if errors:
            raise PhaseError("contract.schema_invalid", errors[0].message)

        self._schema_entry(contract["candidate"]["schema_ref"], contract["candidate"]["schema_digest"])
        self._schema_entry(contract["canonical_result"]["result_schema_ref"], contract["canonical_result"]["result_schema_digest"])
        self._schema_entry(contract["canonical_result"]["result_reference_schema_ref"])
        self._schema_entry(contract["evidence"]["receipt_schema_ref"], contract["evidence"]["receipt_schema_digest"])

        mechanism = contract["operation"]["mechanism"]
        if mechanism.get("availability") != "bundled_v1":
            raise PhaseError("mechanism.unavailable", mechanism["id"])
        self._resolve_binding(kind="mechanism", binding=mechanism, capability="mutation_mechanism")
        for declaration in contract["validators"]:
            self._resolve_binding(kind="validator", binding=declaration["binding"], capability="validator")
        for binding in contract["verification"]["validators"]:
            self._resolve_binding(kind="validator", binding=binding, capability="validator")
        self._resolve_binding(kind="path_policy", binding=contract["write_scope"]["default_path_policy"], capability="path_policy")
        for root in contract["write_scope"]["roots"]:
            self._resolve_binding(kind="path_policy", binding=root["path_policy"], capability="path_policy")

        return ResolvedContract(
            document=contract,
            package_digest=package_digest,
            registry_snapshot_digest=self.digest,
            entry=MappingProxyType(deepcopy(entry)),
        )


class BundledRegistry:
    """Loads only package resources; it has no path, import, or network resolver."""

    @staticmethod
    def resources() -> dict[str, bytes]:
        root = package_resources.files("phase_tool").joinpath("data")
        result: dict[str, bytes] = {}

        def visit(node: Any, prefix: str = "") -> None:
            for child in node.iterdir():
                name = f"{prefix}{child.name}"
                if child.is_dir():
                    visit(child, name + "/")
                elif name != _REGISTRY_RESOURCE:
                    result[name] = child.read_bytes()

        visit(root)
        return result

    @staticmethod
    def load() -> RegistrySnapshot:
        root = package_resources.files("phase_tool").joinpath("data")
        document = parse_json_bytes(root.joinpath(_REGISTRY_RESOURCE).read_bytes())
        return RegistrySnapshot.from_document(document, BundledRegistry.resources())
