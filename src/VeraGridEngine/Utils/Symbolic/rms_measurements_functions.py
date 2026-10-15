# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.001--.0-
from __future__ import annotations

import math
from typing import Dict, List, Tuple

import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory

from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.enumerations import BlockType, VarPowerFlowReferenceType
from VeraGridEngine.Devices.types import ALL_DEV_TYPES

measurement_vars_dict = {"dc_bus": {BlockType.MEASUREMENTS_VOLTAGE_FROM_DC: [VarPowerFlowReferenceType.UR, VarPowerFlowReferenceType.U,
                                                                             VarPowerFlowReferenceType.URf, VarPowerFlowReferenceType.Uf,
                                                                             VarPowerFlowReferenceType.URt, VarPowerFlowReferenceType.Ut],
                                    BlockType.MEASUREMENTS_CURRENT_FROM_DC: [VarPowerFlowReferenceType.I_DC,
                                                                            VarPowerFlowReferenceType.If_dc,
                                                                            VarPowerFlowReferenceType.It_dc],
                                    BlockType.MEASUREMENTS_VOLTAGE_ANGLE: [VarPowerFlowReferenceType.Vdc,
                                                                          VarPowerFlowReferenceType.Vf_dc,
                                                                          VarPowerFlowReferenceType.Vt_dc],
                                    BlockType.MEASUREMENTS_P_Q: [VarPowerFlowReferenceType.P,
                                                                 VarPowerFlowReferenceType.Pf,
                                                                 VarPowerFlowReferenceType.Pt]

                                    },

                         "a_c_bus": {BlockType.MEASUREMENTS_VOLTAGE_FROM_POLAR: [VarPowerFlowReferenceType.U, VarPowerFlowReferenceType.Uf, VarPowerFlowReferenceType.Ut,
                                                                             VarPowerFlowReferenceType.UR, VarPowerFlowReferenceType.UI,
                                                                             VarPowerFlowReferenceType.URf, VarPowerFlowReferenceType.UIf,
                                                                             VarPowerFlowReferenceType.URt, VarPowerFlowReferenceType.UIt,
                                                                             VarPowerFlowReferenceType.UR_A, VarPowerFlowReferenceType.UR_B, VarPowerFlowReferenceType.UR_C,
                                                                             VarPowerFlowReferenceType.UI_A, VarPowerFlowReferenceType.UI_B, VarPowerFlowReferenceType.UI_C,
                                                                             VarPowerFlowReferenceType.URf_A, VarPowerFlowReferenceType.URf_B, VarPowerFlowReferenceType.URf_C,
                                                                             VarPowerFlowReferenceType.UIf_A, VarPowerFlowReferenceType.UIf_B, VarPowerFlowReferenceType.UIf_C,
                                                                             VarPowerFlowReferenceType.URt_A, VarPowerFlowReferenceType.URt_B, VarPowerFlowReferenceType.URt_C,
                                                                             VarPowerFlowReferenceType.UIt_A, VarPowerFlowReferenceType.UIt_B, VarPowerFlowReferenceType.UIt_C],
                                      BlockType.MEASUREMENTS_PLL: [VarPowerFlowReferenceType.COSPHI, VarPowerFlowReferenceType.SINPHI,
                                                                   VarPowerFlowReferenceType.COSPHIf, VarPowerFlowReferenceType.SINPHIf,
                                                                   VarPowerFlowReferenceType.COSPHIt, VarPowerFlowReferenceType.SINPHIt],
                                      BlockType.MEASUREMENTS_CURRENT_FROM_PQ: [VarPowerFlowReferenceType.IR,
                                                                               VarPowerFlowReferenceType.II,
                                                                               VarPowerFlowReferenceType.IR_B,
                                                                               VarPowerFlowReferenceType.IR_C,
                                                                               VarPowerFlowReferenceType.II_B,
                                                                               VarPowerFlowReferenceType.II_C],
                                     BlockType.MEASUREMENTS_VOLTAGE_ANGLE: [VarPowerFlowReferenceType.Vm,
                                                                            VarPowerFlowReferenceType.Va,
                                                                            VarPowerFlowReferenceType.Vmf,
                                                                            VarPowerFlowReferenceType.Vaf,
                                                                            VarPowerFlowReferenceType.Vmt,
                                                                            VarPowerFlowReferenceType.Vat],

                                     BlockType.MEASUREMENTS_P_Q: [VarPowerFlowReferenceType.P,
                                                                  VarPowerFlowReferenceType.Q,
                                                                  VarPowerFlowReferenceType.Pf,
                                                                  VarPowerFlowReferenceType.Qf,
                                                                  VarPowerFlowReferenceType.Pt,
                                                                  VarPowerFlowReferenceType.Qt]
                                     }}

