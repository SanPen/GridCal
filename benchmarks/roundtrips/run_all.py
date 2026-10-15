from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def run_script(script_path: Path) -> None:
    print(f"== {script_path.relative_to(Path(__file__).resolve().parent)} ==")
    subprocess.run([sys.executable, str(script_path)], check=True)


def main() -> None:
    root = Path(__file__).resolve().parent
    scripts = [
        root / "cim" / "opendss" / "run_all.py",
        root / "raw" / "psse" / "run_raw_roundtrip.py",
        root / "matpower" / "run_matpower_roundtrip.py",
        root / "ucte" / "run_ucte_roundtrip.py",
        root / "cgmes" / "run_cgmes_roundtrip.py",
        root / "pandapower" / "run_pandapower_roundtrip.py",
        root / "pypowsybl" / "run_pypowsybl_roundtrip.py",
    ]

    for script_path in scripts:
        run_script(script_path)


if __name__ == "__main__":
    main()
