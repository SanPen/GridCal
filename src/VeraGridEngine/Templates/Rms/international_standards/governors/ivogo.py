# SPDX-License-Identifier: MPL-2.0
"""Three-stage rational speed regulation with balanced turbine-power initialization."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.rational_controller import RationalStageLimiting, RationalStageParameters, build_rational_stage
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var


def rational_steady_input_is_zero(stage: RationalStageParameters, output_is_zero: bool) -> bool:
    """Determine whether equilibrium forces this stage's input to zero.

    :param stage: Physical rational stage coefficients.
    :param output_is_zero: Structural zero requirement from the next stage.
    :return: Required zero input, or the propagated nonzero steady-load status.
    :raises ValueError: A zero-DC stage cannot sustain the required steady output.
    """
    if stage.denominator == 0 and stage.numerator > 0:
        return True
    elif stage.gain != 0 and ((stage.numerator > 0 and stage.denominator > 0) or (
            stage.denominator == 0 and stage.numerator == 0 and stage.lead > 0 and stage.lag > 0)):
        return output_is_zero
    elif output_is_zero:
        return True
    else:
        raise ValueError('A zero-DC governor stage cannot sustain the required nonzero steady power')


def build_ivogo_template(vf: VarFactory, name: str | None = None,
                         stages: tuple[RationalStageParameters,RationalStageParameters,RationalStageParameters] | None = None) -> RmsModelTemplate:
    """Build cascaded speed regulation while preserving each rational stage's memory.

    Absolute shaft speed opposes an absolute speed/load reference. Three stages
    have transfer K*(A+s*L)/(B+s*T). The first two use bounded output-tracking
    recovery; the last has an external output clip around unrestricted memory.
    Stable lags, lead-lags, washouts upstream of a balancing integrator and exact
    constant reductions retain their distinct dynamics. Nonnegative numerator,
    denominator and time coefficients are supported, with signed stage gains.

    Equilibrium is solved backward from actual turbine power. Stable DC gains
    determine preceding demands. An integral stage holds its required steady
    output while forcing zero upstream input. This may store load in a middle
    stage rather than requiring a fictitious steady speed error. A final washout
    without a downstream balancing integrator cannot sustain nonzero steady
    power and is rejected. Initial stage demands are frozen using the actual
    symbolic coefficients and must fit their configured capabilities.

    Inputs are absolute shaft speed and speed/load reference. Outputs are
    mechanical power and mechanical torque on one declared turbine base.
    Torque is power divided by positive absolute speed; the connecting host
    owns conversion to its network base. Times are seconds. Up to three states
    store rational memories. Initial power defaults to 0.5 and is replaced by
    the host operating point; the reference includes any required proportional
    steady-speed offset. Zero stages introduce no artificial small time constant.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique controller label.
    :param stages: Exactly three rational coefficient/capability groups.
    :return: Native speed governor with separate turbine power and torque outputs.
    :raises ValueError: Invalid domains, stage count or an impossible loaded equilibrium.
    """
    settings: tuple[RationalStageParameters,RationalStageParameters,RationalStageParameters] = (
        (RationalStageParameters(20.,1.,1.,.1,.2,1.,-1.),
         RationalStageParameters(1.,1.,0.,0.,1.,1.2,0.),RationalStageParameters(1.,1.,1.,0.,.2,1.2,0.))
        if stages is None else stages)
    if len(settings) != 3:
        raise ValueError('Rational speed regulation requires exactly three stages')
    else:
        pass
    last_zero: bool = rational_steady_input_is_zero(settings[2],False)
    middle_zero: bool = rational_steady_input_is_zero(settings[1],last_zero)
    first_zero: bool = rational_steady_input_is_zero(settings[0],middle_zero)
    c: ControlRealization = ControlRealization(vf,'IVOGO' if name is None else name)
    power0: Var = c.parameter('InitialMechanicalPowerPu',.5)
    first0: Var = c.parameter('Stage1InitialInputPu',0.)
    middle0: Var = c.parameter('Stage3InitialInputPu',0.)
    last0: Var = c.parameter('Stage5InitialInputPu',0.)
    initial_parameter: Var
    for initial_parameter in (first0,middle0,last0):
        c.block.event_dict[initial_parameter] = Const(None)
    speed: Var = c.input('OmegaPu',Const(1.))
    reference: Var = c.input('ReferencePu',Const(1.)+first0)
    signal: Var = c.algebraic('SpeedErrorPu',reference-speed,first0)
    stage_index: int
    p: RationalStageParameters
    input_initial: Var
    input_zero: bool
    target_initial: Var
    limiting: RationalStageLimiting
    initial_output: Expr
    zero_output: bool
    for stage_index,p,input_initial,input_zero,target_initial,limiting in (
            (1,settings[0],first0,first_zero,middle0,RationalStageLimiting.OUTPUT_TRACKING),
            (3,settings[1],middle0,middle_zero,last0,RationalStageLimiting.OUTPUT_TRACKING),
            (5,settings[2],last0,last_zero,power0,RationalStageLimiting.OUTPUT_ONLY)):
        signal,initial_output,zero_output = build_rational_stage(c,stage_index,signal,input_initial,input_zero,p,limiting,
            target_initial if p.denominator == 0 and p.numerator > 0 else None)
    # Initial demands use the same symbolic coefficients as runtime equations.
    coefficients: dict[str,Var] = dict((variable.name,variable) for variable in c.block.event_dict)
    for stage_index,p,input_initial,target_initial in (
            (5,settings[2],last0,power0),(3,settings[1],middle0,last0),(1,settings[0],first0,middle0)):
        k: Var = coefficients['K'+str(stage_index)+'_'+c.name]
        a: Var = coefficients['A'+str(stage_index)+'_'+c.name]
        b: Var = coefficients['A'+str(stage_index+1)+'_'+c.name]
        lead: Var = coefficients['T'+str(stage_index)+'_'+c.name]
        lag: Var = coefficients['T'+str(stage_index+1)+'_'+c.name]
        if p.denominator == 0 and p.numerator > 0:
            c.block.init_eqs[input_initial] = Const(0.)
        elif p.denominator == 0 and p.numerator == 0 and p.lead > 0 and p.gain != 0:
            c.block.init_eqs[input_initial] = lag/(k*lead)*target_initial
        elif p.numerator > 0 and p.denominator > 0 and p.gain != 0:
            c.block.init_eqs[input_initial] = b/(k*a)*target_initial
        else:
            c.block.init_eqs[input_initial] = Const(0.)
    power: Var = c.algebraic('MechanicalPowerPu',signal,power0)
    torque: Var = c.algebraic('MechanicalTorquePu',power/speed,power0)
    return c.finish((power,torque),'Three-stage rational speed regulation with balanced turbine power and separate shaft torque')