def find_measurements_for_inputs_group(bus: ALL_DEV_TYPES, inputs: List[Var]) -> List[BlockType]:
    """
    returns the types of measurements blocks needed and input variables sorted by type
    :param self:
    :type self:
    :PARAM bus:
    :param inputs:
    :type inputs:
    :return:
    :rtype:
    """
    if bus.is_dc:
        needed_measurements_type: List[BlockType] = allocate_vars_in_corresponding_measurements_type(inputs, measurement_vars_dict['dc_bus'])

    else:
        needed_measurements_type: List[BlockType] = allocate_vars_in_corresponding_measurements_type(inputs, measurement_vars_dict['a_c_bus'])

    return needed_measurements_type

def allocate_vars_in_corresponding_measurements_type(inputs: List[Var], measurements_dict:Dict[BlockType, List[VarPowerFlowReferenceType]]) -> List[BlockType]:
    """
    relates vars with the corresponding measurements block type
    :param inputs:
    :type inputs:
    :param measurements_dict:
    :type measurements_dict:
    :return:
    :rtype:
    """
    needed_measurements_type: List[BlockType] = list()
    vars_list = inputs
    for var in vars_list:
        for measurements_type, var_power_flow_type_list in measurements_dict.items():
            if var.ref in var_power_flow_type_list:
                if measurements_type in needed_measurements_type:
                    pass
                else:
                    needed_measurements_type.append(measurements_type)

    return needed_measurements_type

def _rotate_complex_components(real_part: Expr, imag_part: Expr, angle_rad: float) -> tuple[Expr, Expr]:
    """
    Rotate one complex quantity by one fixed phase angle.

    :param real_part: Real component.
    :param imag_part: Imaginary component.
    :param angle_rad: Rotation angle in radians.
    :return: Rotated ``(real, imag)`` pair.
    """
    cos_a: Const = Const(math.cos(angle_rad))
    sin_a: Const = Const(math.sin(angle_rad))
    rotated_real: Expr = (real_part * cos_a) - (imag_part * sin_a)
    rotated_imag: Expr = (real_part * sin_a) + (imag_part * cos_a)
    return rotated_real, rotated_imag



def _build_rms_pll_measurements(
        va: Expr,
        var_factory: VarFactory,
        cos_reference: VarPowerFlowReferenceType,
        sin_reference: VarPowerFlowReferenceType,
) -> Tuple[Block, List[Var]]:
    """Build one PLL measurement with an explicit terminal contract.

    :param va: Physical terminal voltage angle in radians.
    :param var_factory: Factory owning the generated output variables.
    :param cos_reference: Reference assigned to the cosine output.
    :param sin_reference: Reference assigned to the sine output.
    :return: Measurement block and ordered output variables.
    """
    block: Block = Block()
    cosphi: Var = var_factory.add_var(name="cosphi", reference=cos_reference)
    sinphi: Var = var_factory.add_var(name="sinphi", reference=sin_reference)
    variables: List[Var] = list((cosphi, sinphi))
    block.algebraic_vars = variables
    block.algebraic_eqs = list((
        cosphi - sym.cos(va),
        sinphi - sym.sin(va),
    ))
    block.in_vars = list((va,))
    block.out_vars = variables
    return block, variables


def build_rms_pll_measurements(va: Expr,
                               var_factory: VarFactory
                               ) -> Tuple[Block, List[Var]]:
    """
       Build the VeraGrid RMS output set of one PLL meter.

       :param va:
       :param var_factory:
       """

    block: Block
    variables: List[Var]
    block, variables = _build_rms_pll_measurements(
        va=va,
        var_factory=var_factory,
        cos_reference=VarPowerFlowReferenceType.COSPHI,
        sin_reference=VarPowerFlowReferenceType.SINPHI,
    )
    return block, variables


