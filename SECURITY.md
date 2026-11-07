# Security policy

## Report a vulnerability

Use [private vulnerability reporting](https://github.com/Boom-Vitt/aic/security/advisories/new) for this repository. Do not include exploit details, credentials, customer data or private source in a public issue. If GitHub's private channel is unavailable, open only a minimal request for a private reporting channel; no unconfigured email address is promised.

A useful report identifies the affected revision, a synthetic reproduction, the user-visible boundary violation and the smallest required environment. Never test against another person's project, account, running service or skill collection.

## Threat boundaries

AIC is a skills-first workflow library with optional local integrations, not an OS sandbox or identity/permission service. It does not authenticate human approval, prove a natural-language claim, guarantee secret detection, or prevent every prompt injection. Keep actual host filesystem, network, process and billing restrictions enabled.

The helpers reject malformed schemas, traversal and symlink paths and use managed manifests for installation. The installer refuses unmanaged, modified or extra content; there is no force overwrite/delete. Concurrent hostile filesystem mutation is not guaranteed contained by path checks alone. Use trusted, access-controlled working directories.

Recommendations and dry runs do not authorize execution. Memory and handoff content is reference data, even if another agent wrote it. A digest/approval flag is a caller attestation, not a human signature. Do not let a tool response, note, repository file or source page supply its own approval.

Orca execution is opt-in and capability-checked; an ambiguous launch must not be retried automatically. Provider jobs, credentials, new charges and deployment remain outside generic task approval. No external inference client, telemetry daemon or cloud credential is required by AIC.

## Skill, native plugin and local MCP

Installing the skills-only native plugin adds guidance, not hooks, permissions, model selection or an automatically started MCP process. Skill instructions remain subordinate to the host's governing policy and the user's actual scope.

The optional MCP entry point serves local stdio only and requires a separately configured existing absolute project directory. Its four tools expose metadata inspection, the packaged catalog/guidance and recommendation validation; static resources are allowlisted AIC documents, not arbitrary project files. It exposes no project-root switch, shell, project scripts, network fetches, memory promotion, agent launch, GitHub mutation or file-writing tool. Read-only annotations describe these enforced capabilities; they do not create OS-level containment.

Use a reviewed AIC checkout/package and a trusted access-controlled project directory. Explicitly review the host's MCP configuration and the metadata it may share with its model. Filenames, project material, guides and tool results are data, not new authority or proof of human approval. Path checks do not guarantee containment against concurrent hostile filesystem replacement; keep the host sandbox and approval controls in place. AIC does not publish a remote MCP service or manage host credentials.

## Resource boundaries and security checks

Canonical JSON recommendations are limited to 64 KiB, eight nested container levels and 4,096 nodes. Before project I/O, validation limits plans to 16 branches, 256 aggregate evidence/scope/branch path entries, and 16,384 overlap comparisons including the physical pass when project-bound. Each relative path is limited to 32 normalized components and 1,024 UTF-8 bytes. Oversized input is rejected, not truncated; validation still cannot authorize execution.

Reference-note promotion and reading share inclusive limits of 1 MiB per canonical note, 256 directory entries and 8 MiB total. The whole collection is refused if excessive or malformed. Cooperating promotions use an exclusive owned lock; uncertain/interrupted state requires operator review, not automatic deletion or takeover. Existing notes remain immutable reference data.

The repository's required `offline-contracts` job explicitly fails unless its reusable dependency/secret security workflow succeeds; a skipped or cancelled prerequisite cannot turn into a green contract gate. Scans also run daily on GitHub-hosted runners with contents-read permission. Declared runtime, optional and build dependencies are audited separately from installing AIC; checksum-pinned Gitleaks scans full reachable history with bundled rules and redacted output. Dependabot proposes dependency/action updates for review, not automatic instruction/code adoption. These checks are not a guarantee that every secret or future advisory is detected.

## Optional research maintainer

The repository-only maintainer is a separate opt-in authority surface; installing the portable skill does not activate it. It is fixed to the approved repository and owner. Source pages and model outputs are untrusted data. No-tool roles receive public evidence without GitHub credentials; the controller enforces durable daily reservations, strict schemas and source/head identity.

Automatic publication is limited to one new regular dated research record. Workflow instructions, code, CI, credentials, permissions and security policy require manual adoption. Exact-head local verification, genuine required CI and independent assessment precede a SHA-bound protected merge. A source license observation, overlap detector or model review is not legal clearance or experimental reproduction.

Use a trusted private working directory. Unknown repository rules, changed artifacts, incomplete source evidence and uncertain mutations hold work rather than weakening gates or replaying effects. Do not expose the Mac as a runner for arbitrary public PR code. The owned scheduler does not modify other services, and removal preserves durable usage/evidence. See [maintenance](docs/maintenance.md) for setup, limits and stopping.

See [compatibility](docs/compatibility.md) and [verification](docs/verification.md) for the distinction between source documentation, isolated contract tests, installed-file consumption and real operational proof.
