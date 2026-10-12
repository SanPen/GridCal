from __future__ import annotations

from pathlib import Path

import pytest

from VeraGridEngine.IO.fmu.Elements.bindings import (
    FmiThreeFloat64BindingLayout,
    FmiThreeFloat64VariableCardinalityPlan,
    FmuImportConfig,
    resolve_fmi_three_configurable_float64_binding_layouts,
    resolve_fmi_three_configured_float64_binding_layout,
    resolve_fmi_three_configuration_float64_binding_layout,
    resolve_fmi_three_constant_float64_binding_layouts,
    resolve_fmi_three_scalar_binding_references,
    resolve_fmi_three_scalar_int32_binding_references,
    resolve_fmi_three_variable_serialized_value_count,
)
from VeraGridEngine.IO.fmu.model_description import (
    FmuInterfaceMode,
    FmuModelDescription,
    FmuVariableDescription,
    FmuVariableType,
    choose_fmu_mode,
    read_fmu_model_description,
)
from VeraGridEngine.IO.fmu.Elements.description import (
    FmiThreeCoSimulationCapabilities,
    FmiThreeModelExchangeCapabilities,
    FmiThreeVariableDimension,
)
from VeraGridEngine.IO.fmu.profile import (
    FmiThreeWorkerFloat64Profile,
    resolve_fmi_three_configuration_float64_writable_references,
    resolve_fmi_three_configuration_uint64_writable_references,
    resolve_fmi_three_initialization_writable_references,
    resolve_fmi_three_worker_float64_profile,
    validate_fmi_three_co_simulation_worker_profile,
    validate_fmi_three_model_exchange_worker_profile,
)
from VeraGridEngine.IO.fmu.workers import (
    _resolve_fmi_three_worker_access_controls,
)
from VeraGridEngine.enumerations import FmiVersion


def _write_extracted_fmi3_model_description(directory: Path, xml_text: str) -> Path:
    """Write an FMI 3 model-description fixture into an extracted FMU directory.

    :param directory: Directory that represents the extracted FMU.
    :param xml_text: Model-description XML fixture.
    :return: Extracted FMU directory accepted by the importer.
    """

    directory.mkdir()
    model_description_path: Path = directory / "modelDescription.xml"
    model_description_path.write_text(xml_text, encoding="utf-8")
    return directory


def _scalar_fmi3_worker_profile_fixture_xml() -> str:
    """Return the self-contained scalar FMI 3 worker-profile fixture.

    The XML is stored directly in this test module and requires no external
    FMU. Its v41-style identifiers exercise exact string handling but do not
    authenticate or claim availability of the original runtime artifact.

    :return: Repository-contained FMI 3 model-description XML fixture.
    """

    return """<fmiModelDescription fmiVersion="3.0"
        modelName="VeraGridPhysicalCompositionContainerPFTimeLatticeV41"
        instantiationToken="{78277fc9-f825-54fc-a932-c79731732e85}"
        generationTool="VeraGrid FMI composition container v0"
        variableNamingConvention="flat">
      <CoSimulation
          modelIdentifier="VeraGridPhysicalCompositionContainerPFTimeLatticeV41"
          canHandleVariableCommunicationStepSize="false"
          fixedInternalStepSize="0.001"/>
      <DefaultExperiment startTime="0" stepSize="0.001"/>
      <ModelVariables>
        <Float64 name="speed" valueReference="0" causality="output"
            variability="continuous" initial="calculated"/>
        <Float64 name="angle" valueReference="1" causality="output"
            variability="continuous" initial="calculated"/>
        <Float64 name="electrical_power" valueReference="2" causality="output"
            variability="continuous" initial="calculated"/>
        <Float64 name="mechanical_control" valueReference="3" causality="output"
            variability="continuous" initial="calculated"/>
        <Float64 name="time" valueReference="4" causality="independent"
            variability="continuous"/>
      </ModelVariables>
      <ModelStructure>
        <Output valueReference="0"/>
        <Output valueReference="1"/>
        <Output valueReference="2"/>
        <Output valueReference="3"/>
        <InitialUnknown valueReference="0"/>
        <InitialUnknown valueReference="1"/>
        <InitialUnknown valueReference="2"/>
        <InitialUnknown valueReference="3"/>
      </ModelStructure>
    </fmiModelDescription>"""


def _fmi3_derivative_fixture_xml() -> str:
    """Return valid FMI 3 state, derivative, and independent-variable metadata.

    :return: FMI 3 XML where the derivative references its state by value reference.
    """

    return """<fmiModelDescription fmiVersion="3.0.2" modelName="DerivativeModel"
        instantiationToken="derivative-token">
      <ModelExchange modelIdentifier="derivative_me"/>
      <ModelVariables>
        <Float64 name="state" valueReference="1" causality="local"
            variability="continuous"/>
        <Float64 name="state_derivative" valueReference="2" causality="local"
            variability="continuous" derivative="1"/>
        <Float64 name="time" valueReference="3" causality="independent"
            variability="continuous"/>
      </ModelVariables>
      <ModelStructure>
        <ContinuousStateDerivative valueReference="2"/>
        <InitialUnknown valueReference="1"/>
        <InitialUnknown valueReference="2"/>
      </ModelStructure>
    </fmiModelDescription>"""


def _fmi_three_scalar_binding_fixture_xml() -> str:
    """Return FMI 3 metadata with ordered Float64 access categories.

    :return: Self-contained scalar Co-Simulation model description.
    """

    return """<fmiModelDescription fmiVersion="3.0.2" modelName="BindingModel"
        instantiationToken="binding-token">
      <CoSimulation modelIdentifier="binding_model"
          canHandleVariableCommunicationStepSize="false"/>
      <ModelVariables>
        <Float64 name="output_a" valueReference="11" causality="output"
            variability="continuous" initial="calculated"/>
        <Float64 name="input_b" valueReference="8" causality="input"
            variability="continuous" start="0"/>
        <Float64 name="output_b" valueReference="12" causality="output"
            variability="continuous" initial="calculated"/>
        <Float64 name="input_a" valueReference="7" causality="input"
            variability="continuous" start="0"/>
        <Float64 name="tunable_parameter" valueReference="14"
            causality="parameter" variability="tunable" start="1"/>
        <Float64 name="fixed_parameter" valueReference="15"
            causality="parameter" variability="fixed" start="2"/>
        <Float64 name="constant_local" valueReference="16" causality="local"
            variability="constant" initial="exact" start="4"/>
        <Float64 name="time" valueReference="13" causality="independent"
            variability="continuous"/>
      </ModelVariables>
      <ModelStructure>
        <Output valueReference="11"/>
        <Output valueReference="12"/>
        <InitialUnknown valueReference="11"/>
        <InitialUnknown valueReference="12"/>
      </ModelStructure>
    </fmiModelDescription>"""


def _fmi_three_constant_array_fixture_xml() -> str:
    """Return FMI 3 metadata with one constant two-dimensional Float64 array.

    :return: Self-contained Co-Simulation model description with a 3-by-2 array.
    """

    return """<fmiModelDescription fmiVersion="3.0.2" modelName="ArrayModel"
        instantiationToken="array-token">
      <CoSimulation modelIdentifier="array_model"
          canHandleVariableCommunicationStepSize="false"/>
      <ModelVariables>
        <Float64 name="matrix" valueReference="20" causality="parameter"
            variability="tunable" start="0.0 0.1 1.0 1.1 2.0 2.1">
          <Dimension start="3"/>
          <Dimension start="2"/>
        </Float64>
        <Float64 name="time" valueReference="21" causality="independent"
            variability="continuous"/>
      </ModelVariables>
      <ModelStructure/>
    </fmiModelDescription>"""


def _fmi_three_referenced_dimension_fixture_xml(
    dimension_source_xml: str,
    dimension_value_reference: int = 100,
) -> str:
    """Return an FMI 3 array controlled by one declared dimension source.

    :param dimension_source_xml: Complete source-variable XML element.
    :param dimension_value_reference: Reference used by the array dimension.
    :return: Self-contained FMI 3 model-description fixture.
    """

    return f"""<fmiModelDescription fmiVersion="3.0.2"
        modelName="ReferencedDimensionModel"
        instantiationToken="referenced-dimension-token">
      <CoSimulation modelIdentifier="referenced_dimension_model"
          canHandleVariableCommunicationStepSize="false"/>
      <ModelVariables>
        {dimension_source_xml}
        <Float64 name="matrix" valueReference="20" causality="parameter"
            variability="fixed" initial="exact"
            start="0.0 0.1 1.0 1.1 2.0 2.1">
          <Dimension valueReference="{dimension_value_reference}"/>
          <Dimension start="2"/>
        </Float64>
        <Float64 name="time" valueReference="21" causality="independent"
            variability="continuous"/>
      </ModelVariables>
      <ModelStructure/>
    </fmiModelDescription>"""


