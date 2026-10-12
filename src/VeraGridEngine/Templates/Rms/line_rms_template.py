# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List
import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import DeviceType, ParamPowerFlowReferenceType, VarPowerFlowReferenceType
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var, cos, sin
from VeraGridEngine.Utils.Symbolic.block import Block
import VeraGridEngine.Utils.Symbolic.symbolic as sym


def get_line_rms_template(vfactory: VarFactory, name="Line_rms_template") -> RmsModelTemplate:
    """
    Get the RMS template model of the Line
    :return: RmsModelTemplate
    """
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.LineDevice
    templ.name = name

    inputs: List[Var] = [vfactory.add_var("Vmf", reference=VarPowerFlowReferenceType.Vmf),
                         vfactory.add_var("Vaf", reference=VarPowerFlowReferenceType.Vaf),
                         vfactory.add_var("Vmt", reference=VarPowerFlowReferenceType.Vmt),
                         vfactory.add_var("Vat", reference=VarPowerFlowReferenceType.Vat), ]

    Qf = vfactory.add_var("Qf", reference=VarPowerFlowReferenceType.Qf)
    Qt = vfactory.add_var("Qt", reference=VarPowerFlowReferenceType.Qt)
    Pf = vfactory.add_var("Pf", reference=VarPowerFlowReferenceType.Pf)
    Pt = vfactory.add_var("Pt", reference=VarPowerFlowReferenceType.Pt)

    g = vfactory.add_var("g")
    b = vfactory.add_var("b")
    bsh = vfactory.add_var("bsh")
    gsh: Var = vfactory.add_var("gsh")

    u: Var = vfactory.add_var("u")

    block = Block()

    block.parameters[g] = vfactory.add_const(5)
    block.parameters[b] = vfactory.add_const(-12)
    block.parameters[bsh] = vfactory.add_const(0.03)
    block.parameters[gsh] = vfactory.add_const(0.0)

    block.event_dict[u] = vfactory.add_const(1)

    block.algebraic_vars = [Pf, Pt, Qf, Qt]


    # Physical shunt loss is split equally between the two terminal powers.
    pi2 = np.pi / 2
    block.algebraic_eqs = [
        Pf - u * ((inputs[0] ** 2 * (g + gsh / 2)) - g * inputs[0] * inputs[2] * cos(inputs[1] - inputs[3]) + b * inputs[0] * inputs[2] * cos(inputs[1] - inputs[3] + pi2)),
        Qf - u * (inputs[0] ** 2 * (-bsh / 2 - b) - g * inputs[0] * inputs[2] * sin(inputs[1] - inputs[3]) + b * inputs[0] * inputs[2] * sin(inputs[1] - inputs[3] + pi2)),
        Pt - u * ((inputs[2] ** 2 * (g + gsh / 2)) - g * inputs[2] * inputs[0] * cos(inputs[3] - inputs[1]) + b * inputs[2] * inputs[0] * cos(inputs[3] - inputs[1] + pi2)),
        Qt - u * (inputs[2] ** 2 * (-bsh / 2 - b) - g * inputs[2] * inputs[0] * sin(inputs[3] - inputs[1]) + b * inputs[2] * inputs[0] * sin(inputs[3] - inputs[1] + pi2)),
    ]

    block.in_vars = inputs
    block.out_vars = [Pf, Pt, Qf, Qt]

    block.name = name

    templ.block.children.append(block)

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vaf: inputs[1],
        VarPowerFlowReferenceType.Vat: inputs[3],
        VarPowerFlowReferenceType.Vmf: inputs[0],
        VarPowerFlowReferenceType.Vmt: inputs[2],
        VarPowerFlowReferenceType.Pf: Pf,
        VarPowerFlowReferenceType.Pt: Pt,
        VarPowerFlowReferenceType.Qf: Qf,
        VarPowerFlowReferenceType.Qt: Qt,
    }

    # Static mappings belong to the same child that declares their parameter
    # targets. The root only exposes the external terminal interface, while the
    # recursive RMS/EMT mapper visits this physical line block directly.
    block.api_obj_mapping = {
        ParamPowerFlowReferenceType.g: g,
        ParamPowerFlowReferenceType.b: b,
        ParamPowerFlowReferenceType.bsh: bsh,
        ParamPowerFlowReferenceType.shunt_g_pu: gsh,
    }

    templ.block.in_vars = inputs
    templ.block.out_vars = [Pf, Pt, Qf, Qt]
    # The fixed-size DAE keeps the branch compiled while a scheduled event
    # changes only this retained conduction parameter.
    templ.block.dynamic_model_contract.rms_conduction_status_var_uid = u.uid
    block.dynamic_model_contract.rms_conduction_status_var_uid = u.uid



    templ.comment = 'AC line RMS pi-equivalent model'
    return templ


