"""Compatibility entry point for the Android-derived shared brand icon build."""
from pathlib import Path
import subprocess

if __name__ == '__main__':
    subprocess.run(['node', str(Path(__file__).with_name('build-brand-icons.cjs'))], check=True)
