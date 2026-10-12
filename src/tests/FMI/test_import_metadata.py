from __future__ import annotations

from pathlib import Path

import pytest

from VeraGridEngine.IO.fmu.Elements.bindings import FmuBindingDirection, FmuVariableBinding, validate_bindings
from VeraGridEngine.IO.fmu.Elements.inspection import FmuArchiveInspectionPolicy
from VeraGridEngine.IO.fmu.model_description import (
    FmuInterfaceMode,
    FmuModelDescription,
    FmuVariableDescription,
    read_fmu_model_description,
)
from VeraGridEngine.enumerations import FmiVersion


def _artifacts_root() -> Path:
    """Return the repository directory containing certified FMI artifacts.

    :return: Absolute artifact directory used by FMI integration tests.
    """

    return Path(__file__).resolve().parents[1] / "data" / "fmi" / "artifacts"


def _known_fmi_platforms() -> set[str]:
    """Return platform directory names currently understood by the importer.

    :return: Known FMI 2 binary platform identifiers.
    """

    known_platforms: set[str] = set()
    known_platforms.add("win64")
    known_platforms.add("linux64")
    known_platforms.add("darwin64")
    return known_platforms


def _write_minimal_model_description(
    directory: Path,
    fmi_version: str | None,
) -> Path:
    """Write one extracted FMU fixture with an optional version declaration.

    :param directory: Directory that will represent the extracted FMU.
    :param fmi_version: Exact version value, or ``None`` to omit the attribute.
    :return: Extracted FMU directory accepted by the metadata reader.
    """

    directory.mkdir()
    if fmi_version is None:
        version_attribute: str = ""
    else:
        version_attribute = f' fmiVersion="{fmi_version}"'
    xml_text: str = (
        f'<fmiModelDescription{version_attribute} modelName="VersionFixture" guid="fixture-guid">'
        '<CoSimulation modelIdentifier="version_fixture"/>'
        '<ModelVariables/>'
        '</fmiModelDescription>'
    )
    (directory / "modelDescription.xml").write_text(xml_text, encoding="utf-8")
    return directory


def test_read_existing_co_simulation_fmu_metadata() -> None:
    """Verify the existing FMI 2 artifact retains its parsed contract.

    :return: None.
    """

    fmu_path: Path = _artifacts_root() / "FrequencyLoadPilot.fmu"
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    assert metadata.fmi_version == "2.0"
    assert metadata.fmi_version_family is FmiVersion.FMI_2_0
    assert metadata.inspection_receipt is not None
    assert metadata.inspection_receipt.path == fmu_path.resolve()
    assert metadata.inspection_receipt.model_description_sha256 != ""
    assert metadata.get_supports_co_simulation() is True
    assert metadata.get_supports_model_exchange() is False
    assert metadata.select_declared_interface() == FmuInterfaceMode.CO_SIMULATION
    assert metadata.get_model_identifier(FmuInterfaceMode.CO_SIMULATION) != ""
    assert len(metadata.platforms) > 0
    assert set(metadata.platforms).issubset(_known_fmi_platforms())
    assert any(variable.causality == "input" for variable in metadata.variables)
    assert any(variable.causality == "output" for variable in metadata.variables)


def test_model_description_resolve_mode_compatibility_wrapper() -> None:
    """Verify the historical method delegates to metadata interface selection.

    :return: None.
    """

    fmu_path: Path = _artifacts_root() / "FrequencyLoadPilot.fmu"
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    with pytest.warns(DeprecationWarning, match="select_declared_interface"):
        selected_interface: FmuInterfaceMode = metadata.resolve_mode()

    assert selected_interface == FmuInterfaceMode.CO_SIMULATION


def test_model_description_constructor_preserves_legacy_positional_order() -> None:
    """Verify the new metadata fields do not break existing positional callers.

    :return: None.
    """

    model_identifiers: dict[FmuInterfaceMode, str] = dict()
    model_identifiers[FmuInterfaceMode.CO_SIMULATION] = "legacy_model"
    metadata: FmuModelDescription = FmuModelDescription(
        Path("legacy.fmu"),
        "2.0",
        "Legacy",
        "legacy-guid",
        None,
        0,
        (FmuInterfaceMode.CO_SIMULATION,),
        model_identifiers,
        tuple(),
        tuple(),
    )

    assert metadata.fmi_version_family is FmiVersion.FMI_2_0
    assert metadata.inspection_receipt is None


def test_model_description_rejects_conflicting_version_family() -> None:
    """Verify raw and canonical FMI versions cannot become two truths.

    :return: None.
    """

    model_identifiers: dict[FmuInterfaceMode, str] = dict()
    model_identifiers[FmuInterfaceMode.CO_SIMULATION] = "conflict_model"

    with pytest.raises(ValueError, match="version family conflicts"):
        FmuModelDescription(
            Path("conflict.fmu"),
            "2.0",
            "Conflict",
            "conflict-guid",
            None,
            0,
            (FmuInterfaceMode.CO_SIMULATION,),
            model_identifiers,
            tuple(),
            tuple(),
            fmi_version_family=FmiVersion.FMI_3_0,
        )


