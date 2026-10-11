# Cloud hosting and CI placement for the Agent Factory (research, 2026-10-11)

All prices are per month and exclude VAT unless stated. "Read 2026-10-11" means read on the owner's page today. USD figures are left in USD; where a EUR total is needed, 1 USD = 1 EUR is used as a deliberate upper bound (the real rate was not looked up).

## Summary

1. **Scenario A (agent-factory public).** One VM: Contabo Cloud VPS 8 (8 vCPU / 24 GB / 150 GB NVMe, EU region) on a 1-month term, 14.00 EUR. Factory CI runs on GitHub-hosted standard runners, which are free on public repositories and are 4 cores / 16 GB there. SayMyName backend and frontend/e2e stay on GitHub-hosted `ubuntu-latest`, paid by the Team plan's 3,000 included minutes (measured use: about 490 minutes/month). No self-hosted runner anywhere.
2. **Scenario A cost:** 11.20 to 14.00 EUR/month (24-month prepaid vs 1-month term). CI: 0.
3. **Scenario A scale path:** Cloud VPS 12 (12c / 48 GB) 20.00 to 25.00 EUR, then Cloud VPS 16 (16c / 64 GB) 29.60 to 37.00 EUR.
4. **Scenario A main risk:** the repository's full history and workflows become public (secrets and fork pull requests need a review before the switch); second risk is shared-CPU variance at Contabo, for which no first-party guarantee was found.
5. **Scenario B (agent-factory private).** Two VMs: a Factory VM (Contabo Cloud VPS 8, 14.00 EUR) and a separate CI VM (Contabo Cloud VPS 8, 14.00 EUR) that carries the existing ephemeral rootless-Podman self-hosted runner for agent-factory only. SayMyName backend and frontend/e2e stay on GitHub-hosted runners inside the included 3,000 minutes.
6. **Scenario B cost:** 22.40 to 28.00 EUR/month. CI marginal cost: 0 today.
7. **Scenario B scale path:** CI VM to Cloud VPS 12 (20.00 to 25.00 EUR; three 4-core runners), then Factory VM to Cloud VPS 12 (same price). Total after both steps: 40.00 to 50.00 EUR.
8. **Scenario B main risk:** GitHub's charge for self-hosted runner minutes on private repositories is postponed, not cancelled. At the announced 0.002 USD/min it would add about 19 to 33 USD/month at the measured volume (arithmetic below).
9. **Why not GitHub-hosted for a private Factory CI:** at 1,280 runs/month the cost is about 200 to 370 USD/month on 2-core runners.
10. **Availability constrains the choice today:** OVHcloud VPS-2, VPS-3 and VPS-4 show "VPS temporairement indisponibles" in the configurator, Hetzner CX/CAX are labelled "not available", and the Hetzner auction floor is 64 EUR. Start on a 1-month term because worker test peaks are not measured.

## Measured locally (2026-10-11, supplied by the coordinator)

- Factory without CI: about 2.5 GB RSS (Dolt 1.3 GB), under one core with two agents, 28 GB disk. Peaks with several workers running tests: not measured.
- Factory CI: 1,000 runs in 23.5 days = about 42 runs/day = about 1,280 runs/month. Average 7.3 wall-clock minutes per run (includes failed and short runs). A full green battery is about 13 min on 4 cores of the PC, or about 50 billed minutes on GitHub 2-core runners. Runner box today: 4 cores / 4 GB, job peak memory 1.2 GB.
- SayMyName, last 30 days: backend CI 121 runs / 374 min; backend code review 34 runs / 42 min; frontend CI 54 runs / 69 min; e2e 7 runs / about 0 min; frontend code review 6 runs / 4 min. Total about 489 minutes/month.
- GitHub organization: Team plan (read 2026-10-11).

### Derived volumes (formulas)

