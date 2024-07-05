# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from enum import Enum


class BusMode(Enum):
    """
    Emumetarion of bus modes
    """
    PQ = 1  # control P, Q
    PV = 2  # Control P, Vm
    Slack = 3  # Contol Vm, Va (slack)
    PQV = 4  # control P, Q and Vm
    D = 5  # only control the voltage angle (Va)

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return BusMode[s]
        except KeyError:
            return s


class CpfStopAt(Enum):
    """
    CpfStopAt
    """
    Nose = 'Nose'
    ExtraOverloads = 'Extra overloads'
    Full = 'Full curve'


class CpfParametrization(Enum):
    """
    CpfParametrization
    """
    Natural = 'Natural'
    ArcLength = 'Arc Length'
    PseudoArcLength = 'Pseudo Arc Length'


class ExternalGridMode(Enum):
    """
    Modes of operation of external grids
    """
    PQ = "PQ"
    PV = "PV"
    VD = "VD"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ExternalGridMode[s]
        except KeyError:
            return s


class InvestmentEvaluationMethod(Enum):
    """
    Investment evaluation methods
    """
    Independent = "Independent"
    Hyperopt = "Hyperopt"
    MVRSM = "MVRSM"
    NSGA3 = "NSGA3"
    Random = "Random"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return InvestmentEvaluationMethod[s]
        except KeyError:
            return s


class BranchImpedanceMode(Enum):
    """
    Enumeration of branch impedance modes
    """
    Specified = 0
    Upper = 1
    Lower = 2

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return BranchImpedanceMode[s]
        except KeyError:
            return s


class SolverType(Enum):
    """
    Refer to the :ref:`Power Flow section<power_flow>` for details about the different
    algorithms supported by **GridCal**.
    """

    NR = 'Newton Raphson'
    NRD = 'Newton Raphson Decoupled'
    NRFD_XB = 'Fast decoupled XB'
    NRFD_BX = 'Fast decoupled BX'
    GAUSS = 'Gauss-Seidel'
    DC = 'Linear DC'
    HELM = 'Holomorphic Embedding'
    ZBUS = 'Z-Gauss-Seidel'
    PowellDogLeg = "Powell's Dog Leg"
    IWAMOTO = 'Iwamoto-Newton-Raphson'
    CONTINUATION_NR = 'Continuation-Newton-Raphson'
    HELMZ = 'HELM-Z'
    LM = 'Levenberg-Marquardt'
    FASTDECOUPLED = 'Fast decoupled'
    LACPF = 'Linear AC'
    LINEAR_OPF = 'Linear OPF'
    NONLINEAR_OPF = 'Nonlinear OPF'
    SIMPLE_OPF = 'Simple dispatch'
    Proportional_OPF = 'Proportional OPF'
    NRI = 'Newton-Raphson in current'
    DYCORS_OPF = 'DYCORS OPF'
    GA_OPF = 'Genetic Algorithm OPF'
    NELDER_MEAD_OPF = 'Nelder Mead OPF'
    BFS = 'Backwards-Forward substitution'
    BFS_linear = 'Backwards-Forward substitution (linear)'
    Constant_Impedance_linear = 'Constant impedance linear'
    NoSolver = 'No Solver'

    def __str__(self) -> str:
        """

        :return:
        """
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return SolverType[s]
        except KeyError:
            return s


