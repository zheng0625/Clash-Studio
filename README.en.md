# Clash Studio

**Visual subscription editing, reusable routing modules, and precise traffic routing for Windows.**

[简体中文](README.md) · [Download](https://github.com/zheng0625/Clash-Studio/releases) · [GPL-3.0](LICENSE)

Clash Studio brings the subscription editing capabilities of [Clash Subscription Studio](https://github.com/zheng0625/clash-subscription-studio) into a Tauri desktop client powered by Mihomo. Keep source subscriptions separate from personal edits, then compose routing modules into a configuration you can inspect and apply.

## What makes it different

- **Editable subscriptions:** rename or exclude nodes, edit proxy group members and order, manage rules, preview YAML, publish drafts, and restore history. Saved edits are reapplied after source refreshes, with conflicts and validation results surfaced.
- **Reusable routing modules:** match domains, suffixes, process names or paths, and IPv4/IPv6 subnets. Assign each module to an outbound or proxy group, enable it per plan, and order modules ahead of source rules.
- **Strict outbound review:** check visible nested chains for reachable DIRECT, missing or circular references, and dynamic members that cannot be fully inspected.
- **Inspect real routing:** view the core's actual connections, matched rules, policy chains, and transferred bytes.
- **Desktop features:** system proxy, TUN with an on-demand administrator helper, individual/group/all-node HTTP latency tests, live traffic, session totals, public IP lookup, LAN proxy authentication, custom ports, IPv6, DNS overrides, and GeoData updates.
- **Personalization:** custom palettes, full-window photo backgrounds with crop and preview, and Chinese/English selection following the Windows display language by default.
- **Startup:** concurrent window/backend initialization, a loading view, and on-demand page loading.

Routing precision applies to traffic captured by the core and depends on capture mode, process detection, and network conditions. Strict review does not guarantee a fixed public IP. There is currently no firewall kill switch after the core exits.

## Portable Windows release

Download **0.5.1 Windows x64** from [Releases](https://github.com/zheng0625/Clash-Studio/releases), extract the entire ZIP into a writable directory, and run `ClashStudio.exe`.

Python, Mihomo, Wintun, and four base rule databases are bundled. The system must have [Microsoft Edge WebView2 Runtime](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution). Remote providers or rule sets referenced by your subscription still require a network connection. No proxy service or usable subscription is included.

Import a subscription, edit and publish it, compose routing modules, select system proxy or TUN, and apply. Check actual connections to inspect the result. Language: **Settings and logs → Settings → Interface language**.

Data stays in `data/` beside the application. Close the old version and back up this directory before upgrading. Do not run multiple versions simultaneously.

## Development and status

Stack: **Tauri 2 / Rust, Vue 3 / TypeScript / Vite, a local Python backend, and Mihomo**. See [BUILDING.md](BUILDING.md) for the source layout and build instructions.

This is a development preview for Windows x64. Type checking, frontend/Rust builds, and package integrity checks passed. This release has not undergone full clean-Windows, language-layout, or UAC/TUN validation. Unknown backend and third-party diagnostics retain their original text.

## License and acknowledgements

Project code is licensed under **GNU GPL v3.0, SPDX: GPL-3.0-only**, with no warranty. Dependencies and datasets retain their own terms; see [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Thanks to **Clash Subscription Studio**, **Tauri**, **Clash / Dreamacro and contributors**, **Mihomo / MetaCubeX**, and **Clash Verge Rev** for the foundations and design inspiration. Thanks also to **Vue**, **Vite**, **Lucide**, **Python**, **FastAPI**, **WireGuard / Wintun**, **meta-rules-dat**, **Loyalsoldier**, **v2fly/domain-list-community**, **MaxMind**, and their upstream contributors. Project links and attribution details are in the [Chinese README](README.md#致谢).

Clash Studio is an independent community project and is not endorsed by or affiliated with these upstream projects.