- W1-avg = 1,280 runs x 7.3 min = 9,344 minutes of a 4-core runner = 37,376 core-minutes/month.
- W1-max = 1,280 runs x 13 min = 16,640 minutes of a 4-core runner = 66,560 core-minutes/month.
- W1 on GitHub 2-core: upper bound 1,280 x 50 = 64,000 billed minutes. Average case, scaled by 7.3/13: 1,280 x 28.1 = about 35,940 billed minutes (scaling is an assumption).
- W2 = about 500 minutes/month of 2-core jobs (SayMyName). 500 < 3,000 included minutes, so W2 costs 0 on the Team plan.
- Capacity check for a self-hosted runner: one 4-core runner offers 43,200 minutes/month. W1-avg uses 9,344 / 43,200 = 22%; W1-max uses 16,640 / 43,200 = 39%. Per day: 42 x 7.3 = 307 min (5.1 h) to 42 x 13 = 546 min (9.1 h) on one runner. One runner is enough on average but queues at peaks; two runners (8 cores) remove most queueing. This assumes a rented vCPU is as fast as a PC core, which is not verified.

## Recommendations in detail

### Scenario A: agent-factory public

| CI | Where | Cost |
|---|---|---|
| Factory CI | GitHub-hosted standard runners (`ubuntu-latest`, 4 cores / 16 GB on public repos) | 0 |
| SayMyName backend (Testcontainers) | GitHub-hosted `ubuntu-latest` (2 cores / 8 GB on private repos), included minutes | 0 |
| SayMyName frontend + e2e | Same | 0 |

- VM: Contabo Cloud VPS 8, 14.00 EUR (1 month), 11.90 (12 months), 11.20 (24 months, prepaid 268.80). No setup fee.
- The Factory rule "never a self-hosted runner on a public repo" is met: there is no self-hosted runner.
- Team plan concurrency is 60 standard jobs, so queued runs stop being a capacity problem.
- The VM still needs a container engine for the workers' local product tests.

**Runner-up A: OVHcloud VPS-4** (8c / 24 GB / 200 GB, 19.96 EUR on 12-month commitment; about 23.48 EUR without commitment, computed as 19.96 / 0.85). It has daily backup included, a French provider and a one-click upgrade. It lost because the configurator shows it unavailable today, the range stops at VPS-4 (no 12 or 16-core step), and a downgrade means a new VPS plus data transfer.

### Scenario B: agent-factory private

| CI | Where | Cost |
|---|---|---|
| Factory CI | Self-hosted runner, ephemeral, rootless Podman, on a dedicated CI VM | 0 marginal; VM 14.00 EUR |
| SayMyName backend (Testcontainers) | GitHub-hosted `ubuntu-latest`, included minutes | 0 |
| SayMyName frontend + e2e | Same | 0 |

- Two VMs rather than one: GitHub states self-hosted runners "can be persistently compromised by untrusted code in a workflow" and asks for caution on private repositories. Agent-written pull requests are the code that runs there. On a separate VM the runner does not sit next to the Factory's credentials, Dolt database and agent sessions, and CI load cannot starve the Factory.
- A single larger VM (Cloud VPS 12, 25.00 EUR) is 3.00 EUR cheaper and is one machine to maintain. It is acceptable if the Podman limits stay in place, but it keeps the runner beside the Factory's secrets.
- The runner must be registered to the agent-factory repository only (or a runner group restricted to it), so SayMyName jobs never land on it.

**Runner-up B: one VM + Ubicloud managed runners for Factory CI.** Ubicloud `standard-4` (4 vCPU / 16 GB, Germany) is 0.0025 USD/min: 20.86 to 39.10 USD/month at the measured volume, plus the 14.00 EUR VM = about 35 to 53 EUR. It gives a fresh VM per job, no runner to maintain and elastic concurrency. It lost because the cost grows linearly with agent pull-request volume and reaches the budget ceiling at the upper bound, and because it requires a third-party GitHub App with access to private code. It is the right fallback if the self-hosted charge comes into force or if queueing persists.

