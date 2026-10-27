# Clash Studio 1.2

产品版本 1.2，程序版本 1.2.0，Android versionCode 7。

本版新增桌面 TUN 严格模式开关，以及桌面和安卓的 DNS 防泄漏开关。TUN 严格模式默认开启；DNS 防泄漏默认关闭，兼容已有配置。

开启 DNS 防泄漏后，主解析使用经专用代理组连接的境外加密 DNS，替换订阅及 DNS 覆写中的上游策略；代理不可用时不回落到原明文 DNS。节点域名和直连出口的国内 DNS 解析为明确例外；仅保护内核处理的 DNS。关闭后恢复原订阅或自定义 DNS。Android 网络设置保存后需重新应用 VPN。

交付 Windows x64 安装版和便携版、Linux x64（Ubuntu 22.04 基线）、Android ARM64 Release APK，以及源码与 SHA-256 校验文件。Android 沿用 1.1 本地发布包使用的签名密钥；Windows EXE 未做 Authenticode 签名。

用户已确认本轮验收和功能验证完成。PJE110 Android 专项实测 14 项通过，Windows DNS 实际联网检查 9 项通过；Windows TUN 等手工验收由用户确认完成。版本构建检查记录见 [1.2 构建记录](docs/validation-1.2.md)。

本次生成本地产物；不自动上传 GitHub 或替换已安装应用。