def test_fmi_three_constant_array_dimensions_preserve_order_and_start_values(
    tmp_path: Path,
) -> None:
    """Represent constant dimensions while the scalar runtime remains gated.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "constant-array",
        _fmi_three_constant_array_fixture_xml(),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    array_variable: FmuVariableDescription = metadata.get_variable("matrix")

    assert tuple(
        dimension.constant_size for dimension in array_variable.dimensions
    ) == (3, 2)
    assert array_variable.start == "0.0 0.1 1.0 1.1 2.0 2.1"
    assert metadata.get_variable("time").dimensions == tuple()
    assert (
        resolve_fmi_three_worker_float64_profile(metadata)
        == FmiThreeWorkerFloat64Profile.CONSTANT_ARRAY
    )
    config: FmuImportConfig = FmuImportConfig(fmu_path=fmu_path)
    assert (
        config.resolve_execution_mode(metadata)
        == FmuInterfaceMode.CO_SIMULATION
    )
    with pytest.raises(RuntimeError, match="arrays are outside"):
        validate_fmi_three_co_simulation_worker_profile(
            metadata=metadata,
            preferred_mode=config.preferred_mode,
        )


def test_fmi_three_referenced_dimension_preserves_typed_uint64_owner(
    tmp_path: Path,
) -> None:
    """Preserve a dynamic dimension and validate its UInt64 structural owner.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "referenced-dimension",
        _fmi_three_referenced_dimension_fixture_xml(
            '<UInt64 name="rows" valueReference="100" '
            'causality="structuralParameter" variability="fixed" start="3"/>'
        ),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    dimension_source: FmuVariableDescription = metadata.get_variable("rows")
    matrix: FmuVariableDescription = metadata.get_variable("matrix")

    assert dimension_source.variable_type == FmuVariableType.UINT64
    assert resolve_fmi_three_configuration_uint64_writable_references(
        metadata
    ) == frozenset((100,))
    assert matrix.dimensions[0].constant_size is None
    assert matrix.dimensions[0].value_reference == 100
    assert matrix.dimensions[1].constant_size == 2
    assert (
        resolve_fmi_three_worker_float64_profile(metadata)
        == FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY
    )
    with pytest.raises(ValueError, match="Configuration Mode dimension"):
        resolve_fmi_three_variable_serialized_value_count(
            variable=matrix,
            maximum_serialized_value_count=64,
        )


def test_fmi_three_configurable_array_layout_recalculates_and_vanishes(
    tmp_path: Path,
) -> None:
    """Recalculate a referenced array dimension, including zero cardinality.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "configured-array-layout",
        _fmi_three_referenced_dimension_fixture_xml(
            '<UInt64 name="rows" valueReference="100" '
            'causality="structuralParameter" variability="fixed" start="3"/>'
        ),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    readable_layout: FmiThreeFloat64BindingLayout
    writable_layout: FmiThreeFloat64BindingLayout
    readable_layout, writable_layout = (
        resolve_fmi_three_configurable_float64_binding_layouts(
            metadata=metadata,
            readable_variable_names=("matrix", "time"),
            writable_variable_names=tuple(),
            maximum_serialized_value_count=16,
        )
    )

    assert readable_layout.serialized_value_counts == (6, 1)
    assert writable_layout.serialized_value_counts == tuple()
    resized_layout: FmiThreeFloat64BindingLayout = (
        resolve_fmi_three_configured_float64_binding_layout(
            layout=readable_layout,
            configuration_uint64_value_references=(100,),
            configuration_uint64_values=(4,),
            maximum_serialized_value_count=16,
        )
    )
    assert resized_layout.serialized_value_counts == (8, 1)
    assert resized_layout.serialized_value_count == 9
    vanished_layout: FmiThreeFloat64BindingLayout = (
        resolve_fmi_three_configured_float64_binding_layout(
            layout=resized_layout,
            configuration_uint64_value_references=(100,),
            configuration_uint64_values=(0,),
            maximum_serialized_value_count=16,
        )
    )
    assert vanished_layout.serialized_value_counts == (0, 1)
    assert vanished_layout.serialized_value_count == 1
    with pytest.raises(ValueError, match="serialized value bound"):
        resolve_fmi_three_configured_float64_binding_layout(
            layout=readable_layout,
            configuration_uint64_value_references=(100,),
            configuration_uint64_values=(9,),
            maximum_serialized_value_count=16,
        )


def test_fmi_three_vanished_dimension_short_circuits_later_memory_bound() -> None:
    """Resolve a zero product independently of dimension declaration order.

    :return: None.
    """

    cardinality_plan: FmiThreeFloat64VariableCardinalityPlan = (
        FmiThreeFloat64VariableCardinalityPlan(
            value_reference=20,
            dimension_sizes=(1, 1),
            dimension_value_references=(100, 101),
        )
    )
    configured_plan: FmiThreeFloat64VariableCardinalityPlan = (
        cardinality_plan.configure_uint64(
            value_references=(100, 101),
            values=(18446744073709551615, 0),
            maximum_serialized_value_count=16,
        )
    )

    assert configured_plan.dimension_sizes == (18446744073709551615, 0)
    assert configured_plan.resolve_serialized_value_count(16) == 0


def test_fmi_three_configurable_profile_accepts_constant_uint64_dimension_owner(
    tmp_path: Path,
) -> None:
    """Accept a constant UInt64 dimension source without making it writable.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "constant-referenced-dimension",
        _fmi_three_referenced_dimension_fixture_xml(
            '<UInt64 name="rows" valueReference="100" '
            'variability="constant" start="3"/>'
        ),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    validate_fmi_three_co_simulation_worker_profile(
        metadata=metadata,
        preferred_mode=FmuInterfaceMode.CO_SIMULATION,
        float64_profile=FmiThreeWorkerFloat64Profile.CONFIGURABLE_ARRAY,
    )
    assert resolve_fmi_three_configuration_uint64_writable_references(
        metadata
    ) == frozenset()


@pytest.mark.parametrize(
    ("dimension_source_xml", "dimension_value_reference", "expected_error"),
    (
        (
            '<UInt64 name="rows" valueReference="100" '
            'causality="structuralParameter" variability="fixed" start="3"/>',
            101,
            "referencing missing valueReference",
        ),
        (
            '<Float64 name="rows" valueReference="100" '
            'causality="structuralParameter" variability="fixed" start="3"/>',
            100,
            "is not UInt64",
        ),
        (
            '<UInt64 name="rows" valueReference="100" causality="input" '
            'variability="discrete" start="3"/>',
            100,
            "neither constant nor a structural parameter",
        ),
        (
            '<UInt64 name="rows" valueReference="100" '
            'causality="structuralParameter" variability="fixed" start="0"/>',
            100,
            "positive initial size",
        ),
        (
            '<UInt64 name="rows" valueReference="100" '
            'causality="structuralParameter" variability="fixed" start="3">'
            '<Dimension start="1"/></UInt64>',
            100,
            "must be scalar",
        ),
    ),
)
def test_fmi_three_referenced_dimension_rejects_invalid_owner(
    tmp_path: Path,
    dimension_source_xml: str,
    dimension_value_reference: int,
    expected_error: str,
) -> None:
    """Reject a missing, mistyped, mutable, vanished, or array dimension owner.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param dimension_source_xml: Source variable under test.
    :param dimension_value_reference: Reference used by the array dimension.
    :param expected_error: Stable diagnostic fragment.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-referenced-dimension",
        _fmi_three_referenced_dimension_fixture_xml(
            dimension_source_xml=dimension_source_xml,
            dimension_value_reference=dimension_value_reference,
        ),
    )

    with pytest.raises(ValueError, match=expected_error):
        read_fmu_model_description(fmu_path)


def test_fmi_three_constant_array_accepts_one_broadcast_start_value(
    tmp_path: Path,
) -> None:
    """Accept one FMI start value broadcast over every constant array element.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    broadcast_xml: str = _fmi_three_constant_array_fixture_xml().replace(
        'start="0.0 0.1 1.0 1.1 2.0 2.1"',
        'start="4.5"',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "broadcast-array",
        broadcast_xml,
    )

    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    assert metadata.get_variable("matrix").start == "4.5"


def test_fmi_three_constant_array_keeps_uint64_size_without_expansion(
    tmp_path: Path,
) -> None:
    """Keep a large constant dimension as metadata without allocating elements.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    large_array_xml: str = _fmi_three_constant_array_fixture_xml().replace(
        '<Dimension start="3"/>',
        '<Dimension start="18446744073709551615"/>',
        1,
    ).replace(
        'start="0.0 0.1 1.0 1.1 2.0 2.1"',
        'start="4.5"',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "large-constant-array",
        large_array_xml,
    )

    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    assert tuple(
        dimension.constant_size
        for dimension in metadata.get_variable("matrix").dimensions
    ) == (
        18446744073709551615,
        2,
    )


def test_fmi_three_constant_array_binding_layout_preserves_flattened_order(
    tmp_path: Path,
) -> None:
    """Resolve scalar and row-major array cardinality without expanding values.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "array-layout",
        _fmi_three_constant_array_fixture_xml(),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    readable_layout: FmiThreeFloat64BindingLayout
    writable_layout: FmiThreeFloat64BindingLayout
    readable_layout, writable_layout = (
        resolve_fmi_three_constant_float64_binding_layouts(
            metadata=metadata,
            readable_variable_names=("time", "matrix"),
            writable_variable_names=("matrix",),
            maximum_serialized_value_count=16,
        )
    )

    assert readable_layout.value_references == (21, 20)
    assert readable_layout.serialized_value_counts == (1, 6)
    assert readable_layout.serialized_value_count == 7
    assert writable_layout.value_references == (20,)
    assert writable_layout.serialized_value_counts == (6,)
    assert writable_layout.serialized_value_count == 6


