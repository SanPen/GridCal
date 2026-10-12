# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
from VeraGridEngine.enumerations import DynamicTemplateCategory, VarPowerFlowReferenceType


def block_declares_physical_device_contract(block: Block) -> bool:
    """Return whether a template root declares a physical network boundary.

    A physical template must be bindable to one network object. Native and
    GUI-authored and imported templates express that through canonical
    power-flow references. Persisted legacy terminal metadata does not define
    runtime device identity.

    :param block: Reusable template root block.
    :return: Whether the block can represent one complete physical device.
    """
    if len(block.external_mapping) > 0:
        return True
    else:
        pass

    interface_var: Var
    interface_var_reference: VarPowerFlowReferenceType | None
    for interface_var in block.in_vars:
        interface_var_reference = interface_var.ref
        if (
                interface_var_reference is not None
                and interface_var_reference is not VarPowerFlowReferenceType.NOTHING
        ):
            return True
        else:
            pass
    for interface_var in block.out_vars:
        interface_var_reference = interface_var.ref
        if (
                interface_var_reference is not None
                and interface_var_reference is not VarPowerFlowReferenceType.NOTHING
        ):
            return True
        else:
            pass
    return False


def classify_dynamic_template_block(block: Block) -> DynamicTemplateCategory:
    """Classify a reusable model from its canonical typed contracts.

    Physical-device identity takes precedence because a complete imported
    device may also own local measurement children. A standalone measurement
    is recognized through its immutable physical-measurement point. Every
    remaining template is an internal control or computational component.

    :param block: Reusable template root block.
    :return: Typed template category.
    """
    if block_declares_physical_device_contract(block=block):
        return DynamicTemplateCategory.DEVICE
    else:
        pass

    if block_declares_physical_measurement_contract(block=block):
        return DynamicTemplateCategory.MEASUREMENT
    else:
        pass
    return DynamicTemplateCategory.COMPONENT


def block_declares_physical_measurement_contract(block: Block) -> bool:
    """Return whether a block tree contains a physical measurement contract.

    The walk examines the canonical tree directly so classification does not
    allocate a flattened block collection. It stops at the first declared
    measurement point because one point is sufficient to classify the reusable
    template as a measurement.

    :param block: Reusable template root or child block.
    :return: Whether the block tree declares a physical measurement point.
    """
    # Check the current node before descending so shallow contracts finish in
    # constant work and do not inspect unrelated control descendants.
    if block.dynamic_model_contract.rms_physical_measurement_point is not None:
        return True
    else:
        pass

    # Walk existing children without constructing Blocks, Vars, or an
    # intermediate flattened representation of the model tree.
    child_block: Block
    for child_block in block.children:
        if block_declares_physical_measurement_contract(block=child_block):
            return True
        else:
            pass
    return False


def block_declares_closed_measurement_station_contract(block: Block) -> bool:
    """Return whether a composite block is fully bound by native RMS meters.

    A measurement station is a structural owner for physical meter contracts,
    not an ordinary wire-connected computational block.  Its declared inputs
    are the physical quantities consumed by child meter equations, while its
    outputs are exactly the signals produced by those children.  Verifying
    both boundaries keeps connectivity validation strict without inventing
    external diagram wires for an internally closed measurement composition.

    :param block: Candidate composite measurement station.
    :return: Whether every declared boundary variable is bound internally.
    """
    if block.dynamic_model_contract.rms_physical_measurement_point is None:
        pass
    else:
        return False
    if len(block.children) > 0:
        pass
    else:
        return False

    # Collect the exact child contracts and equation dependencies.  A mixed
    # control/measurement composite remains an ordinary connectable block.
    consumed_var_uids: set[int] = set()
    child_owned_var_uids: set[int] = set()
    produced_var_uids: set[int] = set()
    child_block: Block
    for child_block in block.children:
        if child_block.dynamic_model_contract.rms_physical_measurement_point is not None:
            pass
        else:
            return False

        child_equation: Expr
        for child_equation in child_block.algebraic_eqs:
            equation_var: Var
            for equation_var in child_equation.get_vars():
                consumed_var_uids.add(equation_var.uid)
        child_owned_var: Var
        for child_owned_var in child_block.state_vars:
            child_owned_var_uids.add(child_owned_var.uid)
        for child_owned_var in child_block.algebraic_vars:
            child_owned_var_uids.add(child_owned_var.uid)
        for child_owned_var in child_block.diff_vars:
            child_owned_var_uids.add(child_owned_var.uid)
        for child_owned_var in child_block.parameters.keys():
            child_owned_var_uids.add(child_owned_var.uid)
        child_output_var: Var
        for child_output_var in child_block.out_vars:
            child_owned_var_uids.add(child_output_var.uid)
            produced_var_uids.add(child_output_var.uid)

    # The complete external dependency set must equal the station requirements.
    # This rejects both unused options and hidden physical inputs.
    external_dependency_uids: set[int] = consumed_var_uids.difference(
        child_owned_var_uids
    )
    station_input_uids: set[int] = set()
    station_input_var: Var
    for station_input_var in block.in_vars:
        station_input_uids.add(station_input_var.uid)

    station_output_uids: set[int] = set()
    station_output_var: Var
    for station_output_var in block.out_vars:
        station_output_uids.add(station_output_var.uid)
    return (
            len(block.in_vars) > 0
            and station_input_uids == external_dependency_uids
            and station_output_uids == produced_var_uids
    )
