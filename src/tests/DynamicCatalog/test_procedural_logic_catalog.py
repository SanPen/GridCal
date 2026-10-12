"""Contract tests for native standalone procedural-logic templates."""

from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import ProceduralLogicType
from VeraGridEngine.Templates.ProceduralLogicCatalog import (
    ProceduralBlockTemplateDescriptor,
    build_procedural_block_catalog_template,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_library import (
    get_dynamic_library_procedural_descriptors,
)
from VeraGridEngine.Utils.procedural_logic import ProceduralLogicBase
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var


def _collect_block_variables(block: Block) -> list[Var]:
    """Collect the symbolic surface allocated directly by one catalogue block.

    :param block: Materialized standalone procedural block.
    :return: Ordered variables from ports, equations and runtime dictionaries.
    """
    variables: list[Var] = list()
    variables.extend(block.in_vars)
    variables.extend(block.out_vars)
    variables.extend(block.algebraic_vars)
    variables.extend(list(block.event_dict.keys()))
    variables.extend(list(block.mode_dict.keys()))
    return variables


def test_procedural_catalog_covers_every_concrete_engine_type_once() -> None:
    """Every concrete Engine behavior must have exactly one draggable descriptor.

    :return: None.
    """
    descriptors: list[ProceduralBlockTemplateDescriptor] = list(
        get_dynamic_library_procedural_descriptors()
    )
    descriptor_types: list[ProceduralLogicType] = list(
        descriptor.logic_tpe for descriptor in descriptors
    )
    expected_types: list[ProceduralLogicType] = list(
        logic_tpe
        for logic_tpe in ProceduralLogicType
        if logic_tpe not in (
            ProceduralLogicType.Base,
            ProceduralLogicType.ManufacturerNativeController,
        )
    )

    assert len(descriptor_types) == len(set(descriptor_types))
    assert set(descriptor_types) == set(expected_types)


def test_procedural_catalog_materializes_declared_ports_and_behavior() -> None:
    """Each descriptor must build one block with its exact procedural type.

    :return: None.
    """
    descriptor: ProceduralBlockTemplateDescriptor
    for descriptor in get_dynamic_library_procedural_descriptors():
        template: EmtModelTemplate = build_procedural_block_catalog_template(
            descriptor=descriptor,
            var_factory=VarFactory(),
        )
        block: Block = template.block

        assert len(block.in_vars) == len(descriptor.input_names)
        assert len(block.out_vars) == len(descriptor.output_names)
        assert len(block.algebraic_vars) == len(descriptor.output_names)
        assert len(block.algebraic_eqs) == len(descriptor.output_names)
        assert len(block.event_dict) == len(descriptor.parameter_specs)
        assert len(block.mode_dict) == len(descriptor.output_names)
        assert len(block.procedural_logic) == 1
        assert isinstance(block.procedural_logic[0], ProceduralLogicBase)
        assert block.procedural_logic[0].logic_tpe == descriptor.logic_tpe


def test_procedural_catalog_allocates_fresh_symbolic_identities() -> None:
    """Repeated materialization must never share mutable symbolic variables.

    :return: None.
    """
    var_factory: VarFactory = VarFactory()
    descriptor: ProceduralBlockTemplateDescriptor = list(
        get_dynamic_library_procedural_descriptors()
    )[0]
    first_template: EmtModelTemplate = build_procedural_block_catalog_template(
        descriptor=descriptor,
        var_factory=var_factory,
    )
    second_template: EmtModelTemplate = build_procedural_block_catalog_template(
        descriptor=descriptor,
        var_factory=var_factory,
    )
    first_uids: set[int] = set(
        variable.non_mutable_uid for variable in _collect_block_variables(first_template.block)
    )
    second_uids: set[int] = set(
        variable.non_mutable_uid for variable in _collect_block_variables(second_template.block)
    )

    assert first_uids.isdisjoint(second_uids)