def build_rms_pll_measurements_from(
        va: Expr,
        var_factory: VarFactory,
) -> Tuple[Block, List[Var]]:
    """Build a from-terminal algebraic PLL measurement.

    :param va: From-terminal voltage angle in radians.
    :param var_factory: Factory owning the generated output variables.
    :return: Measurement block and ordered output variables.
    """
    block: Block
    variables: List[Var]
    block, variables = _build_rms_pll_measurements(
        va=va,
        var_factory=var_factory,
        cos_reference=VarPowerFlowReferenceType.COSPHIf,
        sin_reference=VarPowerFlowReferenceType.SINPHIf,
    )
    return block, variables


def build_rms_pll_measurements_to(
        va: Expr,
        var_factory: VarFactory,
) -> Tuple[Block, List[Var]]:
    """Build a to-terminal algebraic PLL measurement.

    :param va: To-terminal voltage angle in radians.
    :param var_factory: Factory owning the generated output variables.
    :return: Measurement block and ordered output variables.
    """
    block: Block
    variables: List[Var]
    block, variables = _build_rms_pll_measurements(
        va=va,
        var_factory=var_factory,
        cos_reference=VarPowerFlowReferenceType.COSPHIt,
        sin_reference=VarPowerFlowReferenceType.SINPHIt,
    )
    return block, variables

def build_rms_voltage_meter_outputs_from_polar(var_factory: VarFactory,
                                               vm: Var,
                                               va: Var,
                                               measured_frequency_hz: Const,
                                               nominal_frequency_hz: Const) -> Tuple[Block, List[Var]]:
    """
    Build the VeraGrid RMS output set of one AC voltage meter.

    :param var_factory: Var factory.
    :param vm: Voltage magnitude.
    :param va: Voltage angle in radians.
    :param measured_frequency_hz: Measured frequency in Hz.
    :param nominal_frequency_hz: Nominal frequency in Hz.
    :return: Signal-name to expression mapping.
    """
    # create block
    block = Block()

    #create_variables

    u = var_factory.add_var(name = "u", reference=VarPowerFlowReferenceType.U)
    ur = var_factory.add_var(name="ur", reference=VarPowerFlowReferenceType.UR)
    ui = var_factory.add_var(name="ui", reference=VarPowerFlowReferenceType.UI)
    ur_a = var_factory.add_var(name = "ur_a", reference=VarPowerFlowReferenceType.UR_A)
    ui_a = var_factory.add_var(name="ui_a", reference=VarPowerFlowReferenceType.UI_A)
    ur_b = var_factory.add_var(name="ur_b", reference=VarPowerFlowReferenceType.UR_B)
    ui_b = var_factory.add_var(name="ui_b", reference=VarPowerFlowReferenceType.UI_B)
    ur_c = var_factory.add_var(name="ur_c", reference=VarPowerFlowReferenceType.UR_C)
    ui_c = var_factory.add_var(name="ui_c", reference=VarPowerFlowReferenceType.UI_C)

    variables = [u, ur, ui, ur_a, ui_a, ur_b, ui_b, ur_c, ui_c]


    # create rotation equations
    rotated_real_ur_b, rotated_imag_ui_b = _rotate_complex_components(ur_a, ui_a, -2.0 * math.pi / 3.0)
    rotated_real_ur_c, rotated_imag_ui_c = _rotate_complex_components(ur_a, ui_a, 2.0 * math.pi / 3.0)

    # fill block
    block.algebraic_vars = variables
    block.algebraic_eqs = [ur_a - vm * sym.cos(va), ui_a - vm * sym.sin(va),
                           ur - ur_a, ui - ui_a, ur_b - rotated_real_ur_b,
                           ui_b - rotated_imag_ui_b, ur_c - rotated_real_ur_c, ui_c - rotated_imag_ui_c,
                           u - vm]

    return block, variables