def test_fmi_three_constant_array_binding_layout_rejects_value_bound(
    tmp_path: Path,
) -> None:
    """Reject an array layout before its declared values can be allocated.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "bounded-array-layout",
        _fmi_three_constant_array_fixture_xml(),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    with pytest.raises(ValueError, match="serialized value bound"):
        resolve_fmi_three_constant_float64_binding_layouts(
            metadata=metadata,
            readable_variable_names=("matrix",),
            writable_variable_names=tuple(),
            maximum_serialized_value_count=5,
        )


def test_fmi_three_constant_array_worker_acl_preserves_cardinality(
    tmp_path: Path,
) -> None:
    """Rebuild exact array cardinality for the child-side native ACL.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "array-worker-acl",
        _fmi_three_constant_array_fixture_xml(),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    readable_value_counts: dict[int, int]
    writable_value_counts: dict[int, int]
    initialization_value_counts: dict[int, int]
    configuration_value_counts: dict[int, int]
    configuration_uint64_references: frozenset[int]
    readable_int32_references: frozenset[int]
    writable_int32_references: frozenset[int]
    initialization_int32_references: frozenset[int]
    cardinality_plans: dict[int, FmiThreeFloat64VariableCardinalityPlan]
    (
        readable_value_counts,
        writable_value_counts,
        initialization_value_counts,
        configuration_value_counts,
        configuration_uint64_references,
        readable_int32_references,
        writable_int32_references,
        initialization_int32_references,
        cardinality_plans,
    ) = _resolve_fmi_three_worker_access_controls(
        metadata=metadata,
        maximum_serialized_value_count=16,
    )

    assert readable_value_counts == dict(((20, 6), (21, 1)))
    assert writable_value_counts == dict(((20, 6),))
    assert initialization_value_counts == dict(((20, 6),))
    assert configuration_value_counts == dict()
    assert configuration_uint64_references == frozenset()
    assert readable_int32_references == frozenset()
    assert writable_int32_references == frozenset()
    assert initialization_int32_references == frozenset()
    assert cardinality_plans[20].dimension_sizes == (3, 2)


def test_fmi_three_int32_metadata_is_preserved(tmp_path: Path) -> None:
    """Preserve scalar signed values and resolve ordered Int32 ACL bindings.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "int32-metadata",
        """<fmiModelDescription fmiVersion="3.0.2" modelName="Int32Model"
            instantiationToken="int32-token">
          <CoSimulation modelIdentifier="int32_model"
              canHandleVariableCommunicationStepSize="false"/>
          <ModelVariables>
            <Int32 name="integer_input" valueReference="7" causality="input"
                variability="discrete" initial="exact" start="-2"/>
            <Int32 name="integer_output" valueReference="8" causality="output"
                variability="discrete" initial="calculated"/>
            <Float64 name="time" valueReference="9" causality="independent"
                variability="continuous"/>
          </ModelVariables>
          <ModelStructure>
            <Output valueReference="8"/>
            <InitialUnknown valueReference="8"/>
          </ModelStructure>
        </fmiModelDescription>""",
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    integer_input: FmuVariableDescription = metadata.get_variable("integer_input")
    integer_output: FmuVariableDescription = metadata.get_variable("integer_output")

    assert integer_input.variable_type is FmuVariableType.INT32
    assert integer_input.start == "-2"
    assert integer_output.variable_type is FmuVariableType.INT32
    initialization_references: tuple[int, ...]
    readable_references: tuple[int, ...]
    writable_references: tuple[int, ...]
    (
        initialization_references,
        readable_references,
        writable_references,
    ) = resolve_fmi_three_scalar_int32_binding_references(
        metadata=metadata,
        initialization_variable_names=("integer_input",),
        readable_variable_names=("integer_output", "integer_input"),
        writable_variable_names=("integer_input",),
    )
    assert initialization_references == (7,)
    assert readable_references == (8, 7)
    assert writable_references == (7,)


def test_fmi_three_worker_profile_accepts_scalar_int32_co_simulation(
    tmp_path: Path,
) -> None:
    """Accept a scalar Int32 variable in every Float64 CS profile.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    scalar_int32_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        '        <Float64 name="time" valueReference="4" causality="independent"',
        '        <Int32 name="counter" valueReference="5" causality="local"\n'
        '            variability="discrete" initial="exact" start="-2"/>\n'
        '        <Float64 name="time" valueReference="4" causality="independent"',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "scalar-int32-cs-profile",
        scalar_int32_xml,
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    float64_profile: FmiThreeWorkerFloat64Profile
    for float64_profile in FmiThreeWorkerFloat64Profile:
        validate_fmi_three_co_simulation_worker_profile(
            metadata=metadata,
            preferred_mode=FmuInterfaceMode.CO_SIMULATION,
            float64_profile=float64_profile,
        )


def test_fmi_three_worker_profile_accepts_scalar_int32_model_exchange(
    tmp_path: Path,
) -> None:
    """Accept a scalar Int32 variable in every Float64 ME profile.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    scalar_int32_xml: str = _fmi3_derivative_fixture_xml().replace(
        '        <Float64 name="time" valueReference="3" causality="independent"',
        '        <Int32 name="counter" valueReference="4" causality="local"\n'
        '            variability="discrete" initial="exact" start="-2"/>\n'
        '        <Float64 name="time" valueReference="3" causality="independent"',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "scalar-int32-me-profile",
        scalar_int32_xml,
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    float64_profile: FmiThreeWorkerFloat64Profile
    for float64_profile in FmiThreeWorkerFloat64Profile:
        validate_fmi_three_model_exchange_worker_profile(
            metadata=metadata,
            preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
            float64_profile=float64_profile,
        )


def test_fmi_three_worker_profile_rejects_int32_array(tmp_path: Path) -> None:
    """Reject Int32 arrays at parsing and at both worker-profile boundaries.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    array_int32_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        '        <Float64 name="time" valueReference="4" causality="independent"',
        '        <Int32 name="counter" valueReference="5" causality="input"\n'
        '            variability="discrete" initial="exact" start="-2 3">\n'
        '          <Dimension start="2"/>\n'
        '        </Int32>\n'
        '        <Float64 name="time" valueReference="4" causality="independent"',
        1,
    )
    array_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "array-int32-parser",
        array_int32_xml,
    )
    with pytest.raises(ValueError, match="Int32 variable.*must be scalar"):
        read_fmu_model_description(array_path)

    cs_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "array-int32-cs-defense",
        _scalar_fmi3_worker_profile_fixture_xml().replace(
            '        <Float64 name="time" valueReference="4" causality="independent"',
            '        <Int32 name="counter" valueReference="5" causality="local"\n'
            '            variability="discrete" initial="exact" start="-2"/>\n'
            '        <Float64 name="time" valueReference="4" causality="independent"',
            1,
        ),
    )
    cs_metadata: FmuModelDescription = read_fmu_model_description(cs_path)
    cs_counter: FmuVariableDescription = cs_metadata.get_variable("counter")
    cs_counter.dimensions = (FmiThreeVariableDimension(2, None),)

    me_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "array-int32-me-defense",
        _fmi3_derivative_fixture_xml().replace(
            '        <Float64 name="time" valueReference="3" causality="independent"',
            '        <Int32 name="counter" valueReference="4" causality="local"\n'
            '            variability="discrete" initial="exact" start="-2"/>\n'
            '        <Float64 name="time" valueReference="3" causality="independent"',
            1,
        ),
    )
    me_metadata: FmuModelDescription = read_fmu_model_description(me_path)
    me_counter: FmuVariableDescription = me_metadata.get_variable("counter")
    me_counter.dimensions = (FmiThreeVariableDimension(2, None),)

    float64_profile: FmiThreeWorkerFloat64Profile
    for float64_profile in FmiThreeWorkerFloat64Profile:
        with pytest.raises(RuntimeError, match="arrays|scalar Int32"):
            validate_fmi_three_co_simulation_worker_profile(
                metadata=cs_metadata,
                preferred_mode=FmuInterfaceMode.CO_SIMULATION,
                float64_profile=float64_profile,
            )
        with pytest.raises(RuntimeError, match="arrays|scalar Int32"):
            validate_fmi_three_model_exchange_worker_profile(
                metadata=me_metadata,
                preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
                float64_profile=float64_profile,
            )


