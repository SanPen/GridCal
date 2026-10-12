# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Adversarial corpus for the FMI 2 model-description consumption boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from VeraGridEngine.IO.fmu.Elements.bindings import FmuImportConfig
from VeraGridEngine.IO.fmu.model_description import (
    FmuInterfaceMode,
    FmuModelDescription,
    read_fmu_model_description,
)
from VeraGridEngine.IO.fmu.Elements.description import (
    FmiOneCoSimulationCapabilities,
)


def _write_fmi_two_document(
    directory: Path,
    root_attributes: str,
    interface_xml: str,
    variables_xml: str = "",
) -> Path:
    """Write one extracted FMI 2 semantic-validation fixture.

    :param directory: Directory that represents the extracted FMU.
    :param root_attributes: Root attributes other than ``fmiVersion``.
    :param interface_xml: Interface declarations placed before variables.
    :param variables_xml: Scalar-variable declarations placed in order.
    :return: Extracted FMU directory containing the model description.
    """

    directory.mkdir()
    xml_text: str = (
        f'<fmiModelDescription fmiVersion="2.0" {root_attributes}>'
        f"{interface_xml}"
        f"<ModelVariables>{variables_xml}</ModelVariables>"
        "</fmiModelDescription>"
    )
    model_description_path: Path = directory / "modelDescription.xml"
    model_description_path.write_text(xml_text, encoding="utf-8")
    return directory


@pytest.mark.parametrize(
    ("root_attributes", "attribute_name"),
    (
        ('guid="semantic-guid"', "modelName"),
        ('modelName="SemanticModel"', "guid"),
        ('modelName="" guid="semantic-guid"', "modelName"),
        ('modelName="SemanticModel" guid="   "', "guid"),
    ),
)
def test_required_root_identity_attributes_fail_closed(
    tmp_path: Path,
    root_attributes: str,
    attribute_name: str,
) -> None:
    """Verify FMI 2 root identity never falls back to archive-derived values.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param root_attributes: Root attributes for the adversarial document.
    :param attribute_name: Required attribute expected in the diagnostic.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / attribute_name,
        root_attributes,
        '<CoSimulation modelIdentifier="semantic_model"/>',
    )

    with pytest.raises(ValueError, match=attribute_name):
        read_fmu_model_description(source)


@pytest.mark.parametrize(
    "interface_xml",
    (
        "",
        (
            '<CoSimulation modelIdentifier="semantic_model"/>'
            '<CoSimulation modelIdentifier="duplicate_model"/>'
        ),
        (
            '<ModelExchange modelIdentifier="semantic_model"/>'
            '<ModelExchange modelIdentifier="duplicate_model"/>'
        ),
    ),
)
def test_interface_cardinality_fails_closed(
    tmp_path: Path,
    interface_xml: str,
) -> None:
    """Verify at least one interface exists and each kind is unique.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param interface_xml: Missing or duplicated interface declarations.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "interfaces",
        'modelName="SemanticModel" guid="semantic-guid"',
        interface_xml,
    )

    with pytest.raises(ValueError, match="interface|duplicated"):
        read_fmu_model_description(source)


@pytest.mark.parametrize(
    "interface_xml",
    (
        "<CoSimulation/>",
        '<CoSimulation modelIdentifier=""/>',
        "<ModelExchange/>",
        '<ModelExchange modelIdentifier="   "/>',
    ),
)
def test_required_interface_identifier_fails_closed(
    tmp_path: Path,
    interface_xml: str,
) -> None:
    """Verify every declared interface has a non-empty model identifier.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param interface_xml: Interface declaration with invalid identity.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "identifier",
        'modelName="SemanticModel" guid="semantic-guid"',
        interface_xml,
    )

    with pytest.raises(ValueError, match="modelIdentifier"):
        read_fmu_model_description(source)


def test_dual_interface_document_remains_unambiguous(tmp_path: Path) -> None:
    """Verify one declaration of each FMI 2 interface remains supported.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "dual-interface",
        'modelName="SemanticModel" guid="semantic-guid"',
        (
            '<CoSimulation modelIdentifier="semantic_cs"/>'
            '<ModelExchange modelIdentifier="semantic_me"/>'
        ),
    )
    metadata: FmuModelDescription = read_fmu_model_description(source)

    assert metadata.interface_modes == (
        FmuInterfaceMode.CO_SIMULATION,
        FmuInterfaceMode.MODEL_EXCHANGE,
    )
    assert metadata.select_declared_interface() == FmuInterfaceMode.CO_SIMULATION


