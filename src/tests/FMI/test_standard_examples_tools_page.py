"""Focused integrity tests for the FMI tools-page submission package."""

import hashlib
import json
from pathlib import Path

from examples.fmi.importer_cross_check import _load_manifest


def test_importer_cross_check_manifest_is_closed() -> None:
    """Keep the external-import evidence fixed at three cases per exporter."""

    repository_root: Path = Path(__file__).resolve().parents[3]
    manifest_path: Path = (
        repository_root / "examples" / "fmi" / "importer_cross_check_cases.json"
    )
    cases = _load_manifest(manifest_path)
    assert len(cases) == 9
    exporter_counts: dict[str, int] = dict()
    case_identities: set[tuple[str, str, str]] = set()
    input_identities: set[tuple[str, str]] = set()
    for case in cases:
        exporter_counts[case.exporter] = exporter_counts.get(case.exporter, 0) + 1
        case_identity: tuple[str, str, str] = (
            case.exporter, case.exporter_version, case.model,
        )
        assert case_identity not in case_identities
        case_identities.add(case_identity)
        assert len(case.fmu_sha256) == 64
        if case.input_variable is None:
            assert case.input_name is None
            assert case.input_sha256 is None
        else:
            input_identities.add((case.model, case.input_variable))
    assert exporter_counts == {
        "Dymola": 3,
        "FMIToolbox_MATLAB": 3,
        "MWorks": 3,
    }
    assert input_identities == {("IntegrateSignal", "In1")}


def _catalog_root() -> Path:
    """Return the canonical downloadable catalog root.

    :return: Absolute path to ``published/win64``.
    """

    return (
        Path(__file__).resolve().parents[3]
        / "examples"
        / "fmi"
        / "veragrid_standard_examples"
        / "published"
        / "win64"
    )


def test_canonical_inventory_and_cells_are_closed() -> None:
    """Close every catalog file, upstream presentation rule, and provenance field."""

    catalog_root: Path = _catalog_root()
    manifest_value: object = json.loads(
        (catalog_root / "manifest.json").read_text(encoding="utf-8")
    )
    assert isinstance(manifest_value, dict)
    # Keep the immutable campaign manifest bound to the artifacts it originally
    # authenticated; current publication state belongs to the adjacent public
    # documentation and to manifests produced by the updated generator.
    assert manifest_value["local_status"] == "PASS"
    assert manifest_value["source_commit"] == (
        "1814ed5f77e0f162df6b9c0809ef2fb97ddda9fd"
    )
    assert manifest_value["source_tree_sha256"] == (
        "fca974f6600a8b93106c24d70dae05d248b36a39573181e4ff1f52eb40634c95"
    )
    assert manifest_value["recipe_sha256"] == (
        "419bba882def3c6a6514f0a17b41cee19dfd4a94aff72dc6ecbe230fcdfd6189"
    )
    source_text: str = (catalog_root / "SOURCE.md").read_text(encoding="utf-8")
    catalog_readme: str = (catalog_root / "README.md").read_text(encoding="utf-8")
    assert "PENDING_PUBLIC_URL_ACTIVATION_AFTER_INTEGRATION" in source_text
    assert "../../../INTEROPERABILITY_STATUS.md" in catalog_readme

    checksum_lines: list[str] = (
        catalog_root / "SHA256SUMS"
    ).read_text(encoding="utf-8").splitlines()
    inventory: dict[str, str] = dict()
    for checksum_line in checksum_lines:
        checksum_parts: list[str] = checksum_line.split("  ", maxsplit=1)
        assert len(checksum_parts) == 2
        expected_sha256: str = checksum_parts[0]
        relative_path: str = checksum_parts[1]
        assert relative_path not in inventory
        inventory[relative_path] = expected_sha256
    actual_paths: set[str] = {
        file_path.relative_to(catalog_root).as_posix()
        for file_path in catalog_root.rglob("*")
        if file_path.is_file() and file_path.name != "SHA256SUMS"
    }
    assert len(inventory) == 94
    assert set(inventory) == actual_paths
    for relative_path, expected_sha256 in inventory.items():
        file_path: Path = catalog_root / relative_path
        with file_path.open("rb") as file_stream:
            observed_sha256: str = hashlib.file_digest(
                file_stream, "sha256"
            ).hexdigest()
        assert observed_sha256 == expected_sha256

    fmu_paths: list[Path] = list(catalog_root.rglob("*.fmu"))
    csv_paths: list[Path] = list(catalog_root.rglob("*.csv"))
    option_paths: list[Path] = list(catalog_root.rglob("*.opt"))
    cell_readme_paths: list[Path] = list(catalog_root.rglob("Readme.txt"))
    nested_markdown_paths: list[Path] = [
        readme_path
        for readme_path in catalog_root.rglob("README.md")
        if readme_path.parent != catalog_root
    ]
    assert len(fmu_paths) == 18
    assert len(csv_paths) == 36
    assert len(option_paths) == 18
    assert len(cell_readme_paths) == 18
    assert nested_markdown_paths == []
    for csv_path in csv_paths:
        header_line: str = csv_path.read_text(encoding="utf-8").splitlines()[0]
        header_fields: list[str] = header_line.split(",")
        assert len(header_fields) >= 2
        for header_field in header_fields:
            assert header_field.startswith('"')
            assert header_field.endswith('"')

    standard_root: Path = catalog_root.parents[1]
    tools_root: Path = standard_root / "tools_page"
    tools_readme: str = (tools_root / "README.md").read_text(encoding="utf-8")
    assert not (tools_root / "win64").exists()
    assert not (standard_root / "prepare_tools_page_examples.py").exists()
    assert "../published/win64/README.md" in tools_readme
    assert "prepare_tools_page_examples.py" not in tools_readme


