# Distribution qualification

A source-tree test pass is not sufficient release evidence. Formal Python distribution qualification uses:

```bash
python scripts/release_distribution.py <output-directory-outside-repository>
```

The command fails unless the Git worktree is clean. It binds the release to the exact commit SHA and to the governance release source-tree digest, builds exactly one wheel and one sdist, then installs each into a fresh isolated virtual environment with `PYTHONPATH` removed and user site packages disabled.

Each installed artifact must:

- import `research_platform.api` from the isolated environment's `site-packages`;
- expose the installed `research` console script;
- execute the deterministic reference lifecycle `run -> inspect -> stop -> resume -> reconcile -> evidence` successfully;
- preserve durable evidence across command processes.

The formal output includes wheel/sdist artifacts, installed-verification receipts, `SBOM.spdx.json`, `SHA256SUMS`, `DISTRIBUTION_RELEASE_EVIDENCE.json`, and a digest for the evidence document.

The evidence document binds source SHA, branch, release-manifest digest, source-tree SHA-256, Python/package versions, build-command output digests, artifact sizes/checksums, SBOM checksum and installed-verification receipt checksums.

## Product assurance gate

CI first runs:

```bash
python scripts/product_assurance_gate.py --full --output product-assurance.json
```

This emits one machine-readable receipt and exits nonzero on the first blocking failure. The full gate verifies the L0鈥揕8 taxonomy assignment, the required provider-conformance matrix, the architecture gate and the complete pytest regression.

Provider conformance is declared in `tests/PROVIDER_CONFORMANCE.json`. The matrix must contain exactly the durable, environment, model, effect and checkpoint classes and points to first-party behavior/recovery tests that are themselves classified exactly once by `tests/TEST_SYSTEM.json`.

The GitHub workflow then runs formal distribution qualification and uploads both gate evidence and distribution evidence for the exact CI source revision.

## Licensing boundary

The SBOM records package license fields as `NOASSERTION` until project ownership selects an explicit OSS license. ROLE 06 does not invent or silently apply a legal license policy. A formal public OSS release therefore still requires ROLE 00/project-owner license selection if no repository `LICENSE` is present.