def _build_rms_terminal_voltage_meter_outputs_from_polar(
        var_factory: VarFactory,
        vm: Var,
        va: Var,
        output_references: Tuple[
            VarPowerFlowReferenceType,
            VarPowerFlowReferenceType,
            VarPowerFlowReferenceType,
            VarPowerFlowReferenceType,
            VarPowerFlowReferenceType,
            VarPowerFlowReferenceType,
            VarPowerFlowReferenceType,
            VarPowerFlowReferenceType,
            VarPowerFlowReferenceType,
        ],
) -> Tuple[Block, List[Var]]:
    """Build one terminal-specific polar-voltage measurement block.

    :param var_factory: Factory owning the generated output variables.
    :param vm: Physical terminal voltage magnitude.
    :param va: Physical terminal voltage angle in radians.
    :param output_references: Ordered U, real-phase and imaginary-phase refs.
    :return: Measurement block and ordered output variables.
    """
    block: Block = Block()
    u: Var = var_factory.add_var(name="u", reference=output_references[0])
    ur: Var = var_factory.add_var(name="ur", reference=output_references[1])
    ui: Var = var_factory.add_var(name="ui", reference=output_references[2])
    ur_a: Var = var_factory.add_var(name="ur_a", reference=output_references[3])
    ui_a: Var = var_factory.add_var(name="ui_a", reference=output_references[4])
    ur_b: Var = var_factory.add_var(name="ur_b", reference=output_references[5])
    ui_b: Var = var_factory.add_var(name="ui_b", reference=output_references[6])
    ur_c: Var = var_factory.add_var(name="ur_c", reference=output_references[7])
    ui_c: Var = var_factory.add_var(name="ui_c", reference=output_references[8])
    variables: List[Var] = list((u, ur, ui, ur_a, ui_a, ur_b, ui_b, ur_c, ui_c))
    rotated_real_ur_b: Expr
    rotated_imag_ui_b: Expr
    rotated_real_ur_c: Expr
    rotated_imag_ui_c: Expr
    rotated_real_ur_b, rotated_imag_ui_b = _rotate_complex_components(
        ur_a,
        ui_a,
        -2.0 * math.pi / 3.0,
    )
    rotated_real_ur_c, rotated_imag_ui_c = _rotate_complex_components(
        ur_a,
        ui_a,
        2.0 * math.pi / 3.0,
    )
    block.algebraic_vars = variables
    block.algebraic_eqs = list((
        ur_a - vm * sym.cos(va),
        ui_a - vm * sym.sin(va),
        ur - ur_a,
        ui - ui_a,
        ur_b - rotated_real_ur_b,
        ui_b - rotated_imag_ui_b,
        ur_c - rotated_real_ur_c,
        ui_c - rotated_imag_ui_c,
        u - vm,
    ))
    block.in_vars = list((vm, va))
    block.out_vars = variables
    return block, variables


def build_rms_voltage_meter_outputs_from_polar_from(
        var_factory: VarFactory,
        vm: Var,
        va: Var,
) -> Tuple[Block, List[Var]]:
    """Build a from-terminal polar-voltage measurement.

    :param var_factory: Factory owning the generated output variables.
    :param vm: From-terminal voltage magnitude.
    :param va: From-terminal voltage angle in radians.
    :return: Measurement block and ordered output variables.
    """
    output_references: Tuple[
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
    ] = (
        VarPowerFlowReferenceType.Uf,
        VarPowerFlowReferenceType.URf,
        VarPowerFlowReferenceType.UIf,
        VarPowerFlowReferenceType.URf_A,
        VarPowerFlowReferenceType.UIf_A,
        VarPowerFlowReferenceType.URf_B,
        VarPowerFlowReferenceType.UIf_B,
        VarPowerFlowReferenceType.URf_C,
        VarPowerFlowReferenceType.UIf_C,
    )
    block: Block
    variables: List[Var]
    block, variables = _build_rms_terminal_voltage_meter_outputs_from_polar(
        var_factory=var_factory,
        vm=vm,
        va=va,
        output_references=output_references,
    )
    return block, variables


