# Security policy

Do not publish credentials, private keys, access tokens, host secrets, private runtime profiles, or sensitive experiment evidence in issues, logs, release bundles, or example configuration.

For a suspected vulnerability, prepare a minimal reproduction that identifies the affected platform version/commit and the security boundary involved. Use the repository host's private security-reporting channel when available rather than opening a public issue with exploit details or secrets.

Security fixes must preserve authority boundaries and fail-closed semantics. In particular, missing evidence must not be converted into effect certainty, qualification, readiness, or scientific success merely to restore service.

Before release, run the machine-readable product assurance gate and formal installed-artifact distribution qualification documented in `docs/release/DISTRIBUTION_QUALIFICATION.md`.