def test_fmi_three_array_accepts_annotations_before_dimensions(tmp_path: Path) -> None:
    """Accept the schema-defined Annotations then Dimension child order.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    annotated_xml: str = _fmi_three_constant_array_fixture_xml().replace(
        '          <Dimension start="3"/>',
        '          <Annotations><Annotation type="urn:vendor:array">'
        '<vendor:data xmlns:vendor="urn:vendor"/>'
        '</Annotation></Annotations>\n'
        '          <Dimension start="3"/>',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "annotated-array",
        annotated_xml,
    )

    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    assert tuple(
        dimension.constant_size
        for dimension in metadata.get_variable("matrix").dimensions
    ) == (3, 2)


@pytest.mark.parametrize(
    ("dimension_fragment", "expected_error"),
    (
        ('<Dimension start="0"/>', "must be positive"),
        ('<Dimension start="-1"/>', "not an unsigned 64-bit"),
        ('<Dimension start="18446744073709551616"/>', "exceeds unsigned 64-bit"),
        (
            '<Dimension start="3" valueReference="100"/>',
            "exactly one of start or valueReference",
        ),
        ("<Dimension/>", "exactly one of start or valueReference"),
        ('<Dimension start="3" extra="1"/>', "attribute 'extra'"),
        (
            '<Dimension start="3"><Nested/></Dimension>',
            "must not contain child elements",
        ),
        ('<Dimension start="3">content</Dimension>', "must not contain text"),
        (
            'content<Dimension start="3"/>',
            "text outside its child elements",
        ),
        (
            '<Dimension start="3"/>content',
            "text outside its child elements",
        ),
        (
            '<Alias name="alias" description="unsupported"/>',
            "out-of-order children",
        ),
        (
            '<Dimension start="3"/><Annotations/>',
            "out-of-order children",
        ),
    ),
)
def test_fmi_three_constant_array_rejects_invalid_dimension_metadata(
    tmp_path: Path,
    dimension_fragment: str,
    expected_error: str,
) -> None:
    """Reject ambiguous, vanished, oversized, and dynamic dimensions.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :param dimension_fragment: First dimension replacement under test.
    :param expected_error: Stable rejection fragment.
    :return: None.
    """

    invalid_xml: str = _fmi_three_constant_array_fixture_xml().replace(
        '<Dimension start="3"/>',
        dimension_fragment,
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-array-dimension",
        invalid_xml,
    )

    with pytest.raises(ValueError, match=expected_error):
        read_fmu_model_description(fmu_path)


@pytest.mark.parametrize("start_value_count", (5, 7))
def test_fmi_three_constant_array_rejects_wrong_start_cardinality(
    tmp_path: Path,
    start_value_count: int,
) -> None:
    """Reject a start list that is neither broadcast nor the complete array.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :param start_value_count: Invalid number of serialized array start values.
    :return: None.
    """

    invalid_start_values: str = " ".join(("0.0",) * start_value_count)
    invalid_xml: str = _fmi_three_constant_array_fixture_xml().replace(
        'start="0.0 0.1 1.0 1.1 2.0 2.1"',
        f'start="{invalid_start_values}"',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-array-start",
        invalid_xml,
    )

    with pytest.raises(ValueError, match="start cardinality"):
        read_fmu_model_description(fmu_path)


def test_fmi_three_array_event_indicator_counts_serialized_values(
    tmp_path: Path,
) -> None:
    """Count every serialized array element declared as an event indicator.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    array_indicator_xml: str = """<fmiModelDescription fmiVersion="3.0.2"
        modelName="ArrayIndicatorModel" instantiationToken="array-indicator-token">
      <CoSimulation modelIdentifier="array_indicator_model"
          canHandleVariableCommunicationStepSize="false"/>
      <ModelVariables>
        <Float64 name="indicators" valueReference="20" causality="local"
            variability="continuous">
          <Dimension start="2"/>
          <Dimension start="3"/>
        </Float64>
        <Float64 name="time" valueReference="21" causality="independent"
            variability="continuous"/>
      </ModelVariables>
      <ModelStructure>
        <EventIndicator valueReference="20"/>
      </ModelStructure>
    </fmiModelDescription>"""
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "array-event-indicator",
        array_indicator_xml,
    )

    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    assert metadata.number_of_event_indicators == 6
    assert metadata.get_variable("indicators").start is None


def test_fmi_three_array_event_indicator_rejects_adversarial_cardinality(
    tmp_path: Path,
) -> None:
    """Reject event-indicator cardinality outside the represented size_t bound.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    adversarial_xml: str = """<fmiModelDescription fmiVersion="3.0.2"
        modelName="LargeIndicatorModel" instantiationToken="large-indicator-token">
      <CoSimulation modelIdentifier="large_indicator_model"
          canHandleVariableCommunicationStepSize="false"/>
      <ModelVariables>
        <Float64 name="indicators" valueReference="20" causality="local"
            variability="continuous">
          <Dimension start="18446744073709551615"/>
          <Dimension start="18446744073709551615"/>
        </Float64>
        <Float64 name="time" valueReference="21" causality="independent"
            variability="continuous"/>
      </ModelVariables>
      <ModelStructure>
        <EventIndicator valueReference="20"/>
      </ModelStructure>
    </fmiModelDescription>"""
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "large-array-event-indicator",
        adversarial_xml,
    )

    with pytest.raises(ValueError, match="unsigned 64-bit size_t limit"):
        read_fmu_model_description(fmu_path)


def test_fmi_one_and_two_metadata_reject_fmi_three_array_dimensions() -> None:
    """Reject FMI 3 dimension metadata attached to an FMI 1 or FMI 2 model.

    :return: None.
    """

    array_variable: FmuVariableDescription = FmuVariableDescription(
        name="array",
        value_reference=1,
        variable_type=FmuVariableType.FLOAT64,
        causality="input",
        variability="continuous",
        initial=None,
        start="0",
        derivative_index=None,
        dimensions=(FmiThreeVariableDimension(2, None),),
    )
    model_identifiers: dict[FmuInterfaceMode, str] = dict()
    model_identifiers[FmuInterfaceMode.CO_SIMULATION] = "fmi_two_array"

    with pytest.raises(ValueError, match="FMI 1 and FMI 2 variables"):
        FmuModelDescription(
            path=Path("invalid-fmi-two-array.fmu"),
            fmi_version="2.0",
            model_name="InvalidFmiTwoArray",
            guid="invalid-fmi-two-guid",
            variable_naming_convention="flat",
            number_of_event_indicators=0,
            interface_modes=(FmuInterfaceMode.CO_SIMULATION,),
            model_identifiers=model_identifiers,
            platforms=tuple(),
            variables=(array_variable,),
        )


def test_fmi_three_initialization_writable_references_follow_exact_values(
    tmp_path: Path,
) -> None:
    """Separate Initialization Mode access from Step Mode binding access.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "initialization-access",
        _fmi_three_scalar_binding_fixture_xml(),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    writable_references: frozenset[int] = (
        resolve_fmi_three_initialization_writable_references(metadata)
    )

    assert writable_references == frozenset((7, 8, 14, 15))


def test_fmi_three_scalar_binding_references_preserve_requested_access_order(
    tmp_path: Path,
) -> None:
    """Preserve requested writable and readable variable order.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "ordered-bindings",
        _fmi_three_scalar_binding_fixture_xml(),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    readable_references: tuple[int, ...]
    writable_references: tuple[int, ...]
    readable_references, writable_references = (
        resolve_fmi_three_scalar_binding_references(
            metadata=metadata,
            readable_variable_names=(
                "input_b",
                "output_b",
                "fixed_parameter",
                "tunable_parameter",
                "time",
                "output_a",
            ),
            writable_variable_names=("input_a", "tunable_parameter", "input_b"),
        )
    )

    assert readable_references == (8, 12, 15, 14, 13, 11)
    assert writable_references == (7, 14, 8)


@pytest.mark.parametrize(
    ("writable_variable_names", "readable_variable_names", "expected_error"),
    (
        (("missing",), tuple(), "was not found"),
        (("input_a", "input_a"), tuple(), "Duplicate writable FMI 3 binding"),
        (("output_a",), tuple(), "not writable in Step Mode"),
        (("fixed_parameter",), tuple(), "not writable in Step Mode"),
        (tuple(), ("output_a", "output_a"), "Duplicate readable FMI 3 binding"),
    ),
)
def test_fmi_three_scalar_binding_references_reject_invalid_targets(
    tmp_path: Path,
    writable_variable_names: tuple[str, ...],
    readable_variable_names: tuple[str, ...],
    expected_error: str,
) -> None:
    """Reject missing, duplicate, or non-writable binding targets.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param writable_variable_names: Ordered writable names under test.
    :param readable_variable_names: Ordered readable names under test.
    :param expected_error: Required diagnostic fragment.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-bindings",
        _fmi_three_scalar_binding_fixture_xml(),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    with pytest.raises(ValueError, match=expected_error):
        resolve_fmi_three_scalar_binding_references(
            metadata=metadata,
            readable_variable_names=readable_variable_names,
            writable_variable_names=writable_variable_names,
        )


