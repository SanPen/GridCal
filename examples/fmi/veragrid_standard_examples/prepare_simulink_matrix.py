"""Package the published standard FMUs for licensed Simulink replay."""

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


def prepare_execution_bundle(catalog_root: Path, output_root: Path) -> None:
    """Create one immutable-by-convention replay bundle outside the repository.

    :param catalog_root: Directory containing the published ``win64`` catalog.
    :param output_root: New, nonexistent directory for the execution bundle.
    :return: Nothing; a manifest binds all copied files to their source hashes.
    """
    source_root: Path = Path(__file__).resolve().parent
    repository_root: Path = source_root.parents[3]
    catalog_path: Path = catalog_root.resolve()
    destination: Path = output_root.resolve()
    expected_catalog: Path = source_root / "published" / "win64"
    if catalog_path != expected_catalog.resolve():
        raise ValueError("Catalog must be the adjacent published/win64 directory")
    else:
        pass
    if destination == repository_root or repository_root in destination.parents:
        raise ValueError("Execution evidence must remain outside the repository")
    else:
        pass
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite {destination}")
    else:
        pass

    manifest_path: Path = catalog_path / "manifest.json"
    sums_path: Path = catalog_path / "SHA256SUMS"
    with manifest_path.open("rb") as manifest_stream:
        manifest_hash: str = hashlib.file_digest(manifest_stream, "sha256").hexdigest()
    with sums_path.open("rb") as sums_stream:
        sums_hash: str = hashlib.file_digest(sums_stream, "sha256").hexdigest()
    if manifest_hash != "7099296e4360555daa1ca14f854f3c6b7f11b1c6b0ba38e5e603b9896e726113":
        raise ValueError("Published manifest identity differs from sealed contract")
    else:
        pass
    if sums_hash != "2c86682dbf6f9fc5374b32261907eae87e1cbe8647f80d1ea5c2c53ccce90e4e":
        raise ValueError("Published SHA256SUMS identity differs from sealed contract")
    else:
        pass
    declared_files: dict[str, str] = dict()
    for checksum_line in sums_path.read_text(encoding="utf-8").splitlines():
        checksum_parts: list[str] = checksum_line.split("  ", maxsplit=1)
        if len(checksum_parts) != 2 or len(checksum_parts[0]) != 64 or checksum_parts[1] in declared_files:
            raise ValueError("Malformed or duplicate SHA256SUMS entry")
        else:
            declared_files[checksum_parts[1]] = checksum_parts[0]
    actual_files: set[str] = {
        catalog_file.relative_to(catalog_path).as_posix()
        for catalog_file in catalog_path.rglob("*") if catalog_file.is_file() and catalog_file != sums_path
    }
    if len(declared_files) != 94 or set(declared_files) != actual_files:
        raise ValueError("Catalog has missing or extra paths against SHA256SUMS")
    else:
        pass
    for relative_name, declared_checksum in declared_files.items():
        with (catalog_path / relative_name).open("rb") as declared_stream:
            actual_checksum: str = hashlib.file_digest(declared_stream, "sha256").hexdigest()
        if actual_checksum != declared_checksum:
            raise ValueError(f"Published file checksum mismatch: {relative_name}")
        else:
            pass
    with manifest_path.open("r", encoding="utf-8") as manifest_stream:
        manifest: dict[str, object] = json.load(manifest_stream)
    cells: object = manifest.get("cells")
    if not isinstance(cells, list) or len(cells) != 18:
        raise ValueError("Exactly 18 published cells are required")
    else:
        pass
    cell_ids: set[str] = set()
    execution_cells: list[dict[str, object]] = list()
    for cell in cells:
        if not isinstance(cell, dict):
            raise ValueError("Malformed manifest cell")
        else:
            pass
        cell_name: object = cell.get("model_name")
        relative_fmu: object = cell.get("fmu_path")
        declared_hash: object = cell.get("fmu_sha256")
        if not isinstance(cell_name, str) or not isinstance(relative_fmu, str) or not isinstance(declared_hash, str):
            raise ValueError("Malformed manifest identity")
        else:
            pass
        if cell_name in cell_ids:
            raise ValueError(f"Duplicate cell {cell_name}")
        else:
            cell_ids.add(cell_name)
        fmu_path: Path = (catalog_path / relative_fmu).resolve()
        if catalog_path not in fmu_path.parents or not fmu_path.is_file():
            raise ValueError(f"Unsafe or missing FMU path {relative_fmu}")
        else:
            pass
        with fmu_path.open("rb") as fmu_stream:
            actual_hash: str = hashlib.file_digest(fmu_stream, "sha256").hexdigest()
        if actual_hash != declared_hash:
            raise ValueError(f"FMU hash mismatch {relative_fmu}")
        else:
            pass
        with ZipFile(fmu_path) as fmu_archive:
            description: ElementTree.Element = ElementTree.fromstring(fmu_archive.read("modelDescription.xml"))
        fmi_version: object = cell.get("fmi_version")
        interface: object = cell.get("interface")
        family: object = cell.get("family")
        if not isinstance(fmi_version, str) or not isinstance(interface, str) or not isinstance(family, str):
            raise ValueError("Malformed cell classification")
        else:
            pass
        interface_element: ElementTree.Element | None = description.find("CoSimulation" if interface == "cs" else "ModelExchange")
        if fmi_version == "1.0":
            xml_identifier: str | None = description.get("modelIdentifier")
        elif interface_element is not None:
            xml_identifier = interface_element.get("modelIdentifier")
        else:
            xml_identifier = None
        if xml_identifier != cell_name or description.get("fmiVersion") != fmi_version:
            raise ValueError(f"XML identity mismatch {relative_fmu}")
        else:
            pass
        model_variables: ElementTree.Element | None = description.find("ModelVariables")
        if model_variables is None:
            raise ValueError(f"No ModelVariables in {relative_fmu}")
        else:
            pass
        xml_inputs: set[str] = set()
        xml_outputs: set[str] = set()
        for variable in model_variables:
            variable_name: str | None = variable.get("name")
            causality: str | None = variable.get("causality")
            if causality == "input" and variable_name is not None:
                xml_inputs.add(variable_name)
            elif causality == "output" and variable_name is not None:
                xml_outputs.add(variable_name)
            else:
                pass
        stem: str = fmu_path.stem
        input_path: Path = fmu_path.parent / f"{stem}_in.csv"
        reference_path: Path = fmu_path.parent / f"{stem}_ref.csv"
        with input_path.open("r", encoding="utf-8", newline="") as input_stream:
            input_header: list[str] = next(csv.reader(input_stream))
        with reference_path.open("r", encoding="utf-8", newline="") as reference_stream:
            reference_header: list[str] = next(csv.reader(reference_stream))
        input_names: list[str] = input_header[1:]
        output_names: list[str] = reference_header[1:]
        if input_header[0] != "time" or reference_header[0] != "time" or set(input_names) != xml_inputs or set(output_names) != xml_outputs:
            raise ValueError(f"XML/CSV port-set mismatch {relative_fmu}")
        else:
            pass
        execution_cell: dict[str, object] = dict()
        execution_cell["family"] = family
        execution_cell["fmi_version"] = fmi_version
        execution_cell["interface"] = interface
        execution_cell["model_name"] = cell_name
        execution_cell["model_identifier"] = xml_identifier
        execution_cell["fmu_path"] = relative_fmu
        execution_cell["fmu_sha256"] = declared_hash
        execution_cell["input_names"] = input_names
        execution_cell["output_names"] = output_names
        execution_cell["input_csv"] = (Path(relative_fmu).parent / input_path.name).as_posix()
        execution_cell["reference_csv"] = (Path(relative_fmu).parent / reference_path.name).as_posix()
        execution_cells.append(execution_cell)

    git_head_result: subprocess.CompletedProcess[str] = subprocess.run(
        ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, encoding="utf-8"
    )
    git_status_result: subprocess.CompletedProcess[str] = subprocess.run(
        ["git", "-C", str(repository_root), "status", "--porcelain", "--untracked-files=all", "--", "examples/fmi"],
        check=True, capture_output=True, text=True, encoding="utf-8"
    )
    source_commit: object = manifest.get("source_commit")
    if git_head_result.stdout.strip() != source_commit:
        raise ValueError("Current Git HEAD differs from published source commit")
    else:
        pass

    destination.mkdir(parents=True)
    bundle_catalog: Path = destination / "catalog"
    shutil.copytree(catalog_path, bundle_catalog)
    script_names: tuple[str, ...] = (
        "build_simulink_matrix.m", "run_simulink_matrix.m",
        "validate_simulink_matrix.py", "plot_simulink_matrix.py",
        "sober-scientific.mplstyle", "SIMULINK_VALIDATION.md",
    )
    for script_name in script_names:
        shutil.copy2(source_root / script_name, destination / script_name)
    execution_cells_path: Path = destination / "execution-cells.json"
    with execution_cells_path.open("x", encoding="utf-8", newline="\n") as cells_stream:
        json.dump(execution_cells, cells_stream, indent=2)
        cells_stream.write("\n")

    file_hashes: dict[str, str] = dict()
    for bundle_path in sorted(destination.rglob("*")):
        if bundle_path.is_file():
            with bundle_path.open("rb") as bundle_stream:
                file_hashes[bundle_path.relative_to(destination).as_posix()] = hashlib.file_digest(bundle_stream, "sha256").hexdigest()
        else:
            pass
    receipt: dict[str, object] = dict()
    receipt["schema"] = "veragrid.standard-simulink-execution-bundle/1"
    receipt["status"] = "PREPARED_NOT_EXECUTED"
    receipt["source_commit"] = source_commit
    receipt["git_status_at_preparation"] = git_status_result.stdout.splitlines()
    receipt["manifest_sha256"] = manifest_hash
    receipt["sha256sums_sha256"] = sums_hash
    receipt["cell_count"] = len(cells)
    receipt["files"] = file_hashes
    receipt_path: Path = destination / "execution-bundle-receipt.json"
    with receipt_path.open("x", encoding="utf-8", newline="\n") as receipt_stream:
        json.dump(receipt, receipt_stream, indent=2, sort_keys=True)
        receipt_stream.write("\n")


def main() -> None:
    """Parse an external output directory and package the adjacent catalog.

    :return: Nothing; exits nonzero if any identity or file check fails.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_root", type=Path, help="Nonexistent directory outside the Git repository")
    arguments: argparse.Namespace = parser.parse_args()
    catalog_root: Path = Path(__file__).resolve().parent / "published" / "win64"
    prepare_execution_bundle(catalog_root, arguments.output_root)
    print(arguments.output_root.resolve())


if __name__ == "__main__":
    main()
else:
    pass
