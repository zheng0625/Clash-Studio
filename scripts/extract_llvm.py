from pathlib import Path
import sys
import tarfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / '.toolchain/pydeps'))
import zstandard

destination = root / '.toolchain/llvm/bin'
destination.mkdir(parents=True, exist_ok=True)
wanted = {'clang-cl.exe', 'lld-link.exe', 'llvm-rc.exe', 'llvm-ar.exe', 'llvm-lib.exe', 'llvm-cvtres.exe'}
with (root / '.toolchain/downloads/llvm.tar.zst').open('rb') as source:
    with zstandard.ZstdDecompressor().stream_reader(source) as reader:
        with tarfile.open(fileobj=reader, mode='r|') as archive:
            for member in archive:
                name = Path(member.name).name
                if member.isfile() and '/bin/' in member.name and (name in wanted or name.lower().endswith('.dll')):
                    stream = archive.extractfile(member)
                    if stream:
                        (destination / name).write_bytes(stream.read())
                        print(name)