def test_scalar_fmi3_fixture_preserves_identity_interface_and_variables(tmp_path: Path) -> None:
    """Verify the self-contained fixture identity and variables.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "scalar-fmi3",
        _scalar_fmi3_worker_profile_fixture_xml(),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    assert metadata.fmi_version == "3.0"
    assert metadata.fmi_version_family is FmiVersion.FMI_3_0
    assert metadata.guid is None
    assert metadata.instantiation_token == "{78277fc9-f825-54fc-a932-c79731732e85}"
    assert metadata.interface_modes == (FmuInterfaceMode.CO_SIMULATION,)
    assert metadata.get_model_identifier(FmuInterfaceMode.CO_SIMULATION) == (
        "VeraGridPhysicalCompositionContainerPFTimeLatticeV41"
    )
    assert metadata.get_variable_names() == (
        "speed",
        "angle",
        "electrical_power",
        "mechanical_control",
        "time",
    )
    assert all(variable.variable_type is FmuVariableType.FLOAT64 for variable in metadata.variables)



def test_scalar_fmi3_fixture_preserves_worker_capabilities_and_gate(tmp_path: Path) -> None:
    """Verify fixture capabilities persist while execution remains disconnected.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "scalar-worker-profile",
        _scalar_fmi3_worker_profile_fixture_xml(),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    capabilities: FmiThreeCoSimulationCapabilities | None = (
        metadata.fmi_three_co_simulation_capabilities
    )
    if capabilities is None:
        raise AssertionError("The fixture Co-Simulation capabilities must be retained")
    else:
        pass
    assert not capabilities.needs_execution_tool
    assert not capabilities.can_be_instantiated_only_once_per_process
    assert not capabilities.can_get_and_set_fmu_state
    assert not capabilities.can_serialize_fmu_state
    assert not capabilities.can_handle_variable_communication_step_size
    assert not capabilities.provides_intermediate_update
    assert not capabilities.might_return_early_from_do_step
    assert not capabilities.can_return_early_after_intermediate_update
    assert not capabilities.has_event_mode
    assert capabilities.fixed_internal_step_size == pytest.approx(0.001)

    config: FmuImportConfig = FmuImportConfig(fmu_path=fmu_path)
    assert (
        config.resolve_execution_mode(metadata)
        == FmuInterfaceMode.CO_SIMULATION
    )


def test_fmi_three_metadata_preserves_supported_worker_capabilities(tmp_path: Path) -> None:
    """Verify supported and explicitly disabled capabilities remain typed.

    One worker process owns one FMU instance, so an FMU restricted to one
    instantiation per process is compatible with the planned lifecycle. Variable
    communication-step enforcement belongs to the worker once it is connected.
    Optional lifecycle features may be advertised while the importer declines
    them through its native instantiation arguments.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    modified_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        'canHandleVariableCommunicationStepSize="false"',
        'canBeInstantiatedOnlyOncePerProcess="true" '
        'canGetAndSetFMUState="true" '
        'canSerializeFMUState="true" '
        'canHandleVariableCommunicationStepSize="true" '
        'providesIntermediateUpdate="true" '
        'mightReturnEarlyFromDoStep="true" '
        'canReturnEarlyAfterIntermediateUpdate="true" '
        'hasEventMode="true"',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "supported-worker-capabilities",
        modified_xml,
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    capabilities: FmiThreeCoSimulationCapabilities | None = (
        metadata.fmi_three_co_simulation_capabilities
    )
    if capabilities is None:
        raise AssertionError("The supported worker capabilities must be retained")
    else:
        pass
    assert capabilities.can_be_instantiated_only_once_per_process
    assert capabilities.can_get_and_set_fmu_state
    assert capabilities.can_serialize_fmu_state
    assert capabilities.can_handle_variable_communication_step_size
    assert capabilities.provides_intermediate_update
    assert capabilities.might_return_early_from_do_step
    assert capabilities.can_return_early_after_intermediate_update
    assert capabilities.has_event_mode

    config: FmuImportConfig = FmuImportConfig(fmu_path=fmu_path)
    assert (
        config.resolve_execution_mode(metadata)
        == FmuInterfaceMode.CO_SIMULATION
    )


def test_fmi_three_rejects_intermediate_early_return_without_intermediate_update(
    tmp_path: Path,
) -> None:
    """Reject an early-return capability without its required callback mode.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    modified_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        'canHandleVariableCommunicationStepSize="false"',
        'canReturnEarlyAfterIntermediateUpdate="true" '
        'canHandleVariableCommunicationStepSize="false"',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-intermediate-early-return",
        modified_xml,
    )

    with pytest.raises(
        ValueError,
        match="requires providesIntermediateUpdate=true",
    ):
        read_fmu_model_description(fmu_path)


def test_fmi_three_worker_profile_rejects_required_external_execution_tool(
    tmp_path: Path,
) -> None:
    """Verify an FMU requiring an external tool fails before the worker.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    modified_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        'canHandleVariableCommunicationStepSize="false"',
        'needsExecutionTool="true" canHandleVariableCommunicationStepSize="false"',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "external-execution-tool",
        modified_xml,
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    config: FmuImportConfig = FmuImportConfig(fmu_path=fmu_path)

    assert (
        config.resolve_execution_mode(metadata)
        == FmuInterfaceMode.CO_SIMULATION
    )
    with pytest.raises(RuntimeError, match="external execution tool"):
        validate_fmi_three_co_simulation_worker_profile(
            metadata=metadata,
            preferred_mode=config.preferred_mode,
        )


def test_fmi_three_worker_profile_rejects_float32(
    tmp_path: Path,
) -> None:
    """Verify Float32 remains outside the bounded numeric worker profile.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    float32_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        '<Float64 name="speed"',
        '<Float32 name="speed"',
        1,
    )
    float32_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "float32-profile",
        float32_xml,
    )
    float32_metadata: FmuModelDescription = read_fmu_model_description(float32_path)
    float32_config: FmuImportConfig = FmuImportConfig(fmu_path=float32_path)
    assert (
        float32_config.resolve_execution_mode(float32_metadata)
        == FmuInterfaceMode.CO_SIMULATION
    )
    with pytest.raises(RuntimeError, match="supports Float64 variables"):
        validate_fmi_three_co_simulation_worker_profile(
            metadata=float32_metadata,
            preferred_mode=float32_config.preferred_mode,
        )


def test_fmi_three_worker_profile_accepts_float64_structural_parameters(
    tmp_path: Path,
) -> None:
    """Resolve Float64 structural parameters into the Configuration Mode ACL.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    structural_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        '<Float64 name="speed" valueReference="0" causality="output"\n'
        '            variability="continuous" initial="calculated"/>',
        '<Float64 name="speed" valueReference="0" causality="structuralParameter"\n'
        '            variability="fixed" initial="exact" start="1"/>',
        1,
    )
    structural_xml = structural_xml.replace(
        '        <Output valueReference="0"/>\n',
        "",
        1,
    )
    structural_xml = structural_xml.replace(
        '        <InitialUnknown valueReference="0"/>\n',
        "",
        1,
    )
    structural_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "structural-parameter-profile",
        structural_xml,
    )
    structural_metadata: FmuModelDescription = read_fmu_model_description(structural_path)
    validate_fmi_three_co_simulation_worker_profile(
        metadata=structural_metadata,
        preferred_mode=FmuInterfaceMode.CO_SIMULATION,
        float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
    )
    configuration_layout: FmiThreeFloat64BindingLayout = (
        resolve_fmi_three_configuration_float64_binding_layout(
            metadata=structural_metadata,
            configuration_variable_names=("speed",),
            maximum_serialized_value_count=8,
            float64_profile=FmiThreeWorkerFloat64Profile.SCALAR,
        )
    )

    assert configuration_layout.value_references == (0,)
    assert configuration_layout.serialized_value_counts == (1,)
    assert resolve_fmi_three_configuration_float64_writable_references(
        structural_metadata
    ) == frozenset((0,))


def test_fmi_three_worker_profile_rejects_model_exchange(tmp_path: Path) -> None:
    """Verify the generic selector resolves declared FMI 3 Model Exchange.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "model-exchange-profile",
        _fmi3_derivative_fixture_xml(),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    config: FmuImportConfig = FmuImportConfig(
        fmu_path=fmu_path,
        preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
    )

    assert (
        config.resolve_execution_mode(metadata)
        == FmuInterfaceMode.MODEL_EXCHANGE
    )