def build_rms_voltage_meter_outputs_from_polar_to(
        var_factory: VarFactory,
        vm: Var,
        va: Var,
) -> Tuple[Block, List[Var]]:
    """Build a to-terminal polar-voltage measurement.

    :param var_factory: Factory owning the generated output variables.
    :param vm: To-terminal voltage magnitude.
    :param va: To-terminal voltage angle in radians.
    :return: Measurement block and ordered output variables.
    """
    output_references: Tuple[
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
        VarPowerFlowReferenceType,
    ] = (
        VarPowerFlowReferenceType.Ut,
        VarPowerFlowReferenceType.URt,
        VarPowerFlowReferenceType.UIt,
        VarPowerFlowReferenceType.URt_A,
        VarPowerFlowReferenceType.UIt_A,
        VarPowerFlowReferenceType.URt_B,
        VarPowerFlowReferenceType.UIt_B,
        VarPowerFlowReferenceType.URt_C,
        VarPowerFlowReferenceType.UIt_C,
    )
    block: Block
    variables: List[Var]
    block, variables = _build_rms_terminal_voltage_meter_outputs_from_polar(
        var_factory=var_factory,
        vm=vm,
        va=va,
        output_references=output_references,
    )
    return block, variables


def build_rms_voltage_meter_outputs_from_dc(var_factory: VarFactory,
                                            vdc: Var,
                                            nominal_frequency_hz: Expr)  -> Tuple[Block, List[Var]]:
    """
    Build the VeraGrid RMS output set of one DC voltage meter.

    :param var_factory: Var factory.
    :param vdc: DC voltage magnitude.
    :param nominal_frequency_hz: Nominal frequency in Hz.
    :return: Signal-name to expression mapping.
    """
    # zero: Const = Const(0.0)

    # create block
    block = Block()

    # create_variables

    u = var_factory.add_var(name="u", reference=VarPowerFlowReferenceType.U)
    ur = var_factory.add_var(name="ur", reference=VarPowerFlowReferenceType.UR)

    variables = [u, ur]

    # fill block
    block.algebraic_vars = variables
    block.algebraic_eqs = [ur - vdc,
                           u - vdc]

    return block, variables


def _build_rms_terminal_voltage_meter_outputs_from_dc(
        var_factory: VarFactory,
        vdc: Var,
        magnitude_reference: VarPowerFlowReferenceType,
        real_reference: VarPowerFlowReferenceType,
) -> Tuple[Block, List[Var]]:
    """Build one terminal-specific DC voltage measurement.

    :param var_factory: Factory owning the generated output variables.
    :param vdc: Physical terminal DC voltage.
    :param magnitude_reference: Reference assigned to output magnitude.
    :param real_reference: Reference assigned to output real component.
    :return: Measurement block and ordered output variables.
    """
    block: Block = Block()
    u: Var = var_factory.add_var(name="u", reference=magnitude_reference)
    ur: Var = var_factory.add_var(name="ur", reference=real_reference)
    variables: List[Var] = list((u, ur))
    block.algebraic_vars = variables
    block.algebraic_eqs = list((ur - vdc, u - vdc))
    block.in_vars = list((vdc,))
    block.out_vars = variables
    return block, variables


def build_rms_voltage_meter_outputs_from_dc_from(
        var_factory: VarFactory,
        vdc: Var,
) -> Tuple[Block, List[Var]]:
    """Build a from-terminal DC voltage measurement.

    :param var_factory: Factory owning the generated output variables.
    :param vdc: From-terminal physical DC voltage.
    :return: Measurement block and ordered output variables.
    """
    block: Block
    variables: List[Var]
    block, variables = _build_rms_terminal_voltage_meter_outputs_from_dc(
        var_factory=var_factory,
        vdc=vdc,
        magnitude_reference=VarPowerFlowReferenceType.Uf,
        real_reference=VarPowerFlowReferenceType.URf,
    )
    return block, variables


