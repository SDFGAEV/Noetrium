from __future__ import annotations

import hashlib
import os
from pathlib import Path
import threading
from types import TracebackType

if os.name == "nt":
    import ctypes
    from ctypes import wintypes
else:
    import fcntl


class PublicationLockBusy(RuntimeError):
    pass


class PublicationLockUnavailable(RuntimeError):
    pass


_LOCAL_MUTEX_NAMES: set[str] = set()
_LOCAL_MUTEX_GUARD = threading.Lock()


class PublicationLock:
    """Provider-local nonblocking lock for one artifact publication destination."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fd: int | None = None
        self._handle: int | None = None
        self._mutex_name: str | None = None
    def _windows_mutex_name(self) -> str:
        identity = str(self.path.resolve(strict=False)).casefold().encode("utf-8", "surrogatepass")
        return "Local\\ResearchArtifactPublication-" + hashlib.sha256(identity).hexdigest()

    def __enter__(self) -> "PublicationLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            self.path.touch(exist_ok=True)
            mutex_name = self._windows_mutex_name()
            with _LOCAL_MUTEX_GUARD:
                if mutex_name in _LOCAL_MUTEX_NAMES:
                    raise PublicationLockBusy(f"artifact publication lock busy: {self.path}")
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_mutex = kernel32.CreateMutexW
            create_mutex.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
            create_mutex.restype = wintypes.HANDLE
            wait_for_single_object = kernel32.WaitForSingleObject
            wait_for_single_object.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            wait_for_single_object.restype = wintypes.DWORD
            handle = create_mutex(None, False, mutex_name)
            invalid = wintypes.HANDLE(-1).value
            if not handle or handle == invalid:
                raise PublicationLockUnavailable(f"cannot create artifact publication lock: {self.path}")
            result = wait_for_single_object(handle, 0)
            if result == 0x00000102:
                kernel32.CloseHandle(handle)
                raise PublicationLockBusy(f"artifact publication lock busy: {self.path}")
            if result not in {0x00000000, 0x00000080}:
                kernel32.CloseHandle(handle)
                raise PublicationLockUnavailable(f"cannot acquire artifact publication lock: {self.path}")
            self._handle = int(handle)
            self._mutex_name = mutex_name
            with _LOCAL_MUTEX_GUARD:
                _LOCAL_MUTEX_NAMES.add(mutex_name)
            return self
        flags = os.O_RDWR | os.O_CREAT
        fd = os.open(self.path, flags, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(fd)
            raise PublicationLockBusy(f"artifact publication lock busy: {self.path}") from exc
        except OSError as exc:
            os.close(fd)
            raise PublicationLockUnavailable(f"cannot acquire artifact publication lock: {self.path}") from exc
        self._fd = fd
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb
        fd = self._fd
        self._fd = None
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
            return
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        try:
            if not kernel32.ReleaseMutex(handle):
                raise OSError(ctypes.get_last_error(), "failed to release artifact publication mutex")
        finally:
            if self._mutex_name is not None:
                with _LOCAL_MUTEX_GUARD:
                    _LOCAL_MUTEX_NAMES.discard(self._mutex_name)
                self._mutex_name = None
            kernel32.CloseHandle(handle)


def fsync_directory(path: Path) -> None:
    if os.name != "nt":
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        fd = os.open(path, flags)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path),
        0xC0000000,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x02000000,
        None,
    )
    invalid = wintypes.HANDLE(-1).value
    if handle == invalid:
        raise OSError(ctypes.get_last_error(), f"failed to open artifact directory for flush: {path}")
    try:
        if not kernel32.FlushFileBuffers(handle):
            raise OSError(ctypes.get_last_error(), f"failed to flush artifact directory: {path}")
    finally:
        kernel32.CloseHandle(handle)


__all__ = [
    "PublicationLock",
    "PublicationLockBusy",
    "PublicationLockUnavailable",
    "fsync_directory",
]