def get_dc_line_rms_template(
        vfactory: VarFactory,
        name: str = "DC_Line_rms_template",
        use_dynamic_inductance: bool = True,
) -> RmsModelTemplate:
    """
    Build the RMS series R-L model of a DC line.

    The retained status input opens the driving voltage while preserving the
    fixed DAE dimensions and the physical current decay.

    :param vfactory: Symbolic variable factory shared by the circuit.
    :param name: Human-readable RMS template name.
    :param use_dynamic_inductance: Use a model-owned series inductance event
        parameter and represent current as a differential state. When
        ``False``, retain the exact purely resistive algebraic branch law.
    :return: DC-line RMS template for the requested branch topology.
    """
    templ: RmsModelTemplate = RmsModelTemplate()
    templ.tpe = DeviceType.DCLineDevice
    templ.name = name

    Vdcf: Var = vfactory.add_var("Vdcf", reference=VarPowerFlowReferenceType.Vmf)
    Vdct: Var = vfactory.add_var("Vdct", reference=VarPowerFlowReferenceType.Vmt)
    inputs: List[Var] = [Vdcf, Vdct]

    If_dc: Var = vfactory.add_var("If_dc")
    Pf: Var = vfactory.add_var("Pf", reference=VarPowerFlowReferenceType.Pf)
    Pt: Var = vfactory.add_var("Pt", reference=VarPowerFlowReferenceType.Pt)
    r: Var = vfactory.add_var("r")
    u: Var = vfactory.add_var("u")

    block: Block = Block()

    block.parameters[r] = vfactory.add_const(0.01)
    block.event_dict[u] = vfactory.add_const(1.0)

    if use_dynamic_inductance:
        # The model-owned series inductance stores magnetic energy, so its
        # current is a genuine state. This explicit ODE form is the normal RMS
        # contract and avoids embedding a differential variable in an
        # algebraic row, which produces a badly scaled mixed DAE near events.
        l: Var = vfactory.add_var("l")
        # Inductance belongs to the RMS model rather than to the static DC-line
        # device. Register it as a runtime parameter so it keeps this model's
        # default and can be targeted explicitly by RMS events.
        block.event_dict[l] = vfactory.add_const(0.05)
        block.state_vars = list([If_dc])
        block.state_eqs = list([
            (u * (Vdcf - Vdct) - r * If_dc) / l,
        ])
        block.algebraic_vars = list([Pf, Pt])
        block.algebraic_eqs = list([
            Pf - u * Vdcf * If_dc,
            Pt + u * Vdct * If_dc,
        ])
    else:
        # A branch with no exported inductance has no magnetic state. Keeping
        # its exact Ohm-law equation avoids introducing an arbitrary epsilon or
        # a fictitious time constant into static or dynamic studies.
        block.algebraic_vars = list([If_dc, Pf, Pt])
        block.algebraic_eqs = list([
            r * If_dc - u * (Vdcf - Vdct),
            Pf - u * Vdcf * If_dc,
            Pt + u * Vdct * If_dc,
        ])
    block.init_eqs = {
        # Initial conditions obey the same retained conduction flag as the
        # runtime equations, so an initially open line starts de-energized.
        If_dc: u * (Vdcf - Vdct) / r,
        Pf: u * Vdcf * If_dc,
        Pt: -u * Vdct * If_dc,
    }
    # Converter startup initializers can refine the DC terminal voltages after
    # the branch's first explicit seed. Re-evaluate the same acyclic physical
    # closure at the end of every global startup sweep so the first implicit
    # step sees one coherent V/I/P operating point.
    block.post_init_seed_eqs = {
        If_dc: u * (Vdcf - Vdct) / r,
        Pf: u * Vdcf * If_dc,
        Pt: -u * Vdct * If_dc,
    }
    block.in_vars = inputs
    # The branch current is an internal state. Only terminal powers form the
    # visible output interface consumed by the network connection layer.
    block.out_vars = list([Pf, Pt])
    block.name = name

    # The DC implementation is stored as one child block, matching the AC line
    # layout above. Registering the child is essential: otherwise its current,
    # equations, and initialization contract never reach RMS compilation even
    # though the root external mapping still exposes their variables.
    templ.block.children.append(block)

    templ.block.external_mapping = {
        VarPowerFlowReferenceType.Vmf: Vdcf,
        VarPowerFlowReferenceType.Vmt: Vdct,
        VarPowerFlowReferenceType.If_dc: If_dc,
        VarPowerFlowReferenceType.Pf: Pf,
        VarPowerFlowReferenceType.Pt: Pt,
    }

    # Keep the resistance mapping beside its declaration. A wrapper mapping to
    # this child parameter would be rejected by the owner-local static contract.
    block.api_obj_mapping = {
        # A native DC-line device exposes its physical resistance through the
        # dedicated dynamic reference.
        ParamPowerFlowReferenceType.dc_line_r_pu: r,
        # DGS ElmLne cables retain the normal Line device identity and expose
        # their imported resistance through the generic typed reference.
        ParamPowerFlowReferenceType.r: r,
    }

    templ.block.in_vars = inputs
    templ.block.out_vars = list([Pf, Pt])
    templ.block.dynamic_model_contract.rms_conduction_status_var_uid = u.uid
    block.dynamic_model_contract.rms_conduction_status_var_uid = u.uid

    templ.comment = 'DC line RMS series R-L model'
    return templ


