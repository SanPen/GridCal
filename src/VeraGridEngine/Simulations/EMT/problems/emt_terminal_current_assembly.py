# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""Assemble canonical EMT current mappings into topology-owned KCL balances."""

from typing import Dict, List, Tuple

from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var


_BUS_AC_CURRENT_REFERENCES = (
    VarPowerFlowReferenceType.i_N,
    VarPowerFlowReferenceType.i_A,
    VarPowerFlowReferenceType.i_B,
    VarPowerFlowReferenceType.i_C,
)
_FROM_AC_CURRENT_REFERENCES = (
    VarPowerFlowReferenceType.if_N,
    VarPowerFlowReferenceType.if_A,
    VarPowerFlowReferenceType.if_B,
    VarPowerFlowReferenceType.if_C,
)
_TO_AC_CURRENT_REFERENCES = (
    VarPowerFlowReferenceType.it_N,
    VarPowerFlowReferenceType.it_A,
    VarPowerFlowReferenceType.it_B,
    VarPowerFlowReferenceType.it_C,
)


def assemble_emt_mapped_current_references(
        model: Block,
        current_balance: Dict[int, List[Expr | Var | Const]],
        bus_from_index: int | None = None,
        bus_to_index: int | None = None,
        bus_from_is_dc: bool | None = None,
        bus_to_is_dc: bool | None = None,
        bus_index: int | None = None,
        bus_is_dc: bool | None = None,
) -> bool:
    """Assemble mapped currents using topology supplied by the static device."""
    mapping = model.external_mapping
    mapped = {
        reference: model.E(reference)
        for reference in mapping
        if isinstance(model.E(reference), Var)
    }

    bus_references = (VarPowerFlowReferenceType.Idc,) + _BUS_AC_CURRENT_REFERENCES
    from_references = (VarPowerFlowReferenceType.If_dc,) + _FROM_AC_CURRENT_REFERENCES
    to_references = (VarPowerFlowReferenceType.It_dc,) + _TO_AC_CURRENT_REFERENCES
    has_bus_mapping = any(reference in mapped for reference in bus_references)
    has_branch_mapping = any(
        reference in mapped for reference in from_references + to_references
    )
    terminal_specs: List[
        Tuple[int, bool, float, Tuple[VarPowerFlowReferenceType, ...]]
    ]
    if bus_index is not None and has_bus_mapping:
        if bus_index is None or bus_is_dc is None:
            raise ValueError("EMT bus terminal lacks one-terminal topology")
        else:
            pass
        terminal_specs = [(bus_index, bus_is_dc, 1.0, bus_references)]
    elif bus_from_index is not None and bus_to_index is not None and has_branch_mapping:
        has_from_mapping = any(reference in mapped for reference in from_references)
        has_to_mapping = any(reference in mapped for reference in to_references)
        if has_from_mapping and (bus_from_index is None or bus_from_is_dc is None):
            raise ValueError("EMT from terminal lacks branch topology")
        else:
            pass
        if has_to_mapping and (bus_to_index is None or bus_to_is_dc is None):
            raise ValueError("EMT to terminal lacks branch topology")
        else:
            pass
        terminal_specs = list()
        if has_from_mapping:
            terminal_specs.append((bus_from_index, bus_from_is_dc, -1.0, from_references))
        else:
            pass
        if has_to_mapping:
            terminal_specs.append((bus_to_index, bus_to_is_dc, -1.0, to_references))
        else:
            pass
    else:
        if has_bus_mapping or has_branch_mapping:
            raise ValueError("EMT current mappings lack matching device topology")
        return False

    resolved: List[Tuple[int, int, float, Var]] = list()
    for terminal_bus_index, terminal_is_dc, sign, references in terminal_specs:
        dc_reference = references[0]
        ac_references = references[1:]
        if terminal_is_dc:
            if any(reference in mapped for reference in ac_references):
                raise ValueError(
                    "EMT terminal conductor does not match the connected bus domain"
                )
            selected_references = (dc_reference,)
        else:
            if dc_reference in mapped:
                raise ValueError(
                    "EMT terminal conductor does not match the connected bus domain"
                )
            selected_references = ac_references
        for phase_index, reference in enumerate(selected_references):
            if reference in mapped:
                if phase_index >= len(current_balance[terminal_bus_index]):
                    raise ValueError("EMT terminal conductor is absent from the bus shell")
                else:
                    pass
                resolved.append((terminal_bus_index, phase_index, sign, mapped[reference]))

    for target_bus_index, phase_index, sign, current in resolved:
        current_balance[target_bus_index][phase_index] = (
            current_balance[target_bus_index][phase_index] + sign * current
        )
    return len(resolved) > 0
