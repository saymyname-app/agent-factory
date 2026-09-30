# C01 research: iPhone access to a cockpit served from WSL2 (2026-09-30)

Ticket: `af-arlph5.2` (map `af-arlph5`, C01 Cockpit V2). Facts only, no recommendation.
This note resolves the **UNVERIFIED** points in `po/c01-cockpit:docs/planning/c01-cockpit/research.md` (§3, §4, implications b–d). It does not repeat what that file already sources.

Sources: Microsoft Learn (WSL docs), tailscale.com docs, and tailscale source on `main` @ `f5f32603` (files `ipn/ipnlocal/serve.go`, `ipn/ipnlocal/local.go`, `ipn/ipnlocal/node_backend.go`, `ipn/prefs.go`, `cmd/tailscale/cli/serve_v2.go`, `serve_legacy.go`). The last group is **read-only local observations on this host** (2026-09-30), labelled **HOST**.
Machine name, tailnet name and IPs are deliberately left out and appear as `<machine>.<tailnet>.ts.net`.
Anything not confirmed is marked **UNVERIFIED**.

---

## 1. WSL2 networking mode vs. Serve's `127.0.0.1` target

### What Microsoft documents
- The default mode is NAT: "By default, WSL uses a NAT … based architecture". From Windows you reach a Linux app "using `localhost` (just like you normally would)". — https://learn.microsoft.com/en-us/windows/wsl/networking
- `localhostForwarding` (`[wsl2]`, default `true`): "specifying if ports bound to wildcard or localhost in the WSL 2 VM should be connectable from the host via `localhost:port`." — https://learn.microsoft.com/en-us/windows/wsl/wsl-config
  → In NAT mode, a Linux service bound to **`127.0.0.1`** inside WSL is reachable at Windows `127.0.0.1:<port>`. That is exactly what Serve needs, since it proxies to `http://127.0.0.1:<port>`.
- The sample `.wslconfig` comments that `localhostforwarding` "is ignored when networkingMode=mirrored". — same page
- Mirrored mode (`networkingMode=mirrored`, Windows 11 22H2+): "the Windows host and WSL2 VM can connect to each other using `localhost` (127.0.0.1)". IPv6 `::1` is "not supported". Among its benefits it lists "Improved networking compatibility for VPNs" and "Connect to WSL directly from your local area network (LAN)". Inbound traffic is filtered by the Hyper-V firewall (on by default since WSL 2.0.9 on 22H2+). — https://learn.microsoft.com/en-us/windows/wsl/networking ; https://learn.microsoft.com/en-us/windows/wsl/wsl-config (`firewall`, `hostAddressLoopback`)
- `networkingMode` values: `none`, `nat` (default), `bridged` (deprecated), `mirrored`, `consomme`. "starting from WSL 2.3.25, if NAT network mode fails, it falls back to using Consomme network mode." — https://learn.microsoft.com/en-us/windows/wsl/wsl-config
- An app bound to `0.0.0.0` is reachable from the LAN only through remote addresses. That takes an explicit `netsh interface portproxy` rule in NAT mode, and happens natively in mirrored mode. — https://learn.microsoft.com/en-us/windows/wsl/networking
- How Windows-originated connections are forwarded under Consomme mode: **UNVERIFIED** (not documented on the pages read).

### HOST (read-only, 2026-09-30)
- `%UserProfile%\.wslconfig` has `[wsl2]` memory, processors and swap, plus `[experimental] autoMemoryReclaim`. It has **no `networkingMode` and no `localhostForwarding` key**, so the documented defaults apply: **NAT + localhostForwarding=true**.
- `wsl --version`: WSL 2.7.13.0, kernel 6.18.x, Windows 10.0.26200 (Windows 11).
- `/etc/wsl.conf` in Ubuntu-24.04: `systemd=true`, default user. No network section.
- **The path works today.** A WSL process (`gc`) listens on `127.0.0.1:8372` inside WSL. On Windows, a `wslrelay` process listens on `127.0.0.1:8372`, and a Windows `curl http://127.0.0.1:8372/` returned HTTP 200.
  → The prior note's point "WSL forwarding behaviour UNVERIFIED" is **resolved for NAT mode on this host**.

### Serve target: docs vs. source
- The docs say "only http://127.0.0.1 is supported for proxies". — https://tailscale.com/kb/1242/tailscale-serve
- The source is less strict:
  - `expandProxyArg` accepts `http://…`, `https://…`, `https+insecure://…`, `unix:` and `host:port`, and maps a bare port to `http://127.0.0.1:<port>`. — `ipn/ipnlocal/serve.go`
  - The CLI treats any host other than `localhost`/`127.0.0.1`/`::1` as "remote". It warns only on the macOS App Store/System Extension builds and on Linux without SO_MARK. There is **no Windows check**. — `cmd/tailscale/cli/serve_v2.go` (`isRemote`, `shouldWarnRemoteDestCompatibility`)
  - So a Windows Serve could technically target the WSL VM address directly. Whether this is supported is **UNVERIFIED** (the docs say no). In NAT mode that address can change. See `wsl hostname -I` usage in the MS networking doc.

