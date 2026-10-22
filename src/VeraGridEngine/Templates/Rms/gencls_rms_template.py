# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Standard two-state classical synchronous-generator RMS model."""

from __future__ import annotations

import math
from enum import Enum

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.enumerations import ParamPowerFlowReferenceType, DeviceType
from VeraGridEngine.enumerations import VarPowerFlowReferenceType
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import configure_tgov1_block
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import get_tgov1_rms_template
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import Tgov1RmsParameters
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class GenclsMechanicalInput(Enum):
    """Mechanical-input structures supported by GENCLS."""

    CONSTANT = 1
    TGOV1 = 2


class GenclsRmsParameters:
    """Numerical parameters for one classical synchronous machine."""

    __slots__ = ("fn", "d", "m", "ra", "xd1")

    def __init__(
        self: "GenclsRmsParameters",
        fn: float,
        d: float,
        m: float,
        ra: float,
        xd1: float,
    ) -> None:
        """Store one GENCLS parameter record.

        :param fn: Nominal electrical frequency in hertz.
        :param d: System-base damping coefficient.
        :param m: System-base acceleration time constant.
        :param ra: System-base armature resistance.
        :param xd1: System-base transient reactance.
        :return: None.
        """
        self.fn: float = fn
        self.d: float = d
        self.m: float = m
        self.ra: float = ra
        self.xd1: float = xd1


def _add_parameter(
    block: Block,
    vfactory: VarFactory,
    name: str,
    value: float | None,
) -> Var:
    """Create one named event parameter.

    :param block: Owning symbolic block.
    :param vfactory: Shared variable factory.
    :param name: Parameter name.
    :param value: Default value, or ``None`` for an initialized hold value.
    :return: Created parameter variable.
    """
    parameter: Var = vfactory.add_var(name)
    block.event_dict[parameter] = vfactory.add_const(value=value, name=name)
    return parameter


