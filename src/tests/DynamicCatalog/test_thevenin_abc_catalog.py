# SPDX-License-Identifier: MPL-2.0
"""Exercise actual source library and structural-property recovery owners."""

import pytest

from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_library import (
    LibraryDeviceTemplateSpec, build_dynamic_library_device_template, get_dynamic_library_device_specs,
)
from VeraGrid.Gui.DynamicModelEditor.Editor.DynamicLibrary.dynamic_editor_utilities import (
    create_default_template_builder, get_blocktype2template_builder_dict, initialize_template_builder_from_block,
)
from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import TheveninSourceEmtTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import BlockType, DynamicSimulationMode, TheveninSourceVoltageMode


def test_thevenin_library_uses_registered_builder() -> None:
    """Library creation uses the canonical configurable source builder.

    :return: None.
    """
    assert get_blocktype2template_builder_dict()[BlockType.EMT_THEVENIN] is TheveninSourceEmtTemplate
    spec: LibraryDeviceTemplateSpec
    matches: tuple[LibraryDeviceTemplateSpec, ...] = tuple(
        spec for spec in get_dynamic_library_device_specs(DynamicSimulationMode.EMT)
        if spec.source == BlockType.EMT_THEVENIN)
    assert len(matches) == 1
    template: object = build_dynamic_library_device_template(matches[0], VarFactory())
    assert isinstance(template, EmtModelTemplate)
    builder: object = create_default_template_builder(VarFactory(), BlockType.EMT_THEVENIN, "Source")
    assert isinstance(builder, TheveninSourceEmtTemplate)
    assert builder.get_value("source_voltage_mode") == TheveninSourceVoltageMode.Balanced
    assert "grounded" in matches[0].description.lower()


@pytest.mark.parametrize("mode", (TheveninSourceVoltageMode.Balanced, TheveninSourceVoltageMode.Phase))
def test_thevenin_properties_recover_selected_mode(mode: TheveninSourceVoltageMode) -> None:
    """Real structural properties recover the saved mode and rebuild its contract.

    :param mode: Source capability selected in the existing property owner.
    :return: None.
    """
    builder: TheveninSourceEmtTemplate = TheveninSourceEmtTemplate(VarFactory())
    builder.params_dict["source_voltage_mode"].value = mode
    original: Block = builder.eval().block
    restored: Block = Block.parse(original.to_dict())
    recovered: TheveninSourceEmtTemplate = TheveninSourceEmtTemplate(VarFactory())
    initialize_template_builder_from_block(recovered, restored, BlockType.EMT_THEVENIN)
    assert recovered.get_value("source_voltage_mode") == mode
    rebuilt: Block = recovered.eval().block
    child: Block
    variable: Var
    expression: Expr
    marker: tuple[Const, ...] = tuple(expression for child in rebuilt.get_all_blocks()
        for variable, expression in child.parameters.items() if variable.name == "source_voltage_mode")
    assert len(marker) == 1
    assert marker[0].value == (0.0 if mode == TheveninSourceVoltageMode.Balanced else 1.0)


@pytest.mark.parametrize("marker_value", (None, 7.0))
def test_thevenin_legacy_properties_default_to_balanced(marker_value: float | None) -> None:
    """Missing legacy markers default to balanced; invalid known markers fail.

    :param marker_value: Missing marker or explicitly malformed structural value.
    :return: None.
    """
    original: Block = TheveninSourceEmtTemplate(VarFactory()).eval().block
    child: Block
    for child in original.get_all_blocks():
        variable: Var
        expression: Expr
        for variable, expression in tuple(child.parameters.items()):
            if variable.name == "source_voltage_mode":
                # Legacy models predate the optional source-capability declaration.
                child.dynamic_model_contract.emt_finite_reciprocal_source_mode_var_uid = None
                if marker_value is None:
                    del child.parameters[variable]
                else:
                    child.parameters[variable] = Const(marker_value)
            else:
                pass
    before: dict[str, object] = original.to_dict()
    recovered: TheveninSourceEmtTemplate = TheveninSourceEmtTemplate(VarFactory())
    if marker_value is None:
        initialize_template_builder_from_block(recovered, original, BlockType.EMT_THEVENIN)
        assert recovered.get_value("source_voltage_mode") == TheveninSourceVoltageMode.Balanced
    else:
        with pytest.raises(ValueError, match="mode marker"):
            initialize_template_builder_from_block(recovered, original, BlockType.EMT_THEVENIN)
    assert original.to_dict() == before