### Is a self-hosted runner on the same VM sound? (question 4)

| Option | Isolation | Cost | Verdict |
|---|---|---|---|
| Same VM, rootless Podman, `--ephemeral` | Container boundary only; shares kernel, disk and CPU with the Factory | 0 | Works, same level as today's PC setup; weakest |
| Second small VM for CI | VM boundary from the Factory; runner still reused between jobs unless wiped | 14.00 EUR | Recommended for B |
| actions-runner-controller | GitHub describes it as "Kubernetes-based" | Cluster to run | Too heavy for one developer |
| On-demand VM per job (TestFlows on Hetzner) | Fresh VM per job | Hetzner bills by the hour; cheapest orderable type today is CPX32 at 0.0577 EUR/h | Not competitive while CX/CAX are unavailable: 1,280 runs x 1 h minimum x 0.0577 = about 74 EUR, more if each of the four lots gets its own server |
| Managed ephemeral runners (Ubicloud) | Fresh VM per job, operated by a third party | 21 to 39 USD | Runner-up B |

GitHub recommends ephemeral runners with autoscaling and notes that reused hardware "can risk exposing information from the environment". It also says self-hosted runners "should almost never be used for public repositories".

## Comparison: VM providers

Net prices. "12m" = 12-month term, "1m" = monthly term.

