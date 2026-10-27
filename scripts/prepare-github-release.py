"""Add public documentation, notices and corresponding sources to a built ZIP.

The application binary and runtime payload are copied unchanged. Existing
release outputs are never overwritten. All paths remain inside this project.
"""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = "ClashStudio-0.5.1-portable-windows-x64"
PUBLISH = ROOT / "artifacts/github-publish"
SOURCE = PUBLISH / "Clash-Studio"
RELEASE = PUBLISH / "release"
OUT = RELEASE / NAME
COMMIT = "630a329f3d153780545939f5e0f52efd9ac2a57e"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    original = ROOT / "artifacts/releases" / NAME
    if RELEASE.exists():
        raise SystemExit("Public release output already exists; refusing to overwrite.")
    shutil.copytree(original, OUT)
    for name in ["README.md", "README.en.md", "BUILDING.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "RELEASE.md"]:
        shutil.copy2(SOURCE / name, OUT / name)
    shutil.copytree(SOURCE / "licenses", OUT / "licenses", dirs_exist_ok=True)
    shutil.copy2(SOURCE / "bin/geodata/source.json", OUT / "bin/geodata/source.json")
    mihomo = PUBLISH / "mihomo-v1.19.33-source.tar.gz"
    shutil.copy2(mihomo, OUT / "source" / mihomo.name)
    source_zip = RELEASE / "ClashStudio-0.5.1-source.zip"
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(SOURCE.rglob("*")):
            if path.is_file() and ".git" not in path.relative_to(SOURCE).parts:
                archive.write(path, path.relative_to(SOURCE).as_posix())
    shutil.copy2(source_zip, OUT / "source/ClashStudio-source.zip")
    shutil.copy2(mihomo, RELEASE / mihomo.name)
    assert digest(original / "ClashStudio.exe") == digest(OUT / "ClashStudio.exe")
    manifest = json.loads((original / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(public_source_commit=COMMIT, public_release=True,
                    package_changes="Documentation, licenses, provenance and corresponding sources only; executable unchanged")
    manifest["files"] = [{"path": path.relative_to(OUT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
                         for path in sorted(OUT.rglob("*")) if path.is_file() and path != OUT / "manifest.json"]
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive_path = RELEASE / (NAME + ".zip")
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                archive.write(path, (Path(NAME) / path.relative_to(OUT)).as_posix())
    files = [archive_path, source_zip, RELEASE / mihomo.name]
    lines = [digest(path) + "  " + path.name for path in files]
    (RELEASE / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    archive_path.with_suffix(".zip.sha256").write_text(lines[0] + "\n", encoding="ascii")
    print(json.dumps({"files": [{"name": path.name, "bytes": path.stat().st_size, "sha256": digest(path)} for path in files],
                      "manifest_files": len(manifest["files"]), "source_commit": COMMIT}))


if __name__ == "__main__":
    main()
