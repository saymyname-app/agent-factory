# C01 research — push channels to the iPhone (primary sources, 2026-09-30)

- **Bead:** af-arlph5.1 (map af-arlph5, C01 Cockpit V2).
- **Scope:** facts only, no recommendation.
- **Starting input:** `po/c01-cockpit:docs/planning/c01-cockpit/research.md` (ntfy + Tailscale, 2026-09-29). Its ntfy facts are not repeated here. §1 corrects and extends that input. §2–§5 cover the alternatives.
- **Method:** read-only. Nothing was published, subscribed or configured.
- **Convention:** anything not confirmed on a primary page is marked **UNVERIFIED**.

---

## 0. Apple baseline (applies to every channel)

- **`timeSensitive`:** "can break through system controls such as Notification Summary and Focus. The user can turn off the ability for time sensitive notification interruptions." — https://developer.apple.com/documentation/usernotifications/unnotificationinterruptionlevel/timesensitive
- **`critical`:** "requires an approved entitlement. The system always presents this notification, even when Do Not Disturb is active". It also bypasses the mute switch. — https://developer.apple.com/documentation/usernotifications/unnotificationinterruptionlevel/critical ; https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.usernotifications.critical-alerts
- **Consequence:** a critical alert is only possible through a native app that has the Apple-approved entitlement **and** that the user has authorised.
- Whether time-sensitive also needs a declared entitlement or capability: **UNVERIFIED** (the Apple entitlement page could not be retrieved).

## 1. ntfy — corrections and fills to the starting input

| Point | Fact | Source |
|---|---|---|
| Latest iOS release | The starting input says v1.4.1, because it read the GitHub *releases* list. The changelog also lists **v1.5.1 (27 Apr), v1.6.0 (12 May) and v1.7.0 (30 May 2026)**. v1.8.0 is marked **UNRELEASED**; the changelog was last changed 2026-09-26. | https://github.com/binwiederhier/ntfy/blob/main/docs/releases.md |
| Tap opens the Click URL | Added in **v1.6.0**: "Tap a notification to open its click URL, or copy the message text if no click URL is set". | same |
| Priority 5 → critical | The changelog lists "Deliver priority 5 (max/urgent) notifications as critical alerts that bypass silent mode and Do Not Disturb" under **v1.8.0 (UNRELEASED)**. The `critical-alerts` entitlement is in `ntfy.entitlements` on `main` but **absent at tag v1.7.0**. v1.7.0 code already sets `.critical` for priority 5. What iOS does with `.critical` when the app lacks the entitlement: **UNVERIFIED**. | releases.md ; https://github.com/binwiederhier/ntfy-ios/blob/v1.7.0/ntfy/ntfy.entitlements ; https://github.com/binwiederhier/ntfy-ios/blob/v1.7.0/ntfy/Utils/NotificationContent.swift |
| Priority 4 → time-sensitive | The v1.7.0 code sets `.timeSensitive`. Neither entitlements file (v1.7.0 or `main`) contains a time-sensitive entitlement. Whether it breaks through Focus in practice: **UNVERIFIED**. | same |
| Reserved topic access (paid) | The web app offers four "everyone" modes: "Only I can publish and subscribe" (deny-all), everyone can subscribe, everyone can publish, everyone can publish and subscribe. | https://github.com/binwiederhier/ntfy/blob/main/web/public/static/langs/en.json |
| Price currency | The web app shows prices as `$` + amount/100 (`formatPrice`). The dollar sign is confirmed; that it means USD is still an inference. | https://github.com/binwiederhier/ntfy/blob/main/web/src/app/utils.js |
| Self-hosted + iOS | With `upstream-base-url: https://ntfy.sh`, ntfy.sh, FCM and APNs carry only a `poll_request` (the message ID). The phone then fetches the content from the self-hosted server. If the iPhone "can not talk to your self-hosted server", the notification reads **"New message"** with no content. A tailnet-only server behaves this way when the iPhone VPN is off. Also documented: "Firebase+APNS are being weird and buggy"; the fix is to remove and re-add the subscription. | https://docs.ntfy.sh/known-issues/ ; https://docs.ntfy.sh/config/#ios-instant-notifications |
| ntfy web app as a PWA on iOS | Supported on "Safari: iOS 16.4+". Server-side Web Push needs VAPID keys, and "A *valid* certificate is required". "Web Push is only supported for the same server." | https://docs.ntfy.sh/subscribe/pwa/ ; https://docs.ntfy.sh/config/#web-push |
| Latency ntfy.sh → iOS | Still **UNVERIFIED**: no primary source gives a figure. | — |

## 2. Pushover (hosted SaaS, closed source)