@pytest.mark.parametrize(
    (
        "capability_attributes",
        "expected_needs_execution_tool",
        "expected_single_instantiation",
        "expected_get_and_set_state",
        "expected_serialize_state",
        "expected_completed_integrator_step",
        "expected_evaluate_discrete_states",
    ),
    (
        ("", False, False, False, False, False, False),
        (
            'needsExecutionTool="true" '
            'canBeInstantiatedOnlyOncePerProcess="true" '
            'canGetAndSetFMUState="true" '
            'canSerializeFMUState="true" '
            'needsCompletedIntegratorStep="true" '
            'providesEvaluateDiscreteStates="true"',
            True,
            True,
            True,
            True,
            True,
            True,
        ),
    ),
)
def test_fmi_three_model_exchange_capabilities_are_typed_metadata(
    tmp_path: Path,
    capability_attributes: str,
    expected_needs_execution_tool: bool,
    expected_single_instantiation: bool,
    expected_get_and_set_state: bool,
    expected_serialize_state: bool,
    expected_completed_integrator_step: bool,
    expected_evaluate_discrete_states: bool,
) -> None:
    """Preserve default and enabled Model Exchange lifecycle capabilities.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param capability_attributes: Optional capability attributes added to the fixture.
    :param expected_needs_execution_tool: Expected external-tool requirement.
    :param expected_single_instantiation: Expected process-instantiation restriction.
    :param expected_get_and_set_state: Expected native checkpoint capability.
    :param expected_serialize_state: Expected state serialization capability.
    :param expected_completed_integrator_step: Expected integrator notification flag.
    :param expected_evaluate_discrete_states: Expected discrete-evaluation flag.
    :return: None.
    """

    model_exchange_element: str = (
        f'<ModelExchange modelIdentifier="derivative_me" {capability_attributes}/>'
    )
    modified_xml: str = _fmi3_derivative_fixture_xml().replace(
        '<ModelExchange modelIdentifier="derivative_me"/>',
        model_exchange_element,
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "model-exchange-capabilities",
        modified_xml,
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    capabilities: FmiThreeModelExchangeCapabilities | None = (
        metadata.fmi_three_model_exchange_capabilities
    )

    if capabilities is None:
        raise AssertionError("The Model Exchange capabilities must be retained")
    else:
        pass
    assert capabilities.needs_execution_tool is expected_needs_execution_tool
    assert (
        capabilities.can_be_instantiated_only_once_per_process
        is expected_single_instantiation
    )
    assert capabilities.can_get_and_set_fmu_state is expected_get_and_set_state
    assert capabilities.can_serialize_fmu_state is expected_serialize_state
    assert (
        capabilities.needs_completed_integrator_step
        is expected_completed_integrator_step
    )
    assert (
        capabilities.provides_evaluate_discrete_states
        is expected_evaluate_discrete_states
    )
    assert metadata.fmi_three_co_simulation_capabilities is None


def test_fmi_three_model_exchange_capability_owner_requires_its_interface() -> None:
    """Reject a missing capability owner and capabilities without their interface.

    :return: None.
    """

    model_identifiers: dict[FmuInterfaceMode, str] = dict()
    model_identifiers[FmuInterfaceMode.MODEL_EXCHANGE] = "model_exchange"
    with pytest.raises(ValueError, match="requires its capability declaration"):
        FmuModelDescription(
            path=Path("missing-model-exchange-capabilities.fmu"),
            fmi_version="3.0.2",
            model_name="MissingModelExchangeCapabilities",
            guid=None,
            variable_naming_convention="flat",
            number_of_event_indicators=0,
            interface_modes=(FmuInterfaceMode.MODEL_EXCHANGE,),
            model_identifiers=model_identifiers,
            platforms=tuple(),
            variables=tuple(),
            instantiation_token="missing-capabilities-token",
        )

    capabilities: FmiThreeModelExchangeCapabilities = (
        FmiThreeModelExchangeCapabilities(
            needs_execution_tool=False,
            can_be_instantiated_only_once_per_process=False,
            can_get_and_set_fmu_state=False,
            can_serialize_fmu_state=False,
            needs_completed_integrator_step=False,
            provides_evaluate_discrete_states=False,
        )
    )
    with pytest.raises(ValueError, match="capabilities require that interface"):
        FmuModelDescription(
            path=Path("orphan-model-exchange-capabilities.fmu"),
            fmi_version="3.0.2",
            model_name="OrphanModelExchangeCapabilities",
            guid=None,
            variable_naming_convention="flat",
            number_of_event_indicators=0,
            interface_modes=tuple(),
            model_identifiers=dict(),
            platforms=tuple(),
            variables=tuple(),
            instantiation_token="orphan-capabilities-token",
            fmi_three_model_exchange_capabilities=capabilities,
        )


def test_fmi_three_worker_profile_accepts_bounded_event_indicators(tmp_path: Path) -> None:
    """Accept declared indicators now owned by the Model Exchange worker.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    modified_xml: str = _fmi3_derivative_fixture_xml().replace(
        '        <InitialUnknown valueReference="2"/>\n',
        '        <InitialUnknown valueReference="2"/>\n'
        '        <EventIndicator valueReference="1"/>\n',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "event-indicator-profile",
        modified_xml,
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    assert metadata.number_of_event_indicators == 1
    validate_fmi_three_model_exchange_worker_profile(
        metadata=metadata,
        preferred_mode=FmuInterfaceMode.MODEL_EXCHANGE,
    )


def test_fmi3_derivative_references_its_state(tmp_path: Path) -> None:
    """Verify FMI 3 derivative direction uses the state's value reference.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "derivative",
        _fmi3_derivative_fixture_xml(),
    )
    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)
    state_variable: FmuVariableDescription = metadata.get_state_variables()[0]
    derivative_variable: FmuVariableDescription = metadata.get_derivative_variables()[0]

    assert state_variable.name == "state"
    assert derivative_variable.name == "state_derivative"
    assert derivative_variable.derivative_index is None
    assert derivative_variable.state_value_reference == state_variable.value_reference


def test_deprecated_mode_selector_preserves_metadata_api_compatibility(tmp_path: Path) -> None:
    """Verify the former public selector delegates with an explicit warning.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "deprecated-selector",
        _scalar_fmi3_worker_profile_fixture_xml(),
    )
    with pytest.warns(DeprecationWarning, match="select_declared_fmu_interface"):
        selected_interface: FmuInterfaceMode = choose_fmu_mode(fmu_path)
    assert selected_interface is FmuInterfaceMode.CO_SIMULATION


@pytest.mark.parametrize(
    "generation_date_and_time",
    (
        "2026-08-17T17:41:57Z",
        "2025-06-12T19:14:15.927318+00:00",
        "2026-03-04T18:13:43",
        "2026-03-04T18:13:43.5-05:30",
        "2026-03-04T18:13:43+14:00",
        "2026-03-04T18:13:43-14:00",
    ),
)
def test_fmi3_accepts_standard_generation_date_and_time(
    tmp_path: Path,
    generation_date_and_time: str,
) -> None:
    """Verify the contracted FMI 3 generation timestamp producer forms.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param generation_date_and_time: Standard date-time value under test.
    :return: None.
    """

    valid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        'generationTool="VeraGrid FMI composition container v0"',
        'generationTool="VeraGrid FMI composition container v0" '
        f'generationDateAndTime="{generation_date_and_time}"',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "valid-generation-date-time",
        valid_xml,
    )

    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    assert metadata.model_name == "VeraGridPhysicalCompositionContainerPFTimeLatticeV41"


def test_fmi3_accepts_valid_log_categories(tmp_path: Path) -> None:
    """Accept the complete represented FMI 3 log-category metadata surface.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :return: None.
    """

    # Exercise the retained Reference FMU categories together with the full
    # normalizedString spacing envelope and the Annotation mixed-content point.
    log_categories_xml: str = """      <LogCategories>
        <Category name="logEvents" description="Log events"/>
        <Category name="logStatusError" description="Log error messages"/>
        <Category name=""/>
        <Category name="   "/>
        <Category name=" leading "/>
        <Category name="a b"/>
        <Category name="a  b"/>
        <Category name="annotated">
          <Annotations>
            <Annotation type="">mixed<vendor:data xmlns:vendor="urn:vendor"/>content</Annotation>
            <Annotation type="   ">spaced type</Annotation>
          </Annotations>
        </Category>
      </LogCategories>