@pytest.mark.parametrize("boolean_text", ("false", "0"))
def test_co_simulation_without_execution_tool_is_consumable(
    tmp_path: Path,
    boolean_text: str,
) -> None:
    """Verify both false lexical forms preserve native Co-Simulation.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param boolean_text: Valid false ``xs:boolean`` lexical form.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / f"false-{boolean_text}",
        'modelName="SemanticModel" guid="semantic-guid"',
        (
            '<CoSimulation modelIdentifier="semantic_model" '
            f'needsExecutionTool="{boolean_text}"/>'
        ),
    )

    metadata: FmuModelDescription = read_fmu_model_description(source)
    assert metadata.select_declared_interface() == FmuInterfaceMode.CO_SIMULATION


@pytest.mark.parametrize("boolean_text", ("true", "1"))
def test_co_simulation_execution_tool_requirement_fails_closed(
    tmp_path: Path,
    boolean_text: str,
) -> None:
    """Verify external-tool Co-Simulation waits for an explicit integration.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param boolean_text: Valid true ``xs:boolean`` lexical form.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / f"true-{boolean_text}",
        'modelName="SemanticModel" guid="semantic-guid"',
        (
            '<CoSimulation modelIdentifier="semantic_model" '
            f'needsExecutionTool="{boolean_text}"/>'
        ),
    )

    with pytest.raises(RuntimeError, match="external execution tool"):
        read_fmu_model_description(source)


@pytest.mark.parametrize("interface_name", ("CoSimulation", "ModelExchange"))
@pytest.mark.parametrize(
    "interface_attributes",
    ('needsExecutionTool="TRUE"', 'needsExecutionTool="yes"'),
)
def test_invalid_fmi_boolean_lexical_forms_fail_closed(
    tmp_path: Path,
    interface_name: str,
    interface_attributes: str,
) -> None:
    """Verify the consumed execution-tool flag uses XSD lexical forms.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param interface_name: FMI 2 interface carrying the invalid flag.
    :param interface_attributes: Invalid execution-tool capability text.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "boolean",
        'modelName="SemanticModel" guid="semantic-guid"',
        (
            f'<{interface_name} modelIdentifier="semantic_model" '
            f"{interface_attributes}/>"
        ),
    )

    with pytest.raises(ValueError, match="valid FMI boolean"):
        read_fmu_model_description(source)


@pytest.mark.parametrize(
    "scalar_variable_xml",
    (
        '<ScalarVariable valueReference="1"><Real/></ScalarVariable>',
        '<ScalarVariable name="" valueReference="1"><Real/></ScalarVariable>',
        '<ScalarVariable name="value"><Real/></ScalarVariable>',
        '<ScalarVariable name="value" valueReference=""><Real/></ScalarVariable>',
    ),
)
def test_required_variable_identity_fails_closed(
    tmp_path: Path,
    scalar_variable_xml: str,
) -> None:
    """Verify scalar-variable identity never receives implicit defaults.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param scalar_variable_xml: Variable declaration missing required identity.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "variable-identity",
        'modelName="SemanticModel" guid="semantic-guid"',
        '<CoSimulation modelIdentifier="semantic_model"/>',
        scalar_variable_xml,
    )

    with pytest.raises(ValueError, match="name|valueReference"):
        read_fmu_model_description(source)


@pytest.mark.parametrize(
    "value_reference",
    ("-1", "4294967296", "1.0", "1_0", "9" * 5000),
)
def test_value_reference_requires_unsigned_32_bit_integer(
    tmp_path: Path,
    value_reference: str,
) -> None:
    """Verify Python-specific or out-of-range value references are rejected.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param value_reference: Invalid ``xs:unsignedInt`` lexical or numeric value.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "value-reference",
        'modelName="SemanticModel" guid="semantic-guid"',
        '<CoSimulation modelIdentifier="semantic_model"/>',
        (
            '<ScalarVariable name="value" '
            f'valueReference="{value_reference}"><Real/></ScalarVariable>'
        ),
    )

    with pytest.raises(ValueError, match="unsigned 32-bit"):
        read_fmu_model_description(source)


def test_uint32_parser_preserves_valid_leading_zero_form(tmp_path: Path) -> None:
    """Verify long leading-zero forms remain valid without large conversion.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "leading-zero-value-reference",
        'modelName="SemanticModel" guid="semantic-guid"',
        '<CoSimulation modelIdentifier="semantic_model"/>',
        (
            '<ScalarVariable name="value" valueReference="'
            f'{"0" * 5000}1"><Real/></ScalarVariable>'
        ),
    )
    metadata: FmuModelDescription = read_fmu_model_description(source)

    assert metadata.variables[0].value_reference == 1


