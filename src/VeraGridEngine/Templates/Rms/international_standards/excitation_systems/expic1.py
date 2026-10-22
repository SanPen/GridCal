# SPDX-License-Identifier: MPL-2.0
"""PI excitation with shaped regulator feedback and explicit compound-source field forcing."""
from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Rms.control_realization import ControlRealization
from VeraGridEngine.Templates.Rms.genrou_exc_gov_rms_template import _esst3a_fex
from VeraGridEngine.Templates.Rms.ieeex1_ieeest_rms_template import _quadratic_saturation_coefficients
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
import VeraGridEngine.Utils.Symbolic.symbolic as sym


class PiCompoundFieldParameters:
    """Physical PI, regulator filters, source and rotating-field coefficients."""
    __slots__ = ('tr','ka','ta1','vr1','vr2','ta2','ta3','ta4','vrmax','vrmin','kf','tf1','tf2','efdmax','efdmin','ke','te','e1','se1','e2','se2','kp','ki','kc')

    def __init__(self, tr: float = .02, ka: float = 20., ta1: float = .1, vr1: float = 5.,
                 vr2: float = -5., ta2: float = .05, ta3: float = .02, ta4: float = .03,
                 vrmax: float = 5., vrmin: float = -5., kf: float = .05, tf1: float = 1.,
                 tf2: float = .1, efdmax: float = 5., efdmin: float = -5., ke: float = 1.,
                 te: float = .5, e1: float = 3., se1: float = .1, e2: float = 4.,
                 se2: float = .3, kp: float = 0., ki: float = 0., kc: float = .1) -> None:
        """Store explicit coefficients in compatible per-unit field bases.

        :param tr: Nonnegative sensing lag, seconds.
        :param ka: Positive PI integral gain.
        :param ta1: Nonnegative PI lead time, seconds.
        :param vr1: Upper total PI demand.
        :param vr2: Lower total PI demand.
        :param ta2: First nonnegative regulator lag, seconds.
        :param ta3: Nonnegative regulator lead, seconds.
        :param ta4: Second nonnegative regulator lag, seconds.
        :param vrmax: Upper external regulator capability.
        :param vrmin: Lower external regulator capability.
        :param kf: Nonnegative regulator-rate feedback gain.
        :param tf1: Positive washout time, seconds.
        :param tf2: Nonnegative second feedback lag, seconds.
        :param efdmax: Upper field-forcing bound.
        :param efdmin: Lower field-forcing bound.
        :param ke: Field-resistance coefficient.
        :param te: Nonnegative field time; zero selects direct forcing.
        :param e1: First positive saturation-sample voltage.
        :param se1: First nonnegative saturation factor.
        :param e2: Second saturation-sample voltage.
        :param se2: Second nonnegative saturation factor.
        :param kp: Nonnegative potential-source ratio.
        :param ki: Nonnegative current-compounding ratio.
        :param kc: Nonnegative commutation coefficient.
        """
        self.tr: float = tr
        self.ka: float = ka
        self.ta1: float = ta1
        self.vr1: float = vr1
        self.vr2: float = vr2
        self.ta2: float = ta2
        self.ta3: float = ta3
        self.ta4: float = ta4
        self.vrmax: float = vrmax
        self.vrmin: float = vrmin
        self.kf: float = kf
        self.tf1: float = tf1
        self.tf2: float = tf2
        self.efdmax: float = efdmax
        self.efdmin: float = efdmin
        self.ke: float = ke
        self.te: float = te
        self.e1: float = e1
        self.se1: float = se1
        self.e2: float = e2
        self.se2: float = se2
        self.kp: float = kp
        self.ki: float = ki
        self.kc: float = kc


