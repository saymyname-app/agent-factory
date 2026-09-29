# C01 research — ntfy and Tailscale serve (primary sources, 2026-09-29)

Scope: facts only, from primary sources (docs.ntfy.sh + ntfy GitHub source, the live ntfy.sh API, tailscale.com docs + tailscale GitHub source). Read-only; nothing was published or configured.
Source versions read: ntfy `main` @ `1e6305cc`, ntfy-ios `main` @ `96e659ca` (latest release v1.4.1, 2026-04-23), tailscale `main` @ `a0e471a3`. Tailscale KB pages cited show "Last validated" dates between Nov 2025 and Feb 2026. Tailscale docs now live under `tailscale.com/docs/...`; the old `tailscale.com/kb/NNNN/...` links still resolve.
Anything not confirmed on a primary page is marked **UNVERIFIED**.

---

## 1. ntfy.sh hosted, free tier, no account

### Limits on ntfy.sh (free, anonymous)
The live tier table from the server itself, `GET https://ntfy.sh/v1/tiers` (fetched 2026-09-29), shows this for the anonymous/free entry (no `code`):
`"basis":"ip","messages":250,"messages_expiry_duration":43200,"emails":5,"calls":0,"reservations":0,"attachment_total_size":20971520,"attachment_file_size":2097152,"attachment_expiry_duration":10800`
— source: https://ntfy.sh/v1/tiers

| Limit | ntfy.sh free value | Source |
|---|---|---|
| Messages per day | **250 per day**, counted per **IP** (`basis: ip`) | https://ntfy.sh/v1/tiers ; https://docs.ntfy.sh/publish/#limitations ("On ntfy.sh, the daily message limit is 250.") |
| Request burst / refill | Default server config: "60 requests per visitor at once, and then refills … at a rate of one request per 5 seconds." The exact ntfy.sh values are **UNVERIFIED**. The FAQ says "60 requests as a burst, and then 1 request per 10 seconds" (the two docs disagree) and adds "For ntfy.sh, there's even a fail2ban in place". | https://docs.ntfy.sh/publish/#limitations ; https://docs.ntfy.sh/config/#rate-limiting ; https://docs.ntfy.sh/faq/ |
| Message length | 4,096 bytes; anything longer becomes an attachment | https://docs.ntfy.sh/publish/#limitations |
| Title / tags | Title up to 1 KB, all tags together up to 512 bytes; larger requests get HTTP 400 | https://docs.ntfy.sh/publish/#limitations |
| Message cache (retention) | **12 h** (`messages_expiry_duration: 43200` s). Docs: "By default, the ntfy server caches messages on disk for 12 hours". The cache can be skipped per message with `Cache: no`, but then "messages might be missed" by clients that are reconnecting. | https://ntfy.sh/v1/tiers ; https://docs.ntfy.sh/publish/#message-caching ; https://docs.ntfy.sh/privacy/ |
| Attachments | **2 MB per file, 20 MB total per visitor, expire after 3 h** (10800 s) | https://ntfy.sh/v1/tiers ; https://docs.ntfy.sh/publish/#limitations |
| Daily bandwidth | 200 MB on ntfy.sh | https://docs.ntfy.sh/publish/#limitations |
| E-mails | 5 per day on ntfy.sh | https://docs.ntfy.sh/publish/#limitations |
| Open subscriptions | 30 connections per visitor (default) | https://docs.ntfy.sh/publish/#limitations |