@pytest.mark.parametrize("event_indicator_count", ("-1", "4294967296", "1.0"))
def test_event_indicator_count_requires_unsigned_32_bit_integer(
    tmp_path: Path,
    event_indicator_count: str,
) -> None:
    """Verify the consumed root count follows its XSD integer domain.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param event_indicator_count: Invalid event-indicator count under test.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "event-indicator-count",
        (
            'modelName="SemanticModel" guid="semantic-guid" '
            f'numberOfEventIndicators="{event_indicator_count}"'
        ),
        '<CoSimulation modelIdentifier="semantic_model"/>',
    )

    with pytest.raises(ValueError, match="unsigned 32-bit"):
        read_fmu_model_description(source)


@pytest.mark.parametrize(
    "type_xml",
    (
        "",
        "<Float32/>",
        "<Float64/>",
        "<Int8/>",
        "<UInt8/>",
        "<Int16/>",
        "<UInt16/>",
        "<Int32/>",
        "<UInt32/>",
        "<Int64/>",
        "<UInt64/>",
        "<Binary/>",
        "<Real/><Integer/>",
    ),
)
def test_variable_requires_one_known_primitive_type(
    tmp_path: Path,
    type_xml: str,
) -> None:
    """Verify scalar variables declare exactly one known FMI 2 primitive.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param type_xml: Missing, unknown or duplicated primitive declaration.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "variable-type",
        'modelName="SemanticModel" guid="semantic-guid"',
        '<CoSimulation modelIdentifier="semantic_model"/>',
        f'<ScalarVariable name="value" valueReference="1">{type_xml}</ScalarVariable>',
    )

    with pytest.raises(ValueError, match="primitive type|unknown type"):
        read_fmu_model_description(source)


def test_variable_names_are_unique_and_annotations_remain_supported(tmp_path: Path) -> None:
    """Verify names are unique while optional annotations do not count as types.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    valid_source: Path = _write_fmi_two_document(
        tmp_path / "annotation",
        'modelName="SemanticModel" guid="semantic-guid"',
        '<CoSimulation modelIdentifier="semantic_model"/>',
        (
            '<ScalarVariable name="value" valueReference="1">'
            '<Real/><Annotations/></ScalarVariable>'
        ),
    )
    valid_metadata: FmuModelDescription = read_fmu_model_description(valid_source)

    duplicate_source: Path = _write_fmi_two_document(
        tmp_path / "duplicate-name",
        'modelName="SemanticModel" guid="semantic-guid"',
        '<CoSimulation modelIdentifier="semantic_model"/>',
        (
            '<ScalarVariable name="value" valueReference="1"><Real/></ScalarVariable>'
            '<ScalarVariable name="value" valueReference="2"><Real/></ScalarVariable>'
        ),
    )

    assert valid_metadata.get_variable_names() == ("value",)
    with pytest.raises(ValueError, match="duplicated"):
        read_fmu_model_description(duplicate_source)


@pytest.mark.parametrize("derivative_index", ("0", "3", "1_0"))
def test_derivative_index_requires_valid_one_based_variable_reference(
    tmp_path: Path,
    derivative_index: str,
) -> None:
    """Verify derivative indices use FMI's bounded one-based variable order.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param derivative_index: Invalid derivative index under test.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "derivative",
        'modelName="SemanticModel" guid="semantic-guid"',
        '<ModelExchange modelIdentifier="semantic_model"/>',
        (
            '<ScalarVariable name="state" valueReference="1"><Real/></ScalarVariable>'
            '<ScalarVariable name="derivative" valueReference="2">'
            f'<Real derivative="{derivative_index}"/></ScalarVariable>'
        ),
    )

    with pytest.raises(ValueError, match="derivative|unsigned 32-bit"):
        read_fmu_model_description(source)


def test_valid_derivative_index_preserves_model_exchange_pair(tmp_path: Path) -> None:
    """Verify a valid derivative retains its declared one-based state index.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "valid-derivative",
        'modelName="SemanticModel" guid="semantic-guid"',
        '<ModelExchange modelIdentifier="semantic_model"/>',
        (
            '<ScalarVariable name="state" valueReference="1"><Real/></ScalarVariable>'
            '<ScalarVariable name="derivative" valueReference="2">'
            '<Real derivative="1"/></ScalarVariable>'
        ),
    )
    metadata: FmuModelDescription = read_fmu_model_description(source)

    assert metadata.variables[1].derivative_index == 1


def test_derivative_index_requires_real_state_variable(tmp_path: Path) -> None:
    """Verify a derivative cannot reference a non-Real variable by position.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "non-real-state",
        'modelName="SemanticModel" guid="semantic-guid"',
        '<ModelExchange modelIdentifier="semantic_model"/>',
        (
            '<ScalarVariable name="integer" valueReference="1"><Integer/></ScalarVariable>'
            '<ScalarVariable name="derivative" valueReference="2">'
            '<Real derivative="1"/></ScalarVariable>'
        ),
    )

    with pytest.raises(ValueError, match="Real variable"):
        read_fmu_model_description(source)