def build_expic1_template(vf: VarFactory, name: str | None = None,
                         parameters: PiCompoundFieldParameters | None = None) -> RmsModelTemplate:
    """Build bounded PI excitation with regulator-rate feedback and compound supply.

    Sensed-voltage error plus additive auxiliary voltage opposes shaped rate
    feedback. A parallel PI KA*(1+s*TA1)/s has its own total-demand bounds VR2/VR1
    and directional integral antiwindup. A following regulator transfer
    (1+s*TA3)/((1+s*TA2)*(1+s*TA4)) retains separate memory and external
    VRMIN/VRMAX clipping. Rate feedback senses the bounded regulator through
    KF*s/((1+s*TF1)*(1+s*TF2)), before multiplication by its actual supply.
    The downstream regulator clip does not freeze the upstream PI or filter
    memories beyond the PI's own declared bounds.

    Source potential is abs(KP*V+j*KI*I). Field-current commutation loads the
    existing piecewise diode characteristic. When both source ratios are zero,
    supply is exactly unity. Rectified supply times regulator demand is bounded
    by EFDMIN/EFDMAX before driving field resistance and quadratic saturation.
    These are forcing bounds, not an invented field-memory clamp. TE=0 instead
    selects delivered field equal to bounded forcing, bypassing field losses.

    Nine inputs are sensed voltage, reference, stabilizer, rectangular terminal
    voltage, rectangular outgoing stator current, field current and additive
    minimum-excitation voltage. Outputs are field and bounded regulator voltage.
    Seven states remain with active positive lags and field time. Supported
    zero lags remove memories exactly, and at least one regulator denominator
    time is needed for a nonzero lead. The two regulator poles can exchange
    realization order without changing their physical transfer.

    Initialization balances actual field forcing and loaded supply, stores
    required regulator demand in PI memory and derives the voltage reference
    including auxiliary biases. A feasible point must respect each independent
    capability and have positive supply for a nonzero field. Voltages/currents
    are per unit on compatible connected bases, and times are seconds.

    :param vf: Shared native symbolic factory.
    :param name: Optional unique controller label.
    :param parameters: Explicit PI, filter, field and supply coefficients.
    :return: Native PI/compound-source excitation controller.
    :raises ValueError: Invalid physical coefficients, improper filters or saturation.
    """
    p: PiCompoundFieldParameters = PiCompoundFieldParameters() if parameters is None else parameters
    if min(p.tr,p.ta1,p.ta2,p.ta3,p.ta4,p.kf,p.tf2,p.te,p.e1,p.se1,p.e2,p.se2,p.kp,p.ki,p.kc) < 0 or min(p.ka,p.tf1) <= 0:
        raise ValueError('PI compound excitation coefficients have invalid physical domains')
    elif p.vr1 <= p.vr2 or p.vrmax <= p.vrmin or p.efdmax <= p.efdmin:
        raise ValueError('PI, regulator and field-forcing limits must each be ordered')
    elif p.ta2 == 0 and p.ta4 == 0 and p.ta3 != 0:
        raise ValueError('A regulator lead requires a positive denominator time')
    elif p.te > 0 and (p.se1 != 0 or p.se2 != 0) and (p.e1 <= 0 or p.e2 <= p.e1 or p.e2*p.se2 <= p.e1*p.se1):
        raise ValueError('Enabled saturation requires increasing voltage and loss samples')
    else:
        pass
    c: ControlRealization = ControlRealization(vf,'EXPIC1' if name is None else name)
    tr: Var = c.parameter('TR',p.tr)
    ka: Var = c.parameter('KA',p.ka)
    ta1: Var = c.parameter('TA1',p.ta1)
    vr1: Var = c.parameter('VR1',p.vr1)
    vr2: Var = c.parameter('VR2',p.vr2)
    ta2: Var = c.parameter('TA2',p.ta2)
    ta3: Var = c.parameter('TA3',p.ta3)
    ta4: Var = c.parameter('TA4',p.ta4)
    vrmax: Var = c.parameter('VRMAX',p.vrmax)
    vrmin: Var = c.parameter('VRMIN',p.vrmin)
    kf: Var = c.parameter('KF',p.kf)
    tf1: Var = c.parameter('TF1',p.tf1)
    tf2: Var = c.parameter('TF2',p.tf2)
    efdmax: Var = c.parameter('EFDMAX',p.efdmax)
    efdmin: Var = c.parameter('EFDMIN',p.efdmin)
    ke: Var = c.parameter('KE',p.ke)
    te: Var = c.parameter('TE',p.te)
    e1: Var = c.parameter('E1',p.e1)
    se1: Var = c.parameter('SE1',p.se1)
    e2: Var = c.parameter('E2',p.e2)
    se2: Var = c.parameter('SE2',p.se2)
    kp: Var = c.parameter('KP',p.kp)
    ki: Var = c.parameter('KI',p.ki)
    kc: Var = c.parameter('KC',p.kc)
    field0: Var = c.parameter('Efd0Pu',1.)
    voltage0: Var = c.parameter('Us0Pu',1.)
    supplement0: Var = c.parameter('Vs0Pu',0.)
    minimum0: Var = c.parameter('Uel0Pu',0.)
    sensed: Var = c.input('UsPu',voltage0)
    reference: Var = c.input('UsRefPu',voltage0-supplement0-minimum0)
    supplement: Var = c.input('VsPu',supplement0)
    vr: Var = c.input('VrPu',Const(1.))
    vi: Var = c.input('ViPu',Const(0.))
    ir: Var = c.input('IrPu',Const(.5))
    ii: Var = c.input('IiPu',Const(0.))
    current: Var = c.input('IfdPu',Const(1.))
    minimum: Var = c.input('UelPu',minimum0)
    if p.kp == 0 and p.ki == 0:
        supply: Var = c.algebraic('SupplyPu',Const(1.),Const(1.))
    else:
        potential_expression: Expr = sym.sqrt((kp*vr-ki*ii)**2+(kp*vi+ki*ir)**2)
        potential: Var = c.algebraic('PotentialPu',potential_expression,potential_expression)
        loading: Expr = sym.safe_divide(kc*current,potential,1.)
        supply = c.algebraic('SupplyPu',potential*_esst3a_fex(loading),potential*_esst3a_fex(loading))
    field: Var = vf.add_var('EfdPu_'+c.name)
    loss: Expr
    loss0: Expr
    if p.te == 0 or p.se1 == 0 and p.se2 == 0:
        loss = Const(0.)
        loss0 = Const(0.)
    else:
        threshold: Expr
        saturation_gain: Expr
        threshold,saturation_gain = _quadratic_saturation_coefficients(e1,se1,e2,se2)
        loss = saturation_gain*sym.max(field-threshold,Const(0.))**2
        loss0 = saturation_gain*sym.max(field0-threshold,Const(0.))**2
    forcing0: Expr = ke*field0+loss0 if p.te > 0 else field0
    regulator0: Expr = forcing0/supply
    regulator: Var = vf.add_var('RegulatorPu_'+c.name)
    measured: Var = c.lag('MeasuredPu',sensed,tr,p.tr,voltage0)
    rate: Var = c.washout('RatePu',regulator,tf1,p.tf1,kf/tf1,regulator0)
    feedback: Var = c.lag('FeedbackPu',rate,tf2,p.tf2,Const(0.))
    error: Expr = reference+supplement+minimum-measured-feedback
    proportional: Expr = ka*ta1*error
    integral: Var = c.differential(vf.add_var('PiIntegralPu_'+c.name),ka*error,regulator0,
        vr2-proportional,vr1-proportional)
    pi_demand: Var = c.algebraic('PiDemandPu',sym.hard_sat(proportional+integral,vr2,vr1),regulator0)
    if p.ta2 > 0 or p.ta4 == 0:
        phase: Var = c.lead_lag('RegulatorLeadPu',pi_demand,ta3,ta2,p.ta3,p.ta2,regulator0)
        shaped: Var = c.lag('RegulatorLagPu',phase,ta4,p.ta4,regulator0)
    else:
        # The transfer's denominator factors commute; no differentiator is introduced.
        phase = c.lead_lag('RegulatorLeadPu',pi_demand,ta3,ta4,p.ta3,p.ta4,regulator0)
        shaped = c.lag('RegulatorLagPu',phase,ta2,p.ta2,regulator0)
    c.block.algebraic_vars.append(regulator)
    c.block.algebraic_eqs.append(regulator-sym.hard_sat(shaped,vrmin,vrmax))
    c.block.init_eqs[regulator] = regulator0
    forcing: Var = c.algebraic('FieldForcingPu',sym.hard_sat(supply*regulator,efdmin,efdmax),forcing0)
    if p.te > 0:
        c.differential(field,(forcing-ke*field-loss)/te,field0)
    else:
        c.block.algebraic_vars.append(field)
        c.block.algebraic_eqs.append(field-forcing)
        c.block.init_eqs[field] = field0
    return c.finish((field,regulator),'PI excitation with shaped regulator feedback and explicit compound-source forcing')
