from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.roundtrips.power_flow_roundtrip import run_export_roundtrip_power_flow

SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.ucte.veragrid_to_ucte import write_ucte


def export_ucte_roundtrip_file(circuit: MultiCircuit, file_name: str) -> None:
    write_ucte(file_name=file_name, circuit=circuit, t_idx=None)


def main() -> None:
    root = Path(__file__).resolve().parent
    import_path = root / "IEEE 14 bus.uct"
    export_path = root / "ieee14_roundtrip.uct"
    buses, branches = run_export_roundtrip_power_flow(
        import_file_name=str(import_path),
        export_file_name=str(export_path),
        export_func=export_ucte_roundtrip_file,
    )
    print("ok")
    print(f"fixture={import_path}")
    print(f"export={export_path}")
    print(f"buses={buses}")
    print(f"branches={branches}")


if __name__ == "__main__":
    main()