def test_metadata_reader_propagates_custom_inspection_policy(tmp_path: Path) -> None:
    """Verify metadata parsing uses the caller's finite inspection limits.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_minimal_model_description(tmp_path / "policy", "2.0")
    policy: FmuArchiveInspectionPolicy = FmuArchiveInspectionPolicy(
        max_model_description_bytes=32
    )

    with pytest.raises(ValueError, match="inspection byte limit"):
        read_fmu_model_description(fmu_path, inspection_policy=policy)


def test_validate_bindings_uses_fmu_causality() -> None:
    """Verify binding validation still consumes the parsed causality.

    :return: None.
    """

    fmu_path: Path = _artifacts_root() / "FrequencyLoadPilot.fmu"
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    input_var: FmuVariableDescription = next(
        variable for variable in metadata.variables if variable.causality == "input"
    )
    output_var: FmuVariableDescription = next(
        variable for variable in metadata.variables if variable.causality == "output"
    )

    validate_bindings(
        metadata,
        (
            FmuVariableBinding(
                signal_name="bus_voltage",
                variable_name=input_var.name,
                direction=FmuBindingDirection.INPUT,
            ),
            FmuVariableBinding(
                signal_name="active_power",
                variable_name=output_var.name,
                direction=FmuBindingDirection.OUTPUT,
            ),
        ),
    )

    with pytest.raises(ValueError, match="is not bindable as FMU output"):
        validate_bindings(
            metadata,
            (
                FmuVariableBinding(
                    signal_name="bad",
                    variable_name=input_var.name,
                    direction=FmuBindingDirection.OUTPUT,
                ),
            ),
        )


@pytest.mark.parametrize("fmi_version", ("3.0", "3.0.2"))
def test_fmi_three_cannot_inherit_the_fmi_two_root_contract(
    tmp_path: Path,
    fmi_version: str,
) -> None:
    """Verify FMI 3 XML cannot fall through the FMI 1 or FMI 2 parser.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param fmi_version: Valid FMI 3 declaration used with an invalid legacy root.
    :return: None.
    """

    fmu_path: Path = _write_minimal_model_description(tmp_path / "legacy-root", fmi_version)

    with pytest.raises(ValueError, match="attribute 'guid'.*outside"):
        read_fmu_model_description(fmu_path)


@pytest.mark.parametrize("fmi_version", ("", "2.0.5", "3.1", "3.0-alpha.2"))
def test_invalid_import_version_declarations_fail_closed(
    tmp_path: Path,
    fmi_version: str,
) -> None:
    """Verify malformed or unsupported declarations fail at the boundary.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param fmi_version: Invalid or unsupported declaration under test.
    :return: None.
    """

    fmu_path: Path = _write_minimal_model_description(tmp_path / "invalid", fmi_version)

    with pytest.raises(ValueError, match="Invalid FMI version declaration"):
        read_fmu_model_description(fmu_path)


def test_missing_import_version_declaration_fails_closed(tmp_path: Path) -> None:
    """Verify the required ``fmiVersion`` attribute cannot be omitted.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_minimal_model_description(tmp_path / "missing", None)

    with pytest.raises(ValueError, match="missing fmiVersion"):
        read_fmu_model_description(fmu_path)


@pytest.mark.parametrize(
    "xml_text",
    (
        '<!DOCTYPE fmiModelDescription><fmiModelDescription fmiVersion="2.0"/>',
        '<!ENTITY external_entity "unsafe"><fmiModelDescription fmiVersion="2.0"/>',
    ),
)
def test_dtd_and_entity_declarations_fail_before_xml_parsing(
    tmp_path: Path,
    xml_text: str,
) -> None:
    """Verify FMI metadata parsing does not accept entity declarations.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param xml_text: Untrusted XML declaration under test.
    :return: None.
    """

    fmu_path: Path = tmp_path / "declaration"
    fmu_path.mkdir()
    (fmu_path / "modelDescription.xml").write_text(xml_text, encoding="utf-8")

    with pytest.raises(ValueError, match="DTD and entity declarations"):
        read_fmu_model_description(fmu_path)


def test_invalid_model_description_root_fails_closed(tmp_path: Path) -> None:
    """Verify a different XML vocabulary cannot enter the FMI 2 parser.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = tmp_path / "wrong-root"
    fmu_path.mkdir()
    (fmu_path / "modelDescription.xml").write_text(
        '<notFmi fmiVersion="2.0"/>',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="root element"):
        read_fmu_model_description(fmu_path)
