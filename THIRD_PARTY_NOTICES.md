# Third-party notices and acknowledgements

Clash Studio project code is licensed under GPL-3.0-only; see LICENSE. Third-party components and datasets retain their own licenses. The application is an independent community project and is not an official release of Tauri, Clash, Mihomo, or Clash Verge Rev.

## Subscription editing foundation

Clash Studio incorporates and modifies code from [Clash Subscription Studio](https://github.com/zheng0625/clash-subscription-studio), version 0.4.1, GPL-3.0-only. The integrated backend snapshot is in vendor/app; the desktop editor and runtime integration are developed in this repository. Original project licensing and attribution are retained.

## Desktop, proxy and runtime components

- Tauri 2 and its plugins: MIT OR Apache-2.0. Upstream: https://github.com/tauri-apps/tauri. Bundled notices are under licenses/rust, with the MIT text also under licenses/Tauri-MIT.txt.
- Clash / Dreamacro and contributors: the original configuration, rule and proxy ecosystem on which the Clash-compatible ecosystem is based. Mihomo is the actual bundled core in this release.
- Mihomo v1.19.33, unmodified official Windows and Linux amd64 compatible binaries: GPL-3.0. Upstream: https://github.com/MetaCubeX/mihomo/tree/v1.19.33. Its license is included as licenses/Mihomo-GPL-3.0.txt and the corresponding upstream source archive is provided as the release attachment mihomo-v1.19.33-source.tar.gz. The downloaded binary archive digest is recorded in bin/source.json (Windows) and bin/linux-core-source.json (Linux).
- Wintun 0.14.1: Copyright WireGuard LLC. Source: https://www.wintun.net/builds/wintun-0.14.1.zip. The official DLL is bundled unmodified and its distributed license is in licenses/Wintun-LICENSE.txt.
- Python 3.12 on Windows and Python 3.10 on Linux: PSF license; bundled notices are in runtime/python/LICENSE.txt (Windows) or runtime/python/Python-COPYRIGHT.txt (Linux). Package licenses are retained in the bundled site-packages dist-info directories; versions are in requirements.lock.txt.
- NSIS: the Windows installer is generated using NSIS. Its license notice is provided in licenses/NSIS-COPYING.txt. https://nsis.sourceforge.io/License
- Linux uses system GTK, WebKitGTK, GLib, Ayatana AppIndicator and polkit libraries; these remain system dependencies and retain their respective upstream licenses.
- Vue, Vite and Lucide: frontend framework, tooling and icons. Vue and Lucide notices are reproduced below; available package license files are retained under licenses/frontend.
- Clash Verge Rev: reference for desktop interaction and layout, https://github.com/clash-verge-rev/clash-verge-rev. Acknowledgement does not imply affiliation or endorsement.
- Rust dependency versions are recorded in src-tauri/Cargo.lock; frontend versions in frontend/pnpm-lock.yaml. License files collected from the build dependency sources are inventoried in licenses/dependency-license-files.json. The inventory includes build dependencies as well as runtime dependencies.
- The package uses the system Microsoft Edge WebView2 Runtime. It is not bundled. Official distribution information: https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution.

## Rule and geolocation databases

Country.mmdb, geoip.dat, geosite.dat and ASN.mmdb are bundled as a fixed snapshot. The input download URLs, date and SHA-256 values are recorded in bin/geodata/source.json; the public package retains this provenance. This release does not claim that the snapshot is the latest available data. No subscription or private user data is included.

- Download/build project: MetaCubeX/meta-rules-dat, https://github.com/MetaCubeX/meta-rules-dat. The project GPL-3.0 text and its upstream attribution list are included as licenses/Meta-Rules-Dat-GPL-3.0.txt and licenses/Meta-Rules-Dat-README.md. This does not relicense underlying third-party datasets.
- Upstream GeoIP and domain sources include Loyalsoldier/geoip, Loyalsoldier/v2ray-rules-dat, v2fly/domain-list-community, xishang0128/geoip, blackmatrix7/ios_rule_script and their respective contributors. The preserved upstream README files describe their aggregation and additional sources.
- This product includes GeoLite2 data created by MaxMind, available from https://www.maxmind.com/. Database and contents copyright MaxMind, Inc. Relevant data terms: Creative Commons Attribution-ShareAlike 4.0 International (https://creativecommons.org/licenses/by-sa/4.0/) and the upstream GeoLite2 terms (https://www.maxmind.com/en/geolite2/eula). The CC legal code is included as licenses/MaxMind-CC-BY-SA-4.0.html.
- Country/GeoIP/domain files are redistributed without content changes by Clash Studio. ASN.mmdb is the upstream GeoLite2-ASN.mmdb renamed for the core; its contents are unchanged. Upstream projects perform their own generation and aggregation; their terms and source attributions remain applicable.

The root GPL license covers the application's own code, not a replacement license for these separate databases or components. Trademarks and project names remain with their owners. Software and data are provided without warranties as described by their applicable licenses.

## Vue

```text
The MIT License (MIT)

Copyright (c) 2018-present, Yuxi (Evan) You

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

```

## Lucide

```text
ISC License

Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors 2022.

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

```
# Android 开发版新增依赖

Android 开发版使用 SnakeYAML 2.7（Apache License 2.0）解析 Clash YAML：
https://bitbucket.org/snakeyaml/snakeyaml 。AndroidX WebKit / Activity 同样采用
Apache License 2.0。许可正文随 APK 放在 `assets/licenses/`。
`org.json:json` 与 JUnit 仅供 JVM 单元测试，不作为应用依赖打入 APK。

Android ARM64 内核使用 Mihomo v1.19.32，JNI 包装库为 libmihomo-android v0.3.11（GPL-3.0），
固定提交 `5acd6a9ebf7946e18c8f0feaf8302fedf4ebb17d`。
源码与构建说明：https://github.com/oviron/libmihomo-android/tree/5acd6a9ebf7946e18c8f0feaf8302fedf4ebb17d 。
AAR SHA-256 固定校验，许可与来源记录随 APK 放在 `assets/licenses/`。
Kotlin 标准库 2.2.21 为 Apache-2.0。

Android 二维码识别使用 ZXing Android Embedded 4.3.0（https://github.com/journeyapps/zxing-android-embedded）
和 ZXing Core 3.5.3（https://github.com/zxing/zxing），均为 Apache-2.0。
相机图像与用户选择的照片在设备上识别，不上传至识别服务。
