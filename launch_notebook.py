"""Entry point for launching the raw instrument test notebook."""

import subprocess
import sys
from pathlib import Path

NOTEBOOK_RELATIVE_PATH = Path("notebooks") / "instrument_raw_tests.ipynb"


def main() -> None:
    notebook_path = Path.cwd() / NOTEBOOK_RELATIVE_PATH
    if not notebook_path.is_file():
        sys.exit(f"Could not find {notebook_path}. Run this from the SqueezeCtrl repo root.")
    sys.exit(subprocess.call([sys.executable, "-m", "jupyter", "lab", str(notebook_path)]))


if __name__ == "__main__":
    main()