def get_gencls_rms_template(
    vfactory: VarFactory,
    mechanical_input: GenclsMechanicalInput = GenclsMechanicalInput.CONSTANT,
    name: str = "GENCLS RMS template",
) -> RmsModelTemplate:
    """Build the standard two-state classical-generator realization.

    :param vfactory: Shared symbolic variable factory.
    :param mechanical_input: Constant-torque or TGOV1-driven structure.
    :param name: Template name.
    :return: GENCLS RMS template.
    """
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice
    vm_var: Var = vfactory.add_var("Vm", reference=VarPowerFlowReferenceType.Vm)
    va_var: Var = vfactory.add_var("Va", reference=VarPowerFlowReferenceType.Va)
    pg_var: Var = vfactory.add_var("Pg", reference=VarPowerFlowReferenceType.P)
    qg_var: Var = vfactory.add_var("Qg", reference=VarPowerFlowReferenceType.Q)
    tm_var: Var = vfactory.add_var("Tm", shared_reference="tm_reference")
    delta_var: Var = vfactory.add_var("delta", shared_reference="delta_reference")
    omega_var: Var = vfactory.add_var("omega", shared_reference="omega_reference")
    vd_var: Var = vfactory.add_var("Vd", shared_reference="vd_reference")
    vq_var: Var = vfactory.add_var("Vq", shared_reference="vq_reference")
    id_var: Var = vfactory.add_var("Id", shared_reference="id_reference")
    iq_var: Var = vfactory.add_var("Iq", shared_reference="iq_reference")
    psid_var: Var = vfactory.add_var("psid")
    psiq_var: Var = vfactory.add_var("psiq")
    te_var: Var = vfactory.add_var("Te", shared_reference="te_reference")
    vf_var: Var = vfactory.add_var("Vf")
    block: Block = Block(name=name)
    fn_var: Var = vfactory.add_var("fn")
    block.parameters[fn_var] = vfactory.add_const(60.0)
    block.api_obj_mapping[ParamPowerFlowReferenceType.freq] = fn_var
    d_var: Var = _add_parameter(block, vfactory, "D", 0.0)
    m_var: Var = _add_parameter(block, vfactory, "M", 6.0)
    ra_var: Var = _add_parameter(block, vfactory, "Ra", 0.0)
    xd1_var: Var = _add_parameter(block, vfactory, "Xd_prime", 0.3)
    vf_hold_var: Var = _add_parameter(block, vfactory, "Vf_hold", None)
    tm_hold_var: Var | None
    if mechanical_input is GenclsMechanicalInput.CONSTANT:
        tm_hold_var = _add_parameter(block, vfactory, "Tm_hold", None)
    else:
        tm_hold_var = None

    ws_expr: Expr = sym.Const(2.0 * math.pi) * fn_var
    block.state_vars = list((delta_var, omega_var))
    block.state_eqs = list((
        ws_expr * (omega_var - sym.Const(1.0)),
        (tm_var - te_var - d_var * (omega_var - sym.Const(1.0))) / m_var,
    ))
    block.algebraic_vars = list((
        vd_var, vq_var, id_var, iq_var, pg_var, qg_var,
        psid_var, psiq_var, te_var, vf_var,
    ))
    block.algebraic_eqs = list((
        vm_var * sym.sin(delta_var - va_var) - vd_var,
        vm_var * sym.cos(delta_var - va_var) - vq_var,
        xd1_var * id_var - vf_var + psid_var,
        xd1_var * iq_var + psiq_var,
        vd_var * id_var + vq_var * iq_var - pg_var,
        vq_var * id_var - vd_var * iq_var - qg_var,
        ra_var * iq_var + vq_var - psid_var,
        -ra_var * id_var - vd_var - psiq_var,
        psid_var * iq_var - psiq_var * id_var - te_var,
        vf_hold_var - vf_var,
    ))
    if tm_hold_var is None:
        block.in_vars = list((vm_var, va_var, tm_var))
    else:
        block.algebraic_vars.append(tm_var)
        block.algebraic_eqs.append(tm_hold_var - tm_var)
        block.in_vars = list((vm_var, va_var))

    voltage_complex: Expr = vm_var * sym.exp(sym.Const(1j) * va_var)
    current_complex: Expr = sym.conj(
        (pg_var + sym.Const(1j) * qg_var) / voltage_complex
    )
    internal_complex: Expr = voltage_complex + (
        ra_var + sym.Const(1j) * xd1_var
    ) * current_complex
    delta_initial: Expr = sym.imag(sym.log(internal_complex / sym.abs(internal_complex)))
    dq_rotation: Expr = sym.exp(
        -sym.Const(1j) * (delta_var - sym.Const(math.pi / 2.0))
    )
    block.init_eqs = dict()
    block.init_eqs[delta_var] = delta_initial
    block.init_eqs[omega_var] = sym.Const(1.0)
    block.init_eqs[vd_var] = sym.real(voltage_complex * dq_rotation)
    block.init_eqs[vq_var] = sym.imag(voltage_complex * dq_rotation)
    block.init_eqs[id_var] = sym.real(current_complex * dq_rotation)
    block.init_eqs[iq_var] = sym.imag(current_complex * dq_rotation)
    block.init_eqs[psid_var] = ra_var * iq_var + vq_var
    block.init_eqs[psiq_var] = -ra_var * id_var - vd_var
    block.init_eqs[te_var] = psid_var * iq_var - psiq_var * id_var
    block.init_eqs[vf_var] = vq_var + ra_var * iq_var + xd1_var * id_var
    block.init_eqs[vf_hold_var] = vf_var
    block.init_eqs[tm_var] = te_var
    if tm_hold_var is None:
        pass
    else:
        block.init_eqs[tm_hold_var] = te_var

    block.out_vars = list((pg_var, qg_var, omega_var, te_var))
    block.external_mapping = dict()
    block.external_mapping[VarPowerFlowReferenceType.Vm] = vm_var
    block.external_mapping[VarPowerFlowReferenceType.Va] = va_var
    block.external_mapping[VarPowerFlowReferenceType.P] = pg_var
    block.external_mapping[VarPowerFlowReferenceType.Q] = qg_var
    template.block.children.append(block)
    template.block.external_mapping = dict(block.external_mapping)
    template.block.in_vars = list((vm_var, va_var))
    template.block.out_vars = list((pg_var, qg_var))
    template.block.name = name
    template.comment = 'Generator GENCLS RMS model'
    return template


