from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GuaranteeProfileBinding:
    id: str
    version: str
    descriptor_digest: str
    implementation_id: str
    implementation_version: str
    implementation_artifact_digest: str

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "version": self.version,
            "descriptor_digest": self.descriptor_digest,
        }


def registered_profile_binding(key: str) -> GuaranteeProfileBinding:
    from ..registry import BundledRegistry

    registry = BundledRegistry.load()
    exact = registry.guarantee_profile_bindings()[key]
    descriptor = registry.resolve_guarantee_profile(exact)
    implementation = descriptor["implementation"]
    return GuaranteeProfileBinding(
        id=exact["id"],
        version=exact["version"],
        descriptor_digest=exact["descriptor_digest"],
        implementation_id=implementation["id"],
        implementation_version=implementation["version"],
        implementation_artifact_digest=implementation["artifact_digest"],
    )