"""
    valid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        '      <DefaultExperiment startTime="0" stepSize="0.001"/>',
        log_categories_xml
        + '      <DefaultExperiment startTime="0" stepSize="0.001"/>',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "valid-log-categories",
        valid_xml,
    )

    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    assert metadata.model_name == "VeraGridPhysicalCompositionContainerPFTimeLatticeV41"


@pytest.mark.parametrize(
    ("invalid_log_categories_xml", "expected_error"),
    (
        ("<LogCategories/>", "must contain a Category"),
        (
            '<LogCategories><Category name="first"/></LogCategories>'
            '<LogCategories><Category name="second"/></LogCategories>',
            "LogCategories is duplicated",
        ),
        (
            '<LogCategories vendor="unsupported"><Category name="x"/></LogCategories>',
            "attribute 'vendor'",
        ),
        (
            "<LogCategories><Unexpected/></LogCategories>",
            "Unexpected 'Unexpected'",
        ),
        (
            "<LogCategories><Category/></LogCategories>",
            "missing required attribute name",
        ),
        (
            '<LogCategories><Category name="x" vendor="unsupported"/></LogCategories>',
            "attribute 'vendor'",
        ),
        (
            '<LogCategories><Category name="same"/><Category name="same"/></LogCategories>',
            "name 'same' is duplicated",
        ),
        (
            '<LogCategories><Category name="a b"/><Category name="a&#x9;b"/></LogCategories>',
            "name 'a b' is duplicated",
        ),
        (
            '<LogCategories><Category name="a b"/><Category name="a&#xD;b"/></LogCategories>',
            "name 'a b' is duplicated",
        ),
        (
            '<LogCategories><Category name="a b"/><Category name="a&#xA;b"/></LogCategories>',
            "name 'a b' is duplicated",
        ),
        (
            '<LogCategories>unexpected<Category name="x"/></LogCategories>',
            "LogCategories.*non-whitespace text",
        ),
        (
            '<LogCategories>&#xA0;<Category name="x"/></LogCategories>',
            "LogCategories.*non-whitespace text",
        ),
        (
            '<LogCategories><Category name="x">unexpected</Category></LogCategories>',
            "Category.*non-whitespace text",
        ),
        (
            '<LogCategories><Category name="x"/>unexpected'
            '<Category name="y"/></LogCategories>',
            "LogCategories.*non-whitespace text",
        ),
        (
            '<LogCategories><Category name="x"><Annotations>unexpected'
            '<Annotation type="valid"/></Annotations></Category></LogCategories>',
                "Annotations.*non-whitespace character data",
        ),
        (
            '<LogCategories><Category name="x"><Annotations>'
            '<Annotation type="valid"/>unexpected</Annotations></Category></LogCategories>',
                "Annotations.*non-whitespace character data",
        ),
        (
            '<LogCategories><Category name="x"><Annotations/></Category></LogCategories>',
            "must contain an Annotation",
        ),
        (
            '<LogCategories><Category name="x"><Annotations><Annotation/>'
            "</Annotations></Category></LogCategories>",
            "missing required attribute type",
        ),
        (
            '<LogCategories><Category name="x"><Unexpected/>'
            "</Category></LogCategories>",
            "contains unsupported child elements",
        ),
    ),
)
def test_fmi3_rejects_invalid_log_categories(
    tmp_path: Path,
    invalid_log_categories_xml: str,
    expected_error: str,
) -> None:
    """Reject malformed FMI 3 log-category structures and lexical duplicates.

    :param tmp_path: Isolated extracted-FMU directory provided by pytest.
    :param invalid_log_categories_xml: Invalid complete LogCategories section.
    :param expected_error: Stable validation error fragment.
    :return: None.
    """

    invalid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        '      <DefaultExperiment startTime="0" stepSize="0.001"/>',
        f"      {invalid_log_categories_xml}\n"
        '      <DefaultExperiment startTime="0" stepSize="0.001"/>',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-log-categories",
        invalid_xml,
    )

    with pytest.raises(ValueError, match=expected_error):
        read_fmu_model_description(fmu_path)


@pytest.mark.parametrize(
    ("valid_xml_fragment", "invalid_xml_fragment", "expected_error"),
    (
        ("<Float64 name=", "<Real name=", "outside the represented"),
        ('canHandleVariableCommunicationStepSize="false"',
         'canHandleVariableCommunicationStepSize="False"', "not a valid FMI boolean"),
        ('canHandleVariableCommunicationStepSize="false"',
         'canSerializeFMUState="true" '
         'canHandleVariableCommunicationStepSize="false"',
         "requires canGetAndSetFMUState=true"),
        ('valueReference="4"', 'valueReference="4294967296"', "exceeds unsigned 32-bit"),
        ('name="time"', 'name="speed"', "variable name 'speed' is duplicated"),
        ('valueReference="4"', 'valueReference="3"', "valueReference 3 is ambiguous"),
        ('fixedInternalStepSize="0.001"',
         'fixedInternalStepSize="0.001" needsCompletedIntegratorStep="true"',
         "attribute 'needsCompletedIntegratorStep'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="not-a-date"', "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime=""', "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2025-01-01 12:00:00Z"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2025-02-30T12:00:00Z"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2026-03-04T18:13:43.Z"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2026-03-04T18:13:43+14:01"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2026-03-04T18:13:43-14:01"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2026-03-04T18:13:43+15:00"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2026-03-04T18:13:43+00:60"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2026-03-04T18:13:43+1400"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2026-03-04T18:13:43z"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2026-03-04t18:13:43Z"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="-0001-03-04T18:13:43Z"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="10000-03-04T18:13:43Z"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="٢٠٢٦-٠٣-٠٤T١٨:١٣:٤٣Z"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="0000-03-04T18:13:43Z"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2026-03-04T24:00:00Z"',
         "attribute 'generationDateAndTime'"),
        ('generationTool="VeraGrid FMI composition container v0"',
         'generationTool="VeraGrid FMI composition container v0" '
         'generationDateAndTime="2026-03-04T18:13:60Z"',
         "attribute 'generationDateAndTime'"),
    ),
)
def test_fmi3_rejects_invalid_scalar_identity_and_lexical_values(
    tmp_path: Path,
    valid_xml_fragment: str,
    invalid_xml_fragment: str,
    expected_error: str,
) -> None:
    """Verify scalar types, booleans, names, and references fail closed.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param valid_xml_fragment: Exact valid fixture fragment to replace.
    :param invalid_xml_fragment: Invalid replacement fragment.
    :param expected_error: Stable validation error fragment.
    :return: None.
    """

    invalid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        valid_xml_fragment,
        invalid_xml_fragment,
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-scalar",
        invalid_xml,
    )
    with pytest.raises(ValueError, match=expected_error):
        read_fmu_model_description(fmu_path)


@pytest.mark.parametrize(
    ("variable_change", "expected_error"),
    (
        (' declaredType="DefinedFloat"/>', "unknown declaredType"),
        (' unit="rad"/>', "unknown unit"),
    ),
)
def test_fmi3_rejects_unknown_variable_metadata_references(
    tmp_path: Path,
    variable_change: str,
    expected_error: str,
) -> None:
    """Verify declared metadata references fail closed when their owners are absent.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param variable_change: Unsupported variable XML inserted into the fixture.
    :param expected_error: Stable validation error fragment.
    :return: None.
    """

    invalid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        '/>\n        <Float64 name="angle"',
        f'{variable_change}\n        <Float64 name="angle"',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "unrepresented-variable",
        invalid_xml,
    )
    with pytest.raises(ValueError, match=expected_error):
        read_fmu_model_description(fmu_path)


def test_fmi3_accepts_units_declared_types_bounds_and_dependencies(
    tmp_path: Path,
) -> None:
    """Accept validated optional metadata without changing runtime bindings.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    optional_metadata: str = """      <UnitDefinitions>
        <Unit name="rad">
          <BaseUnit rad="1"/>
          <DisplayUnit name="deg" factor="57.29577951308232"/>
        </Unit>
      </UnitDefinitions>
      <TypeDefinitions>
        <Float64Type name="Angle" unit="rad" displayUnit="deg"
            min="-3.2" max="3.2" nominal="1"/>
      </TypeDefinitions>
"""
    valid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        "      <DefaultExperiment",
        optional_metadata + "      <DefaultExperiment",
        1,
    ).replace(
        'name="speed" valueReference="0" causality="output"',
        'name="speed" valueReference="0" causality="output" declaredType="Angle"',
        1,
    ).replace(
        '<Output valueReference="0"/>',
        '<Output valueReference="0" dependencies="4" dependenciesKind="constant"/>',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "valid-optional-metadata", valid_xml
    )

    metadata: FmuModelDescription = read_fmu_model_description(fmu_path)

    assert metadata.variables[0].name == "speed"
    assert metadata.variables[0].variable_type == FmuVariableType.FLOAT64


@pytest.mark.parametrize(
    ("output_change", "expected_error"),
    (
        ('dependencies="999"', "unknown valueReference 999"),
        ('dependencies="4 4"', "duplicate dependency"),
        ('dependencies="4" dependenciesKind="constant fixed"',
         "dependenciesKind count"),
        ('dependencies="4" dependenciesKind="arbitrary"', "dependency kind"),
        ('dependenciesKind="constant"', "requires dependencies"),
    ),
)
def test_fmi3_rejects_invalid_model_structure_dependencies(
    tmp_path: Path,
    output_change: str,
    expected_error: str,
) -> None:
    """Reject unresolved, duplicate, unaligned, or non-normative dependencies.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param output_change: Dependency attributes inserted on the first output.
    :param expected_error: Stable validation error fragment.
    :return: None.
    """

    invalid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        '<Output valueReference="0"/>',
        f'<Output valueReference="0" {output_change}/>',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-dependencies", invalid_xml
    )

    with pytest.raises(ValueError, match=expected_error):
        read_fmu_model_description(fmu_path)


@pytest.mark.parametrize(
    ("attribute_text", "expected_error"),
    (
        ('min="2" max="1"', "min.*must not exceed max"),
        ('nominal="0"', "nominal.*must be positive"),
        ('nominal="NaN"', "nominal.*must be finite"),
    ),
)
def test_fmi3_rejects_invalid_float_bounds(
    tmp_path: Path,
    attribute_text: str,
    expected_error: str,
) -> None:
    """Reject inconsistent or non-finite floating-point metadata.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param attribute_text: Invalid Float64 metadata inserted into the fixture.
    :param expected_error: Stable validation error fragment.
    :return: None.
    """

    invalid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        'name="speed" valueReference="0" causality="output"',
        f'name="speed" valueReference="0" causality="output" {attribute_text}',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-float-bounds", invalid_xml
    )

    with pytest.raises(ValueError, match=expected_error):
        read_fmu_model_description(fmu_path)