def test_tools_entry_candidate_is_ready_pending_stable_public_location() -> None:
    """Keep the public tools-page submission gates fail-closed."""
    tools_root: Path = _catalog_root().parents[1] / "tools_page"
    entry_value: object = json.loads(
        (tools_root / "tools-list-entry.candidate.json").read_text(encoding="utf-8")
    )
    gate_value: object = json.loads(
        (tools_root / "submission-gates.json").read_text(encoding="utf-8")
    )
    assert isinstance(entry_value, dict)
    expected_keys: set[str] = {
        "name", "license", "url", "logo", "vendor", "vendorURL",
        "description", "features", "platforms", "interfaces", "fmiVersions",
        "fmuExport", "fmuImport", "layeredStandards", "examplesURL",
    }
    assert set(entry_value) == expected_keys
    assert entry_value["vendor"] == "eRoots Analytics"
    assert entry_value["url"] == "https://github.com/SanPen/VeraGrid"
    assert entry_value["platforms"] == ["macOS", "Linux", "Windows"]
    assert entry_value["logo"] == "eroots-analytics.svg"
    assert entry_value["examplesURL"] == (
        "https://github.com/SanPen/VeraGrid/tree/master/examples/fmi"
    )
    logo_path: Path = tools_root / entry_value["logo"]
    with logo_path.open("rb") as logo_stream:
        logo_sha256: str = hashlib.file_digest(logo_stream, "sha256").hexdigest()
    assert logo_sha256 == (
        "28d5a48d00f6b523dd7199b3d0eb90b2e0455a5cc9d054b917addfc2a86a6d60"
    )
    assert isinstance(gate_value, dict)
    assert gate_value["status"] == "READY_FOR_CTO_INTEGRATION"
    assert gate_value["distribution_status"] == (
        "PENDING_PUBLIC_URL_ACTIVATION_AFTER_INTEGRATION"
    )
    assert gate_value["unresolved_gates"] == [
        "PUBLIC_URL_ACTIVATION_AFTER_INTEGRATION",
    ]
    assert gate_value["deferred_actions"] == [
        "UPSTREAM_PULL_REQUEST_AUTHORIZATION",
    ]