### Who can read or publish an unreserved topic
- The default server behaviour is open: "everyone can read and write to any topic". Reserved topics are off unless configured. — https://docs.ntfy.sh/config/#access-control
- ntfy.sh `/v1/config` shows `"require_login":false` and `"enable_reservations":true`. — https://ntfy.sh/v1/config
- FAQ: "If you don't have ACLs set up, the topic name is your password … If you choose a randomly generated topic name, the topic is as good as a good password." It also says brute force is not realistic because of rate limiting and fail2ban. — https://docs.ntfy.sh/faq/
- **Anyone who knows the name of an unreserved topic can publish to it and can read (poll) the messages still cached (12 h).** This follows from the open default above combined with the 12 h cache.
- Messages on a topic that anonymous users can read travel **in full** through Google FCM and Apple APNs. The server puts `title`, `message`, `click`, `priority`, `tags` and `actions` into the Firebase/APNs payload. A message becomes a content-free `poll_request` only when "anonymous read" is not allowed on the topic. — https://github.com/binwiederhier/ntfy/blob/main/server/server_firebase.go (`toFirebaseMessage`). Privacy page: "Message metadata and content may be transmitted through Google's FCM infrastructure". — https://docs.ntfy.sh/privacy/
- The APNs alert body is cut to about 100 characters (`fcmApnsBodyMessageLimit = 100`), and the FCM payload is capped at about 4,000 bytes. — https://github.com/binwiederhier/ntfy/blob/main/server/server_firebase.go
- ntfy.sh keeps the following server-side: message content for the cache duration, topic names, and IP addresses (used for rate limiting and "May be temporarily logged"). — https://docs.ntfy.sh/privacy/

### What the paid tiers add (from `https://ntfy.sh/v1/tiers`)
Prices are shown in minor currency units. The currency is not in the response, so **USD is assumed and UNVERIFIED**.

| Tier | Price (month / year) | Messages/day | Cache | Reserved topics | Attachment file / total / expiry | Calls |
|---|---|---|---|---|---|---|
| Supporter | 600 / 6000 (≈ $6 / $60) | 2,500 | 5 days (432000 s) | 3 | 25 MB / 500 MB / 24 h | 3 |
| Pro | 1200 / 12000 | 20,000 | 7 days | 10 | 250 MB / 2 GB / 72 h | 20 |
| Business | 2500 / 24000 | 50,000 | 10 days | 50 | 1 GB / 10 GB / 7 days | 50 |

- Limits for paid tiers are counted per account (`basis: tier`), not per IP. — https://ntfy.sh/v1/tiers
- Reservations: "you can claim ownership over topics and define access to it". — https://docs.ntfy.sh/subscribe/web/#topic-reservations. Per-tier reservation counts come from https://docs.ntfy.sh/config/#tiers. The exact access modes a reserved topic offers on ntfy.sh (for example, everyone read-only) are **UNVERIFIED** here; they are not quoted on a page I read.
- For a topic that anonymous users cannot read, the server sends only a `poll_request` through FCM/APNs, and the app then fetches the real message with its credentials. The iOS app can store user credentials. — https://github.com/binwiederhier/ntfy/blob/main/server/server_firebase.go ; https://docs.ntfy.sh/privacy/

---

## 2. ntfy iOS app