@pytest.mark.parametrize(
    ("metadata_section", "speed_variable", "expected_error"),
    (
        (
            '<UnitDefinitions><Unit name="rad"><BaseUnit rad="1"/></Unit>'
            '<Unit name="rad"><BaseUnit rad="1"/></Unit></UnitDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "unit 'rad' is duplicated",
        ),
        (
            '<UnitDefinitions><Unit name="rad"><BaseUnit rad="1"/>'
            '<DisplayUnit name="deg"/></Unit></UnitDefinitions>'
            '<TypeDefinitions><Float64Type name="Angle" unit="rad" '
            'displayUnit="grad"/></TypeDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "references invalid display unit",
        ),
        (
            '<UnitDefinitions><Unit name="rad"><BaseUnit rad="1" factor="NaN"/>'
            '</Unit></UnitDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "factor.*must be finite",
        ),
        (
            '<TypeDefinitions><Int32Type name="Count"/></TypeDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated" declaredType="Count"/>',
            "declaredType is incompatible",
        ),
        (
            '<TypeDefinitions><Int32Type name="Count" '
            'max="2147483648"/></TypeDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "exceeds its primitive range",
        ),
        (
            "",
            '<Boolean name="speed" valueReference="0" causality="input" '
            'variability="discrete" start="maybe"/>',
            "attribute start.*is not a valid FMI boolean",
        ),
        (
            "",
            '<Binary name="speed" valueReference="0" causality="input" '
            'variability="discrete"><Start value="0G"/></Binary>',
            "invalid hex start",
        ),
        (
            '<TypeDefinitions><EnumerationType name="Mode">'
            '<Item name="off" value="1"/><Item name="on" value="1"/>'
            '</EnumerationType></TypeDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "duplicate item",
        ),
        (
            '<TypeDefinitions><Float32Type name="Gain" '
            'max="3.5e38"/></TypeDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "exceeds Float32 range",
        ),
        (
            '<UnitDefinitions>unexpected<Unit name="rad"><BaseUnit rad="1"/>'
            '</Unit></UnitDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "UnitDefinitions.*non-whitespace character data",
        ),
        (
            '<TypeDefinitions><Float64Type name="Gain"/>unexpected'
            '</TypeDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "TypeDefinitions.*non-whitespace character data",
        ),
        (
            '<UnitDefinitions><Unit name="rad"><Annotations>unexpected'
            '<Annotation type="vendor"/></Annotations></Unit></UnitDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "Annotations for FMI 3 Unit 'rad'.*non-whitespace character data",
        ),
        (
            '<UnitDefinitions><Unit name="rad"><Annotations>'
            '<Annotation type="vendor"/>unexpected</Annotations></Unit>'
            '</UnitDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "Annotations for FMI 3 Unit 'rad'.*non-whitespace character data",
        ),
        (
            '<TypeDefinitions><Float64Type name="Gain"><Annotations>unexpected'
            '<Annotation type="vendor"/></Annotations></Float64Type>'
            '</TypeDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "Annotations for FMI 3 declared type 'Gain'.*non-whitespace character data",
        ),
        (
            '<TypeDefinitions><Float64Type name="Gain"><Annotations>'
            '<Annotation type="vendor"/>unexpected</Annotations></Float64Type>'
            '</TypeDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "Annotations for FMI 3 declared type 'Gain'.*non-whitespace character data",
        ),
        (
            '<TypeDefinitions><RealType name="Legacy"/></TypeDefinitions>',
            '<Float64 name="speed" valueReference="0" causality="output" '
            'variability="continuous" initial="calculated"/>',
            "Unknown FMI 3 type definition",
        ),
    ),
)
def test_fmi3_rejects_invalid_unit_and_type_metadata(
    tmp_path: Path,
    metadata_section: str,
    speed_variable: str,
    expected_error: str,
) -> None:
    """Reject malformed units, declared types, ranges, and scalar starts.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param metadata_section: Optional unit or type metadata inserted in schema order.
    :param speed_variable: Replacement for the fixture's first scalar variable.
    :param expected_error: Stable validation error fragment.
    :return: None.
    """

    original_speed_variable: str = (
        '<Float64 name="speed" valueReference="0" causality="output"\n'
        '            variability="continuous" initial="calculated"/>'
    )
    invalid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        "      <DefaultExperiment",
        f"      {metadata_section}\n      <DefaultExperiment",
        1,
    ).replace(
        original_speed_variable,
        speed_variable,
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-unit-or-type-metadata",
        invalid_xml,
    )

    with pytest.raises(ValueError, match=expected_error):
        read_fmu_model_description(fmu_path)


@pytest.mark.parametrize(
    ("valid_xml_fragment", "invalid_xml_fragment", "expected_error"),
    (
        ('causality="independent"', 'causality="output"', "exactly one independent"),
        ('variability="continuous" initial="calculated"',
         'variability="fixed" initial="calculated"', "invalid causality"),
        ('causality="output"\n            variability="continuous" initial="calculated"',
         'causality="input"\n            variability="continuous" initial="exact"',
         "requires a start value"),
        ('initial="calculated"/>', 'initial="calculated" start="1"/>',
         "cannot declare a start value"),
    ),
)
def test_fmi3_rejects_invalid_variable_semantics(
    tmp_path: Path,
    valid_xml_fragment: str,
    invalid_xml_fragment: str,
    expected_error: str,
) -> None:
    """Verify FMI 3 causality, variability, initial, and start rules.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param valid_xml_fragment: Exact valid fixture fragment to replace.
    :param invalid_xml_fragment: Semantically invalid replacement.
    :param expected_error: Stable validation error fragment.
    :return: None.
    """

    invalid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        valid_xml_fragment,
        invalid_xml_fragment,
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-semantics",
        invalid_xml,
    )
    with pytest.raises(ValueError, match=expected_error):
        read_fmu_model_description(fmu_path)


@pytest.mark.parametrize(
    ("valid_xml_fragment", "invalid_xml_fragment", "expected_error"),
    (
        ('        <Output valueReference="3"/>\n', "", "outputs do not match"),
        ('<Output valueReference="0"/>', '<Output valueReference="4"/>', "output causality"),
        ('<Output valueReference="0"/>',
         '<Output valueReference="0"/><Output valueReference="0"/>', "duplicates"),
        ('        <InitialUnknown valueReference="3"/>\n', "", "initial unknowns do not match"),
    ),
)
def test_fmi3_rejects_inconsistent_model_structure(
    tmp_path: Path,
    valid_xml_fragment: str,
    invalid_xml_fragment: str,
    expected_error: str,
) -> None:
    """Verify ModelStructure order, uniqueness, and semantic sets.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :param valid_xml_fragment: Exact valid fixture fragment to replace.
    :param invalid_xml_fragment: Inconsistent replacement fragment.
    :param expected_error: Stable validation error fragment.
    :return: None.
    """

    invalid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        valid_xml_fragment,
        invalid_xml_fragment,
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-model-structure",
        invalid_xml,
    )
    with pytest.raises(ValueError, match=expected_error):
        read_fmu_model_description(fmu_path)


def test_fmi3_rejects_scheduled_execution_metadata(tmp_path: Path) -> None:
    """Verify Scheduled Execution is rejected until clocks and partitions are represented.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    scheduled_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        '<CoSimulation\n          modelIdentifier="VeraGridPhysicalCompositionContainerPFTimeLatticeV41"\n'
        '          canHandleVariableCommunicationStepSize="false"\n'
        '          fixedInternalStepSize="0.001"/>',
        '<ScheduledExecution modelIdentifier="scheduled"/>',
        1,
    )
    scheduled_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "scheduled-execution",
        scheduled_xml,
    )
    with pytest.raises(ValueError, match="ScheduledExecution is outside"):
        read_fmu_model_description(scheduled_path)


def test_fmi3_external_tool_requirement_cannot_bypass_execution_gate(
    tmp_path: Path,
) -> None:
    """Verify valid tool-dependent metadata cannot reach an FMI 3 runtime.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    external_tool_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        'canHandleVariableCommunicationStepSize="false"',
        'needsExecutionTool="true" canHandleVariableCommunicationStepSize="false"',
        1,
    )
    external_tool_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "external-tool",
        external_tool_xml,
    )
    metadata: FmuModelDescription = read_fmu_model_description(external_tool_path)
    config: FmuImportConfig = FmuImportConfig(fmu_path=external_tool_path)
    assert (
        config.resolve_execution_mode(metadata)
        == FmuInterfaceMode.CO_SIMULATION
    )
    with pytest.raises(RuntimeError, match="external execution tool"):
        validate_fmi_three_co_simulation_worker_profile(
            metadata=metadata,
            preferred_mode=config.preferred_mode,
        )


def test_fmi3_validates_fixed_internal_step_size(tmp_path: Path) -> None:
    """Verify the fixture Co-Simulation fixed step is finite and positive.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    invalid_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        'fixedInternalStepSize="0.001"',
        'fixedInternalStepSize="NaN"',
        1,
    )
    fmu_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "invalid-fixed-step",
        invalid_xml,
    )
    with pytest.raises(ValueError, match="must be finite and positive"):
        read_fmu_model_description(fmu_path)


def test_fmi3_allows_vendor_namespace_below_valid_annotation(tmp_path: Path) -> None:
    """Verify vendor namespaces remain inside the FMI annotation extension point.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    annotation_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        "    </fmiModelDescription>",
        '      <Annotations><Annotation type="urn:vendor:metadata">'
        '<vendor:data xmlns:vendor="urn:vendor"/>'
        "</Annotation></Annotations>\n    </fmiModelDescription>",
        1,
    )
    annotation_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "vendor-annotation",
        annotation_xml,
    )
    metadata: FmuModelDescription = read_fmu_model_description(annotation_path)
    assert metadata.model_name == "VeraGridPhysicalCompositionContainerPFTimeLatticeV41"


def test_fmi3_rejects_namespaced_root(tmp_path: Path) -> None:
    """Verify the FMI root cannot be moved into an XML namespace.

    :param tmp_path: Isolated fixture directory provided by pytest.
    :return: None.
    """

    namespaced_root_xml: str = _scalar_fmi3_worker_profile_fixture_xml().replace(
        "<fmiModelDescription ",
        '<fmiModelDescription xmlns="urn:not-fmi" ',
        1,
    )
    namespaced_root_path: Path = _write_extracted_fmi3_model_description(
        tmp_path / "namespaced-root",
        namespaced_root_xml,
    )
    with pytest.raises(ValueError, match="XML namespaces are not accepted"):
        read_fmu_model_description(namespaced_root_path)