def get_ideal_ac_connector_rms_template(
        vfactory: VarFactory,
        name: str = "DGS ideal AC connector RMS shell",
        enforce_voltage_constraint: bool = True,
) -> RmsModelTemplate:
    """Build an exact fixed-size RMS model for an ideal AC connector.

    A zero-impedance AC line is a topological contraction in PowerFactory. Its
    RMS counterpart must therefore conserve terminal powers and impose equal
    voltage phasors while closed. Reusing this module's regular line wrapper
    preserves the symbolic port and UID topology expected by the circuit-wide
    DAE assembler.

    :param vfactory: Variable factory shared by the owning circuit.
    :param name: Human-readable model name used by diagnostics and the GUI.
    :param enforce_voltage_constraint: Include this connector in the active
        topology forest. A redundant chord retains zero transfer power.
    :return: Exact ideal-connector RMS template with regular line ports.
    """
    template: RmsModelTemplate = RmsModelTemplate()
    template.tpe = DeviceType.LineDevice
    template.name = name

    # The terminal variables use exactly the standard line ordering so bus
    # mappings and result extraction require no connector-specific handling.
    voltage_magnitude_from: Var = vfactory.add_var(
        "Vmf",
        reference=VarPowerFlowReferenceType.Vmf,
    )
    voltage_angle_from: Var = vfactory.add_var(
        "Vaf",
        reference=VarPowerFlowReferenceType.Vaf,
    )
    voltage_magnitude_to: Var = vfactory.add_var(
        "Vmt",
        reference=VarPowerFlowReferenceType.Vmt,
    )
    voltage_angle_to: Var = vfactory.add_var(
        "Vat",
        reference=VarPowerFlowReferenceType.Vat,
    )
    inputs: List[Var] = list([
        voltage_magnitude_from,
        voltage_angle_from,
        voltage_magnitude_to,
        voltage_angle_to,
    ])

    active_power_from: Var = vfactory.add_var(
        "Pf",
        reference=VarPowerFlowReferenceType.Pf,
    )
    active_power_to: Var = vfactory.add_var(
        "Pt",
        reference=VarPowerFlowReferenceType.Pt,
    )
    reactive_power_from: Var = vfactory.add_var(
        "Qf",
        reference=VarPowerFlowReferenceType.Qf,
    )
    reactive_power_to: Var = vfactory.add_var(
        "Qt",
        reference=VarPowerFlowReferenceType.Qt,
    )
    conduction_status: Var = vfactory.add_var("u")
    topology_constraint_status: Var = vfactory.add_var("c_topology")
    constraint_mode: Expr = conduction_status * topology_constraint_status

    # Closed connectors conserve P/Q and contract both polar-voltage
    # coordinates. Open connectors reduce the same four rows to zero terminal
    # flows, which preserves the fixed DAE dimensions across switching events.
    block: Block = Block()
    block.event_dict[conduction_status] = vfactory.add_const(1.0)
    block.event_dict[topology_constraint_status] = vfactory.add_const(
        1.0 if enforce_voltage_constraint else 0.0
    )
    block.algebraic_vars = list([
        active_power_from,
        active_power_to,
        reactive_power_from,
        reactive_power_to,
    ])
    block.algebraic_eqs = list([
        constraint_mode * (active_power_from + active_power_to)
        + (1.0 - constraint_mode) * active_power_from,
        constraint_mode * (reactive_power_from + reactive_power_to)
        + (1.0 - constraint_mode) * reactive_power_from,
        constraint_mode * (voltage_magnitude_from - voltage_magnitude_to)
        + (1.0 - constraint_mode) * active_power_to,
        constraint_mode * (voltage_angle_from - voltage_angle_to)
        + (1.0 - constraint_mode) * reactive_power_to,
    ])
    block.in_vars = inputs
    block.out_vars = list([
        active_power_from,
        active_power_to,
        reactive_power_from,
        reactive_power_to,
    ])
    block.name = name

    # The root/child layout intentionally matches ``get_line_rms_template``.
    # This detail is part of the VarFactory connection contract in a massive
    # import and prevents unrelated dynamic blocks from being deduplicated.
    template.block.children.append(block)
    template.block.external_mapping = dict({
        VarPowerFlowReferenceType.Vaf: voltage_angle_from,
        VarPowerFlowReferenceType.Vat: voltage_angle_to,
        VarPowerFlowReferenceType.Vmf: voltage_magnitude_from,
        VarPowerFlowReferenceType.Vmt: voltage_magnitude_to,
        VarPowerFlowReferenceType.Pf: active_power_from,
        VarPowerFlowReferenceType.Pt: active_power_to,
        VarPowerFlowReferenceType.Qf: reactive_power_from,
        VarPowerFlowReferenceType.Qt: reactive_power_to,
    })
    template.block.api_obj_mapping = dict()
    template.block.in_vars = inputs
    template.block.out_vars = list([
        active_power_from,
        active_power_to,
        reactive_power_from,
        reactive_power_to,
    ])

    # The global nodal balances determine transfer power. Device-local
    # initialization would be underdetermined, so retain the power-flow seeds
    # until the complete DAE is assembled and polished.
    polish_variable_names: List[str] = list(["Pf", "Pt", "Qf", "Qt"])
    template.block.dynamic_model_contract.rms_conduction_status_var_uid = conduction_status.uid
    template.block.dynamic_model_contract.rms_topology_constraint_status_var_uid = (
        topology_constraint_status.uid
    )
    template.block.dynamic_model_contract.rms_ideal_ac_connector = True
    template.block.dynamic_model_contract.skip_device_local_explicit_init = True
    template.block.dynamic_model_contract.startup_initial_reduced_polish_var_names = list(
        polish_variable_names
    )
    block.dynamic_model_contract.rms_conduction_status_var_uid = conduction_status.uid
    block.dynamic_model_contract.rms_topology_constraint_status_var_uid = (
        topology_constraint_status.uid
    )
    block.dynamic_model_contract.rms_ideal_ac_connector = True
    block.dynamic_model_contract.skip_device_local_explicit_init = True
    block.dynamic_model_contract.startup_initial_reduced_polish_var_names = list(
        polish_variable_names
    )

    template.comment = 'Ideal AC connector RMS model'
    return template