---

## 2. Identity: headers, missing device header, local forgery

Already sourced in the prior note: the three `Tailscale-User-*` headers, stripping of incoming values, no header for tagged nodes or Funnel, and no device header. New facts from the source:

- The identity lookup is `b.WhoIs("tcp", c.SrcAddr)`. If it fails, no headers are set; the comment says "traffic from outside of Tailnet (funneled or local machine)". — `ipn/ipnlocal/serve.go` (`addTailscaleIdentityHeaders`)
- `WhoIs` resolves the source IP through `nodeByAddr`. That map **includes the self node**: `addNodeAddr(nm.SelfNode)` in `ipn/ipnlocal/node_backend.go`, and `nodeByIDLocked` returns "the node (peer or self)".
  → A request whose source address is **this PC's own tailnet IP** resolves to the PC's owner. Serve then sets **genuine** `Tailscale-User-Login` headers for that user. Whether a local Windows process calling `https://<machine>.<tailnet>.ts.net` actually presents the own tailnet IP as its source is **UNVERIFIED** (not tested, to avoid touching state). If it does, a local process does not even need to forge headers.
- Direct forgery path, **HOST-verified**: the backend port is reachable without Serve at Windows `127.0.0.1:<port>` (through `wslrelay`) and inside WSL at `127.0.0.1:<port>`. Anything reaching it can send any `Tailscale-User-*` value.
  - Tailscale's own statement limits tampering "to only other services running on the Serve device". — https://tailscale.com/kb/1312/serve
  - Here the "Serve device" is Windows **plus** the WSL VM (all distros share the VM network in NAT mode; **UNVERIFIED** for multiple distros, only one observed).
- There is still **no device or node header**. The only per-request network fact is `X-Forwarded-For` (the source tailnet IP), which maps to a device through the tailnet but not through a header. — `serve.go` (`addProxyForwardedHeaders`)
- `Tailscale-App-Capabilities` is forwarded only for caps named with `--accept-app-caps`. It is also available for tagged nodes. It is the only header channel that policy can shape per device. — https://tailscale.com/kb/1312/serve#app-capabilities-header (prior note)

## 3. MagicDNS / HTTPS / Certificate Transparency

- **When the name is published:** "Only devices where you run `tailscale cert` will have their certificate in the public ledger." Machine names are published even with a randomized tailnet name. "You can edit your machine name before obtaining a certificate." — https://tailscale.com/kb/1153/enabling-https (validated 2025-12-10)
- **Serve issues the certificate lazily.** The TLS `GetCertificate` hook (`getTLSServeCertForPort`) calls `GetCertPEM(ctx, hi.ServerName)` on the first TLS handshake for a configured name/port. — `ipn/ipnlocal/serve.go`
  → The CT entry appears at the **first HTTPS request** to the Serve name (or at `tailscale cert`), not when HTTPS is enabled tailnet-wide.
  → **HOST:** Serve is already configured on HTTPS for this machine. Whether a certificate was already issued, and so whether the name is already in CT logs, is **UNVERIFIED** (not checked, to avoid querying CT with the name).
- Tailnet DNS name: format `tail<hex>.ts.net`, or a randomized "fun name". "After you use a randomized name for HTTPS certificates, you cannot re-generate it". Changing it may break MagicDNS links, certificates and sharing. — https://tailscale.com/kb/1217/tailnet-name (validated 2026-01-05)
- Whether `*.ts.net` names of non-Funnel nodes resolve on **public** DNS: **still UNVERIFIED**. https://tailscale.com/kb/1081/magicdns (validated 2026-01-05) does not say. Testing it would require sending the name to a public resolver.

## 4. Recovery after reboot (unattended)

- By default "The Tailscale client runs within the user login session". With unattended mode, "the Tailscale client continues to run with the configured profile even after the Windows user logs out or the device restarts". It is enabled by `tailscale set --unattended=true` or tray › Preferences › Run unattended. "the Windows account that activated it owns the Tailscale configuration". — https://tailscale.com/kb/1088/run-unattended (validated **2026-09-25**; the CLI is now `set`, where the prior note said `up`)
- Serve `--bg` config persists and resumes after a reboot or restart. — https://tailscale.com/kb/1242/tailscale-serve (prior note)
- **HOST:**
  - The Windows service `Tailscale` has StartType Automatic and is Running, client version 1.102.4.
  - `tailscale debug prefs` has **no `ForceDaemon` key**. The field is `json:"ForceDaemon,omitempty"` (`ipn/prefs.go`), so **unattended mode is OFF** on this host.
  - Consequence per the doc above: after a reboot, the tailnet connection waits for Benjamin's Windows login.
