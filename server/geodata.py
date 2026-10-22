"""Seed bundled rule databases without replacing an existing runtime database."""
from pathlib import Path
import hashlib
import json
import secrets
import shutil

NAMES = ("Country.mmdb", "geoip.dat", "geosite.dat", "ASN.mmdb")


def seed_databases(home: Path, runtime_dir: Path):
    bundled = home / "bin" / "geodata"
    manifest = bundled / "source.json"
    if not manifest.is_file():
        return []
    metadata = json.loads(manifest.read_text(encoding="utf-8-sig"))
    checksums = {item["name"]: item["sha256"] for item in metadata.get("files", [])}
    copied = []
    for name in NAMES:
        source, destination = bundled / name, runtime_dir / name
        if destination.exists() or not source.is_file() or name not in checksums:
            continue
        expected = checksums[name]
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError(f"随附规则数据库 {name} 的摘要不匹配，请重新补齐数据库")
        temporary = destination.with_name(f".{name}.{secrets.token_hex(4)}.tmp")
        try:
            shutil.copyfile(source, temporary)
            # An existing runtime file belongs to its current configuration.
            if not destination.exists():
                temporary.replace(destination)
                copied.append(name)
        finally:
            temporary.unlink(missing_ok=True)
    return copied


def validation_message(log_path: Path, running: bool):
    text = log_path.read_bytes()[-65536:].decode("utf-8", errors="replace").lower()
    suffix = "原内核继续使用旧配置。" if running else "新内核尚未启动。"
    if "mmdb" in text and any(term in text for term in ("download", "can't initial", "invalid", "not exist")):
        reason = "GeoIP 地区数据库 Country.mmdb 缺失、无法读取或下载失败，请补齐 data/runtime/Country.mmdb 并检查下载网络。"
    elif any(term in text for term in ("can't download geoip", "can't download geosite", "can't initial geosite")):
        reason = "GeoIP/GeoSite 规则数据库无法加载或下载，请检查本地规则数据库和下载网络。"
    else:
        reason = "Mihomo 配置校验未通过。"
    # Do not echo raw kernel output: it may contain URLs and profile credentials.
    return reason + suffix + "详情见 data/runtime/validation.log"