class ReactivePowerControlMode(Enum):
    """
    The :ref:`ReactivePowerControlMode<q_control>` offers 3 modes to control how
    :ref:`Generator<generator>` objects supply reactive power:

    **NoControl**: In this mode, the :ref:`generators<generator>` don't try to regulate
    the voltage at their :ref:`bus<bus>`.

    **Direct**: In this mode, the :ref:`generators<generator>` try to regulate the
    voltage at their :ref:`bus<bus>`. **GridCal** does so by applying the following
    algorithm in an outer control loop. For grids with numerous
    :ref:`generators<generator>` tied to the same system, for example wind farms, this
    control method sometimes fails with some :ref:`generators<generator>` not trying
    hard enough*. In this case, the simulation converges but the voltage controlled
    :ref:`buses<bus>` do not reach their target voltage, while their
    :ref:`generator(s)<generator>` haven't reached their reactive power limit. In this
    case, the slower **Iterative** control mode may be used (see below).

        ON PV-PQ BUS TYPE SWITCHING LOGIC IN POWER FLOW COMPUTATION
        Jinquan Zhao

        1) Bus i is a PQ bus in the previous iteration and its
           reactive power was fixed at its lower limit:

            If its voltage magnitude Vi >= Viset, then

                it is still a PQ bus at current iteration and set Qi = Qimin .

                If Vi < Viset , then

                    compare Qi with the upper and lower limits.

                    If Qi >= Qimax , then
                        it is still a PQ bus but set Qi = Qimax .
                    If Qi <= Qimin , then
                        it is still a PQ bus and set Qi = Qimin .
                    If Qimin < Qi < Qi max , then
                        it is switched to PV bus, set Vinew = Viset.

        2) Bus i is a PQ bus in the previous iteration and
           its reactive power was fixed at its upper limit:

            If its voltage magnitude Vi <= Viset , then:
                bus i still a PQ bus and set Q i = Q i max.

                If Vi > Viset , then

                    Compare between Qi and its upper/lower limits

                    If Qi >= Qimax , then
                        it is still a PQ bus and set Q i = Qimax .
                    If Qi <= Qimin , then
                        it is still a PQ bus but let Qi = Qimin in current iteration.
                    If Qimin < Qi < Qimax , then
                        it is switched to PV bus and set Vinew = Viset

        3) Bus i is a PV bus in the previous iteration.

            Compare Q i with its upper and lower limits.

            If Qi >= Qimax , then
                it is switched to PQ and set Qi = Qimax .
            If Qi <= Qimin , then
                it is switched to PQ and set Qi = Qimin .
            If Qi min < Qi < Qimax , then
                it is still a PV bus.

    **Iterative**: As mentioned above, the **Direct** control mode may not yield
    satisfying results in some isolated cases. The **Direct** control mode tries to
    jump to the final solution in a single or few iterations, but in grids where a
    significant change in reactive power at one :ref:`generator<generator>` has a
    significant impact on other :ref:`generators<generator>`, additional iterations may
    be required to reach a satisfying solution.

    Instead of trying to jump to the final solution, the **Iterative** mode raises or
    lowers each :ref:`generator's<generator>` reactive power incrementally. The
    increment is determined using a logistic function based on the difference between
    the current :ref:`bus<bus>` voltage its target voltage. The steepness factor
    :code:`k` of the logistic function was determined through trial and error, with the
    intent of reducing the number of iterations while avoiding instability. Other
    values may be specified in :ref:`PowerFlowOptions<pf_options>`.

    The :math:`Q_{Increment}` in per unit is determined by:

    .. math::

        Q_{Increment} = 2 * \\left[\\frac{1}{1 + e^{-k|V_2 - V_1|}}-0.5\\right]

    Where:

        k = 30 (by default)

    """
    NoControl = "NoControl"
    Direct = "Direct"
    Iterative = "Iterative"


class TapsControlMode(Enum):
    """
    The :ref:`TapsControlMode<taps_control>` offers 3 modes to control how
    :ref:`transformers<transformer>`' :ref:`tap changer<tap_changer>` regulate
    voltage on their regulated :ref:`bus<bus>`:

    **NoControl**: In this mode, the :ref:`transformers<transformer>` don't try to
    regulate the voltage at their :ref:`bus<bus>`.

    **Direct**: In this mode, the :ref:`transformers<transformer>` try to regulate
    the voltage at their bus. **GridCal** does so by jumping straight to the tap that
    corresponds to the desired transformation ratio, or the highest or lowest tap if
    the desired ratio is outside of the tap range.

    This behavior may fail in certain cases, especially if both the
    :ref:`TapControlMode<taps_control>` and :ref:`ReactivePowerControlMode<q_control>`
    are set to **Direct**. In this case, the simulation converges but the voltage
    controlled :ref:`buses<bus>` do not reach their target voltage, while their
    :ref:`generator(s)<generator>` haven't reached their reactive power limit. When
    this happens, the slower **Iterative** control mode may be used (see below).

    **Iterative**: As mentioned above, the **Direct** control mode may not yield
    satisfying results in some isolated cases. The **Direct** control mode tries to
    jump to the final solution in a single or few iterations, but in grids where a
    significant change of tap at one :ref:`transformer<transformer>` has a
    significant impact on other :ref:`transformers<transformer>`, additional
    iterations may be required to reach a satisfying solution.

    Instead of trying to jump to the final solution, the **Iterative** mode raises or
    lowers each :ref:`transformer's<transformer>` tap incrementally.
    """

    NoControl = "NoControl"
    Direct = "Direct"
    Iterative = "Iterative"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return TapsControlMode[s]
        except KeyError:
            return s


class SyncIssueType(Enum):
    """
    Sync issues enumeration
    """
    Added = 'Added'
    Deleted = 'Deleted'
    Conflict = 'Conflict'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return SyncIssueType[s]
        except KeyError:
            return s


class EngineType(Enum):
    """
    Available engines enumeration
    """
    GridCal = 'GridCal'
    Bentayga = 'Bentayga'
    NewtonPA = 'Newton Power Analytics'
    PGM = 'Power Grid Model'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return EngineType[s]
        except KeyError:
            return s


