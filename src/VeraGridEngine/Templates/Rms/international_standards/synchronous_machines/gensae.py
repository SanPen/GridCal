# SPDX-License-Identifier: MPL-2.0
"""Salient-pole machine with one quadrature damper and two-axis power-law saturation."""
from __future__ import annotations

import math
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import (
    GenrouRmsParameters, GenrouSaturationMode, configure_genrou_block, get_genrou_rms_template,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var


def build_gensae_template(vf: VarFactory, name: str | None = None, frequency: float = 60.0,
                           damping: float = 0.0, inertia: float = 8.0,
                           resistance: float = 0.0, leakage: float = .15,
                           xd_transient: float = .3, saturation1: float = .09,
                           saturation12: float = .38, xd: float = 1.8, xq: float = 1.75,
                           x_subtransient: float = .23, td_transient: float = 6.5,
                           td_subtransient: float = .06, tq_subtransient: float = .05) -> RmsModelTemplate:
    """Build a five-state salient-pole synchronous machine with saturated magnetic axes.

    Rotor angle and speed, direct-axis transient voltage, direct-axis damper flux
    and quadrature subtransient flux are the five differential states. The stator
    retains resistance and saliency, with equal direct/quadrature subtransient
    reactances. The magnetic factor is ``S=S1*psi**n``, where
    ``n=log(S12/S1)/log(1.2)`` and ``psi`` is resultant subtransient flux magnitude.
    Both zero samples select an exactly unsaturated structure.

    Direct-axis field-current demand includes ``S*psi_d``. The single quadrature
    damper obeys ``Tq*d(psi_q)/dt=(Xq-Xsub)*Iq-psi_q-S*psi_q*(Xq-Xl)/(Xd-Xl)``.
    There is no quadrature transient circuit, transient state or transient time
    constant. In particular, the quadrature saturation term is not represented
    by a vanishing transient lag. Shared stator and direct-axis winding equations
    are retained while the quadrature damper is an explicit flux state.

    Inputs are terminal voltage magnitude/angle, mechanical torque and field
    voltage. Outputs include P/Q, absolute rotor speed, field-current equivalent,
    electrical torque and rotor-frame terminal phasors for native controllers.
    Saturated initialization derives rotor angle and both flux components from
    terminal P/Q and the resultant internal flux. It balances both magnetic axes
    at the supplied operating point. Angles are electrical radians; times are
    seconds; reactances, resistance, torque and inertia share the chosen network
    power base. The inertia coefficient is twice the inertia constant on that base.

    :param vf: Shared symbolic factory.
    :param name: Optional instance label.
    :param frequency: Positive nominal network frequency in hertz.
    :param damping: Rotor damping on the selected network base.
    :param inertia: Positive swing-equation inertia coefficient, twice H.
    :param resistance: Armature resistance on the selected base.
    :param leakage: Leakage reactance on the selected base.
    :param xd_transient: Direct-axis transient reactance.
    :param saturation1: Saturation factor at unit resultant flux.
    :param saturation12: Saturation factor at resultant flux 1.2 per unit.
    :param xd: Direct-axis synchronous reactance.
    :param xq: Quadrature-axis synchronous reactance.
    :param x_subtransient: Common direct/quadrature subtransient reactance.
    :param td_transient: Positive direct-axis transient open-circuit time.
    :param td_subtransient: Positive direct-axis damper open-circuit time.
    :param tq_subtransient: Positive quadrature damper open-circuit time.
    :return: Network-ready native five-state synchronous machine.
    :raises ValueError: Invalid coefficient domains or undefined saturation samples.
    """
    values: tuple[float, ...] = (frequency, damping, inertia, resistance, leakage,
        xd_transient, saturation1, saturation12, xd, xq, x_subtransient,
        td_transient, td_subtransient, tq_subtransient)
    if (not all(math.isfinite(value) for value in values) or
            min(frequency, inertia, xd_transient, xd, xq, x_subtransient,
                td_transient, td_subtransient, tq_subtransient) <= 0 or
            min(resistance, leakage) < 0 or xd_transient == leakage or xd == leakage):
        raise ValueError('Salient-pole machine coefficients have invalid domains')
    elif (saturation1 != 0 or saturation12 != 0) and not 0 < saturation1 < saturation12:
        raise ValueError('Power-law saturation requires two increasing positive samples or two zeros')
    else:
        pass
    label: str = 'GENSAE' if name is None else name
    mode: GenrouSaturationMode = GenrouSaturationMode.DISABLED if saturation1 == 0 else GenrouSaturationMode.POWER_LAW
    template: RmsModelTemplate = get_genrou_rms_template(vf, label, mode)
    block: Block = template.block.children[0]
    # Configure shared stator, direct-axis and initialization equations before
    # removing the quadrature transient circuit from the assembled graph.
    configure_genrou_block(block, GenrouRmsParameters(frequency, damping, inertia,
        resistance, leakage, xd_transient, saturation1, saturation12, xd, xq,
        x_subtransient, xq, x_subtransient, td_transient, td_subtransient, 1.0, tq_subtransient), vf)
    variables: dict[str, Var] = dict((variable.name, variable) for variable in block.get_all_vars())
    variables.update((variable.name, variable) for variable in block.event_dict)
    retained_states: tuple[tuple[Var, Expr], ...] = tuple((variable, equation)
        for variable, equation in zip(block.state_vars, block.state_eqs)
        if variable.name not in ('e1d', 'e2q'))
    block.state_vars = [variable for variable, _ in retained_states]
    block.state_eqs = [equation for _, equation in retained_states]
    retained_algebraic: tuple[tuple[Var, Expr], ...] = tuple((variable, equation)
        for variable, equation in zip(block.algebraic_vars, block.algebraic_eqs)
        if variable.name not in ('psi2q', 'XaqI1q'))
    block.algebraic_vars = [variable for variable, _ in retained_algebraic]
    block.algebraic_eqs = [equation for _, equation in retained_algebraic]
    flux_q: Var = variables['psi2q']
    block.state_vars.append(flux_q)
    block.state_eqs.append(((variables['Xq']-variables['Xq_2prime'])*variables['Iq']-flux_q
        -variables['Se']*flux_q*(variables['Xq']-variables['Xl'])/(variables['Xd']-variables['Xl']))
        /variables['Tq0_2prime'])
    block.diff_vars = [vf.add_diff_var('d_'+variable.name+'_'+label, base_var=variable)
                       for variable in block.state_vars]
    for removed in ('e1d', 'e2q', 'XaqI1q'):
        block.init_eqs.pop(variables[removed], None)
    for removed in ('Xq_prime', 'Tq0_prime'):
        block.event_dict.pop(variables[removed], None)
    # Equal subtransient reactances remain a live native identity, not two
    # coincident construction defaults that could later drift independently.
    block.event_dict[variables['Xq_2prime']] = variables['Xd_2prime']
    template.comment = 'Salient-pole synchronous machine with two-axis power-law saturation'
    return template
