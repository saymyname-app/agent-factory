# Install and share Agent Factory

This distribution contains the workflow, portable cockpit, project onboarding
and pinned upstream pack references. It contains no product dossiers, local
profile, credentials, runtime databases, sessions or Git history.

## 1. Export a shareable folder

From the source repository:
```bash
./bin/factory-portable export /absolute/new/agent-factory-share
```

The target must not exist and must be outside an existing Factory.
Share this exported folder (or zip it), not a raw copy of an active installation.
distribution.json records SHA-256 checksums of the distributed source files.
Upstream packs remain dependencies fetched by Gas City under their own licenses.
A folder export does not grant access to private project repositories.

## 2. Prepare a host

V1 targets Ubuntu/Linux, including Ubuntu 24.04 in WSL2. Native Windows and macOS
runtime operation have not been qualified. Use a separate host for a friend.
On your own machine, prepare/export offline; do not initialize a second City
beside an active controller without separately planning supervisor/port isolation.

Install Python 3.10+, Git, GitHub CLI, tmux, jq, Gas City 1.4.1, Beads 1.2.2,
Dolt 2.1.7 and Codex CLI using their official installation instructions.
The installer does not upgrade a host or download/execute arbitrary shell scripts.
Check upstream release artifacts and retain the pinned versions until an upgrade
is qualified. Gas City packs in pack.toml are pinned by commit.
Authenticate GitHub and the agent provider in the new user's account.
Never transfer another person's auth files, API keys or runtime directories.

Run:
```bash
./bin/factory-portable doctor
./bin/factory-portable profile --operator "Your name" --po-model YOUR_PO_MODEL --writer-model YOUR_WRITER_MODEL
```

Choose model IDs available to your account. No paid call is made by these commands.
The local .local/profile.json is ignored by Git and excluded from every export.
For another installation of your own, copy this non-secret profile deliberately
to .local/profile.json; reconnect accounts normally. Do not put credentials in it.
The v1 integrated PO uses Codex; other worker providers require explicit upstream
configuration and qualification rather than pretending all CLIs are interchangeable.

## 3. Initialize only the new host's runtime

```bash
./bin/factory-portable bootstrap-plan
```

Review and run the emitted native gc init command. It includes --no-start and
--preserve-existing. This may initialize storage/fetch packs, but must not launch
the agent controller. No gc doctor --fix or service restart runs automatically.
Run gc doctor and investigate failures with upstream documentation.

Before any gc start, inspect generated city.toml and set the chosen writer model
on the codex provider using its supported args_append = ["-m", "YOUR_WRITER_MODEL"].
No model is shipped as the default for your account.
Inspect provider permissions; full sandbox bypass is not the portable PO default.
Set Git/Dolt author identity locally as required by the doctor.
Only start the new City after provider readiness, storage, permissions and
configuration are verified. Check native gc start --help on the installed version.

## 4. Create or import a project

```bash
./bin/factory-portable project --mode new --slug my-app --name "My App"
./bin/factory-portable project --mode import --slug existing-app --name "Existing App" --repo /absolute/repository
```

Repeat --repo for a multi-repository project. Import reads Git metadata only;
it never edits or registers the original repositories.
Creation prepares the product dossier; the Mayor creates application repositories
only after the product/technical decisions and execution mandate are ready.

Open docs/products/<slug> with your PO and request completion of onboarding.
Its AGENTS.md loads the release preparation protocol automatically.
Run ./bin/factory-portable readiness <slug> to see what remains.
Configure worker repositories separately through upstream gc rig add using fresh
development checkouts, --start-suspended, and a verified default branch. Never
register a source repository currently managed by another factory.

## 5. Open the cockpit

After runtime qualification, choose an unused local port:
```bash
FACTORY_COCKPIT_PRODUCT_CONFIG="$PWD/config/products/my-app.json" \
  python3 lib/factory_cockpit.py serve --host 127.0.0.1 --port 8483
```

Set FACTORY_COCKPIT_CITY_NAME to the new City name reported by gc status.
Set FACTORY_COCKPIT_GAS_CITY_URL to this installation's verified local City API.
Set FACTORY_COCKPIT_COORDINATION_BEAD to its own coordination Bead; do not inherit
another installation's identifiers. Empty/unavailable execution evidence is not
progress. Preview actions remain disabled until a project-specific safe wrapper
is explicitly configured. Public/tailnet publication is not part of installation.

## 6. Qualify before unattended delivery

Run a small authorized canary in a disposable project: PO preparation, Mayor
handoff, Beads dependencies, one writer, PR, real tests and closure evidence.
Verify backup and recovery in the new environment.
Then record the bounded campaign mandate and let the Mayor run eligible work.

PROVEN by local tests: offline export, project creation/import metadata,
readiness validation, configurable PO identity/model and disabled generic preview.
NOT PROVEN by those tests: fresh-host runtime installation, provider
authentication, paid agent execution or end-to-end autonomous delivery.
The installed tools are never silently upgraded and no active factory is migrated.

Codex model/sandbox options: [official CLI reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli).
Gas City command shapes were checked against local v1.4.1 help.
