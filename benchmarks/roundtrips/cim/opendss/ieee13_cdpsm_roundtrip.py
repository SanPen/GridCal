from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import VeraGridEngine.api as vg
from VeraGridEngine.IO.file_open import FileOpenOptions
from VeraGridEngine.IO.file_save import FileSavingOptions
from VeraGridEngine.enumerations import FileType


def run_fixture(cim_path: Path) -> tuple[int, float]:
    export_path = cim_path.with_name(f"{cim_path.stem}_roundtrip_export.xml")

    grid = vg.open_file(str(cim_path), options=FileOpenOptions(file_type=FileType.CIM))
    first = vg.power_flow(grid)
    assert first.converged

    vg.FileSave(
        circuit=grid,
        file_name=str(export_path),
        options=FileSavingOptions(file_type=FileType.CIM),
    ).save()

    roundtrip_grid = vg.open_file(str(export_path), options=FileOpenOptions(file_type=FileType.CIM))
    second = vg.power_flow(roundtrip_grid)
    assert second.converged
    max_abs_voltage_diff = float(np.max(np.abs(first.voltage - second.voltage)))
    assert np.allclose(first.voltage, second.voltage, atol=1e-6)

    print("ok")
    print(f"fixture={cim_path}")
    print(f"export={export_path}")
    print(f"buses={len(grid.buses)}")
    print(f"max_abs_voltage_diff={max_abs_voltage_diff}")
    return len(grid.buses), max_abs_voltage_diff


def main() -> None:
    if len(sys.argv) > 1:
        cim_path = Path(sys.argv[1]).resolve()
    else:
        cim_path = Path(__file__).with_name("ieee13cdpsm.xml")

    run_fixture(cim_path)


if __name__ == "__main__":
    main()
