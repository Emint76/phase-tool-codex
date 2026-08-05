from __future__ import annotations

import ctypes
import os
import stat
from pathlib import Path
from typing import Callable

from ..canonical import digest_bytes
from ..errors import PhaseError
from ..paths import _is_reparse_point, _platform_path, safe_relative_locator


def _target_observation(path: Path, reparse_detector: Callable[[Path], bool]) -> dict[str, object]:
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
    with open(_platform_path(path), "rb") as stream:
        data = stream.read()
    return {"known": True, "exists": True, "digest": digest_bytes(data), "length": len(data), "head_token": None}


if os.name == "nt":
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
        if os.name != "nt":
            raise AssertionError("Windows-only authority")
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


def _windows_leaf_descriptor(
    path: Path,
    *,
    create_new: bool,
    locator: str,
    writable: bool = False,
    deny_write_sharing: bool = False,
) -> int:
    if os.name != "nt":
        raise AssertionError("Windows-only leaf authority")
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


class TargetRootLock:
    """Artifact-free cross-process lock bound to the shared target-root authority."""

    def __init__(self, root: Path, scope: str) -> None:
        self.root = Path(root)
        self.scope = scope
        self._descriptor: int | None = None
        self._directory: _WindowsPinnedDirectory | None = None
        self._mutex = None

    def __enter__(self) -> "TargetRootLock":
        if self.root.is_symlink() or _is_reparse_point(self.root):
            raise PhaseError("path.reparse_forbidden", str(self.root))
        root = self.root.resolve(strict=True)
        if os.name == "nt":
            self._directory = _WindowsPinnedDirectory(root, self.scope)
            identity = self._directory.identity()
            mutex_digest = digest_bytes(f"{identity[0]}:{identity[1]}:{identity[2]}:{self.scope}".encode("utf-8")).split(":", 1)[1]
            self._mutex = _kernel32.CreateMutexW(None, False, "Local\\phase-tool-effect-" + mutex_digest)
            if not self._mutex:
                self._directory.close()
                raise OSError(ctypes.get_last_error(), "CreateMutexW failed")
            waited = _kernel32.WaitForSingleObject(self._mutex, _INFINITE)
            if waited not in {_WAIT_OBJECT_0, _WAIT_ABANDONED}:
                self.__exit__()
                raise OSError(int(waited), "WaitForSingleObject failed")
            return self
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        self._descriptor = os.open(root, flags)
        import fcntl

        fcntl.flock(self._descriptor, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_exc: object) -> None:
        if os.name == "nt":
            if self._mutex is not None:
                _kernel32.ReleaseMutex(self._mutex)
                _kernel32.CloseHandle(self._mutex)
                self._mutex = None
            if self._directory is not None:
                self._directory.close()
                self._directory = None
            return
        if self._descriptor is not None:
            import fcntl

            fcntl.flock(self._descriptor, fcntl.LOCK_UN)
            os.close(self._descriptor)
            self._descriptor = None


