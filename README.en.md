<p align="center"><img src="frontend/src/assets/brand.svg" width="84" alt="Clash Studio"></p>
<h1 align="center">Clash Studio</h1>
<p align="center">Project maintenance and code contributions: <a href="https://github.com/zheng0625">zheng0625</a></p>
<p align="center">Precise routing. Thoughtful desktop design.</p>
<p align="center"><a href="https://github.com/zheng0625/Clash-Studio/releases/tag/v1.3">Download for Windows / Linux / Android</a> · <a href="README.md">简体中文</a> · <a href="CHANGELOG.md">Changelog</a> · <a href="LICENSE">GPL-3.0</a></p>

**Clash Studio is a Windows / Linux Mihomo desktop client focused on visual subscription editing, reusable routing modules and precise routing, with a customizable desktop interface.**

It connects source subscriptions, personal edits, routing modules and runtime configuration. Organize nodes, groups and rules, then route domains, application processes and IP subnets through selected groups and exits.

![Clash Studio 0.5.17 overview using a demo configuration; public IP lookup disabled](docs/screenshots/overview.png)

## Precise routing comes first

- Match domains, domain suffixes, process names, process paths, and IPv4 / IPv6 subnets.
- Assign each module a group or exit; reuse, enable and order modules across subscription plans. Module rules precede source subscription rules.
- Inspect visible nested exit chains in strict mode, rejecting reachable DIRECT exits, missing or cyclic references, and dynamic members that cannot be fully inspected.
- Check actual Mihomo rule matches, chains and traffic in the connection view.

![Reusable routing modules](docs/screenshots/routing-modules.png)

Precision applies to traffic captured by the core with identifiable matching conditions. Coverage depends on system proxy / TUN, process recognition and network conditions. Strict checks do not guarantee a fixed public IP. There is currently no firewall kill switch after the core exits.

## On-device checks: routing and DNS leak prevention

These three IPLeak screenshots were supplied by the user, who confirmed the test states. Images are cropped; opaque blocks cover IP addresses, DNS server addresses and mDNS host identifiers. Reported locations, providers and detection counts remain visible.

| Test state | Public IP / WebRTC | DNS results |
| --- | --- | --- |
| Proxy off | China Unicom exit; IPv4 and IPv6 detected; WebRTC shows the local ISP public IP | Page reports 19 servers and 37 tests; visible entries are domestic ISP servers |
| TUN on, DNS leak prevention off | Both show Singapore exits; IPv6 test unreachable | Page reports 23 servers and 5 tests; visible entries mix China Unicom and Singapore servers |
| DNS leak prevention on / routing result example | Both show Singapore exits; IPv6 test unreachable | Page reports 12 servers and 7 tests; all listed DNS servers are labeled Singapore / Amazon |

**Proxy off — local network baseline.** Public IP, WebRTC and visible DNS entries identify the local ISP.

![Proxy off: local ISP public exit and DNS results; addresses redacted](docs/screenshots/ipleak-no-proxy.png)

**TUN on, protection off — a proxy exit alone does not establish DNS protection.** Web access and WebRTC show Singapore, while the DNS list still includes China Unicom servers.

![TUN on, DNS leak prevention off: Singapore exit with mixed domestic and overseas DNS entries; addresses redacted](docs/screenshots/ipleak-tun-dns-off.png)

**Protection on — no local ISP DNS appears in this capture.** The tester also supplied this image as an exit result example for precise routing. Web access and WebRTC show Singapore; every listed DNS server is labeled Singapore / Amazon. Web access and WebRTC use different IP addresses. Verify the actual routing rule and chain in Clash Studio's connection view.

![DNS leak prevention on and routing exit example: Singapore exits and DNS entries; addresses redacted](docs/screenshots/ipleak-tun-dns-on-routing.png)

These are observations at capture time. Test counts differ, so server counts are not a performance metric. OS, application version and browser secure DNS settings were not supplied. An unreachable IPv6 test does not validate every IPv6 scenario. Protection covers DNS handled by the core, with explicit domestic DNS exceptions for node domains and direct exits; these captures do not establish leak prevention for every application or network.

## A considered desktop interface

