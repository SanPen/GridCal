# SPDX-License-Identifier: MPL-2.0
"""Field-transient salient-pole synchronous machine without damper windings."""
from __future__ import annotations

import math

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _quadratic_saturation_coefficients
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const
import VeraGridEngine.Utils.Symbolic.symbolic as sym
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType, ParamPowerFlowReferenceType


def build_gentra_template(vf: VarFactory, name: str | None = None,
                          frequency: float = 50.0, inertia: float = 4.0,
                          damping: float = 0.0, resistance: float = 0.0,
                          direct_reactance: float = 1.8, quadrature_reactance: float = 1.7,
                          transient_reactance: float = 0.3, transient_time: float = 6.0,
                          saturation_10: float = 0.09, saturation_12: float = 0.38) -> RmsModelTemplate:
    """Build a three-state synchronous machine with field-winding transients.

    The rotor angle, absolute per-unit speed and direct-axis transient flux are
    the continuous states. Damper windings and quadrature-axis rotor transients
    are omitted. This reduced representation therefore has no damper-winding
    contribution to oscillation damping. Its stator equations retain saliency
    and resistance, and electromagnetic torque includes copper losses.

    Direct-axis saturation is a quadratic excess-field characteristic fitted
    to the specified saturation factors at transient fluxes 1.0 and 1.2 pu.
    Both factors zero select an exactly unsaturated structure; an enabled fit
    requires two positive factors. A single zero sample is rejected rather than
    silently discarding the other sample. Saturation acts
    on transient flux rather than terminal voltage or subtransient flux.

    Inputs are terminal voltage magnitude/angle, mechanical torque and field
    voltage. Outputs are active/reactive power, speed, field-current equivalent,
    electromagnetic torque, d/q terminal voltages and d/q stator currents.
    Angles are electrical radians; time is seconds. Powers, impedances, inertia
    and damping must share the network power base. The field-voltage input uses
    the air-gap field-current equivalent on the machine voltage base.

    Initialization reconstructs rotor position and currents from terminal P/Q,
    then balances field voltage and mechanical torque against those currents.
    Network algebraic equations are solved simultaneously with the rotor DAE;
    no model-specific iterative relaxation parameter enters the physics.

    :param vf: Shared native symbolic variable factory.
    :param name: Optional unique instance label.
    :param frequency: Nominal electrical frequency in hertz.
    :param inertia: Inertia constant on the common power base, in seconds.
    :param damping: Torque damping per unit speed deviation.
    :param resistance: Stator resistance on the common power base.
    :param direct_reactance: Unsaturated direct-axis synchronous reactance.
    :param quadrature_reactance: Unsaturated quadrature-axis synchronous reactance.
    :param transient_reactance: Direct-axis transient reactance.
    :param transient_time: Open-circuit direct-axis transient time constant.
    :param saturation_10: Saturation factor at transient flux 1.0 pu.
    :param saturation_12: Saturation factor at transient flux 1.2 pu.
    :return: Network-ready native machine template.
    :raises ValueError: Nonfinite values or an invalid physical parameter domain.
    """
    # Reject undefined fits before constructing expressions that contain ratios.
    coefficients: tuple[float, ...] = (frequency, inertia, damping, resistance,
        direct_reactance, quadrature_reactance, transient_reactance, transient_time,
        saturation_10, saturation_12)
    if not all(math.isfinite(value) for value in coefficients):
        raise ValueError('Machine parameters must be finite')
    elif min(frequency, inertia, direct_reactance, quadrature_reactance,
             transient_reactance, transient_time) <= 0 or resistance < 0:
        raise ValueError('Machine frequency, inertia, reactances and time must be positive; resistance nonnegative')
    elif saturation_10 < 0 or saturation_12 < 0 or (saturation_10 > 0 and saturation_12 <= saturation_10):
        raise ValueError('Saturation factors must be nonnegative and increasing')
    elif (saturation_10 == 0) != (saturation_12 == 0):
        raise ValueError('Use two positive saturation factors, or two zeros for an unsaturated machine')
    else:
        pass
    label: str = 'GENTRA' if name is None else name
    realization: ControlRealization = ControlRealization(vf, label)
    block: Block = realization.block
    fn: Var = realization.parameter('FNomHz', frequency)
    h: Var = realization.parameter('H', inertia)
    d: Var = realization.parameter('D', damping)
    ra: Var = realization.parameter('RaPu', resistance)
    xd: Var = realization.parameter('XdPu', direct_reactance)
    xq: Var = realization.parameter('XqPu', quadrature_reactance)
    xdp: Var = realization.parameter('XpdPu', transient_reactance)
    td: Var = realization.parameter('Tpd0', transient_time)
    s10: Var = realization.parameter('S10', saturation_10)
    s12: Var = realization.parameter('S12', saturation_12)
    block.api_obj_mapping[ParamPowerFlowReferenceType.freq] = fn
    vm: Var = vf.add_var('Vm_' + label, reference=VarPowerFlowReferenceType.Vm)
    va: Var = vf.add_var('Va_' + label, reference=VarPowerFlowReferenceType.Va)
    pg: Var = vf.add_var('Pg_' + label, reference=VarPowerFlowReferenceType.P)
    qg: Var = vf.add_var('Qg_' + label, reference=VarPowerFlowReferenceType.Q)
    tm: Var = vf.add_var('Tm_' + label)
    efd: Var = vf.add_var('Efd_' + label)
    delta: Var = vf.add_var('DeltaRad_' + label)
    omega: Var = vf.add_var('OmegaPu_' + label)
    epq: Var = vf.add_var('EpqPu_' + label)
    block.in_vars = [vm, va, tm, efd]

    # Rotor position follows the unsaturated q-axis stator phasor equation.
    voltage: Expr = vm * sym.exp(Const(1j) * va)
    current: Expr = sym.conj((pg + Const(1j)*qg)/voltage)
    internal: Expr = voltage + (ra+Const(1j)*xq)*current
    delta0: Expr = sym.imag(sym.log(internal))
    rotor_current: Expr = current*sym.exp(-Const(1j)*delta)
    id0: Expr = -sym.imag(rotor_current)
    iq0: Expr = sym.real(rotor_current)
    block.init_eqs[vm] = Const(1.0)
    block.init_eqs[va] = Const(0.0)
    block.init_eqs[pg] = Const(0.8)
    block.init_eqs[qg] = Const(0.2)
    vd: Var = realization.algebraic('VdPu',vm*sym.sin(delta-va),vm*sym.sin(delta-va))
    vq: Var = realization.algebraic('VqPu',vm*sym.cos(delta-va),vm*sym.cos(delta-va))
    id_var: Var = vf.add_var('IdPu_' + label)
    iq_var: Var = vf.add_var('IqPu_' + label)
    block.algebraic_vars.extend([id_var, iq_var, pg, qg])
    block.algebraic_eqs.extend([vq+ra*iq_var+xdp*id_var-epq,
        vd+ra*id_var-xq*iq_var, pg-vd*id_var-vq*iq_var, qg-vq*id_var+vd*iq_var])
    block.init_eqs[id_var] = id0
    block.init_eqs[iq_var] = iq0
    sat_flux: Expr
    if saturation_10 == 0 and saturation_12 == 0:
        sat_flux = Const(0.0)
    else:
        threshold: Expr
        gain: Expr
        threshold, gain = _quadratic_saturation_coefficients(s10,s12)
        sat_flux = gain*sym.max(epq-threshold,Const(0.0))**2
    field: Var = realization.algebraic('XadIfdPu',epq+(xd-xdp)*id_var+sat_flux,
        epq+(xd-xdp)*id_var+sat_flux)
    torque: Var = realization.algebraic('TePu',pg+ra*(id_var**2+iq_var**2),
        pg+ra*(id_var**2+iq_var**2))
    # State order and controller ports match the other network-ready machines.
    realization.differential(delta,Const(2*math.pi)*fn*(omega-Const(1.0)),delta0)
    realization.differential(omega,(tm-torque-d*(omega-Const(1.0)))/(Const(2.0)*h),Const(1.0))
    realization.differential(epq,(efd-field)/td,vq+ra*iq_var+xdp*id_var)
    block.init_eqs[tm] = torque
    block.init_eqs[efd] = field
    block.out_vars = [pg,qg,omega,field,torque,vd,vq,id_var,iq_var]
    block.external_mapping = dict([(VarPowerFlowReferenceType.Vm,vm),
        (VarPowerFlowReferenceType.Va,va),(VarPowerFlowReferenceType.P,pg),
        (VarPowerFlowReferenceType.Q,qg)])
    template: RmsModelTemplate = RmsModelTemplate(name=label)
    template.tpe = DeviceType.GeneratorDevice
    template.comment = 'Field-transient salient-pole synchronous machine without damper windings'
    template.block.children = [block]
    template.block.in_vars = [vm,va]
    template.block.out_vars = [pg,qg]
    template.block.external_mapping = dict(block.external_mapping)
    return template