| Provider / plan | 4c / 8 GB | about 8c / 16-24 GB | 12-16c / 32-64 GB | Resize | Hourly billing | Backups / snapshots | EU DC | Orderable today | Source (read 2026-10-11) |
|---|---|---|---|---|---|---|---|---|---|
| Contabo Cloud VPS | 4.40 (24m); about 5.50 (1m, computed 4.40 / 0.8) | VPS 8, 8c/24 GB: 14.00 (1m), 11.90 (12m), 11.20 (24m) | VPS 12, 12c/48 GB: 20.00 (24m), about 25.00 (1m); VPS 16, 16c/64 GB: 29.60 (24m), about 37.00 (1m) | Upgrade in panel (free redeploy wipes data, or paid live migration); downgrade = buy smaller plan and move data | No | 1 to 3 snapshots included; auto backup 5.00 | "European Union" region | Yes (order form reached) | https://contabo.com/en/vps/ ; https://contabo.com/en/vps/cloud-vps-core-8/ ; https://contabo.com/blog/kb/103000269722-can-i-change-my-virtual-private-server-vps-plan/ |
| OVHcloud VPS 2027 | VPS-2: 7.21 (12m); about 8.48 no commitment | VPS-3 6c/12 GB: 10.40 (12m), about 12.24; VPS-4 8c/24 GB: 19.96 (12m), about 23.48 | None listed | Upgrade one click, same datacenter; downgrade = new VPS + transfer | No (term billing) | Daily backup included; snapshot option 0.70 | Yes | VPS-1 yes; VPS-2, 3, 4 show "temporairement indisponibles" | https://www.ovhcloud.com/fr/vps/ and its configurator |
| Netcup VPS G12.5 (shared) | VPS 1000: 12.18 (12m), 14.02 (1m) | VPS 2000 8c/16 GB: 22.62 (12m), 26.02 (1m) | VPS 4000 12c/32 GB: 38.12 (12m), 43.83 (1m); VPS 8000 16c/64 GB: 56.39 (12m), 64.84 (1m) | Upgrade within the same generation; downgrade not addressed | No | Snapshots included | Nuremberg, Vienna, Amsterdam | Yes ("Order now") | https://www.netcup.com/en/server/vps |
| Netcup Root Server G12.5 (dedicated cores) | RS 1000: 18.26 (12m), 21.01 (1m) | RS 2000 8c/16 GB: 34.20 (12m), 39.34 (1m) | RS 4000 12c/32 GB: 65.40 (12m), 75.21 (1m) | Same as above | No | Snapshots included | Nuremberg, Vienna | Yes | https://www.netcup.com/en/server/root-server |
| Hetzner Cloud CPX (shared) | CPX32: 35.99 incl. IPv4, 0.0577/h | CPX42 8c/16 GB: 69.99, 0.1122/h | CPX62 16c/32 GB: 130.49 | Rescale up; down only if the disk was not grown | Yes | Extra | Nuremberg, Helsinki | Yes | https://www.hetzner.com/cloud/regular-performance/ |
| Hetzner Cloud CX / CAX | CX33 8.49 (price doc) | CX43 15.99 | CX53 29.49 | Same | Yes | Extra | Germany, Finland | No: every plan carries a "not available" label | https://www.hetzner.com/cloud/cost-optimized/ |
| Hetzner server auction | n/a | n/a | Floor 64.00 + 1.70 IPv4: i7-6700, 4 cores / 8 threads, 64 GB, 2 x 512 GB SSD; no setup fee; 153 servers listed | None (fixed hardware) | Hourly rate shown (0.1026/h) | None included | Falkenstein, Helsinki | Yes | https://www.hetzner.com/sb/ (live data file) |
| IONOS VPS | VPS L+: 7 for 3 months, then 22 | VPS XL+ 8c/16 GB: 12 then 41 | VPS XXL+ 12c/24 GB: 17 then 59 | Not read | No (prepaid) | Not read | Germany, Spain | Not checked | https://www.ionos.fr/serveurs/vps |
| Scaleway | DEV1-L: 31.27; BASIC2-A4C-8G: 37.74 | BASIC2-A8C-16G: 75.48 | BASIC2-A16C-32G: 150.89 | Yes | Yes | Storage and IPv4 extra | Paris | Not checked | https://www.scaleway.com/en/pricing/virtual-instances/ |
| Oracle Always Free (Ampere A1) | Docs state the allowance is "equivalent to 2 OCPUs and 12 GB" for Always Free tenancies | n/a | n/a | n/a | n/a | 200 GB block storage | Home region only | "Out of host capacity" errors are documented; idle instances may be reclaimed (7-day window, CPU 95th percentile, network and memory all under 20%) | https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm |
| Infomaniak VPS Lite | CHF 18.00 (secondary) | Not read | Not read | Not read | Not read | Not read | Switzerland | Not checked | https://www.infomaniak.com/fr/hebergement/vps-lite (not read directly) |
| OVH Public Cloud B3 | b3-8 is 2c / 8 GB at 0.0566 USD/h (about 41 USD/month); b3-16 4c/16 GB 0.1132 USD/h (secondary, USD page) | Above budget | Above budget | Yes | Yes | Extra | Yes | Not checked | https://www.ovhcloud.com/fr/public-cloud/prices/ (table did not load) |

Notes:
- OVH no-commitment prices are computed from the configurator's statement "12 mois: économisez 15 %" (and 6 months: 5 %); they were not displayed because no datacenter could be selected. The VPS-1 total of 45.72 EUR for 12 months (= 3.81 x 12) confirms the "à partir de" price is the 12-month price.
- Netcup net prices are computed as displayed gross / 1.19. The page shows the 12-month and 1-month price side by side (14.50 and 16.68 for VPS 1000; 14.50 / 0.87 = 16.67).
- The Oracle allowance of 2 OCPU / 12 GB contradicts the commonly cited 4 OCPU / 24 GB. The same page still lists 1,500 OCPU-hours and 9,000 GB-hours "for all tenancies". It is too small and too uncertain for the Factory either way.
- OVH Public Cloud is not a better scalable option inside this budget: a 2-core instance already costs about as much as the whole budget.

## Comparison: CI options

Factory CI cost uses W1-avg (9,344 four-core minutes) and W1-max (16,640). W2 = 500 two-core minutes.