def configure_gencls_block(
    block: Block,
    parameters: GenclsRmsParameters,
    vfactory: VarFactory,
) -> None:
    """Configure a classical machine with a dynamic or fixed rotor.

    Positive acceleration time enables the swing equation and electrical-angle
    integration. Exactly zero acceleration time selects a prescribed internal
    voltage source: rotor angle and speed retain their initialized values with
    identically zero derivatives. This is a structural choice, not division by
    a small substitute inertia. The stator equations still calculate changing
    electrical power and current during network disturbances.

    Reconfiguration reconstructs both rotor equations, so switching back from
    fixed-rotor to positive-inertia behavior restores the original dynamics.

    :param block: GENCLS machine block.
    :param parameters: Numerical parameter record.
    :param vfactory: Shared variable factory.
    :return: None.
    :raises ValueError: Nonfinite settings, negative inertia or invalid machine base dynamics.
    """
    if not all(math.isfinite(value) for value in (parameters.fn,parameters.d,parameters.m,parameters.ra,parameters.xd1)):
        raise ValueError('Classical machine settings must be finite')
    elif parameters.fn <= 0 or parameters.m < 0 or parameters.xd1 <= 0:
        raise ValueError('Classical machine frequency/reactance must be positive and inertia nonnegative')
    else:
        pass
    names: tuple[str, ...] = ("fn", "D", "M", "Ra", "Xd_prime")
    values: tuple[float, ...] = (
        parameters.fn, parameters.d, parameters.m, parameters.ra, parameters.xd1,
    )
    parameter_name: str
    parameter_value: float
    for parameter_name, parameter_value in zip(names, values):
        destination = block.parameters if parameter_name == "fn" else block.event_dict
        matches: list[Var] = list(
            variable for variable in destination if variable.name == parameter_name
        )
        if len(matches) == 1:
            destination[matches[0]] = vfactory.add_const(
                value=parameter_value,
                name=parameter_name,
            )
        else:
            raise ValueError(
                f"Expected one GENCLS parameter {parameter_name!r}; found {len(matches)}."
            )
    # Rebuild the structural choice explicitly; numerical parameter updates
    # alone cannot represent a prescribed rotor at exactly zero inertia.
    if parameters.m == 0:
        block.state_eqs = list((sym.Const(0.0),sym.Const(0.0)))
    else:
        symbols: dict[str,Var] = dict()
        for registry in (block.init_eqs,block.parameters,block.event_dict):
            for variable in registry:
                symbols[variable.name] = variable
        block.state_eqs = list((sym.Const(2*math.pi)*symbols['fn']*(symbols['omega']-sym.Const(1.0)),
            (symbols['Tm']-symbols['Te']-symbols['D']*(symbols['omega']-sym.Const(1.0)))/symbols['M']))


def get_complete_gencls_rms_template(
    vfactory: VarFactory,
    mechanical_input: GenclsMechanicalInput = GenclsMechanicalInput.CONSTANT,
    name: str = "Complete GENCLS RMS template",
) -> RmsModelTemplate:
    """Build GENCLS with either constant torque or a TGOV1 controller.

    :param vfactory: Shared symbolic variable factory.
    :param mechanical_input: Mechanical-input structure.
    :param name: Composite template name.
    :return: Connected GENCLS generator template.
    """
    template: RmsModelTemplate = RmsModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice
    machine_block: Block = get_gencls_rms_template(
        vfactory=vfactory,
        mechanical_input=mechanical_input,
        name=f"{name} GENCLS",
    ).block.children[0]
    template.block.children.append(machine_block)
    if mechanical_input is GenclsMechanicalInput.TGOV1:
        governor_block: Block = get_tgov1_rms_template(
            vfactory=vfactory,
            name=f"{name} TGOV1",
        ).block.children[0]
        vfactory.add_connection(machine_block.in_vars[2], governor_block.out_vars[0])
        vfactory.add_connection(governor_block.in_vars[0], machine_block.out_vars[2])
        vfactory.add_connection(governor_block.in_vars[1], machine_block.out_vars[3])
        template.block.children.append(governor_block)
    else:
        pass
    template.block.external_mapping = dict(machine_block.external_mapping)
    template.block.in_vars = list((machine_block.in_vars[0], machine_block.in_vars[1]))
    template.block.out_vars = list((machine_block.out_vars[0], machine_block.out_vars[1]))
    template.block.name = name
    template.comment = 'Complete generator GENCLS RMS model'
    return template


def configure_gencls_tgov1_block(
    template: RmsModelTemplate,
    machine_parameters: GenclsRmsParameters,
    governor_parameters: Tgov1RmsParameters | None,
    vfactory: VarFactory,
) -> None:
    """Configure one complete GENCLS assembly.

    :param template: GENCLS composite template.
    :param machine_parameters: Machine parameters.
    :param governor_parameters: Optional TGOV1 parameters.
    :param vfactory: Shared variable factory.
    :return: None.
    """
    configure_gencls_block(template.block.children[0], machine_parameters, vfactory)
    if governor_parameters is None:
        if len(template.block.children) == 1:
            pass
        else:
            raise ValueError("A governor block exists but no TGOV1 parameters were supplied.")
    else:
        if len(template.block.children) == 2:
            configure_tgov1_block(template.block.children[1], governor_parameters, vfactory)
        else:
            raise ValueError("TGOV1 parameters were supplied to a constant-torque GENCLS model.")
