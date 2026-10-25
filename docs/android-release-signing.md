# Android 正式签名

正式构建：设置 `CLASHSTUDIO_KEYSTORE`（PKCS12 文件绝对路径）及 `CLASHSTUDIO_STORE_PASSWORD`，别名为 `clashstudio`，再运行 `scripts/build-android.ps1 -Release`。私钥和密码必须保存在仓库外并独立备份。

1.0 使用独立正式签名，旧调试版必须先导出配置、卸载再安装。包标识保持不变。正式 APK 已关闭调试标志，证书 SHA256 为 `8197aaec5fd1565944174bccd8c30f9d5d9f7aff96e7234343ccf1a36aed8968`。
