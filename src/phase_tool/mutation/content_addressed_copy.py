from __future__ import annotations

import os
import stat
import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..canonical import digest_bytes
from ..errors import PhaseError
from ..paths import _is_reparse_point, contained_target_path, safe_relative_locator

_MAX_CONTENT_BYTES = 16 * 1024 * 1024


if os.name == "nt":
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _GENERIC_READ = 0x80000000
    _FILE_SHARE_READ = 0x00000001
    _FILE_SHARE_WRITE = 0x00000002
    _OPEN_EXISTING = 3
    _FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _FileBasicInfo = 0

    class _FILE_BASIC_INFO(ctypes.Structure):
        _fields_ = [
            ("CreationTime", ctypes.c_longlong),
            ("LastAccessTime", ctypes.c_longlong),
            ("LastWriteTime", ctypes.c_longlong),
            ("ChangeTime", ctypes.c_longlong),
            ("FileAttributes", ctypes.c_ulong),
        ]

    _kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
    ]
    _kernel32.CreateFileW.restype = ctypes.c_void_p
    _kernel32.GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
    _kernel32.GetFileInformationByHandleEx.restype = ctypes.c_int
    _kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    _kernel32.CloseHandle.restype = ctypes.c_int


@dataclass(frozen=True)
class ContentAddressedCopyFaults:
    maximum_write_size: int | None = None
    fail_after_bytes: int | None = None
    readback_override: bytes | None = None
    readback_error: bool = False
    reparse_detector: Callable[[Path], bool] | None = None
    write_primitive: Callable[[int, memoryview], int] | None = None
    before_exclusive_create: Callable[[Path], None] | None = None


def _unknown() -> dict[str, object]:
    return {"known": False, "exists": None, "digest": None, "length": None, "head_token": None}


def _observe(path: Path, reparse_detector: Callable[[Path], bool]) -> dict[str, object]:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"known": True, "exists": False, "digest": None, "length": None, "head_token": None}
    if path.is_symlink():
        raise PhaseError("path.link_forbidden", str(path))
    if reparse_detector(path):
        raise PhaseError("path.reparse_forbidden", str(path))
    if not stat.S_ISREG(info.st_mode):
        return {"known": True, "exists": True, "digest": None, "length": None, "head_token": None}
    data = path.read_bytes()
    return {"known": True, "exists": True, "digest": digest_bytes(data), "length": len(data), "head_token": None}


def _observe_at(parent_fd: int, name: str, reparse_detector: Callable[[Path], bool], fallback_path: Path) -> dict[str, object]:
    if os.name == "nt":
        return _observe(fallback_path, reparse_detector)
    try:
        info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return {"known": True, "exists": False, "digest": None, "length": None, "head_token": None}
    if stat.S_ISLNK(info.st_mode):
        raise PhaseError("path.link_forbidden", str(fallback_path))
    if not stat.S_ISREG(info.st_mode):
        return {"known": True, "exists": True, "digest": None, "length": None, "head_token": None}
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(name, flags, dir_fd=parent_fd)
    try:
        data = b""
        with os.fdopen(os.dup(descriptor), "rb") as stream:
            data = stream.read()
    finally:
        os.close(descriptor)
    return {"known": True, "exists": True, "digest": digest_bytes(data), "length": len(data), "head_token": None}