- Key expiry is a second break point:
  - "By default, new domains are set with an expiry period of 180 days". On expiry, "connections to/from the given endpoint will stop working".
  - It can be disabled per device (admin console). Tagged devices get it disabled by default.
  - Source: https://tailscale.com/kb/1028/key-expiry (validated 2026-01-05)
  - This applies to both the PC and the iPhone. The state for this tailnet is **UNVERIFIED** (admin console not opened, by instruction).
- The WSL side also has to be up. `.wslconfig` has `vmIdleTimeout` (default 60000 ms, Windows 11) and `[general] instanceIdleTimeout` (default 15000 ms, "-1 to disable auto shutdown"). — https://learn.microsoft.com/en-us/windows/wsl/wsl-config
  - How the Factory's WSL instance is started after a Windows reboot is **UNVERIFIED** (out of this ticket's scope).

## 5. Funnel state

- The docs still contradict each other:
  - Serve page (validated 2026-01-20): "Tailscale Funnel is enabled by default. If you don't plan to use Tailscale Funnel on the device, you can turn it off."
  - Funnel page (validated 2026-01-20): "Tailscale Funnel is disabled by default". It requires a `funnel` nodeAttr in the policy file and prompts for approval on first use.
  - Sources: https://tailscale.com/kb/1312/serve ; https://tailscale.com/kb/1223/funnel
- **HOST:** `tailscale serve status` and `tailscale funnel status` both list two HTTPS handlers on this machine: port 443 → `http://127.0.0.1:8372`, and port 8443 → `http://127.0.0.1:8383`. Both are labelled **"(tailnet only)"**.
  - In the CLI source, that label is replaced by "Funnel on" when Funnel is active for the handler (`cmd/tailscale/cli/serve_legacy.go`). So **no Funnel is active on this machine today**.
  - Whether the policy grants the `funnel` attribute (the capability, as opposed to its use) is **UNVERIFIED**: the policy was not read, by instruction.
- **HOST:** there is **no listener on port 8383**, neither on Windows nor in WSL. The 8443 handler points at nothing. It looks like a leftover Serve entry; its origin is **UNVERIFIED**.
- **HOST:** port 443 of the tailnet name already proxies to the `gc` process on WSL port 8372. A C01 cockpit would share or replace this mapping.

## 6. Alternatives without public exposure (facts only)

| Option | What it needs / implies | Source |
|---|---|---|
| Tailscale Serve (current path) | NAT + localhostForwarding → `127.0.0.1`. HTTPS + CT publication of the name. Identity headers are user-only | §1–§5 |
| Tailscale, plain tailnet IP:port (no Serve) | A Windows listener on the tailnet interface, e.g. `netsh interface portproxy` to the WSL VM address in NAT mode, or a WSL app on `0.0.0.0` in mirrored mode plus a Hyper-V firewall rule. **No TLS cert, no identity headers.** Whether mirrored mode exposes WSL on the Tailscale interface is **UNVERIFIED** | https://learn.microsoft.com/en-us/windows/wsl/networking |
| Tailscale inside WSL instead of Windows | Tailscale says to run it on the Windows host only; both at once breaks on MTU ("Tailscale packets not being able to fit in Tailscale packets") | https://tailscale.com/kb/1295/install-windows-wsl2 |
| LAN only (home Wi-Fi) | `portproxy` (NAT) or mirrored mode plus a firewall rule. Unreachable away from home. Exposed to every LAN device | https://learn.microsoft.com/en-us/windows/wsl/networking |
| Self-hosted WireGuard | Needs a reachable UDP port on the router (a public port). The server "does not even respond at all to an unauthorized client; it is silent and invisible" | https://www.wireguard.com/protocol/ |
| Headscale (self-hosted Tailscale control server) | Lists Serve and Funnel as supported features. Official iOS client compatibility and internet reachability of the control server are **UNVERIFIED** from the pages read | https://headscale.net/stable/about/features/ |

A public-hostname tunnel with an auth gateway (e.g. Funnel, or a third-party tunnel) is public exposure by definition and is out of scope.

## Contradictions with the 29/09 note

1. "WSL forwarding UNVERIFIED" → **verified**. NAT is the default, `localhostForwarding` defaults to true, and it works on this host (HTTP 200 through `wslrelay`).
2. "Only `http://127.0.0.1` targets" → true in the docs; the **source accepts remote targets on Windows without warning**.
3. "Headers absent when WhoIs fails, including local machine" → **incomplete**. The self node is in the WhoIs map, so a request sourced from the PC's own tailnet IP gets **real** owner headers (the runtime path is UNVERIFIED).
4. CT publication happens at the **first certificate issuance** (lazily, on the first TLS handshake), not at the tailnet-wide HTTPS toggle.
5. The unattended command is `tailscale set --unattended=true` (the docs now say `set`, not `up`). Unattended is **off** on this host.
6. Serve is **already in use** on this machine (port 443 → `gc`), with a dangling 8443 handler. No Funnel is active.
