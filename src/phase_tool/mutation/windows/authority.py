from __future__ import annotations

import ctypes
import os
import stat
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Callable

from ...canonical import digest_bytes
from ...errors import PhaseError
from ...paths import _is_reparse_point, _platform_path, safe_relative_locator
from ..authority import TargetAuthority
from ..guarantees import GuaranteeProfileBinding, registered_profile_binding

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_EXISTING = 3
_CREATE_NEW = 1
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_FileBasicInfo = 0
_WAIT_OBJECT_0 = 0
_WAIT_ABANDONED = 0x80
_INFINITE = 0xFFFFFFFF


class _FILE_BASIC_INFO(ctypes.Structure):
    _fields_ = [
        ("CreationTime", ctypes.c_longlong),
        ("LastAccessTime", ctypes.c_longlong),
        ("LastWriteTime", ctypes.c_longlong),
        ("ChangeTime", ctypes.c_longlong),
        ("FileAttributes", ctypes.c_ulong),
    ]


class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("FileAttributes", ctypes.c_ulong),
        ("CreationTimeLow", ctypes.c_ulong),
        ("CreationTimeHigh", ctypes.c_ulong),
        ("LastAccessTimeLow", ctypes.c_ulong),
        ("LastAccessTimeHigh", ctypes.c_ulong),
        ("LastWriteTimeLow", ctypes.c_ulong),
        ("LastWriteTimeHigh", ctypes.c_ulong),
        ("VolumeSerialNumber", ctypes.c_ulong),
        ("FileSizeHigh", ctypes.c_ulong),
        ("FileSizeLow", ctypes.c_ulong),
        ("NumberOfLinks", ctypes.c_ulong),
        ("FileIndexHigh", ctypes.c_ulong),
        ("FileIndexLow", ctypes.c_ulong),
    ]


_kernel32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
_kernel32.CreateFileW.restype = ctypes.c_void_p
_kernel32.GetFileInformationByHandleEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong]
_kernel32.GetFileInformationByHandleEx.restype = ctypes.c_int
_kernel32.GetFileInformationByHandle.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_kernel32.GetFileInformationByHandle.restype = ctypes.c_int
_kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
_kernel32.CloseHandle.restype = ctypes.c_int
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
_kernel32.CreateMutexW.restype = ctypes.c_void_p
_kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
_kernel32.WaitForSingleObject.restype = ctypes.c_ulong
_kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
_kernel32.ReleaseMutex.restype = ctypes.c_int