### How instant delivery works
- The docs explain: "iOS heavily restricts background processing, which sadly makes it impossible to implement instant push notifications without a central server." ntfy.sh is that central, APNs-connected server. — https://docs.ntfy.sh/config/#ios-instant-notifications
- For a normal ntfy.sh topic, the server publishes to Firebase, and Firebase forwards to APNs as an **alert** push (`MutableContent: true`), with the full data in the payload. The app's Notification Service Extension can then change the notification on the phone. — https://github.com/binwiederhier/ntfy/blob/main/server/server_firebase.go (`createAPNSAlertConfig`)
- The iOS app also subscribes to a `~poll` topic, which the server uses to make the app poll all topics now and then. These are background pushes; the source comment says "Apple only allows us to send 2-3 of these notifications per hour, and delivery not guaranteed". — same file (`createAPNSBackgroundConfig`)
- Self-hosted servers are different. They forward a `poll_request` (containing only the message ID) to `upstream-base-url` (ntfy.sh). Without that setting, "delivery can take hours … shouldn't take more than 20-30 minutes" when the phone is in use. — https://docs.ntfy.sh/config/#ios-instant-notifications. This does not apply to hosted ntfy.sh, but it shows the fallback if pushes are lost.
- Typical latency numbers for ntfy.sh → iOS: **UNVERIFIED**. No primary page gives them. Delivery depends on FCM and APNs, which ntfy does not control. The Android doc calls Firebase "overall pretty bad at delivering messages in time" (https://docs.ntfy.sh/subscribe/phone/), but that remark is about Android.

### Click action (`Click` / `X-Click` header)
- Click is supported on Android, iOS and web. "Tapping the notification will open the web browser (or the app) and open the website … If you pass a website URL (`http://` or `https://`) the web browser will open." — https://docs.ntfy.sh/publish/#click-action
- In the iOS source, a tap with no action button calls `UIApplication.shared.open(URL(string: click))`, so any URL the OS can parse is handed to iOS. An `https://<machine>.<tailnet>.ts.net/...` URL therefore opens in the default browser. The app does not check or fetch the URL itself. — https://github.com/binwiederhier/ntfy-ios/blob/main/ntfy/App/AppDelegate.swift (`userNotificationCenter(_:didReceive:)`)
- If the user taps an action button instead, that action runs rather than the click URL. — same function
- Whether the page actually loads depends on the phone reaching the tailnet (see §4). ntfy has no part in that step.

### Priority mapping on iOS (source code; the docs describe only Android behaviour)
From https://github.com/binwiederhier/ntfy-ios/blob/main/ntfy/Utils/NotificationContent.swift:

| ntfy priority | iOS `interruptionLevel` | relevance |
|---|---|---|
| 1 min | `.passive` | 0 |
| 2 low | `.passive` | 0.25 |
| 3 default | `.active` | 0.5 |
| 4 high | `.timeSensitive` | 0.75 |
| 5 max/urgent | `.critical` with the critical sound, **only if** the user enabled "Critical Alerts" in the app **and** iOS granted that permission; otherwise `.timeSensitive` | 1 |

- Priority is set with `X-Priority` / `Priority` / `prio` / `p`, as a number 1–5 or a name. — https://docs.ntfy.sh/publish/#message-priority
- Whether the App Store build (v1.4.1, 2026-04-23) already includes the critical-alert path on `main` is **UNVERIFIED**. So is whether Apple granted the critical-alerts entitlement. The settings view exists in source: `ntfy/Views/Settings/CriticalAlertsSettingView.swift`.
- Whether `.timeSensitive` gets through Focus modes depends on the user's iOS Focus settings. There is no ntfy doc on this: **UNVERIFIED**.

---

## 3. `tailscale serve`

### Identity headers (docs + source)
- Doc: "When you use Serve to proxy traffic to a local service … it adds a few Tailscale identity headers to the request sent to your backend." — https://tailscale.com/kb/1312/serve#identity-headers
  - `Tailscale-User-Login`: the requester's login name (e.g. alice@example.com)
  - `Tailscale-User-Name`: display name
  - `Tailscale-User-Profile-Pic`: profile picture URL, "if their identity provider provides one"
- The source adds two more:
  - `Tailscale-Headers-Info: https://tailscale.com/s/serve-headers` on requests that carry identity.
  - `Tailscale-Funnel-Request: ?1` on Funnel requests, which carry no identity.
  - Serve **removes** all five from incoming requests before it sets them. — https://github.com/tailscale/tailscale/blob/main/ipn/ipnlocal/serve.go (`addTailscaleIdentityHeaders`)
- **There is no device or node header.** Only user fields are set. The source does always set `X-Forwarded-For` (source tailnet IP), `X-Forwarded-Host`, and `X-Forwarded-Proto: https` (over TLS). — same file (`addProxyForwardedHeaders`)
- `Tailscale-App-Capabilities` (JSON) is forwarded only for capabilities named with `--accept-app-caps`. It is available for users **and tagged nodes**, and never for Funnel. — https://tailscale.com/kb/1312/serve#app-capabilities-header ; https://tailscale.com/kb/1242/tailscale-serve
- Values are RFC 2047 Q-encoded when they contain non-ASCII characters, and are empty when the value is not valid UTF-8. — serve.go (`encTailscaleHeaderValue`)

**When the headers are absent:**
- The requester is a **tagged** device: "These identity headers are not populated for traffic originating from tagged devices." — https://tailscale.com/kb/1312/serve
- The request is **Funnel** traffic: "Funnel traffic, which is publicly available, does not include identity headers." — same page. The source sets only `Tailscale-Funnel-Request`.
- `WhoIs` of the source address fails. The source comment reads "traffic from outside of Tailnet (funneled or local machine)". — serve.go. Exactly which on-machine requests fall into this case is **UNVERIFIED**.
- Headers **are** set for external users who accepted a **share** of the device. — https://tailscale.com/kb/1312/serve

**Trust caveat, from the docs:** "it's best practice to only have the service listen on localhost. Otherwise, any user that can call your service directly … could trivially provide their own values for these HTTP headers. By listening only on localhost, this limits tampering to only other services running on the Serve device." — https://tailscale.com/kb/1312/serve

### Proxy target, Windows, WSL
- Targets can be written as a port number, as `localhost:3000`, or as a full URL. The docs add: "Note that only http://127.0.0.1 is supported for proxies." For example, `tailscale serve 3000` proxies to `http://127.0.0.1:3000`. — https://tailscale.com/kb/1242/tailscale-serve ; https://tailscale.com/kb/1312/serve
- On Windows, serving files needs an Admin terminal, but "When using Serve to forward ports, you don't need to use `sudo` or an Administrator console." — https://tailscale.com/docs/reference/examples/serve
- WSL2, per Tailscale: run Tailscale **on the Windows host only**, not inside WSL 2. Running both breaks traffic because "Tailscale packets not being able to fit in Tailscale packets" (MTU 1280). — https://tailscale.com/kb/1295/install-windows-wsl2
- **Tailscale has no official note** about proxying to a WSL2 service through WSL's localhost forwarding. Whether a WSL service bound to 127.0.0.1 is reachable at Windows `127.0.0.1:<port>` depends on Microsoft's WSL networking mode. **UNVERIFIED** from the allowed sources (it is Microsoft documentation, which is out of scope).
- Windows runs Tailscale "as the logged in user, not as the system … if a device is restarted … Tailscale won't automatically connect". The fix is "Run Unattended" (`tailscale up --unattended=true`). — https://tailscale.com/kb/1088/run-unattended

### Background and persistence
- `--bg`: "runs persistently in the background until you disable it. When you reboot the device or restart Tailscale … Serve automatically resumes sharing." Without `--bg`, you must restart it by hand. — https://tailscale.com/kb/1242/tailscale-serve#effects-of-rebooting-and-restarting
- Resuming after reboot on Windows still needs Tailscale itself to be connected, which may require unattended mode (see above).

### HTTPS / MagicDNS requirement
- "Tailscale Serve requires you to enable HTTPS certificates in your tailnet." The interactive CLI sends you to a consent page to turn it on. — https://tailscale.com/kb/1312/serve
- Enabling HTTPS takes these steps in the admin DNS page: turn on MagicDNS, then "Enable HTTPS", then "Acknowledge that your machine names and your tailnet DNS name will be published on a public ledger" (Certificate Transparency). The certificates come from Let's Encrypt, valid 90 days. There is a rate-limit risk ("waiting 34 hours"). — https://tailscale.com/kb/1153/enabling-https
- DNS names are limited to `device-name.tailnet-name.ts.net`. — https://tailscale.com/kb/1312/serve#limitations
- Tailnet ACLs apply to Serve "just like any other service". — https://tailscale.com/kb/1312/serve

### Serve vs Funnel
- Serve shares within the tailnet. Funnel routes "traffic from the broader internet … for anyone to access". — https://tailscale.com/kb/1312/serve ; https://tailscale.com/kb/1223/funnel
- Funnel requirements: v1.38.3+, MagicDNS, HTTPS, and **a `funnel` node attribute in the tailnet policy file**. It can use only ports 443, 8443 and 10000. — https://tailscale.com/kb/1223/funnel
- One port cannot be both Serve and Funnel. "If the most recent command to configure the port was funnel, then the port will be completely public." — https://tailscale.com/kb/1312/serve#limitations
- **The docs contradict each other:** the Serve page says "Tailscale Funnel is enabled by default. If you don't plan to use Tailscale Funnel on the device, you can turn it off." (https://tailscale.com/kb/1312/serve), while the Funnel page says "Tailscale Funnel is disabled by default" and requires approval plus the policy attribute (https://tailscale.com/kb/1223/funnel). The actual default state of the policy for this tailnet is **UNVERIFIED** and needs a live check of the policy file.
- Running `tailscale funnel` for the first time adds the `funnel` node attribute to the policy. By default it lets `autogroup:member` use Funnel. — https://tailscale.com/kb/1223/funnel
- Funnel cannot be turned on while shields-up is enabled. — serve.go

---

## 4. iPhone reaching a `*.ts.net` Serve URL
- The Tailscale iOS app installs a VPN configuration. It requires iOS 15+. — https://tailscale.com/kb/1020/install-ios
- iOS allows **only one VPN at a time**: "iOS and Android enforce a limit of running only one VPN at a time." — https://tailscale.com/docs/reference/faq/other-vpns
- VPN On Demand (iOS 1.48+) has rules per Wi-Fi/Cellular/Ethernet: Always, Only On, Except On, Never, Do Nothing.
  - **MagicDNS hostname matching** can connect Tailscale automatically when the device reaches a hostname ending in `*.ts.net`, but "only when you have set the connection rule for an interface to Do Nothing".
  - While Tailscale is enabled, the app also installs a broad On Demand policy so the VPN comes back after a restart, crash or update. Custom rules replace that policy.
  - Source: https://tailscale.com/docs/features/client/ios-vpn-on-demand
- Reaching the URL needs HTTPS (a valid LE cert for `machine.tailnet.ts.net`) and MagicDNS. — https://tailscale.com/kb/1153/enabling-https
- Tailnet ACLs must allow the iPhone's user to reach the serving node. — https://tailscale.com/kb/1312/serve
- Whether `*.ts.net` Serve names (non-Funnel) resolve through public DNS when the VPN is off: **UNVERIFIED**. The docs describe the resolution only through MagicDNS.
- The iOS app asks for push permission so it can warn before key expiry and re-authentication. Node key expiry can therefore cut access until the user logs in again. — https://tailscale.com/kb/1020/install-ios. The default expiry period is **UNVERIFIED** here.

---

## Implications for the C01 Spec (only facts that contradict or constrain)

**(a) "Minimal payload on ntfy.sh free with a secret topic is acceptable"**
- The topic name is the only access control. Anyone who holds it can **publish** fake notifications and **read** the cached messages (12 h). — https://docs.ntfy.sh/faq/ ; https://docs.ntfy.sh/config/#access-control ; https://ntfy.sh/v1/tiers
- A public topic sends the full title, body and **click URL** through Google FCM and Apple APNs. The click URL reveals the machine and tailnet name (`<machine>.<tailnet>.ts.net`) and the item path. "Minimal payload" therefore has to cover the Click URL and tags too, not just the body. — server_firebase.go ; https://docs.ntfy.sh/privacy/
- The budget is **250 messages/day per public IP**. Everything behind the same home IP shares it: Windows, WSL and anything else. That includes other ntfy use from the house. — https://ntfy.sh/v1/tiers
- Visible text should fit about 100 characters, because the APNs body is cut there. — server_firebase.go
- The only way to keep content out of FCM/APNs and make the topic non-public is a reserved topic that anonymous users cannot read. That needs a paid tier (Supporter ≈ $6/month, 3 reservations; currency UNVERIFIED), and the phone then fetches messages with credentials. — https://ntfy.sh/v1/tiers ; server_firebase.go
- `Cache: no` stops server-side retention but "messages might be missed". Its effect on iOS push delivery is **UNVERIFIED**.

**(b) "A notification tap opens the cockpit item URL on the tailnet"**
- Supported: the iOS app passes any `https://` Click URL to `UIApplication.open`, which opens the default browser. — AppDelegate.swift
- It works only if the Tailscale VPN is up on the iPhone, and iOS allows only one VPN at a time. The "Do Nothing" On Demand rule with `*.ts.net` MagicDNS matching can connect it automatically; any other rule turns that matching off. — https://tailscale.com/docs/features/client/ios-vpn-on-demand ; https://tailscale.com/docs/reference/faq/other-vpns
- If a notification carries action buttons, a tap on a button runs the action instead of the click URL. — AppDelegate.swift
- Delivery speed through FCM/APNs has no documented bound (**UNVERIFIED**). "Instant" is not guaranteed. Priority 4 maps to time-sensitive; priority 5 maps to critical only when the user has opted in.

**(c) "The cockpit trusts Tailscale identity headers added by serve and binds 127.0.0.1 only"**
- There is **no device/node header**, only user fields plus `X-Forwarded-For`. Authorizing "Benjamin's iPhone" specifically is not possible from headers alone. — serve.go
- Headers are **absent** for tagged requesters, for Funnel, and when WhoIs fails (the source comment includes "local machine"). The cockpit has to treat "no header" as unauthenticated and reject it, not trust it by default. — https://tailscale.com/kb/1312/serve ; serve.go
- Tailscale's own guarantee is that binding to localhost "limits tampering to only other services running on the Serve device". Here the service runs in WSL2 behind Windows localhost forwarding. **Any Windows process or any process in the WSL distro (including Factory agents) can call the port directly and forge `Tailscale-User-Login`.** The trust boundary is the whole PC plus WSL, not the Serve proxy. — https://tailscale.com/kb/1312/serve
- Tailscale gives no official guidance for proxying from Windows to a WSL2 localhost port (the WSL forwarding behaviour is **UNVERIFIED**). Serve accepts only `http://127.0.0.1` targets. — https://tailscale.com/kb/1242/tailscale-serve ; https://tailscale.com/kb/1295/install-windows-wsl2
- Non-ASCII display names arrive RFC 2047-encoded. Compare on `Tailscale-User-Login`. — serve.go
- The PC is a Windows gaming machine. Without "Run Unattended", Tailscale does not connect after a reboot until the user logs in, even with `--bg`. — https://tailscale.com/kb/1088/run-unattended ; https://tailscale.com/kb/1242/tailscale-serve

**(d) "No public exposure (no funnel)"**
- Enabling HTTPS, which Serve requires, **publishes the machine name and tailnet DNS name in public Certificate Transparency logs**. Access is still restricted, but the name is public. Rename the machine first if the name is sensitive. — https://tailscale.com/kb/1153/enabling-https
- The docs conflict on whether Funnel is "enabled by default" (Serve page) or "disabled by default" (Funnel page). Funnel needs a `funnel` nodeAttr in the policy file, and one `tailscale funnel` command on the same port makes it "completely public". Keeping "no funnel" true means checking that the policy has no `funnel` nodeAttr for this node. That check needs admin/policy access, which is Benjamin's tier. — https://tailscale.com/kb/1312/serve ; https://tailscale.com/kb/1223/funnel
- Sharing the device with an external user gives that user a reachable Serve URL **with** identity headers. "No public exposure" should also exclude device shares. — https://tailscale.com/kb/1312/serve
- The ntfy.sh path counts as a public third-party channel: topic, message and click URL go through ntfy.sh, Google and Apple (see (a)).
