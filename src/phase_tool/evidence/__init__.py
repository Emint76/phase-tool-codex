from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from ..canonical import canonical_bytes, digest_bytes
from ..errors import PhaseError
from ..paths import _is_reparse_point
from ..registry import RegistrySnapshot

_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def validate_run_id(run_id: str) -> str:
    if not _RUN_ID.fullmatch(run_id) or run_id in {".", ".."}:
        raise PhaseError("evidence.invalid_run_id", run_id)
    return run_id


def _reject_existing_links(path: Path) -> None:
    current = Path(path.anchor) if path.is_absolute() else Path()
    for part in path.parts[1:] if path.is_absolute() else path.parts:
        current = current / part
        if current.exists() and (current.is_symlink() or _is_reparse_point(current)):
            code = "path.link_forbidden" if current.is_symlink() else "path.reparse_forbidden"
            raise PhaseError(code, str(current))


class EvidenceStore:
    def __init__(self, evidence_root: Path, run_id: str) -> None:
        validate_run_id(run_id)
        absolute = evidence_root.absolute()
        _reject_existing_links(absolute)
        absolute.mkdir(parents=True, exist_ok=True)
        _reject_existing_links(absolute)
        self.evidence_root = absolute.resolve(strict=True)
        phase_root = self.evidence_root / ".phase"
        runs_root = phase_root / "runs"
        runs_root.mkdir(parents=True, exist_ok=True)
        self.run_root = runs_root / run_id
        try:
            self.run_root.mkdir()
        except FileExistsError as exc:
            raise PhaseError("evidence.run_exists", run_id) from exc
        self.blob_root = self.run_root / "blobs"
        self.attachment_root = self.run_root / "attachments"
        self.blob_root.mkdir()
        self.attachment_root.mkdir()

    def write_canonical(self, relative: str, value: Any) -> tuple[Path, str]:
        if "/" in relative:
            parent_name, file_name = relative.split("/", 1)
            if parent_name != "attachments" or "/" in file_name:
                raise PhaseError("evidence.invalid_path", relative)
            path = self.attachment_root / file_name
        else:
            path = self.run_root / relative
        data = canonical_bytes(value)
        with path.open("xb", buffering=0) as stream:
            view = memoryview(data)
            written = 0
            while written < len(view):
                count = stream.write(view[written:])
                if count is None or count <= 0:
                    raise PhaseError("evidence.short_write", relative)
                written += count
            stream.flush()
            os.fsync(stream.fileno())
        return path, digest_bytes(data)


def validate_intent(intent: dict[str, Any], registry: RegistrySnapshot) -> None:
    schema = registry.schema_document("https://phase-tool.local/schemas/phase-intent.schema.json")
    Draft202012Validator(schema, registry=registry.schema_registry(), format_checker=FormatChecker()).validate(intent)


def validate_receipt(receipt: dict[str, Any], registry: RegistrySnapshot) -> None:
    schema = registry.schema_document("https://phase-tool.local/schemas/phase-receipt.schema.json")
    Draft202012Validator(schema, registry=registry.schema_registry(), format_checker=FormatChecker()).validate(receipt)