class _WindowsPinnedDirectory:
    def __init__(self, path: Path, locator: str) -> None:
        handle = _kernel32.CreateFileW(
            _platform_path(path),
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
        if not _kernel32.GetFileInformationByHandleEx(handle, _FileBasicInfo, ctypes.byref(info), ctypes.sizeof(info)):
            self.close()
            raise PhaseError("path.parent_missing", locator)
        if info.FileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            self.close()
            raise PhaseError("path.reparse_forbidden", locator)

    def identity(self) -> tuple[int, int, int]:
        info = _BY_HANDLE_FILE_INFORMATION()
        if not _kernel32.GetFileInformationByHandle(self.handle, ctypes.byref(info)):
            raise OSError(ctypes.get_last_error(), "GetFileInformationByHandle failed")
        return info.VolumeSerialNumber, info.FileIndexHigh, info.FileIndexLow

    def close(self) -> None:
        if self.handle is not None:
            _kernel32.CloseHandle(self.handle)
            self.handle = None


def _read_descriptor(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _leaf_descriptor(
    path: Path,
    *,
    create_new: bool,
    locator: str,
    writable: bool = False,
    deny_write_sharing: bool = False,
) -> int:
    access = _GENERIC_READ | (_GENERIC_WRITE if create_new or writable else 0)
    creation = _CREATE_NEW if create_new else _OPEN_EXISTING
    handle = _kernel32.CreateFileW(
        _platform_path(path),
        access,
        _FILE_SHARE_READ | (0 if deny_write_sharing else _FILE_SHARE_WRITE),
        None,
        creation,
        _FILE_ATTRIBUTE_NORMAL | _FILE_FLAG_OPEN_REPARSE_POINT | (0 if create_new else _FILE_FLAG_BACKUP_SEMANTICS),
        None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        error = ctypes.get_last_error()
        if create_new and error in {80, 183}:
            raise FileExistsError(error, "target exists", str(path))
        if not create_new and error in {2, 3}:
            raise FileNotFoundError(error, "target missing", str(path))
        raise OSError(error, "CreateFileW failed", str(path))
    try:
        info = _FILE_BASIC_INFO()
        if not _kernel32.GetFileInformationByHandleEx(handle, _FileBasicInfo, ctypes.byref(info), ctypes.sizeof(info)):
            raise OSError(ctypes.get_last_error(), "GetFileInformationByHandleEx failed", str(path))
        if info.FileAttributes & _FILE_ATTRIBUTE_REPARSE_POINT:
            code = "path.link_forbidden" if path.is_symlink() else "path.reparse_forbidden"
            raise PhaseError(code, locator)
        if info.FileAttributes & _FILE_ATTRIBUTE_DIRECTORY:
            raise PhaseError("path.special_forbidden", locator)
        import msvcrt

        flags = os.O_RDWR if create_new or writable else os.O_RDONLY
        flags |= getattr(os, "O_BINARY", 0)
        descriptor = msvcrt.open_osfhandle(int(handle), flags)
        handle = None
        return descriptor
    finally:
        if handle not in {None, _INVALID_HANDLE_VALUE}:
            _kernel32.CloseHandle(handle)


class WindowsTargetRootLock:
    def __init__(self, root: Path, scope: str) -> None:
        self.root = Path(root)
        self.scope = scope
        self._directory: _WindowsPinnedDirectory | None = None
        self._mutex = None

    def __enter__(self) -> "WindowsTargetRootLock":
        if self.root.is_symlink() or _is_reparse_point(self.root):
            raise PhaseError("path.reparse_forbidden", str(self.root))
        root = self.root.resolve(strict=True)
        self._directory = _WindowsPinnedDirectory(root, self.scope)
        try:
            identity = self._directory.identity()
            mutex_digest = digest_bytes(f"{identity[0]}:{identity[1]}:{identity[2]}:{self.scope}".encode("utf-8")).split(":", 1)[1]
            self._mutex = _kernel32.CreateMutexW(None, False, "Local\\phase-tool-effect-" + mutex_digest)
            if not self._mutex:
                raise OSError(ctypes.get_last_error(), "CreateMutexW failed")
            waited = _kernel32.WaitForSingleObject(self._mutex, _INFINITE)
            if waited not in {_WAIT_OBJECT_0, _WAIT_ABANDONED}:
                raise OSError(int(waited), "WaitForSingleObject failed")
            return self
        except Exception:
            if self._mutex is not None:
                _kernel32.CloseHandle(self._mutex)
                self._mutex = None
            self._directory.close()
            self._directory = None
            raise

    def __exit__(self, *_exc: object) -> None:
        if self._mutex is not None:
            _kernel32.ReleaseMutex(self._mutex)
            _kernel32.CloseHandle(self._mutex)
            self._mutex = None
        if self._directory is not None:
            self._directory.close()
            self._directory = None


class WindowsTargetAuthority:
    def __init__(
        self,
        root: Path,
        locator: str,
        reparse_detector: Callable[[Path], bool] | None = None,
        expected_root_identity: tuple[int, int] | None = None,
    ) -> None:
        self.locator = safe_relative_locator(locator)
        self.reparse_detector = reparse_detector or _is_reparse_point
        self.root = root.resolve(strict=True)
        self.target = self.root.joinpath(*self.locator.split("/"))
        self.parent_path = self.target.parent
        self.name = self.target.name
        self.parent_fd: int | None = None
        self._handles: list[_WindowsPinnedDirectory] = []
        try:
            self._prepare_and_pin_parent(expected_root_identity)
        except Exception:
            self.close()
            raise

    def _prepare_and_pin_parent(self, expected_root_identity: tuple[int, int] | None) -> None:
        root_handle = _WindowsPinnedDirectory(self.root, self.locator)
        self._handles.append(root_handle)
        volume, high, low = root_handle.identity()
        root_identity = (int(volume), (int(high) << 32) | int(low))
        if expected_root_identity is not None and root_identity != expected_root_identity:
            raise PhaseError("broker.root_identity_mismatch")
        current = self.root
        for part in self.locator.split("/")[:-1]:
            current = current / part
            try:
                os.mkdir(_platform_path(current))
            except FileExistsError:
                pass
            if current.is_symlink():
                raise PhaseError("path.link_forbidden", self.locator)
            if self.reparse_detector(current):
                raise PhaseError("path.reparse_forbidden", self.locator)
            if not current.is_dir():
                raise PhaseError("path.parent_missing", self.locator)
            self._handles.append(_WindowsPinnedDirectory(current, self.locator))
        if self.target.is_symlink():
            raise PhaseError("path.link_forbidden", self.locator)
        if self.reparse_detector(self.target):
            raise PhaseError("path.reparse_forbidden", self.locator)

    def close(self) -> None:
        for handle in reversed(self._handles):
            handle.close()
        self._handles = []

    def assert_namespace_binding(self) -> None:
        return None

    def observe(self) -> dict[str, object]:
        try:
            descriptor = _leaf_descriptor(self.target, create_new=False, locator=self.locator)
        except FileNotFoundError:
            if os.path.lexists(self.target):
                if self.target.is_symlink():
                    raise PhaseError("path.link_forbidden", self.locator)
                if self.reparse_detector(self.target):
                    raise PhaseError("path.reparse_forbidden", self.locator)
                info = self.target.lstat()
                if not stat.S_ISREG(info.st_mode):
                    return {"known": True, "exists": True, "digest": None, "length": None, "head_token": None}
            return {"known": True, "exists": False, "digest": None, "length": None, "head_token": None}
        except PhaseError as exc:
            if exc.code == "path.special_forbidden":
                return {"known": True, "exists": True, "digest": None, "length": None, "head_token": None}
            raise
        try:
            data = _read_descriptor(descriptor)
        finally:
            os.close(descriptor)
        return {"known": True, "exists": True, "digest": digest_bytes(data), "length": len(data), "head_token": None}

    def open_exclusive(self) -> int:
        return _leaf_descriptor(self.target, create_new=True, locator=self.locator)

    def open_existing(self, *, writable: bool = False, deny_write_sharing: bool = False) -> int:
        return _leaf_descriptor(
            self.target,
            create_new=False,
            locator=self.locator,
            writable=writable,
            deny_write_sharing=deny_write_sharing,
        )

    def read_bytes(self, descriptor: int | None = None) -> bytes:
        opened = descriptor if descriptor is not None else self.open_existing()
        try:
            return _read_descriptor(opened)
        finally:
            if descriptor is None:
                os.close(opened)

    def readback(self, override: bytes | None, descriptor: int | None = None) -> dict[str, object]:
        observed_bytes = override if override is not None else self.read_bytes(descriptor)
        return {"known": True, "exists": True, "digest": digest_bytes(observed_bytes), "length": len(observed_bytes), "head_token": None}

    def replace_from(self, source: TargetAuthority) -> None:
        os.replace(_platform_path(source.target), _platform_path(self.target))

    def link_from(self, source: TargetAuthority) -> None:
        os.link(_platform_path(source.target), _platform_path(self.target))

    def unlink(self, *, missing_ok: bool = False) -> None:
        try:
            os.unlink(_platform_path(self.target))
        except FileNotFoundError:
            if not missing_ok:
                raise

    def fsync_parent(self) -> None:
        return None


class WindowsAuthorityProvider:
    def guarantee_profile_binding(self) -> GuaranteeProfileBinding:
        return registered_profile_binding("phase.windows.authority.v1@1.0.0")

    def open_authority(
        self,
        root: Path,
        locator: str,
        reparse_detector: Callable[[Path], bool] | None = None,
        expected_root_identity: tuple[int, int] | None = None,
    ) -> WindowsTargetAuthority:
        return WindowsTargetAuthority(root, locator, reparse_detector, expected_root_identity)

    def lock_target_root(self, root: Path, scope: str) -> AbstractContextManager[object]:
        return WindowsTargetRootLock(root, scope)
