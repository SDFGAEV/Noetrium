from __future__ import annotations

import ctypes
import errno
import math
import os
import select
import struct
import sys
from pathlib import Path

from research_platform.reliability.forensics.providers.hashchain_core import stat_signature


# Linux inotify constants.  They are kept local so the provider has no third-party
# dependency and can use the same state model on the server and on developer hosts.
_IN_CREATE = 0x00000100
_IN_DELETE = 0x00000200
_IN_MOVED_FROM = 0x00000040
_IN_MOVED_TO = 0x00000080
_IN_DELETE_SELF = 0x00000400
_IN_MOVE_SELF = 0x00000800
_IN_UNMOUNT = 0x00002000
_IN_Q_OVERFLOW = 0x00004000
_IN_IGNORED = 0x00008000
_INOTIFY_EVENT = struct.Struct("<iIII")
_DIRECTORY_WATCH_MASK = (
    _IN_CREATE
    | _IN_DELETE
    | _IN_MOVED_FROM
    | _IN_MOVED_TO
    | _IN_DELETE_SELF
    | _IN_MOVE_SELF
)
_DIRECTORY_MUTATION_MASK = (
    _DIRECTORY_WATCH_MASK
    | _IN_UNMOUNT
    | _IN_Q_OVERFLOW
    | _IN_IGNORED
)


_FILE_NOTIFY_CHANGE_FILE_NAME = 0x00000001
_FILE_NOTIFY_CHANGE_DIR_NAME = 0x00000002
_WAIT_OBJECT_0 = 0x00000000
_WAIT_TIMEOUT = 0x00000102
_WAIT_FAILED = 0xFFFFFFFF
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


def _open_windows_directory_watch(root: Path) -> int | None:
    if sys.platform != "win32":
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    find_first = kernel32.FindFirstChangeNotificationW
    find_first.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.c_uint32]
    find_first.restype = ctypes.c_void_p
    handle = find_first(str(root), 0, _FILE_NOTIFY_CHANGE_FILE_NAME | _FILE_NOTIFY_CHANGE_DIR_NAME)
    value = ctypes.cast(handle, ctypes.c_void_p).value
    if value in (None, _INVALID_HANDLE_VALUE):
        error = ctypes.get_last_error()
        raise OSError(error, "failed to open Windows directory change notification", str(root))
    return int(value)


