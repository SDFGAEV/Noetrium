# JSONL storage concurrency contract

## Authority model

`JsonlLogStore` treats the caller-requested log path as a **logical storage authority**.
The active file may be renamed during rotation, but that rename must never change the
logical identity used for the writer actor or the cross-process guard.

The runtime therefore uses `logical_absolute_path()` rather than `Path.resolve()`.
The former anchors the requested pathname lexically without dereferencing the current
filesystem leaf. This matters on Windows because resolving a file while another process
renames it can observe the renamed file object and return a rotated-segment pathname.

## Typed port coupling

`JsonlLogStore` satisfies the logging sink/query Protocols structurally rather than
nominally inheriting the Protocol classes. The runtime therefore keeps the same typed
`append()`/`query()` contract without adding implementation-to-Protocol inheritance
edges. Composition obtains the normalized authority through `JsonlLogStore.logical_path()`
so path identity has one runtime definition instead of duplicate cross-layer imports.

## Append and rotation

Every append enters one `InterprocessFileLock` derived from the stable active-log path.
Inside that critical section the store checks the byte threshold, performs any required
segment rotation, appends one complete UTF-8 JSON line, flushes the file, and preserves
the directory metadata transitions required by the durability layer.

The storage layer owns rotation ordering. Generic fsync/replace primitives remain owned
by the platform durability subsystem; observability does not broaden or reinterpret their
error semantics.

## Query snapshot semantics

Queries freeze segment device/inode/size boundaries while holding the same writer guard,
then release the guard before scanning bytes. If rotation wins after the snapshot and a
segment identity no longer matches, the query retries from a fresh snapshot rather than
mixing generations. Observation therefore remains downstream of storage authority and
does not block writers for the duration of JSON decoding/filtering.

On Windows, a rename can transiently surface as `PermissionError` between the frozen
metadata snapshot and the subsequent file open. That error is treated exactly like a
stale generation: the query refreezes and retries. The retry is bounded; persistent
permission failure therefore fails closed instead of returning partial evidence. Linux
`PermissionError` remains a hard failure and is never reclassified as a rotation race.

## Regression requirements

Windows and Linux qualification must cover all of the following:

- multiple spawned writers appending and rotating the same log;
- concurrent readers querying while those writers rotate;
- exact preservation of all committed record identities;
- no duplicate records from mixed segment generations;
- stable logical path identity even when a live-leaf `resolve()` would report a renamed
  segment;
- one cross-process guard domain for the active logical log path.

A retry-only change is not sufficient evidence for correctness. A qualifying fix must
show that the lock/actor identity itself cannot drift with a rotating file object.