| Criterion | Fact | Source |
|---|---|---|
| Cost | "$4.99 USD one-time purchase" per platform, after a "free for 30 days" trial. Teams: "$5 USD per-user, per-month". | https://pushover.net/pricing |
| Quota | "10,000 messages per month for free" per account (Teams: 25,000). Over quota, the API returns HTTP 429. At most 2 concurrent HTTP connections. | https://pushover.net/api |
| Size limits | Message 1,024 chars, title 250, `url` 512, `url_title` 100, attachment 5 MB. | https://pushover.net/api |
| Access control | Every message needs an application `token` and the recipient's `user` key. There are no public topics. | https://pushover.net/api |
| Content confidentiality | By default Pushover sees the content. Optional **E2E**: with `encrypted=1`, the `message`, `title`, `url` and `url_title` fields are AES-256-CBC encrypted with a key "not visible to Pushover servers", and the iOS app supports it. Apple is a listed sub-processor for "Notification Transport". Whether Apple sees plaintext when E2E is off: **UNVERIFIED**. | https://pushover.net/api ; https://pushover.net/privacy |
| Retention | Messages are "deleted from Pushover's servers once delivery has been verified". Undelivered messages are deleted after 21 days. The `ttl` parameter also deletes the message from the devices. | https://pushover.net/privacy ; https://pushover.net/api |
| Link at tap | `url` and `url_title` add a supplementary link, "shown below" the message when it is opened. Whether one tap on the banner opens the URL directly: **UNVERIFIED**. | https://pushover.net/api |
| Urgency levels | Priorities run from −2 to 2. Priority 1 bypasses the user's quiet hours. Priority 2 repeats until acknowledged (`retry` ≥ 30 s, `expire` ≤ 10,800 s, returns a `receipt`). **iOS Critical Alerts** are Apple-approved and "not enabled by default"; the user turns them on in the app settings. They "bypass the device's mute switch and Do Not Disturb", and the Pushover blog ties them to high-priority messages. How priorities map to iOS time-sensitive: **UNVERIFIED** (only user feature requests were found). | https://pushover.net/api ; https://blog.pushover.net/posts/2020/2/ios-critical-alerts ; https://support.pushover.net/i148-option-to-have-critical-alerts-on-ios-for-emergency-priority-messages-only-not-high-priority-and-emergency-priority-as-it-is-now |
| Latency | **UNVERIFIED**: no primary source gives a figure. | — |

## 3. Web Push to an iOS Home Screen web app (the cockpit as a PWA)

| Criterion | Fact | Source |
|---|---|---|
| Availability | Works for "Home Screen web apps in iOS 16.4 or later". The manifest `display` must be `standalone` or `fullscreen`, and the app must be added to the Home Screen. Permission can only be requested after "direct user interaction". "You don't need to join the Apple Developer Program." | https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers ; https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/ |
| Path / third parties | Factory server → Apple push service (`https://*.push.apple.com`) → device. No other third party is involved. The server needs a VAPID key pair. | Apple doc above |
| Content confidentiality | The payload is encrypted under RFC 8291, which "provides confidentiality and integrity for messages sent from an application server to a user agent". Apple, as the push service, cannot read the content but sees timing and size. | https://www.rfc-editor.org/rfc/rfc8291 |
| Access control | Only the holder of the VAPID private key can push to the subscription endpoint; a mismatch returns `VapidPkHashMismatch` or `BadJwtToken`. The phone creates the endpoint and keys, and the server stores them. | Apple doc above |
| Cost / quotas | Free. The payload is at most **4 KB**. The `TTL` header allows up to 30 days of storage while the phone is offline, and "The number of notifications the push services stores while the device is offline is limited". Apple returns `429 TooManyRequests` for "too many consecutive requests to the same device token". No numeric quota is published: **UNVERIFIED**. | Apple doc above |
| Reliability rule | "Safari doesn't support invisible push notifications … If you don't [display it], Safari revokes the push notification permission". **Declarative Web Push** (iOS/iPadOS 18.4, Home Screen apps) removes that risk: "there is no penalty for service workers failing to display a notification; the declarative push message itself is used as a fallback". | Apple doc above ; https://webkit.org/blog/16535/meet-declarative-web-push/ |
| Urgency | The `Urgency` header takes `very-low`, `low`, `normal` or `high`; to "attempt to deliver the notification immediately, specify `high`". The notifications "integrate with Focus". No primary source mentions **time-sensitive or critical for web push**, so treat both as unavailable (**UNVERIFIED**). | Apple doc above ; WebKit 13878 |
| Link at tap | Declarative Web Push: the required `navigate` field "describes a URL that will be navigated to by the browser upon activation". Classic Web Push: a service-worker `notificationclick` handler (not detailed in the Apple and WebKit pages read). | WebKit 16535 |
| Tailnet constraint | The PWA origin needs HTTPS with a valid certificate: service workers require it (ntfy: "A *valid* certificate is required"). A `*.ts.net` Serve origin has a Let's Encrypt certificate (starting input §3–4). Showing the notification needs no tailnet, because the payload travels through Apple. Opening the page on tap needs the phone to reach the origin, and so does **subscribing**. That a PWA can be installed from a tailnet-only origin is an inference, not documented: **UNVERIFIED**. | https://docs.ntfy.sh/config/#web-push ; starting input §3–4 |
| Latency | **UNVERIFIED**. | — |

## 4. Telegram bot

