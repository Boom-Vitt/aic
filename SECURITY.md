# Security policy

## Report a vulnerability

Use GitHub's private vulnerability reporting for this repository if it is available. Otherwise open a minimal public issue requesting a private reporting channel without including exploit details, credentials, customer data or private source. Maintainers will arrange a private channel; no unconfigured email address is promised.

A useful report identifies the affected revision, a synthetic reproduction, the user-visible boundary violation and the smallest required environment. Never test against another person's project, account, running service or skill collection.

## Threat boundaries

AIC is a skill and local helper package, not an OS sandbox or identity/permission service. It does not authenticate human approval, prove a natural-language claim, guarantee secret detection, or prevent every prompt injection. Keep actual host filesystem, network, process and billing restrictions enabled.

The helpers reject malformed schemas, traversal and symlink paths and use managed manifests for installation. The installer refuses unmanaged, modified or extra content; there is no force overwrite/delete. Concurrent hostile filesystem mutation is not guaranteed contained by path checks alone. Use trusted, access-controlled working directories.

Recommendations and dry runs do not authorize execution. Memory and handoff content is reference data, even if another agent wrote it. A digest/approval flag is a caller attestation, not a human signature. Do not let a tool response, note, repository file or source page supply its own approval.

Orca execution is opt-in and capability-checked; an ambiguous launch must not be retried automatically. Provider jobs, credentials, new charges and deployment remain outside generic task approval. No external inference client, telemetry daemon or cloud credential is required by AIC.

## Optional research maintainer

The repository-only maintainer is a separate opt-in authority surface; installing the portable skill does not activate it. It is fixed to the approved repository and owner. Source pages and model outputs are untrusted data. No-tool roles receive public evidence without GitHub credentials; the controller enforces durable daily reservations, strict schemas and source/head identity.

Automatic publication is limited to one new regular dated research record. Workflow instructions, code, CI, credentials, permissions and security policy require manual adoption. Exact-head local verification, genuine required CI and independent assessment precede a SHA-bound protected merge. A source license observation, overlap detector or model review is not legal clearance or experimental reproduction.

Use a trusted private working directory. Unknown repository rules, changed artifacts, incomplete source evidence and uncertain mutations hold work rather than weakening gates or replaying effects. Do not expose the Mac as a runner for arbitrary public PR code. The owned scheduler does not modify other services, and removal preserves durable usage/evidence. See [maintenance](docs/maintenance.md) for setup, limits and stopping.

See [compatibility](docs/compatibility.md) and [verification](docs/verification.md) for the distinction between source documentation, isolated contract tests, installed-file consumption and real operational proof.