def _open_linux_directory_watch(root: Path) -> int | None:
    """Open a non-blocking inotify watch, or return None when unavailable."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        init = getattr(libc, "inotify_init1")
        add_watch = getattr(libc, "inotify_add_watch")
        init.argtypes = [ctypes.c_int]
        init.restype = ctypes.c_int
        add_watch.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
        add_watch.restype = ctypes.c_int
        flags = os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
        fd = int(init(flags))
        if fd < 0:
            return None
        watch = int(add_watch(fd, os.fsencode(root), _DIRECTORY_WATCH_MASK))
        if watch < 0:
            os.close(fd)
            return None
        return fd
    except (AttributeError, OSError, TypeError):
        return None


class DirectoryChangeSignal:
    """Detect directory-entry mutations without enumerating the directory.

    Linux uses inotify and Windows uses a kernel change-notification handle.
    Other platforms use directory stat only as a portability fallback.  The caller owns the
    authoritative expected signature; this object only owns the event cursor and
    a fail-closed pending bit.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self._fd = _open_linux_directory_watch(root)
        self._windows_handle = _open_windows_directory_watch(root)
        self._pending = False
        self._close_error: OSError | None = None

    @property
    def mode(self) -> str:
        if self._fd is not None:
            return "inotify"
        if self._windows_handle is not None:
            return "windows-notify"
        return "stat"

    def _drain_events(self) -> bool:
        if self._fd is None:
            return False
        changed = False
        while True:
            try:
                data = os.read(self._fd, 64 * 1024)
            except BlockingIOError:
                return changed
            except OSError as exc:
                if exc.errno == errno.EINTR:
                    continue
                self._pending = True
                return True
            if not data:
                return changed
            offset = 0
            while offset < len(data):
                if len(data) - offset < _INOTIFY_EVENT.size:
                    self._pending = True
                    return True
                _watch_descriptor, mask, _cookie, name_length = _INOTIFY_EVENT.unpack_from(
                    data, offset
                )
                record_length = _INOTIFY_EVENT.size + name_length
                if record_length > len(data) - offset:
                    self._pending = True
                    return True
                if mask & _DIRECTORY_MUTATION_MASK:
                    changed = True
                offset += record_length

    def _windows_changed(self, timeout_ms: int = 0) -> bool:
        handle = self._windows_handle
        if handle is None:
            return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        wait = kernel32.WaitForSingleObject
        wait.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        wait.restype = ctypes.c_uint32
        result = int(wait(ctypes.c_void_p(handle), timeout_ms))
        if result == _WAIT_OBJECT_0:
            return True
        if result == _WAIT_TIMEOUT:
            return False
        if result == _WAIT_FAILED:
            error = ctypes.get_last_error()
            raise OSError(error, "Windows directory change notification wait failed", str(self.root))
        raise OSError(f"unexpected Windows wait result: {result}")

    def changed_since(
        self,
        expected_signature: tuple[int, int, int, int] | None,
    ) -> bool:
        """Return whether an unacknowledged external mutation is observable."""
        if self._pending:
            return True
        if self._drain_events():
            self._pending = True
            return True
        if self._windows_changed():
            self._pending = True
            return True
        if self._fd is None and self._windows_handle is None and stat_signature(self.root) != expected_signature:
            self._pending = True
            return True
        return False

    def wait_changed_since(
        self,
        expected_signature: tuple[int, int, int, int] | None,
        *,
        timeout_seconds: float,
    ) -> bool:
        """Boundedly await one directory mutation without weakening the pending latch."""
        if isinstance(timeout_seconds, bool) or not math.isfinite(float(timeout_seconds)) or timeout_seconds < 0:
            raise ValueError("directory change wait must be finite and non-negative")
        if self.changed_since(expected_signature) or timeout_seconds == 0:
            return self._pending
        if self._windows_handle is not None:
            timeout_ms = min(0xFFFFFFFE, max(1, math.ceil(timeout_seconds * 1000.0)))
            if self._windows_changed(timeout_ms):
                self._pending = True
                return True
            return False
        if self._fd is not None:
            readable, _, _ = select.select((self._fd,), (), (), timeout_seconds)
            if readable and self._drain_events():
                self._pending = True
                return True
            return self._pending
        return self.changed_since(expected_signature)

    def acknowledge(self) -> None:
        """Consume mutations caused by the owning writer and clear the latch."""
        self._drain_events()
        if self._windows_handle is not None and self._windows_changed():
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            advance = kernel32.FindNextChangeNotification
            advance.argtypes = [ctypes.c_void_p]
            advance.restype = ctypes.c_int
            if not advance(ctypes.c_void_p(self._windows_handle)):
                error = ctypes.get_last_error()
                raise OSError(error, "failed to advance Windows directory change notification", str(self.root))
        self._pending = False

    def close(self) -> None:
        fd, self._fd = self._fd, None
        if fd is not None:
            try:
                os.close(fd)
            except OSError as exc:
                self._close_error = exc
                raise
        handle, self._windows_handle = self._windows_handle, None
        if handle is not None:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            close = kernel32.FindCloseChangeNotification
            close.argtypes = [ctypes.c_void_p]
            close.restype = ctypes.c_int
            if not close(ctypes.c_void_p(handle)):
                error = ctypes.get_last_error()
                exc = OSError(error, "failed to close Windows directory change notification", str(self.root))
                self._close_error = exc
                raise exc

    def __del__(self) -> None:
        try:
            self.close()
        except Exception as exc:
            if isinstance(exc, OSError):
                self._close_error = exc


__all__ = ["DirectoryChangeSignal"]