- Liquid Glass inspired layers, rounded cards and a floating Dock organize the workspace.
- Light / dark themes, custom colors and full-window photo backgrounds, with cropping and previews.
- Dedicated appearance dialogs and horizontally centered notifications above the Dock.
- Immediate node feedback, coalesced rapid clicks and less repeated rendering. Select manual nodes before starting the main core.
- Simplified Chinese / English, system language following, lazy page loading and parallel desktop / backend startup.

![Appearance settings](docs/screenshots/appearance.png)

## Edit subscriptions and keep your changes

Built on [Clash Subscription Studio](https://github.com/zheng0625/clash-subscription-studio), the editor separates source configuration from persistent user edits. Import URL / YAML subscriptions, edit nodes, groups and rules, refresh while replaying edits, review conflicts, preview YAML, publish and restore history.

The workflow is draft → preview → save and publish → apply to the core. Manual node choices are stored per subscription and restored on the next start. Automatic groups retain automatic routing.

![Configuration workbench](docs/screenshots/configuration-workbench.png)

## Desktop features

Windows supports system proxy and TUN with an on-demand administrator helper. Linux supports GNOME system proxy and TUN with graphical authorization for the bundled core. Both include tray integration, desktop startup preferences, HTTP delay testing, traffic and connections, LAN proxy settings, IPv6, DNS overrides and GeoData updates. Login startup launches the application without automatically starting a subscription core.

## Download 1.2

Current version: **1.3** (application version `1.3.0`), integrating the latest desktop and Android UI, responsive subscription cards, rule pagination, shared branding and memory management fixes. TUN strict mode and DNS leak prevention remain available. See the [changelog](CHANGELOG.md) for validation boundaries.

| Package | Download | Application data |
| --- | --- | --- |
| Windows x64 portable | [ZIP](https://github.com/zheng0625/Clash-Studio/releases/download/v1.3/ClashStudio-1.3-portable-windows-x64.zip) | Adjacent `data/` |
| Windows x64 installer | [EXE](https://github.com/zheng0625/Clash-Studio/releases/download/v1.3/ClashStudio-1.3-setup-windows-x64.exe) | `%LOCALAPPDATA%\ClashStudio` |
| Android arm64-v8a | [APK](https://github.com/zheng0625/Clash-Studio/releases/download/v1.3/ClashStudio-1.3-android-arm64-v8a.apk) | App private storage; export settings and uninstall the old debug build first |
| Linux x64 | [tar.gz](https://github.com/zheng0625/Clash-Studio/releases/download/v1.3/ClashStudio-1.3-linux-x64.tar.gz) | Adjacent `data/`, or `--data-dir` |

Extract the entire Windows ZIP and run `ClashStudio.exe`, or use the installer. On Linux, extract and run `./Start.sh`. The Linux package uses an Ubuntu 22.04 x64 baseline . See the [Linux guide](docs/linux-preview.md).

Python, Mihomo v1.19.33 and four base databases are bundled; Windows also includes Wintun. Windows requires system WebView2; Linux requires desktop GTK / WebKit libraries. No development tools are required. Remote providers / rule sets referenced by subscriptions still need network access. No proxy service or usable subscription is provided.

Version 1.2 includes Windows, Linux and Android packages. Automated checks and their scope are in [validation notes](docs/validation-1.2.md). Validation on these devices does not cover every system and network. Windows packages are unsigned. Exit the old version and back up data before upgrading; portable and installed data locations differ.

## Source and license

Tauri 2 / Rust + Vue 3 / TypeScript / Vite + Python local configuration service + Mihomo. See [BUILDING.md](BUILDING.md). Releases include corresponding application source, upstream Mihomo source and SHA-256 checksums. Personal data, subscriptions, binary cores and local toolchains are excluded from the repository.

Project code: **GPL-3.0-only**, see [LICENSE](LICENSE). Dependencies and datasets retain their respective licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Software is provided without warranty. This independent community project is not an official release of Tauri, Clash, Mihomo or Clash Verge Rev.

Thanks to Clash Subscription Studio, Tauri, Clash / Dreamacro and contributors, Mihomo / MetaCubeX, Clash Verge Rev, Vue, Vite, Lucide, Python, FastAPI, WireGuard / Wintun, meta-rules-dat, Loyalsoldier, v2fly, MaxMind and other upstream contributors.

See the [project statement](docs/project-statement.md) for scope, upstream attribution, privacy and platform limits.