class TargetAuthority:
    """Create/pin one bounded parent chain, then address the leaf through that authority."""

    def __init__(self, root: Path, locator: str, reparse_detector: Callable[[Path], bool] | None = None) -> None:
        self.locator = safe_relative_locator(locator)
        self.reparse_detector = reparse_detector or _is_reparse_point
        self.root = root.resolve(strict=True)
        self.target = self.root.joinpath(*self.locator.split("/"))
        self.parent_path = self.target.parent
        self.name = self.target.name
        self._handles: list[object] = []
        self.parent_fd: int | None = None
        self._namespace_bindings: list[tuple[Path, tuple[int, int]]] = []
        try:
            self._prepare_and_pin_parent()
        except Exception:
            self.close()
            raise

    def _prepare_and_pin_parent(self) -> None:
        parts = self.locator.split("/")[:-1]
        if os.name == "nt":
            self._handles.append(_WindowsPinnedDirectory(self.root, self.locator))
            current = self.root
            for part in parts:
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
            return
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if self.reparse_detector(self.root):
            raise PhaseError("path.reparse_forbidden", self.locator)
        root_fd = os.open(self.root, flags)
        self._handles.append(root_fd)
        root_info = os.fstat(root_fd)
        self._namespace_bindings.append((self.root, (int(root_info.st_dev), int(root_info.st_ino))))
        parent_fd = root_fd
        current = self.root
        for part in parts:
            current = current / part
            if self.reparse_detector(current):
                raise PhaseError("path.reparse_forbidden", self.locator)
            try:
                child_fd = os.open(part, flags, dir_fd=parent_fd)
            except FileNotFoundError:
                try:
                    os.mkdir(part, 0o700, dir_fd=parent_fd)
                except FileExistsError:
                    pass
                if self.reparse_detector(current):
                    raise PhaseError("path.reparse_forbidden", self.locator)
                child_fd = os.open(part, flags, dir_fd=parent_fd)
            self._handles.append(child_fd)
            child_info = os.fstat(child_fd)
            self._namespace_bindings.append((current, (int(child_info.st_dev), int(child_info.st_ino))))
            parent_fd = child_fd
        self.parent_fd = parent_fd
        if self.target.is_symlink():
            raise PhaseError("path.link_forbidden", self.locator)
        if self.reparse_detector(self.target):
            raise PhaseError("path.reparse_forbidden", self.locator)

    def close(self) -> None:
        for handle in reversed(self._handles):
            if isinstance(handle, int):
                os.close(handle)
            else:
                handle.close()
        self._handles = []
        self.parent_fd = None
        self._namespace_bindings = []

    def assert_namespace_binding(self) -> None:
        if os.name == "nt":
            return
        for path, expected_identity in self._namespace_bindings:
            try:
                current = os.lstat(path)
            except FileNotFoundError as exc:
                raise PhaseError("path.parent_identity_changed", self.locator) from exc
            if not stat.S_ISDIR(current.st_mode):
                raise PhaseError("path.parent_identity_changed", self.locator)
            current_identity = (int(current.st_dev), int(current.st_ino))
            if current_identity != expected_identity:
                raise PhaseError("path.parent_identity_changed", self.locator)

    def observe(self) -> dict[str, object]:
        if os.name == "nt":
            try:
                descriptor = _windows_leaf_descriptor(self.target, create_new=False, locator=self.locator)
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
        if self.parent_fd is None:
            return _target_observation(self.target, self.reparse_detector)
        try:
            info = os.stat(self.name, dir_fd=self.parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return {"known": True, "exists": False, "digest": None, "length": None, "head_token": None}
        if stat.S_ISLNK(info.st_mode):
            raise PhaseError("path.link_forbidden", self.locator)
        if not stat.S_ISREG(info.st_mode):
            return {"known": True, "exists": True, "digest": None, "length": None, "head_token": None}
        flags = os.O_RDONLY | (getattr(os, "O_NOFOLLOW", 0))
        descriptor = os.open(self.name, flags, dir_fd=self.parent_fd)
        try:
            with os.fdopen(os.dup(descriptor), "rb") as stream:
                data = stream.read()
        finally:
            os.close(descriptor)
        return {"known": True, "exists": True, "digest": digest_bytes(data), "length": len(data), "head_token": None}

    def open_exclusive(self) -> int:
        if os.name == "nt":
            return _windows_leaf_descriptor(self.target, create_new=True, locator=self.locator)
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        if os.name != "nt":
            flags |= getattr(os, "O_NOFOLLOW", 0)
            assert self.parent_fd is not None
            return os.open(self.name, flags, 0o600, dir_fd=self.parent_fd)
        raise AssertionError("unreachable")

    def open_existing(self, *, writable: bool = False, deny_write_sharing: bool = False) -> int:
        if os.name == "nt":
            return _windows_leaf_descriptor(
                self.target,
                create_new=False,
                locator=self.locator,
                writable=writable,
                deny_write_sharing=deny_write_sharing,
            )
        flags = (os.O_RDWR if writable else os.O_RDONLY) | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        assert self.parent_fd is not None
        return os.open(self.name, flags, dir_fd=self.parent_fd)

    def readback(self, override: bytes | None, descriptor: int | None = None) -> dict[str, object]:
        if override is not None:
            observed_bytes = override
        elif descriptor is not None:
            observed_bytes = _read_descriptor(descriptor)
        elif self.parent_fd is None:
            opened = _windows_leaf_descriptor(self.target, create_new=False, locator=self.locator)
            try:
                observed_bytes = _read_descriptor(opened)
            finally:
                os.close(opened)
        else:
            descriptor = os.open(self.name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=self.parent_fd)
            try:
                with os.fdopen(os.dup(descriptor), "rb") as stream:
                    observed_bytes = stream.read()
            finally:
                os.close(descriptor)
        return {"known": True, "exists": True, "digest": digest_bytes(observed_bytes), "length": len(observed_bytes), "head_token": None}

    def replace_from(self, source: "TargetAuthority") -> None:
        """Atomically replace this leaf from another pinned leaf authority."""

        if os.name == "nt":
            os.replace(_platform_path(source.target), _platform_path(self.target))
            return
        assert source.parent_fd is not None
        assert self.parent_fd is not None
        os.replace(
            source.name,
            self.name,
            src_dir_fd=source.parent_fd,
            dst_dir_fd=self.parent_fd,
        )

    def link_from(self, source: "TargetAuthority") -> None:
        """Publish this leaf as a create-only hard link to a pinned source leaf."""

        if os.name == "nt":
            os.link(_platform_path(source.target), _platform_path(self.target))
            return
        assert source.parent_fd is not None
        assert self.parent_fd is not None
        os.link(
            source.name,
            self.name,
            src_dir_fd=source.parent_fd,
            dst_dir_fd=self.parent_fd,
            follow_symlinks=False,
        )

    def unlink(self, *, missing_ok: bool = False) -> None:
        """Remove this leaf through its pinned parent authority."""

        try:
            if os.name == "nt":
                os.unlink(_platform_path(self.target))
            else:
                assert self.parent_fd is not None
                os.unlink(self.name, dir_fd=self.parent_fd)
        except FileNotFoundError:
            if not missing_ok:
                raise

    def fsync_parent(self) -> None:
        if self.parent_fd is not None:
            os.fsync(self.parent_fd)