def build_rms_voltage_meter_outputs_from_dc_to(
        var_factory: VarFactory,
        vdc: Var,
) -> Tuple[Block, List[Var]]:
    """Build a to-terminal DC voltage measurement.

    :param var_factory: Factory owning the generated output variables.
    :param vdc: To-terminal physical DC voltage.
    :return: Measurement block and ordered output variables.
    """
    block: Block
    variables: List[Var]
    block, variables = _build_rms_terminal_voltage_meter_outputs_from_dc(
        var_factory=var_factory,
        vdc=vdc,
        magnitude_reference=VarPowerFlowReferenceType.Ut,
        real_reference=VarPowerFlowReferenceType.URt,
    )
    return block, variables

def build_rms_current_meter_outputs_from_pq(var_factory: VarFactory,
                                            vm: Var,
                                            va: Var,
                                            p: Var,
                                            q: Var) -> Tuple[Block, List[Var]]:
    """
    Build the VeraGrid RMS current outputs from ``P/Q`` and ``V``.

    :param var_factory: Var factory.
    :param vm: Voltage magnitude.
    :param va: Voltage angle in radians.
    :param p: Active power.
    :param q: Reactive power.
    :return: Signal-name to expression mapping.
    """

    # create block
    block = Block()

    # create_variables

    ur = var_factory.add_var(name="ur", reference=VarPowerFlowReferenceType.UR)
    ui = var_factory.add_var(name="ui", reference=VarPowerFlowReferenceType.UI)
    ir = var_factory.add_var(name="ir", reference=VarPowerFlowReferenceType.IR)
    ii = var_factory.add_var(name="ii", reference=VarPowerFlowReferenceType.II)
    ir_b = var_factory.add_var(name="ir_b", reference=VarPowerFlowReferenceType.IR_B)
    ii_b = var_factory.add_var(name="ii_b", reference=VarPowerFlowReferenceType.II_B)
    ir_c = var_factory.add_var(name="ir_c", reference=VarPowerFlowReferenceType.IR_C)
    ii_c = var_factory.add_var(name="ii_c", reference=VarPowerFlowReferenceType.II_C)


    variables = [ur, ui, ir, ii, ir_b, ii_b, ir_c, ii_c]

    ir_b_expr, ii_b_expr = _rotate_complex_components(ir, ii, -2.0 * math.pi / 3.0)
    ir_c_expr, ii_c_expr = _rotate_complex_components(ir, ii, 2.0 * math.pi / 3.0)

    # fill block
    block.algebraic_vars = variables
    block.algebraic_eqs = [ur - vm * sym.cos(va),
                           ui -  vm * sym.sin(va),
                           ir - (p * ur + q * ui) /(vm * vm) + Const(1e-9),
                           ii - (p * ui - q * ur) / (vm * vm) + Const(1e-9),
                           ir_b - ir_b_expr,
                           ii_b - ii_b_expr,
                           ir_c - ir_c_expr,
                           ii_c - ii_c_expr]

    return block, variables

def build_rms_current_meter_outputs_from_dc(
        var_factory: VarFactory,
        vdc: Var,
        p: Var,
) -> Tuple[Block, List[Var]]:
    """Build the RMS-editor current channels of one DC terminal.

    DC terminal power follows ``P = Vdc * Idc``.  The regularized quotient
    keeps the generated symbolic model finite while a bus is de-energized and
    uses the real current channel shared by the balanced meter interface.

    :param var_factory: Var factory.
    :param vdc: DC terminal voltage.
    :param p: Signed active power at the same terminal.
    :return: Single signed ``Idc`` current expression.
    """

    # create block
    block = Block()

    # create_variables
    idc = var_factory.add_var(name="idc", reference=VarPowerFlowReferenceType.I_DC)

    variables = [idc]

    # fill block
    block.algebraic_vars = variables
    block.algebraic_eqs = [idc - (p * vdc) / ((vdc * vdc) + Const(1e-9))]

    return block, variables

def build_rms_power_meter_outputs_from_pq(p: Expr, q: Expr) -> Dict[str, Expr]:
    """
    Build the VeraGrid RMS active/reactive power outputs.

    :param p: Active power.
    :param q: Reactive power.
    :return: Signal-name to expression mapping.
    """
    zero: Const = Const(0.0)
    return {
        "p": p,
        "q": q,
        "p2": zero,
        "q2": zero,
        "p0": zero,
        "q0": zero,
    }