class MIPSolvers(Enum):
    """
    MIP solvers enumeration
    """
    GLOP = "GLOP"
    CBC = 'CBC'
    HIGHS = 'HIGHS'
    SCIP = 'SCIP'
    CPLEX = 'CPLEX'
    GUROBI = 'GUROBI'
    XPRESS = 'XPRESS'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return MIPSolvers[s]
        except KeyError:
            return s


class TimeGrouping(Enum):
    """
    Time groupings enumeration
    """
    NoGrouping = 'No grouping'
    Monthly = 'Monthly'
    Weekly = 'Weekly'
    Daily = 'Daily'
    Hourly = 'Hourly'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return TimeGrouping[s]
        except KeyError:
            return s


class ZonalGrouping(Enum):
    """
    Zonal groupings enumeration
    """
    NoGrouping = 'No grouping'
    Area = 'Area'
    All = 'All (copper plate)'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ZonalGrouping[s]
        except KeyError:
            return s


class ContingencyMethod(Enum):
    """
    Enumeratio of contingency calculation engines
    """
    PowerFlow = 'Power flow'
    OptimalPowerFlow = 'Optimal power flow'
    HELM = 'HELM'
    PTDF = 'PTDF'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ZonalGrouping[s]
        except KeyError:
            return s


class DiagramType(Enum):
    """
    Types of diagrams
    """
    Schematic = 'schematic'
    SubstationLineMap = 'substation-line-map'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return DiagramType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class AcOpfMode(Enum):
    """
    AC-OPF problem types
    """
    ACOPFstd = 'ACOPFstd'
    ACOPFslacks = 'ACOPFslacks'
    ACOPFMaxInjections = 'ACOPFMaxInjections'

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return AcOpfMode[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class TransformerControlType(Enum):
    """
    Transformer control types
    """
    fixed = '0:Fixed'
    Pf = '1:Pf'
    Qt = '2:Qt'
    PtQt = '3:Pt+Qt'
    V = '4:V'
    PtV = '5:Pt+V'

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return TransformerControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class TapModuleControl(Enum):
    """
    Tap module control types
    """
    fixed = 'Fixed'
    Vm = 'Vm'
    Qf = 'Qf'
    Qt = 'Qt'

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return TapModuleControl[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class TapAngleControl(Enum):
    """
    Tap angle control types
    """
    fixed = 'Fixed'
    Pf = 'Pf'
    Pt = 'Pt'

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return TapAngleControl[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class ConverterControlType(Enum):
    """
    Converter control types
    """
    # Type I
    # theta_vac = '1:Angle+Vac'
    # pf_qac = '2:Pflow + Qflow'
    # pf_vac = '3:Pflow + Vac'
    #
    # # Type II
    # vdc_qac = '4:Vdc+Qflow'
    # vdc_vac = '5:Vdc+Vac'
    #
    # # type III
    # vdc_droop_qac = '6:VdcDroop+Qac'
    # vdc_droop_vac = '7:VdcDroop+Vac'

    type_0_free = '0:Free'

    type_I_1 = '1:Vac'
    type_I_2 = '2:Pdc+Qac'
    type_I_3 = '3:Pdc+Vac'

    type_II_4 = '4:Vdc+Qac'
    type_II_5 = '5:Vdc+Vac'

    type_III_6 = '6:Droop+Qac'
    type_III_7 = '7:Droop+Vac'

    type_IV_I = '8:Vdc'
    type_IV_II = '9:Pdc'

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ConverterControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class HvdcControlType(Enum):
    """
    Simple HVDC control types
    """
    type_0_free = '0:Free'
    type_1_Pset = '1:Pdc'

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ConverterControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class GenerationNtcFormulation(Enum):
    """
    NTC formulation type
    """
    Proportional = 'Proportional'
    Optimal = 'Optimal'


class TimeFrame(Enum):
    """
    Time frame
    """
    Continuous = 'Continuous'


class FaultType(Enum):
    """
    Short circuit type
    """
    ph3 = '3x'
    LG = 'LG'
    LL = 'LL'
    LLG = 'LLG'

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return FaultType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class WindingsConnection(Enum):
    """
    Transformer windings connection types
    """
    # G: grounded star
    # S: ungrounded star
    # D: delta
    GG = 'GG'
    GS = 'GS'
    GD = 'GD'
    SS = 'SS'
    SD = 'SD'
    DD = 'DD'

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return WindingsConnection[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class ActionType(Enum):
    """
    ActionType
    """
    NoAction = 'No action'
    Add = 'Add'
    Modify = 'Modify'
    Delete = 'Delete'

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ActionType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class DeviceType(Enum):
    """
    Device types
    """
    NoDevice = "NoDevice"
    TimeDevice = "Time"
    CircuitDevice = 'Circuit'
    BusDevice = 'Bus'
    BranchDevice = 'Branch'
    BranchTypeDevice = 'Branch template'
    LineDevice = 'Line'
    LineTypeDevice = 'Line Template'
    Transformer2WDevice = 'Transformer'
    Transformer3WDevice = 'Transformer3W'
    WindingDevice = 'Winding'
    SeriesReactanceDevice = 'Series reactance'
    HVDCLineDevice = 'HVDC Line'
    DCLineDevice = 'DC line'
    VscDevice = 'VSC'
    BatteryDevice = 'Battery'
    LoadDevice = 'Load'
    CurrentInjectionDevice = 'Current injection'
    ControllableShuntDevice = 'Controllable shunt'
    GeneratorDevice = 'Generator'
    StaticGeneratorDevice = 'Static Generator'
    ShuntDevice = 'Shunt'
    UpfcDevice = 'UPFC'  # unified power flow controller
    ExternalGridDevice = 'External grid'
    LoadLikeDevice = 'Load like'
    BranchGroupDevice = 'Branch group'
    LambdaDevice = r"Loading from the base situation ($\lambda$)"

    PiMeasurementDevice = 'Pi Measurement'
    QiMeasurementDevice = 'Qi Measurement'
    PfMeasurementDevice = 'Pf Measurement'
    QfMeasurementDevice = 'Qf Measurement'
    VmMeasurementDevice = 'Vm Measurement'
    IfMeasurementDevice = 'If Measurement'

    WireDevice = 'Wire'
    SequenceLineDevice = 'Sequence line'
    UnderGroundLineDevice = 'Underground line'
    OverheadLineTypeDevice = 'Tower'
    TransformerTypeDevice = 'Transformer type'
    SwitchDevice = 'Switch'

    GenericArea = 'Generic Area'
    SubstationDevice = 'Substation'
    ConnectivityNodeDevice = 'Connectivity Node'
    AreaDevice = 'Area'
    ZoneDevice = 'Zone'
    CountryDevice = 'Country'
    CommunityDevice = 'Comunity'
    RegionDevice = 'Region'
    MunicipalityDevice = 'Municipality'
    BusBarDevice = 'BusBar'
    VoltageLevelDevice = 'Voltage level'

    Technology = 'Technology'
    TechnologyGroup = 'Technology Group'
    TechnologyCategory = 'Technology Category'

    ContingencyDevice = 'Contingency'
    ContingencyGroupDevice = 'Contingency Group'

    InvestmentDevice = 'Investment'
    InvestmentsGroupDevice = 'Investments Group'

    FuelDevice = 'Fuel'
    EmissionGasDevice = 'Emission'

    GeneratorEmissionAssociation = 'Generator Emission'
    GeneratorFuelAssociation = 'Generator Fuel'
    GeneratorTechnologyAssociation = 'Generator Technology'

    DiagramDevice = 'Diagram'

    FluidInjectionDevice = 'Fluid Injection'
    FluidTurbineDevice = 'Fluid Turbine'
    FluidPumpDevice = 'Fluid Pump'
    FluidP2XDevice = 'Fluid P2X'
    FluidPathDevice = 'Fluid path'
    FluidNodeDevice = 'Fluid node'

    LineLocation = "Line Location"
    LineLocations = "Line Locations"

    ModellingAuthority = "Modelling Authority"

    SimulationOptionsDevice = "SimulationOptionsDevice"

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return DeviceType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class SubObjectType(Enum):
    """
    Types of objects that act as complicated variable types
    """
    Profile = "Profile"
    GeneratorQCurve = 'Generator Q curve'
    LineLocations = 'Line locations'
    TapChanger = 'Tap changer'
    Array = "Array"
    ObjectsList = "ObjectsList"
    Associations = "AssociationsList"

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return SubObjectType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class TapChangerTypes(Enum):
    """
    Types of objects that act as complicated variable types
    """
    NoRegulation = 'NoRegulation'
    VoltageRegulation = "VoltageRegulation"
    Asymmetrical = 'Asymmetrical'
    Symmetrical = 'Symmetrical'

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return TapChangerTypes[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class BuildStatus(Enum):
    """
    Asset build status options
    """
    Commissioned = 'Commissioned'  # Already there, not planned for decommissioning
    Decommissioned = 'Decommissioned'  # Already retired (does not exist)
    Planned = 'Planned'  # Planned for commissioning some time, does not exist yet)
    Candidate = 'Candidate'  # Candidate for commissioning, does not exist yet, might be selected for commissioning
    PlannedDecommission = 'PlannedDecommission'  # Already there, but it has been selected for decommissioning

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return BuildStatus[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class StudyResultsType(Enum):
    """
    Types of simulation results
    """
    PowerFlow = 'PowerFlow'
    PowerFlowTimeSeries = 'PowerFlowTimeSeries'
    OptimalPowerFlow = 'PowerFlow'
    OptimalPowerFlowTimeSeries = 'PowerFlowTimeSeries'
    ShortCircuit = 'ShortCircuit'
    ContinuationPowerFlow = 'ContinuationPowerFlow'
    ContingencyAnalysis = 'ContingencyAnalysis'
    ContingencyAnalysisTimeSeries = 'ContingencyAnalysisTimeSeries'
    SigmaAnalysis = 'SigmaAnalysis'
    LinearAnalysis = 'LinearAnalysis'
    LinearAnalysisTimeSeries = 'LinearAnalysisTimeSeries'
    AvailableTransferCapacity = 'AvailableTransferCapacity'
    AvailableTransferCapacityTimeSeries = 'AvailableTransferCapacityTimeSeries'
    Clustering = 'Clustering'
    StateEstimation = 'StateEstimation'
    InputsAnalysis = 'InputsAnalysis'
    InvestmentEvaluations = 'InvestmentEvaluations'
    NetTransferCapacity = 'NetTransferCapacity'
    NetTransferCapacityTimeSeries = 'NetTransferCapacityTimeSeries'
    StochasticPowerFlow = 'StochasticPowerFlow'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return StudyResultsType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class AvailableTransferMode(Enum):
    """
    AvailableTransferMode
    """

    Generation = "Generation"
    InstalledPower = "InstalledPower"
    Load = "Load"
    GenerationAndLoad = "GenerationAndLoad"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return AvailableTransferMode[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class InvestmentsEvaluationObjectives(Enum):
    """
    Types of investment optimization objectives
    """
    PowerFlow = 'PowerFlow'
    TimeSeriesPowerFlow = 'TimeSeriesPowerFlow'
    OptimalPowerFlow = 'OptimalPowerFlow'
    TimeSeriesOptimalPowerFlow = 'TimeSeriesOptimalPowerFlow'

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return InvestmentsEvaluationObjectives[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(map(lambda c: c.value, cls))


class LogSeverity(Enum):
    """
    Enumeration of logs severities
    """
    Error = 'Error'
    Warning = 'Warning'
    Information = 'Information'
    Divergence = 'Divergence'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return LogSeverity[s]
        except KeyError:
            return s


class CGMESVersions(Enum):
    """
    Enumeration of logs severities
    """
    v2_4_15 = '2.4.15'
    v3_0_0 = '3.0.0'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return CGMESVersions[s]
        except KeyError:
            return s


class SparseSolver(Enum):
    """
    Sparse solvers to use
    """
    ILU = 'ILU'
    KLU = 'KLU'
    SuperLU = 'SuperLU'
    Pardiso = 'Pardiso'
    GMRES = 'GMRES'
    UMFPACK = 'UmfPack'
    UMFPACKTriangular = 'UmfPackTriangular'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return CGMESVersions[s]
        except KeyError:
            return s


class NodalCapacityMethod(Enum):
    """
    Sparse solvers to use
    """
    NonlinearOptimization = 'Nonlinear Optimization'
    LinearOptimization = 'Linear Optimization'
    CPF = "Continuation power flow"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return NodalCapacityMethod[s]
        except KeyError:
            return s


class ResultTypes(Enum):
    """
    ResultTypes
    """
    # Power flow
    BusVoltage = 'Voltage'
    BusVoltagePolar = 'Voltage (polar)'
    BusActivePower = 'P: Active power'
    BusReactivePower = 'Q: Reactive power'
    BranchPower = 'Sf: Power'
    BranchActivePowerFrom = 'Pf: Active power "from"'
    BranchReactivePowerFrom = 'Qf: Reactive power "from"'
    BranchActivePowerTo = 'Pt: Active power "to"'
    BranchReactivePowerTo = 'Qt: Reactive power "to"'

    BranchCurrent = 'I: Current'
    BranchActiveCurrentFrom = 'Irf: Active current "from"'
    BranchReactiveCurrentFrom = 'Iif: Reactive current "from"'
    BranchActiveCurrentTo = 'Irt: Active current "to"'
    BranchReactiveCurrentTo = 'Iit: Reactive current "to"'

    BranchTapModule = 'm: Tap module'
    BranchTapAngle = '𝜏: Tap angle'
    BranchBeq = 'Beq: Equivalent susceptance'

    BranchLoading = 'Branch Loading'
    Transformer2WTapModule = 'Transformer tap module'
    BranchVoltage = 'ΔV: Voltage modules drop'
    BranchAngles = 'Δθ: Voltage angles drop'
    BranchLosses = 'Branch losses'
    BranchActiveLosses = 'Pl: Active losses'
    BranchReactiveLosses = 'Ql: Reactive losses'
    BranchActiveLossesPercentage = 'Pl: Active losses (%)'
    BatteryPower = 'Battery power'
    BatteryEnergy = 'Battery energy'

    HvdcLosses = 'HVDC losses'
    HvdcPowerFrom = 'HVDC power "from"'
    HvdcLoading = 'HVDC loading'
    HvdcPowerTo = 'HVDC power "to"'

    # StochasticPowerFlowDriver
    BusVoltageAverage = 'Bus voltage avg'
    BusVoltageStd = 'Bus voltage std'
    BusVoltageCDF = 'Bus voltage CDF'
    BusPowerCDF = 'Bus power CDF'
    BranchPowerAverage = 'Branch power avg'
    BranchPowerStd = 'Branch power std'
    BranchPowerCDF = 'Branch power CDF'
    BranchLoadingAverage = 'loading avg'
    BranchLoadingStd = 'Loading std'
    BranchLoadingCDF = 'Loading CDF'
    BranchLossesAverage = 'Losses avg'
    BranchLossesStd = 'Losses std'
    BranchLossesCDF = 'Losses CDF'

    # PF
    BusVoltageModule = 'V: Voltage module'
    BusVoltageAngle = 'θ: Voltage angle'
    BusPower = 'Bus power'
    BusShadowPrices = 'Nodal shadow prices'
    BranchOverloads = 'Branch overloads'
    LoadShedding = 'Load shedding'
    GeneratorShedding = 'Generator shedding'
    GeneratorPower = 'Generator power'
    GeneratorCost = 'Generator cost'
    GeneratorFuels = 'Generator fuels'
    GeneratorEmissions = 'Generator emissions'
    GeneratorProducing = 'Generator producing'
    GeneratorStartingUp = 'Generator starting up'
    GeneratorShuttingDown = 'Generator shutting down'
    BusVoltagePolarPlot = 'Voltage plot'
    BusNodalCapacity = "Nodal capacity"

    # OPF-NTC
    HvdcOverloads = 'HVDC overloads'
    NodeSlacks = 'Nodal slacks'
    GenerationDelta = 'Generation deltas'
    GenerationDeltaSlacks = 'Generation delta slacks'
    InterAreaExchange = 'Inter-Area exchange'
    LossesPercentPerArea = 'Losses % per area'
    LossesPerArea = 'Losses per area'
    ActivePowerFlowPerArea = 'Active power flow per area'
    LossesPerGenPerArea = 'Losses per generation unit in area'

    SystemFuel = 'System fuel consumption'
    SystemEmissions = 'System emissions'
    SystemEnergyCost = 'System energy cost'

    # NTC TS
    OpfNtcTsContingencyReport = 'Contingency flow report'
    OpfNtcTsBaseReport = 'Base flow report'

    # Short-circuit
    BusShortCircuitActivePower = 'Short circuit active power'
    BusShortCircuitReactivePower = 'Short circuit reactive power'

    # PTDF
    PTDF = 'PTDF'
    PTDFBusVoltageSensitivity = 'Bus voltage sensitivity'
    LODF = 'LODF'

    MaxOverloads = 'Maximum contingency flow'
    ContingencyFlows = 'Contingency flow'
    ContingencyLoading = 'Contingency loading'
    MaxContingencyFlows = 'Max contingency flow'
    MaxContingencyLoading = 'Max contingency loading'

    ContingencyOverloadSum = 'Contingency overload sum'
    MeanContingencyOverLoading = 'Mean contingency overloading'
    StdDevContingencyOverLoading = 'Std-dev contingency overloading'

    ContingencyFrequency = 'Contingency frequency'
    ContingencyRelativeFrequency = 'Contingency relative frequency'

    SimulationError = 'Error'

    OTDFSimulationError = 'Error'

    # contingency analysis
    ContingencyAnalysisReport = 'Contingencies report'
    ContingencyStatisticalAnalysisReport = 'Contingencies statistical report'

    # Srap
    SrapUsedPower = 'Srap used power'

    # Hydro OPF
    FluidCurrentLevel = 'Reservoir fluid level'
    FluidFlowIn = 'Flow entering the node'
    FluidFlowOut = 'Flow exiting the node'
    FluidP2XFlow = 'Flow from the P2X'
    FluidSpillage = 'Spillage flow leaving'

    FluidFlowPath = 'Flow in the river'
    FluidFlowInjection = 'Flow circulating in the device'

    # sigma
    SigmaReal = 'Sigma real'
    SigmaImag = 'Sigma imaginary'
    SigmaDistances = 'Sigma distances'
    SigmaPlusDistances = 'Sigma + distances'

    # ATC
    AvailableTransferCapacityMatrix = 'Available transfer capacity'
    AvailableTransferCapacity = 'Available transfer capacity (final)'
    AvailableTransferCapacityN = 'Available transfer capacity (N)'
    AvailableTransferCapacityAlpha = 'Sensitivity to the exchange'
    AvailableTransferCapacityAlphaN1 = 'Sensitivity to the exchange (N-1)'
    NetTransferCapacity = 'Net transfer capacity'
    AvailableTransferCapacityReport = 'ATC Report'

    BaseFlowReport = 'Ntc: Base flow report'
    ContingencyFlowsReport = 'Ntc: Contingency flow report'
    ContingencyFlowsBranchReport = 'Ntc: Contingency flow report. (Branch)'
    ContingencyFlowsGenerationReport = 'Ntc: Contingency flow report. (Generation)'
    ContingencyFlowsHvdcReport = 'Ntc: Contingency flow report. (Hvdc)'

    # Time series
    TsBaseFlowReport = 'Time series base flow report'
    TsContingencyFlowReport = 'Time series contingency flow report'
    TsContingencyFlowBranchReport = 'Time series Contingency flow report (Branches)'
    TsContingencyFlowGenerationReport = 'Time series contingency flow report. (Generation)'
    TsContingencyFlowHvdcReport = 'Time series contingency flow report. (Hvdc)'
    TsGenerationPowerReport = 'Time series generation power report'
    TsGenerationDeltaReport = 'Time series generation delta power report'
    TsAlphaReport = 'Time series sensitivity to the exchange report'
    TsWorstAlphaN1Report = 'Time series worst sensitivity to the exchange report (N-1)'
    TsBranchMonitoring = 'Time series branch monitoring logic report'
    TsCriticalBranches = 'Time series critical Branches report'
    TsContingencyBranches = 'Time series contingency Branches report'

    # Clustering
    ClusteringReport = 'Clustering time series report'

    # inputs analysis
    ZoneAnalysis = 'Zone analysis'
    CountryAnalysis = 'Country analysis'
    AreaAnalysis = 'Area analysis'

    AreaGenerationAnalysis = 'Area generation analysis'
    ZoneGenerationAnalysis = 'Zone generation analysis'
    CountryGenerationAnalysis = 'Country generation analysis'

    AreaLoadAnalysis = 'Area load analysis'
    ZoneLoadAnalysis = 'Zone load analysis'
    CountryLoadAnalysis = 'Country load analysis'

    AreaBalanceAnalysis = 'Area balance analysis'
    ZoneBalanceAnalysis = 'Zone balance analysis'
    CountryBalanceAnalysis = 'Country balance analysis'

    # Short circuit
    BusVoltageModule0 = 'Voltage module (0)'
    BusVoltageAngle0 = 'Voltage angle (0)'
    BranchActivePowerFrom0 = 'Branch active power "from" (0)'
    BranchReactivePowerFrom0 = 'Branch reactive power "from" (0)'
    BranchActiveCurrentFrom0 = 'Branch active current "from" (0)'
    BranchReactiveCurrentFrom0 = 'Branch reactive current "from" (0)'
    BranchLoading0 = 'Branch loading (0)'
    BranchActiveLosses0 = 'Branch active losses (0)'
    BranchReactiveLosses0 = 'Branch reactive losses (0)'

    BusVoltageModule1 = 'Voltage module (1)'
    BusVoltageAngle1 = 'Voltage angle (1)'
    BranchActivePowerFrom1 = 'Branch active power "from" (1)'
    BranchReactivePowerFrom1 = 'Branch reactive power "from" (1)'
    BranchActiveCurrentFrom1 = 'Branch active current "from" (1)'
    BranchReactiveCurrentFrom1 = 'Branch reactive current "from" (1)'
    BranchLoading1 = 'Branch loading (1)'
    BranchActiveLosses1 = 'Branch active losses (1)'
    BranchReactiveLosses1 = 'Branch reactive losses (1)'

    BusVoltageModule2 = 'Voltage module (2)'
    BusVoltageAngle2 = 'Voltage angle (2)'
    BranchActivePowerFrom2 = 'Branch active power "from" (2)'
    BranchReactivePowerFrom2 = 'Branch reactive power "from" (2)'
    BranchActiveCurrentFrom2 = 'Branch active current "from" (2)'
    BranchReactiveCurrentFrom2 = 'Branch reactive current "from" (2)'
    BranchLoading2 = 'Branch loading (2)'
    BranchActiveLosses2 = 'Branch active losses (2)'
    BranchReactiveLosses2 = 'Branch reactive losses (2)'
    BranchMonitoring = 'Branch monitoring logic'

    ShortCircuitInfo = 'Short-circuit information'

    # classifiers
    SystemResults = 'System'
    BusResults = 'Bus'
    BranchResults = 'Branch'
    HvdcResults = 'Hvdc'
    AreaResults = 'Area'
    InfoResults = 'Information'
    ReportsResults = 'Reports'
    ParetoResults = 'Pareto'
    SlacksResults = 'Slacks'
    DispatchResults = 'Dispatch'
    FlowReports = 'Flow Reports'
    Sensibilities = 'Sensibilities'
    SeriesResults = 'Series'
    SnapshotResults = 'Snapshot'
    NTCResults = 'NTC'
    SpecialPlots = 'Special plots'
    GeneratorResults = 'Generators'
    LoadResults = 'Loads'
    BatteryResults = 'Batteries'
    StatisticResults = 'Statistics'

    # fluid
    FluidNodeResults = 'Fluid nodes'
    FluidPathResults = 'Fluid paths'
    FluidInjectionResults = 'Fluid injections'
    FluidTurbineResults = 'Fluid turbines'
    FluidPumpResults = 'Fluid pumps'
    FluidP2XResults = 'Fluid P2Xs'

    # investments evaluation
    InvestmentsReportResults = 'Evaluation report'
    InvestmentsFrequencyResults = "Frequency"
    InvestmentsCombinationsResults = "Combinations"
    InvestmentsObjectivesResults = "Objectives"

    InvestmentsParetoReportResults = 'Pareto evaluation report'
    InvestmentsParetoFrequencyResults = "Pareto frequency"
    InvestmentsParetoCombinationsResults = "Pareto combinations"
    InvestmentsParetoObjectivesResults = "Pareto objectives"

    InvestmentsParetoPlot = 'Pareto plots'
    InvestmentsIterationsPlot = 'Iterations plot'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self.value)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ResultTypes[s]
        except KeyError:
            return s


class SimulationTypes(Enum):
    """
    Enumeration of simulation types
    """
    TemplateDriver = 'Template'
    PowerFlow_run = 'Power flow'
    ShortCircuit_run = 'Short circuit'
    MonteCarlo_run = 'Monte Carlo'
    PowerFlowTimeSeries_run = 'Power flow time series'
    ClusteringAnalysis_run = 'Clustering Analysis'
    ContinuationPowerFlow_run = 'Voltage collapse'
    LatinHypercube_run = 'Latin Hypercube'
    StochasticPowerFlow = 'Stochastic Power Flow'
    Cascade_run = 'Cascade'
    OPF_run = 'Optimal power flow'
    OPF_NTC_run = 'Optimal net transfer capacity'
    OPF_NTC_TS_run = 'Optimal net transfer capacity time series'
    OPFTimeSeries_run = 'Optimal power flow time series'
    TransientStability_run = 'Transient stability'
    TopologyReduction_run = 'Topology reduction'
    LinearAnalysis_run = 'Linear analysis'
    LinearAnalysis_TS_run = 'Linear analysis time series'
    NonLinearAnalysis_run = 'Nonlinear analysis'
    NonLinearAnalysis_TS_run = 'Nonlinear analysis time series'
    ContingencyAnalysis_run = 'Contingency analysis'
    ContingencyAnalysisTS_run = 'Contingency analysis time series'
    Delete_and_reduce_run = 'Delete and reduce'
    NetTransferCapacity_run = 'Available transfer capacity'
    NetTransferCapacityTS_run = 'Available transfer capacity time series'
    SigmaAnalysis_run = "Sigma Analysis"
    NodeGrouping_run = "Node groups"
    InputsAnalysis_run = 'Inputs Analysis'
    OptimalNetTransferCapacityTimeSeries_run = 'Optimal net transfer capacity time series'
    InvestmentsEvaluation_run = 'Investments evaluation'
    TopologyProcessor_run = 'Topology Processor'
    NodalCapacityTimeSeries_run = 'Nodal capacity time series'

    NoSim = "No simulation"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return SimulationTypes[s]
        except KeyError:
            return s


class JobStatus(Enum):
    """
    Job status types
    """
    Done = 'Done'
    Running = 'Running'
    Failed = "Failed"
    Waiting = "Waiting"
    Cancelled = "Cancelled"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return JobStatus[s]
        except KeyError:
            return s


class ContingencyFilteringMethods(Enum):
    """
    Contingency filtering methods
    """
    All = "All contingencies"
    Country = "Country"
    Zone = "Zone"
    Area = "Area"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ContingencyFilteringMethods[s]
        except KeyError:
            return s


class Colormaps(Enum):
    GridCal = 'GridCal'
    TSO = 'TSO'  # -1, 1
    TSO2 = 'TSO 2'  # -1, 1
    SCADA = 'SCADA'  # -1, 1
    Heatmap = 'Heatmap'  # 0, 1
    Blues = 'Blue'  # 0, 1
    Greens = 'Green'  # 0, 1
    Blue2Gray = 'Blue to gray'  # 0, 1
    Green2Red = 'Green to red'  # -1, 1
    Red2Blue = 'Red to blue'  # -1, 1

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return Colormaps[s]
        except KeyError:
            return s
