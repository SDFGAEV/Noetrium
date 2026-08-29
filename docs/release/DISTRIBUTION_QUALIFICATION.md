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

## Container qualification

The release container is also source-bound. Formal builds pass the exact Git SHA into the image:

```bash
docker build --build-arg PLATFORM_SOURCE_SHA="$GIT_SHA" -t "research-platform:$GIT_SHA" -f deploy/Dockerfile .
python scripts/verify_container_image.py "research-platform:$GIT_SHA" \
  --expected-source-sha "$GIT_SHA" --output container-verification.json
```

The verifier rejects a revision-label mismatch, runs the image's non-root `doctor`, checks the installed canonical `research` CLI, and executes the full deterministic reference lifecycle inside the installed container. The receipt records the image ID, source SHA, package/Python versions, lifecycle actions, and command output digests.

The container test does not create domain evidence. Minecraft/model/live qualification remains with the owning Roles and their explicitly allocated server windows.

## Product assurance gate

CI first runs:

```bash
python scripts/product_assurance_gate.py --full --output product-assurance.json
```

This emits one machine-readable receipt and exits nonzero on the first blocking failure. The full gate verifies the L0-L8 taxonomy assignment, the required provider-conformance matrix, the architecture gate and the complete pytest regression. The receipt also records repository, branch, exact HEAD SHA, release source-tree SHA-256, and whether the worktree was clean at evaluation time.

Provider conformance is declared in `tests/PROVIDER_CONFORMANCE.json`. The matrix must contain exactly the durable, environment, model, effect and checkpoint classes and points to first-party behavior/recovery tests that are themselves classified exactly once by `tests/TEST_SYSTEM.json`.

The GitHub workflow runs source-bound product assurance, wheel/sdist qualification, exact-SHA container build/verification, and uploads all receipts for the exact CI source revision.

## Licensing boundary

The SBOM records package license fields as `NOASSERTION` until project ownership selects an explicit OSS license. ROLE 06 does not invent or silently apply a legal license policy. A formal public OSS release therefore still requires ROLE 00/project-owner license selection if no repository `LICENSE` is present.

The container image uses a multi-stage build: source exists only in the builder stage, while the runtime stage installs the built wheel and carries no importable source checkout. Container qualification rejects root runtime users and runs doctor plus the full reference lifecycle with networking disabled.
