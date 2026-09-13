# Security

## Trust boundaries

- WSL2 is a Linux compatibility environment, not a security sandbox.
- A Git worktree prevents many Git collisions but is not a security boundary against arbitrary filesystem writes.
- Gas City orchestrates processes; do not assume it provides isolation that has not been proven in the deployed version/runtime.
- GitHub branch protections and required checks remain independent controls.

## V1 concurrency policy

One writer per rig.

Do not enable parallel writers in one repository until canaries prove:

1. each writer receives a genuinely isolated work directory/worktree;
2. the canonical checkout and peer worktrees remain untouched;
3. branches are deterministic and pushes are non-force;
4. integration/merge contention is serialized;
5. provider writes outside the allowed scope are prevented or fail visibly.

## Secrets

Secrets and provider credentials never go into:

- Git;
- Beads issue text/metadata;
- prompts;
- logs or receipts intended for durable sharing.

Use host/provider credential stores and grant only the credentials necessary for the current provider/repository.

## Operator dashboard

The Gas City dashboard is a local operator surface, not a public service. Keep its supervisor listener on `127.0.0.1`; the embedded UI can expose beads, workflow activity and provider transcripts. Windows browser access through WSL localhost forwarding stays within the supported host-local boundary. Any non-loopback bind, port publication or reverse proxy requires a separate security design covering authentication, authorization and transport encryption.

## Human gates

Human approval is reserved for:

- substantial new product direction;
- new spend outside the approved envelope;
- production/secret/irreversible operations not already authorized;
- major product ambiguity that cannot be resolved from authoritative sources.

A red test, broken CI, agent failure, quota problem or deterministic technical correction is not by itself a human gate.

## Production

Production remains explicitly gated in V1. No deployment capability is inferred from Gas City, Beads or provider access.
