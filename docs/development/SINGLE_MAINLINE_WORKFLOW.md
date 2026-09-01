# Single-mainline workflow

Noetrium now uses one canonical platform worktree and one serialized mainline.
Role-owned branches and long-lived role worktrees are retired.

## Canonical state

- The canonical local checkout is `master`.
- The public remote mainline is `main`; `master` is kept as the repository's default-branch alias.
- `main` and `master` must point to the same validated commit after a release change.
- SEM remains a separate downstream project and is never edited from this repository.

## Change protocol

1. Work only in the canonical platform worktree.
2. Serialize writes: one active implementation at a time; reviewers inspect read-only.
3. Keep each commit focused on one semantic change and include its tests and evidence.
4. Run the applicable architecture, contract, and regression gates before pushing.
5. Push the validated tip to both `main` and `master` without recreating role branches.
6. Keep generated caches, experiment state, and downstream project files out of the platform repository.

## Review and recovery

A reviewer may reject a commit with exact evidence, but review does not require another worktree.
If a change is rejected, preserve the rejected commit in Git history and move the canonical tip
forward with a corrective commit or an explicit revert. Never hide a failed experiment by rewriting
published mainline history.
