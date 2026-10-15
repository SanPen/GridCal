from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmvsc_runtime_adapter import (
    build_dgs_elmvscmono_rms_runtime_template,
    is_dgs_elmvsc_slot_contract,
    is_dgs_elmvscmono_slot_contract,
)
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var


def test_elmvsc_slot_contract_accepts_complete_converter_boundary() -> None:
    """Recognize a complete PowerFactory MMC converter slot."""

    block: Block = Block(
        in_vars=[Var(name="Pmr"), Var(name="Pmi"), Var(name="mdc")],
        out_vars=[Var(name="idc"), Var(name="Ucap")],
    )

    assert is_dgs_elmvsc_slot_contract(block=block)


def test_elmvsc_slot_contract_rejects_incomplete_converter_boundary() -> None:
    """Reject an MMC converter slot without its DC modulation input."""

    block: Block = Block(
        in_vars=[Var(name="Pmr"), Var(name="Pmi")],
        out_vars=[Var(name="idc"), Var(name="Ucap")],
    )

    assert not is_dgs_elmvsc_slot_contract(block=block)


def test_elmvsc_slot_contract_does_not_search_unrelated_children() -> None:
    """Require the isolated equipment boundary instead of recursive names.

    :return: None.
    """
    unrelated_child: Block = Block(
        in_vars=[Var(name="Pmr"), Var(name="Pmi"), Var(name="mdc")],
        out_vars=[Var(name="idc"), Var(name="Ucap")],
    )
    composite_root: Block = Block(children=[unrelated_child])

    assert not is_dgs_elmvsc_slot_contract(block=composite_root)


def test_elmvscmono_slot_contract_accepts_complete_bridge_boundary() -> None:
    """Recognize a complete PowerFactory monopolar converter slot."""

    block: Block = Block(
        in_vars=[
            Var(name="Pmd"),
            Var(name="Pmq"),
            Var(name="cosref"),
            Var(name="sinref"),
        ],
        out_vars=[Var(name="id"), Var(name="iq"), Var(name="uDC")],
    )

    assert is_dgs_elmvscmono_slot_contract(block=block)


def test_elmvscmono_slot_contract_rejects_incomplete_bridge_boundary() -> None:
    """Reject a monopolar converter slot without its sine reference."""

    block: Block = Block(
        in_vars=[Var(name="Pmd"), Var(name="Pmq"), Var(name="cosref")],
        out_vars=[Var(name="id"), Var(name="iq"), Var(name="uDC")],
    )

    assert not is_dgs_elmvscmono_slot_contract(block=block)


def test_elmvscmono_runtime_exposes_physical_equipment_as_child() -> None:
    """Keep physical bridge equations on one visible controller sibling.

    :return: None.
    """
    pmd: Var = Var(name="Pmd")
    pmq: Var = Var(name="Pmq")
    cosref: Var = Var(name="cosref")
    sinref: Var = Var(name="sinref")
    current_d: Var = Var(name="id")
    current_q: Var = Var(name="iq")
    dc_voltage: Var = Var(name="uDC")
    controller_child: Block = Block(
        name="Inner controller",
        in_vars=list((
            cosref,
            sinref,
            current_d,
            current_q,
            dc_voltage,
        )),
        out_vars=list((pmd, pmq)),
        algebraic_vars=list((pmd, pmq)),
    )
    control_block: Block = Block(
        name="Imported controller",
        children=list((controller_child,)),
        out_vars=list((current_d, current_q, dc_voltage)),
    )
    control_template: RmsModelTemplate = RmsModelTemplate(
        name="Imported VSC",
    )
    control_template.block = control_block

    runtime_template: RmsModelTemplate | None = (
        build_dgs_elmvscmono_rms_runtime_template(
            control_template=control_template,
            clone_control_block=False,
        )
    )

    assert runtime_template is not None
    runtime_root: Block = runtime_template.block
    assert len(runtime_root.algebraic_vars) == 0
    assert len(runtime_root.algebraic_eqs) == 0
    assert len(runtime_root.children) == 1

    imported_control_block: Block = runtime_root.children[0]
    assert len(imported_control_block.children) == 2
    assert imported_control_block.children[0] is controller_child
    equipment_block: Block = imported_control_block.children[1]
    assert equipment_block.name == "VSC Converter"
    assert len(equipment_block.algebraic_vars) == 9
    assert len(equipment_block.algebraic_eqs) == 9
    assert set(output_var.name for output_var in equipment_block.out_vars) == set((
        "id",
        "iq",
        "uDC",
        "Pdc",
        "Pac",
        "Qac",
    ))
    assert set(
        algebraic_var.name for algebraic_var in equipment_block.algebraic_vars
    ) == set((
        "id",
        "iq",
        "uDC",
        "Pdc",
        "Pdc_conversion",
        "Pac",
        "Qac",
        "Iac",
        "Idc_network",
    ))

    control_input_names: set[str] = set(
        input_var.name for input_var in imported_control_block.in_vars
    )
    assert set((
        "Vdc_monopolar",
        "Vac_magnitude",
        "Vac_angle",
        "cosref",
        "sinref",
    )).issubset(control_input_names)
    assert "Pmd" not in control_input_names
    assert "Pmq" not in control_input_names
    assert "id" not in control_input_names
    assert "iq" not in control_input_names
    assert "uDC" not in control_input_names

    expected_boundary_output_names: set[str] = {"Pdc", "Pac", "Qac"}
    assert set(
        output_var.name for output_var in imported_control_block.out_vars
    ) == expected_boundary_output_names
    assert set(
        output_var.name for output_var in runtime_root.out_vars
    ) == expected_boundary_output_names

    equipment_output_uid_by_name: dict[str, int] = dict(
        (output_var.name, output_var.uid)
        for output_var in equipment_block.out_vars
    )
    controller_input_uid_by_name: dict[str, int] = dict(
        (input_var.name, input_var.uid)
        for input_var in controller_child.in_vars
    )
    assert equipment_output_uid_by_name["id"] == controller_input_uid_by_name["id"]
    assert equipment_output_uid_by_name["iq"] == controller_input_uid_by_name["iq"]
    assert equipment_output_uid_by_name["uDC"] == controller_input_uid_by_name["uDC"]
