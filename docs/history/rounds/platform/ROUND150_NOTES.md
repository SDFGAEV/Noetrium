# Platform Round 150 Notes

Date: 2026-08-30

## Deadline/cancellation race closure

`_OwnedTaskHandle.result()` now preserves the logical deadline authority when the provider future is cancelled during the tiny residual wait after an initial bounded `Future.result()` timeout. The residual branch reconciles the task record and surfaces `TaskDeadlineExceeded` when the deadline watcher has already committed that failure, instead of leaking provider-level `concurrent.futures.CancelledError`.

A deterministic regression uses a fake raw handle that times out on the first wait and cancels on the residual wait, reproducing the exact race window without scheduler timing dependence.

## Verification

Verification results are recorded in the ROLE01 handoff for the exact candidate containing this fix.