@pytest.mark.parametrize(
    "root_opening",
    (
        '<fmiModelDescription xmlns="urn:fmi"',
        '<fmi:fmiModelDescription xmlns:fmi="urn:fmi"',
    ),
)
def test_namespace_qualified_fmi_vocabulary_fails_closed(
    tmp_path: Path,
    root_opening: str,
) -> None:
    """Verify FMI 2 elements cannot be moved into an XML namespace.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param root_opening: Namespace-qualified root opening tag.
    :return: None.
    """

    source: Path = tmp_path / "namespace"
    source.mkdir()
    xml_text: str = (
        f'{root_opening} fmiVersion="2.0" modelName="SemanticModel" guid="semantic-guid">'
        '<CoSimulation modelIdentifier="semantic_model"/>'
        "</fmiModelDescription>"
    )
    if root_opening.startswith("<fmi:"):
        xml_text = xml_text.replace("</fmiModelDescription>", "</fmi:fmiModelDescription>")
    else:
        pass
    (source / "modelDescription.xml").write_text(xml_text, encoding="utf-8")

    with pytest.raises(ValueError, match="namespaces"):
        read_fmu_model_description(source)


@pytest.mark.parametrize(
    ("interface_xml", "variables_xml"),
    (
        (
            '<CoSimulation modelIdentifier="semantic_model"/>'
            '<fmi:ModelExchange xmlns:fmi="urn:fmi" modelIdentifier="hidden_model"/>',
            "",
        ),
        (
            '<CoSimulation modelIdentifier="semantic_model"/>',
            (
                '<fmi:ScalarVariable xmlns:fmi="urn:fmi" name="hidden" valueReference="1">'
                "<fmi:Real/></fmi:ScalarVariable>"
            ),
        ),
    ),
)
def test_nested_namespace_qualified_fmi_elements_fail_closed(
    tmp_path: Path,
    interface_xml: str,
    variables_xml: str,
) -> None:
    """Verify qualified FMI children cannot disappear from exact lookups.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param interface_xml: Interface declarations under the unqualified root.
    :param variables_xml: Variable declarations under ModelVariables.
    :return: None.
    """

    source: Path = _write_fmi_two_document(
        tmp_path / "nested-namespace",
        'modelName="SemanticModel" guid="semantic-guid"',
        interface_xml,
        variables_xml,
    )

    with pytest.raises(ValueError, match="namespaces"):
        read_fmu_model_description(source)


def test_fmi_three_namespace_rules_apply_after_version_dispatch(tmp_path: Path) -> None:
    """Verify FMI 3 dispatch applies the FMI 3 namespace contract.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    source: Path = tmp_path / "version-before-namespace"
    source.mkdir()
    xml_text: str = (
        '<fmi:fmiModelDescription xmlns:fmi="urn:fmi" fmiVersion="3.0" '
        'modelName="FutureModel" instantiationToken="future-token"/>'
    )
    (source / "modelDescription.xml").write_text(xml_text, encoding="utf-8")

    with pytest.raises(ValueError, match="namespaces are not accepted for FMI 3.0"):
        read_fmu_model_description(source)


def test_import_config_gate_accepts_connected_fmi_one_family() -> None:
    """Verify the central mode gate accepts the supported FMI 1 CS profile.

    :return: None.
    """

    # Supply the complete FMI 1 capability record so the gate is exercised on
    # the supported synchronous, variable-step Stand-Alone profile.
    model_identifiers: dict[FmuInterfaceMode, str] = dict()
    model_identifiers[FmuInterfaceMode.CO_SIMULATION] = "connected_fmi_one_model"
    capabilities: FmiOneCoSimulationCapabilities = FmiOneCoSimulationCapabilities(
        needs_execution_tool=False,
        can_handle_variable_communication_step_size=True,
        can_handle_events=False,
        can_reject_steps=False,
        can_interpolate_inputs=False,
        max_output_derivative_order=0,
        can_run_asynchronuously=False,
        can_signal_events=False,
        can_be_instantiated_only_once_per_process=False,
        can_not_use_memory_management_functions=False,
    )
    metadata: FmuModelDescription = FmuModelDescription(
        path=Path("connected-fmi-one.fmu"),
        fmi_version="1.0",
        model_name="ConnectedFmiOneModel",
        guid="connected-fmi-one-guid",
        variable_naming_convention=None,
        number_of_event_indicators=0,
        interface_modes=(FmuInterfaceMode.CO_SIMULATION,),
        model_identifiers=model_identifiers,
        platforms=tuple(),
        variables=tuple(),
        fmi_one_co_simulation_capabilities=capabilities,
    )
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=metadata.path,
        preferred_mode=FmuInterfaceMode.CO_SIMULATION,
    )

    # A connected family resolves through the existing public configuration
    # owner; no importer-specific bypass or special test path is permitted.
    resolved_mode: FmuInterfaceMode = config.resolve_execution_mode(metadata)
    assert resolved_mode == FmuInterfaceMode.CO_SIMULATION
