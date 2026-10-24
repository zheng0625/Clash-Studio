import os
from pathlib import Path
import sys

HOME = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HOME))
sys.path.insert(0, str(HOME / "vendor"))
os.environ["CLASH_STUDIO_DATA"] = str(HOME / "artifacts" / "import-data")