| Criterion | Fact | Source |
|---|---|---|
| Cost / quotas | "Bots are able to message their users at no cost". Limits: about 1 message/s per chat, 20 messages/min per group, about 30 messages/s for broadcasts. Paid broadcasts cost 0.1 Stars per message. | https://core.telegram.org/bots/faq |
| Path / third parties | Factory → Telegram Bot API (`api.telegram.org`, or a self-hosted `telegram-bot-api` that still talks to Telegram) → Telegram cloud → iOS app. The iOS app most likely gets the alert through APNs: **UNVERIFIED**. | https://core.telegram.org/bots/api ; https://github.com/tdlib/telegram-bot-api |
| Content confidentiality | Cloud chats use "client-server/server-client encryption" and are "stored encrypted in the Telegram Cloud". Only Secret Chats are end-to-end. No primary statement was found on bots in secret chats, so "bots cannot use them" is **UNVERIFIED**. Bots have "limited cloud storage – older messages may be removed". | https://telegram.org/faq ; https://core.telegram.org/bots |
| Access control | The bot token grants full sending rights. "Bots can't start conversations with users. A user must … send them a message first." Anyone can message a public bot, so the Factory has to filter by `chat_id` itself. | https://core.telegram.org/bots |
| Link at tap | Tapping the notification opens the chat. An `InlineKeyboardButton.url` is an "HTTP or tg:// URL to be opened when button is pressed". Reaching the cockpit therefore takes 2 taps. | https://core.telegram.org/bots/api |
| Urgency | Only `disable_notification` ("without sound"). The Bot API reference has no time-sensitive or critical control. That no other mechanism exists: **UNVERIFIED**. | https://core.telegram.org/bots/api |
| Text limit | 1 to 4,096 characters. | same |

## 5. Other: Bark (open-source iOS app, MIT)

| Criterion | Fact | Source |
|---|---|---|
| Nature | An iOS app plus `bark-server` (Go). The server "sends push requests to Apple's servers" directly; no FCM is involved. The server can be self-hosted (Docker or binary). Latest app release: v2.3.7, 2026-09-28. | https://github.com/Finb/Bark/blob/master/docs/en-us/deploy.md ; https://github.com/Finb/Bark/releases |
| Confidentiality | The route is "Sender → Server① → Apple APNS Server → Your Device → Bark APP②". On the public server, "the author can see the request logs". With encrypted push (AES, custom key), content "will not be obtained or leaked by Bark server and Apple APNs server". App builds are verifiable through GitHub Actions run IDs. | https://github.com/Finb/Bark/blob/master/docs/en-us/privacy.md ; https://github.com/Finb/Bark/blob/master/docs/en-us/encryption.md |
| Access control | A per-device key in the URL path. If it leaks, "reset it in the server list page". | https://github.com/Finb/Bark/blob/master/docs/en-us/faq.md |
| Cost / quotas | Free. Public server: "Normal usage is not restricted", but abuse patterns trigger a 24 h IP ban; "These limits don't apply if you're self-hosting". | same |
| Urgency | `level` accepts `active`, `timeSensitive`, `passive` or `critical`. `critical` "requires the critical alert permission in the app; without it the push is downgraded to a normal notification"; its volume is set with `volume`. `call` repeats the ringtone for 30 s. | https://github.com/Finb/Bark/blob/master/docs/en-us/params.md |
| Link at tap | `url` is the "URL to open when the push is tapped"; "`http` / `https` links are opened with the Universal Link first and fall back to Safari". | same |
| Self-hosted caveat | The deploy doc implies that a self-hosted bark-server can push to the App Store app (the Apple push key is embedded in the server), but it does not say so explicitly: **UNVERIFIED**. | deploy.md |

## 6. Summary matrix (condensed from the tables above)

| Channel | Third parties that see content | Access control | Cost | Tap → cockpit URL | iOS time-sensitive / critical |
|---|---|---|---|---|---|
| ntfy.sh free, public topic | ntfy.sh, Google FCM, Apple | topic name only | free, 250/day per IP | yes, 1 tap (app ≥ 1.6.0) | TS on prio 4 (effect UNVERIFIED) / critical unreleased (1.8.0) |
| ntfy self-hosted + ntfy.sh relay | ntfy.sh, FCM and APNs see the message ID only | server ACL | free + hosting | yes; content needs the tailnet | same as above |
| Pushover | Pushover (unless E2E), Apple | app token + user key | $4.99 once, 10,000/month | link in the opened message (1 tap UNVERIFIED) | critical yes (opt-in); TS UNVERIFIED |
| Web Push PWA | Apple, ciphertext only (RFC 8291) | VAPID key | free, 4 KB payload | yes (`navigate`); page needs the tailnet | none documented |
| Telegram bot | Telegram (cloud chat, not E2E) | bot token + `chat_id` filter | free | 2 taps (inline button) | none (silent flag only) |
| Bark | Bark server (unless encrypted or self-hosted), Apple | device key | free | yes, 1 tap | all four levels; critical is opt-in |