| Option | Unit price (Linux x64) | Free tier | W1 Factory CI per month | W2 SayMyName per month | Docker / Testcontainers / browser e2e | EU region | GitHub App needed | Source (read 2026-10-11) |
|---|---|---|---|---|---|---|---|---|
| GitHub-hosted, public repo | 0 on standard runners (4c / 16 GB); larger runners always charged | Unlimited | 0 | n/a (repos private) | Yes | n/a | No | https://docs.github.com/en/billing/concepts/product-billing/github-actions ; https://docs.github.com/en/actions/reference/runners/github-hosted-runners |
| GitHub-hosted, private, 2-core | 0.006 USD/min; arm64 2-core 0.005; 1-core 0.002 | Team: 3,000 min | (35,940 + 500 - 3,000) x 0.006 = about 201 USD; max (64,000 + 500 - 3,000) x 0.006 = 369 USD | 0 (500 < 3,000) | Yes | n/a | No | https://docs.github.com/en/billing/reference/actions-runner-pricing |
| GitHub larger runners, private | 4-core 0.012; 8-core 0.022; 16-core 0.042; arm64 4-core 0.008, 8-core 0.014 | None assumed | 9,344 x 0.012 = 112 USD; max 16,640 x 0.012 = 200 USD | n/a | Yes | n/a | No | Same |
| Self-hosted runner, private | 0 today. Announced then postponed: 0.002 USD/min | n/a | 0. If the charge applied without quota: 9,344 x 0.002 = 18.7 USD; max 16,640 x 0.002 = 33.3 USD | n/a | Yes if a container engine is installed | Own VM | No | https://github.com/resources/insights/2026-pricing-changes-for-github-actions |
| Ubicloud | 2 vCPU 0.00125; 4 vCPU 0.0025; 8 vCPU 0.005; 16 vCPU 0.01 (premium: 0.002 / 0.004 / 0.008 / 0.016) | 2.50 USD credit/month | 9,344 x 0.0025 - 2.50 = 20.86 USD; max 16,640 x 0.0025 - 2.50 = 39.10 USD | 500 x 0.00125 = 0.63 USD | Not stated on the pages read | Germany | Yes ("Ubicloud Managed Runners") | https://www.ubicloud.com/docs/about/pricing |
| Blacksmith | 2 vCPU 0.004; 4 vCPU 0.008; 8 vCPU 0.016 (linear) | 3,000 two-vCPU min/month per organization (= 1,500 four-vCPU min) | (9,344 - 1,500) x 0.008 = 62.75 USD; max (16,640 - 1,500) x 0.008 = 121.12 USD | 0 if the free tier is not used by W1; else 500 x 0.004 = 2.00 USD | Linux Docker not stated on the page read | Amsterdam, Frankfurt (change of region via support) | Yes, on every repository using it | https://www.blacksmith.sh/pricing ; https://docs.blacksmith.sh/blacksmith-runners/overview.md |
| WarpBuild | 2 vCPU 0.004; 4 vCPU 0.008; 8 vCPU 0.016; BYOC 0.002 | Amount not stated | 9,344 x 0.008 = 74.75 USD; max 133.12 USD | 2.00 USD | Not read | Not listed | Yes (assumed) | https://www.warpbuild.com/pricing |
| Namespace | 0.0015 USD per unit-minute pay-as-you-go (1 unit = 1 vCPU + 2 GB); 4c/8 GB = 0.006/min; Team plan 100 USD for 100,000 units | 30-day trial only | 9,344 x 0.006 = 56.06 USD; max 99.84 USD | 500 x 0.003 = 1.50 USD | Not read | Not stated | Yes (assumed) | https://namespace.so/pricing |
| Depot | 2x8 0.006/min; 4x16 0.012; 8x32 0.024; Developer plan 20 USD with 2,000 min | 7-day trial | About 112 USD; max about 200 USD, plus plan | Inside the plan | Not read | "US & EU regions" | Yes (assumed) | https://depot.dev/pricing |
| RunsOn (own AWS account) | License 300 EUR/year (25 EUR/month) for commercial use; AWS spot 4 vCPU about 0.0015 USD/min (us-east-1); control plane about 7 USD | Free license for non-commercial use | 25 EUR + 7 USD + 9,344 x 0.0015 = 25 EUR + 21 USD; max 25 EUR + 32 USD | Negligible | Yes (full EC2 VM) | AWS EU regions exist; EU prices not read | Yes (private app) | https://runs-on.com/pricing/ |
| Cirrus Runners | 150 USD per runner per month, unlimited minutes (x64: 16 vCPU / 48 GB) | None | 150 USD | n/a | KVM available | Not stated | Yes (assumed) | https://cirrus-runners.app/pricing/ |
| BuildJet | Closed: stopped accepting jobs on 2026-03-31 (secondary) | n/a | n/a | n/a | n/a | n/a | n/a | https://runs-on.com/blog/buildjet-shutting-down-runson-alternative/ |
| TestFlows github-hetzner-runners | Hetzner hourly price per server (one-hour minimum unless recycling); needs an always-on service and a classic GitHub token | n/a | About 74 EUR or more on CPX32 (see above) | n/a | Yes, native Docker | Germany, Finland | No | https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners |

### GitHub Actions facts (question 1)

- Public repositories: standard GitHub-hosted runners are free; "Larger runners are always charged for, even when used by public repositories."
- Standard Linux runner size: 4 cores / 16 GB on public repositories, 2 cores / 8 GB on private repositories.
- Team plan: 3,000 included minutes, 2 GB artifact storage, 10 GB cache per repository. Team plan price: 4 USD per user per month.
- Concurrency on Team: 60 standard jobs, 1,000 larger-runner jobs. GitHub-hosted job limit 6 hours; self-hosted job limit 5 days, queue limit 24 hours.
- Hosted-runner price cuts took effect on 2026-01-01 (GitHub changelog).
- Self-hosted charge: GitHub announced on 2025-12-16 a 0.002 USD/min "Actions cloud platform charge" for self-hosted runners on private repositories from 2026-03-01. GitHub's own page then states: "We're postponing the announced billing change for self-hosted GitHub Actions to take time to re-evaluate our approach." No new date was found on github.com, docs.github.com or the changelog. The billing documentation read today says self-hosted usage is free. Status: postponed, not cancelled.
- Copilot code review has consumed Actions minutes on private repositories since 2026-06-01.

## Not verified

Figures not confirmed on a primary page:
- Contabo: whether the displayed prices are VAT-exclusive (no VAT label on the order form; the coordinator's figures treat them as net). The 1-month price was read only for Cloud VPS 8 (14.00); the others are computed as the 24-month price / 0.8.
- Contabo: no first-party statement on CPU allocation, overselling or steal was found. Cloud VPS is the shared line; Contabo sells a separate "Cloud VDS" with dedicated resources.
- OVHcloud: no-commitment prices are computed, not read. The unavailability message was read on the Europe tab of the configurator for VPS-2, VPS-3 and VPS-4; no restock date is given.
- OVH Public Cloud: EUR prices not read (table did not load); USD figures are from a search summary of OVH's English page.
- Hetzner: CX/CAX prices could not be read today; the "not available" label was read. CCX prices were only seen in a screenshot and are not reported.
- Hetzner auction: floor read from the live data file at one moment; it changes hourly.
- IONOS: the price after the 3-month promotion is taken from the crossed-out price; term and resize rules not read.
- Infomaniak: CHF 18.00 for 4c / 8 GB comes from a search summary; VAT basis and EUR price unknown.
- Blacksmith: the per-size table (0.008 USD for 4 vCPU) comes from a search summary of its docs; the pricing page itself shows one rate (0.004 USD) with a size selector.
- BuildJet closure: vendor blogs only; BuildJet's own notice was not read.
- WarpBuild, Namespace, Depot, Cirrus: GitHub App requirement, Linux Docker support and EU region are assumed or not stated on the pages read.
- Ubicloud: Docker / Testcontainers support, concurrency quota for new accounts and repository scope of the GitHub App were not stated on the pages read.
- RunsOn: AWS prices are us-east-1 seven-day spot averages; EU region prices not read.
- GitHub: whether larger runners can draw on included minutes was not read (assumed not). Current status of the self-hosted charge after December 2025 rests on the absence of a newer official notice.
- USD to EUR rate not looked up.

Assumptions:
- A rented vCPU is treated as equal to one core of the PC. Shared vCPUs are probably slower, so run times and runner-minutes may be higher than computed.
- The average-case billed minutes on GitHub 2-core runners (28.1 per run) are scaled from the green-run figure.
- Factory CI volume (1,280 runs/month) is taken as stable; it depends on agent activity and can grow.
- Worker test peaks on the Factory VM are not measured. The 8c / 24 GB size is a starting point; the 1-month term exists to measure before committing.
- Testcontainers and browser e2e are taken to work on GitHub-hosted `ubuntu-latest` because the three SayMyName workflows already run there.
- Making agent-factory public (Scenario A) is Benjamin's decision; secret scanning of history and fork pull-request settings were not examined.

## Sources

GitHub
- https://docs.github.com/en/billing/reference/actions-runner-pricing
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/limits
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/actions/reference/runners/self-hosted-runners
- https://docs.github.com/en/actions/reference/security/secure-use
- https://github.com/pricing
- https://github.com/resources/insights/2026-pricing-changes-for-github-actions
- https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/
- https://github.blog/changelog/2026-01-01-reduced-pricing-for-github-hosted-runners-usage/
- https://github.blog/changelog/2026-04-27-github-copilot-code-review-will-start-consuming-github-actions-minutes-on-june-1-2026/
- https://github.com/orgs/community/discussions/182186

Managed runners
- https://www.ubicloud.com/docs/about/pricing
- https://www.ubicloud.com/docs/github-actions-integration/price-performance
- https://www.ubicloud.com/docs/github-actions-integration/quickstart
- https://www.blacksmith.sh/pricing
- https://docs.blacksmith.sh/blacksmith-runners/overview.md
- https://namespace.so/pricing
- https://depot.dev/pricing
- https://www.warpbuild.com/pricing
- https://runs-on.com/pricing/
- https://cirrus-runners.app/pricing/
- https://github.com/testflows/TestFlows-GitHub-Hetzner-Runners
- https://runs-on.com/blog/buildjet-shutting-down-runson-alternative/ (secondary)
- https://www.warpbuild.com/blog/buildjet-shutting-down (secondary)

VM providers
- https://www.ovhcloud.com/fr/vps/
- https://www.ovhcloud.com/fr/vps/configurator/?planCode=vps-2027-model3&brick=VPS%2BModel%2B3&pricing=upfront12
- https://www.ovhcloud.com/fr/public-cloud/prices/
- https://contabo.com/en/vps/
- https://contabo.com/en/vps/cloud-vps-core-8/
- https://contabo.com/blog/kb/103000269722-can-i-change-my-virtual-private-server-vps-plan/
- https://www.netcup.com/en/server/vps
- https://www.netcup.com/en/server/root-server
- https://www.hetzner.com/cloud/
- https://www.hetzner.com/cloud/cost-optimized/
- https://www.hetzner.com/cloud/regular-performance/
- https://www.hetzner.com/cloud/general-purpose/
- https://www.hetzner.com/sb/
- https://www.scaleway.com/en/pricing/virtual-instances/
- https://www.ionos.fr/serveurs/vps
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://www.infomaniak.com/fr/hebergement/vps-lite (not read directly)