class _WindowsDirectoryHandle:
    def __init__(self, path: Path, locator: str) -> None:
        handle = _kernel32.CreateFileW(
            str(path),
            _GENERIC_READ,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if handle == _INVALID_HANDLE_VALUE:
            raise PhaseError("path.parent_missing", locator)
        self.handle = handle
        info = _FILE_BASIC_INFO()
        ok = _kernel32.GetFileInformationByHandleEx(handle, _FileBasicInfo, ctypes.byref(info), ctypes.sizeof(info))
        if not ok:
            self.close()
            raise PhaseError("path.parent_missing", locator)
        if info.FileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            self.close()
            raise PhaseError("path.reparse_forbidden", locator)

    def close(self) -> None:
        if self.handle is not None:
            _kernel32.CloseHandle(self.handle)
            self.handle = None


class _TargetAuthority:
    def __init__(self, root: Path, locator: str, reparse_detector: Callable[[Path], bool]) -> None:
        self.locator = safe_locator = safe_relative_locator(locator)
        self.reparse_detector = reparse_detector
        self.root = root.resolve(strict=True)
        self.target = contained_target_path(self.root, safe_locator, reparse_detector=reparse_detector)
        self.parent_path = self.target.parent
        self.name = self.target.name
        self._handles: list[object] = []
        self.parent_fd: int | None = None
        try:
            self._pin_parent()
        except Exception:
            self.close()
            raise

    def _pin_parent(self) -> None:
        parts = self.locator.split("/")[:-1]
        if os.name == "nt":
            self._handles.append(_WindowsDirectoryHandle(self.root, self.locator))
            current = self.root
            for part in parts:
                current = current / part
                if not current.is_dir():
                    raise PhaseError("path.parent_missing", self.locator)
                if current.is_symlink() or self.reparse_detector(current):
                    raise PhaseError("path.reparse_forbidden" if self.reparse_detector(current) else "path.link_forbidden", self.locator)
                self._handles.append(_WindowsDirectoryHandle(current, self.locator))
            return
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        root_fd = os.open(self.root, flags)
        self._handles.append(root_fd)
        parent_fd = root_fd
        for part in parts:
            child_fd = os.open(part, flags, dir_fd=parent_fd)
            self._handles.append(child_fd)
            parent_fd = child_fd
        self.parent_fd = parent_fd

    def observe(self) -> dict[str, object]:
        if self.parent_fd is None:
            return _observe(self.target, self.reparse_detector)
        return _observe_at(self.parent_fd, self.name, self.reparse_detector, self.target)

    def open_exclusive(self) -> int:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if self.parent_fd is None:
            return os.open(self.target, flags, 0o600)
        return os.open(self.name, flags, 0o600, dir_fd=self.parent_fd)

    def readback(self, override: bytes | None) -> dict[str, object]:
        if override is not None:
            observed_bytes = override
        elif self.parent_fd is None:
            observed_bytes = self.target.read_bytes()
        else:
            flags = os.O_RDONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(self.name, flags, dir_fd=self.parent_fd)
            try:
                with os.fdopen(os.dup(descriptor), "rb") as stream:
                    observed_bytes = stream.read()
            finally:
                os.close(descriptor)
        return {"known": True, "exists": True, "digest": digest_bytes(observed_bytes), "length": len(observed_bytes), "head_token": None}

    def fsync_parent(self) -> None:
        if self.parent_fd is not None:
            os.fsync(self.parent_fd)
        else:
            _fsync_directory_best_effort(self.parent_path)

    def close(self) -> None:
        for handle in reversed(self._handles):
            if isinstance(handle, int):
                os.close(handle)
            else:
                handle.close()
        self._handles = []

def _receipt(
    effect: dict[str, object],
    *,
    run_id: str,
    timestamp: str,
    status: str,
    attempted: bool,
    before: dict[str, object],
    after: dict[str, object],
    bytes_written: int | None,
    verification_refs: list[str],
    error_code: str | None,
    error_message: str | None = None,
) -> dict[str, object]:
    return {
        "effect_receipt_version": "1.0",
        "run_id": run_id,
        "effect_id": effect["effect_id"],
        "kind": effect["kind"],
        "status": status,
        "attempted": attempted,
        "before": before,
        "after": after,
        "bytes_written": bytes_written,
        "verification_refs": verification_refs,
        "error": None if error_code is None else {"code": error_code, "message": error_message or error_code},
        "started_at": timestamp,
        "finished_at": timestamp,
    }


def _same_content(observation: dict[str, object], effect: dict[str, object]) -> bool:
    return observation.get("digest") == effect["content_digest"] and observation.get("length") == effect["content_length"]


def _fsync_directory_best_effort(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def execute_content_addressed_copy(
    effect: dict[str, object],
    target_root: Path,
    content: bytes,
    *,
    run_id: str,
    timestamp: str,
    faults: ContentAddressedCopyFaults | None = None,
) -> dict[str, object]:
    active = faults or ContentAddressedCopyFaults()
    if len(content) > _MAX_CONTENT_BYTES:
        raise PhaseError("mechanism.content_too_large")
    if len(content) != effect["content_length"] or digest_bytes(content) != effect["content_digest"]:
        raise PhaseError("mechanism.content_binding_mismatch")
    expected_locator = "objects/" + str(effect["content_digest"]).split(":", 1)[1]
    if effect["target"]["relative_locator"] != expected_locator:  # type: ignore[index]
        raise PhaseError("mechanism.locator_digest_mismatch")
    detector = active.reparse_detector or _is_reparse_point
    authority = _TargetAuthority(
        target_root,
        str(effect["target"]["relative_locator"]),  # type: ignore[index]
        detector,
    )
    target = authority.target
    try:
        before = authority.observe()
    except Exception:
        authority.close()
        raise
    if before["exists"] is True:
        authority.close()
        if _same_content(before, effect):
            return _receipt(
                effect,
                run_id=run_id,
                timestamp=timestamp,
                status="applied_verified",
                attempted=True,
                before=before,
                after=before,
                bytes_written=0,
                verification_refs=["target.before", "target.existing_content"],
                error_code=None,
            )
        return _receipt(
            effect,
            run_id=run_id,
            timestamp=timestamp,
            status="failed_no_effect",
            attempted=True,
            before=before,
            after=before,
            bytes_written=0,
            verification_refs=["target.before", "target.unchanged"],
            error_code="target.same_key_conflict",
        )
    if active.before_exclusive_create is not None:
        try:
            active.before_exclusive_create(target)
        except Exception:
            authority.close()
            raise
    descriptor: int | None = None
    written = 0
    try:
        descriptor = authority.open_exclusive()
        view = memoryview(content)
        writer = active.write_primitive or os.write
        while written < len(content):
            if active.fail_after_bytes is not None and written >= active.fail_after_bytes:
                raise OSError("injected failure after target creation")
            count = len(content) - written
            if active.maximum_write_size is not None:
                if active.maximum_write_size <= 0:
                    raise OSError("injected zero-length write")
                count = min(count, active.maximum_write_size)
            if active.fail_after_bytes is not None:
                count = min(count, active.fail_after_bytes - written)
                if count <= 0:
                    raise OSError("injected failure after target creation")
            actual = writer(descriptor, view[written : written + count])
            if actual <= 0:
                raise OSError("short write made no progress")
            written += actual
        os.fsync(descriptor)
        authority.fsync_parent()
    except FileExistsError:
        try:
            after = authority.observe()
        except Exception:
            authority.close()
            raise
        authority.close()
        if _same_content(after, effect):
            return _receipt(
                effect,
                run_id=run_id,
                timestamp=timestamp,
                status="applied_verified",
                attempted=True,
                before=before,
                after=after,
                bytes_written=0,
                verification_refs=["target.after", "target.existing_content"],
                error_code=None,
            )
        return _receipt(
            effect,
            run_id=run_id,
            timestamp=timestamp,
            status="failed_no_effect",
            attempted=True,
            before=before,
            after=after,
            bytes_written=0,
            verification_refs=["target.after"],
            error_code="target.same_key_conflict",
        )
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
            descriptor = None
        try:
            after = authority.observe()
        except (OSError, PhaseError):
            after = _unknown()
        authority.close()
        effect_observed = after.get("exists") is True
        return _receipt(
            effect,
            run_id=run_id,
            timestamp=timestamp,
            status="failed_partial" if effect_observed else "failed_no_effect",
            attempted=True,
            before=before,
            after=after,
            bytes_written=written,
            verification_refs=["target.after"] if after["known"] else [],
            error_code="mechanism.write_failed",
            error_message=str(exc),
        )
    finally:
        if descriptor is not None:
            os.close(descriptor)
    try:
        if active.readback_error:
            raise OSError("injected read-back failure")
        after = authority.readback(active.readback_override)
    except OSError as exc:
        authority.close()
        return _receipt(
            effect,
            run_id=run_id,
            timestamp=timestamp,
            status="indeterminate",
            attempted=True,
            before=before,
            after=_unknown(),
            bytes_written=written,
            verification_refs=[],
            error_code="verification.readback_failed",
            error_message=str(exc),
        )
    authority.close()
    verified = _same_content(after, effect)
    return _receipt(
        effect,
        run_id=run_id,
        timestamp=timestamp,
        status="applied_verified" if verified else "applied_unverified",
        attempted=True,
        before=before,
        after=after,
        bytes_written=written,
        verification_refs=["target.readback"],
        error_code=None if verified else "verification.result_mismatch",
    )
