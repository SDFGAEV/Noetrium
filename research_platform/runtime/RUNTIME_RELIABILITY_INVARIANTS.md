# Runtime & Reliability Invariants

This document records ROLE 02 runtime invariants that are enforced directly by the production contracts in `research_platform/runtime`, `research_platform/resource`, and `research_platform/reliability`.

## Process-command ownership

`ProcessCommandRunnerPort.execute` accepts only a finite positive `timeout_seconds`. The timeout is an end-to-end command budget: structured ASYNC_IO admission is deadline-bound, process execution uses only the budget that remains after admission/spawn, and a separate cleanup reserve is retained so timeout or cancellation can terminate and reap the owned process tree before normal completion is reported.

Callers must wait on the owned task handle itself rather than impose a second `Future.result(timeout=...)` deadline. A detached caller deadline can return failure while the structured task remains eligible to start later, which is forbidden for external effects. `ProcessSupervisorPort.await_exit` and `terminate` likewise require an explicit structured `Deadline`; queue admission and process polling must never exist without a terminal owner budget.

## SSH and remote-operation bounds

Automated SSH commands, SCP transfers, repository operations, and foreground interactive SSH/tmux attaches all have finite profile budgets. Interactive attaches use `ServerConnectionProfile.interactive_timeout_seconds` (environment key `RP_SERVER_<ID>_SSH_INTERACTIVE_TIMEOUT_SECONDS`) rather than an unbounded process wait. The interactive budget is identity-bearing and is included in the composed server profile digest.

## Effect certainty

A timeout, cancellation, network loss, process ownership loss, or other failure after a mutating server operation has been journaled must never be interpreted as `NO_EFFECT`. The server operation ledger keeps such operations effect-uncertain until typed reconciliation evidence resolves the original operation identity. New mutations remain fenced while an unreconciled effect exists.

## Validation expectation

Changes to these invariants require focused Windows tests plus Linux validation for POSIX process-group cleanup and SSH/process behavior. Server validation must use the designated Platform validation host; protected SEM runtime directories, GPU allocations, and model-serving endpoints are outside this subsystem's validation authority.
