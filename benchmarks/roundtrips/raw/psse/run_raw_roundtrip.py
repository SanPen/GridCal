from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import VeraGridEngine.api as vg
from VeraGridEngine.IO.file_open import FileOpenOptions
from VeraGridEngine.IO.file_save import FileSave, FileSavingOptions, FileType


def run_case(import_path: Path, export_path: Path, version: int = 33) -> None:
    circuit_1 = vg.FileOpen(file_name=str(import_path), options=FileOpenOptions()).open()
    numerical_circuit_1 = vg.compile_numerical_circuit_at(circuit_1)
    power_flow_results = vg.power_flow(circuit_1)

    options = FileSavingOptions(file_type=FileType.PSSE_raw if export_path.suffix.lower() == ".raw" else FileType.PSSE_rawx)
    options.raw_version = version
    vg.FileSave(circuit=circuit_1, file_name=str(export_path), options=options).save()

    circuit_2 = vg.FileOpen(file_name=str(export_path), options=FileOpenOptions()).open()
    numerical_circuit_2 = vg.compile_numerical_circuit_at(circuit_2)

    ok, logger = circuit_1.compare_circuits(circuit_2)
    if not ok:
        logger.print()
    ok, logger = numerical_circuit_1.compare(nc_2=numerical_circuit_2, tol=1e-6)
    assert ok, logger

    print("ok")
    print(f"fixture={import_path}")
    print(f"export={export_path}")
    print(f"buses={len(circuit_1.buses)}")
    print(f"converged={power_flow_results.converged}")


def main() -> None:
    root = Path(__file__).resolve().parent
    run_case(root / "IEEE 14 bus.raw", root / "IEEE 14 bus_roundtrip.raw", version=33)
    run_case(root / "IEEE 30 bus.raw", root / "IEEE 30 bus_roundtrip.raw", version=33)
    run_case(root / "IEEE 14 bus.rawx", root / "IEEE 14 bus_roundtrip.rawx", version=33)
    run_case(
        root / "IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss.raw",
        root / "IEEE_14_v35_3_nudox_1_hvdc_desf_rates_fs_ss_roundtrip.raw",
        version=35,
    )


if __name__ == "__main__":
    main()
