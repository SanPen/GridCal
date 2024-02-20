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
    Nose = 'Nose'
    ExtraOverloads = 'Extra overloads'
    Full = 'Full curve'


class CpfParametrization(Enum):
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
    MVRSM_multi = "MVRSM_multi"

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
    BusBranch = 'bus-branch'
    SubstationLineMap = 'substation-line-map'
    NodeBreaker = 'node-breaker'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return DiagramType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class TransformerControlType(Enum):
    """
    Transformer control types
    """
    fixed = '0:Fixed'
    Pf = '1:Pf'
    Qt = '2:Qt'
    PtQt = '3:Pt+Qt'
    Vt = '4:Vt'
    PtVt = '5:Pt+Vt'

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return TransformerControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
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

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return ConverterControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class HvdcControlType(Enum):
    """
    Simple HVDC control types
    """
    type_0_free = '0:Free'
    type_1_Pset = '1:Pdc'

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return ConverterControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
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
        try:
            return FaultType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
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

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return WindingsConnection[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


class DeviceType(Enum):
    """
    Device types
    """
    NoDevice = "NoDevice"
    CircuitDevice = 'Circuit'
    BusDevice = 'Bus'
    BranchDevice = 'Branch'
    BranchTypeDevice = 'Branch template'
    LineDevice = 'Line'
    LineTypeDevice = 'Line Template'
    Transformer2WDevice = 'Transformer'
    Transformer3WDevice = 'Transformer3W'
    WindingDevice = 'Winding'
    HVDCLineDevice = 'HVDC Line'
    DCLineDevice = 'DC line'
    VscDevice = 'VSC'
    BatteryDevice = 'Battery'
    LoadDevice = 'Load'
    GeneratorDevice = 'Generator'
    StaticGeneratorDevice = 'Static Generator'
    ShuntDevice = 'Shunt'
    UpfcDevice = 'UPFC'  # unified power flow controller
    ExternalGridDevice = 'External grid'

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
    BusBarDevice = 'BusBar'

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

    GeneratorQCurve = 'Generator Q curve'

    FluidInjectionDevice = 'Fluid Injection'
    FluidTurbineDevice = 'Fluid Turbine'
    FluidPumpDevice = 'Fluid Pump'
    FluidP2XDevice = 'Fluid P2X'
    FluidPathDevice = 'Fluid path'
    FluidNodeDevice = 'Fluid node'

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return DeviceType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
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

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return BuildStatus[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
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
        try:
            return StudyResultsType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
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
        try:
            return InvestmentsEvaluationObjectives[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
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


class ResultTypes(Enum):
    # Power flow
    BusVoltage = 'Voltage', DeviceType.BusDevice
    BusVoltagePolar = 'Voltage (polar)', DeviceType.BusDevice
    BusActivePower = 'P: Active power', DeviceType.BusDevice
    BusReactivePower = 'Q: Reactive power', DeviceType.BusDevice
    BranchPower = 'Sf: Power', DeviceType.BranchDevice
    BranchActivePowerFrom = 'Pf: Active power "from"', DeviceType.BranchDevice
    BranchReactivePowerFrom = 'Qf: Reactive power "from"', DeviceType.BranchDevice
    BranchActivePowerTo = 'Pt: Active power "to"', DeviceType.BranchDevice
    BranchReactivePowerTo = 'Qt: Reactive power "to"', DeviceType.BranchDevice

    BranchCurrent = 'I: Current', DeviceType.BranchDevice
    BranchActiveCurrentFrom = 'Irf: Active current "from"', DeviceType.BranchDevice
    BranchReactiveCurrentFrom = 'Iif: Reactive current "from"', DeviceType.BranchDevice
    BranchActiveCurrentTo = 'Irt: Active current "to"', DeviceType.BranchDevice
    BranchReactiveCurrentTo = 'Iit: Reactive current "to"', DeviceType.BranchDevice

    BranchTapModule = 'm: Tap module', DeviceType.BranchDevice
    BranchTapAngle = '𝜏: Tap angle', DeviceType.BranchDevice
    BranchBeq = 'Beq: Equivalent susceptance', DeviceType.BranchDevice

    BranchLoading = 'Branch Loading', DeviceType.BranchDevice
    Transformer2WTapModule = 'Transformer tap module', DeviceType.Transformer2WDevice
    BranchVoltage = 'ΔV: Voltage modules drop', DeviceType.BranchDevice
    BranchAngles = 'Δθ: Voltage angles drop', DeviceType.BranchDevice
    BranchLosses = 'Branch losses', DeviceType.BranchDevice
    BranchActiveLosses = 'Pl: Active losses', DeviceType.BranchDevice
    BranchReactiveLosses = 'Ql: Reactive losses', DeviceType.BranchDevice
    BranchActiveLossesPercentage = 'Pl: Active losses (%)', DeviceType.BranchDevice
    BatteryPower = 'Battery power', DeviceType.BatteryDevice
    BatteryEnergy = 'Battery energy', DeviceType.BatteryDevice

    HvdcLosses = 'HVDC losses', DeviceType.HVDCLineDevice
    HvdcPowerFrom = 'HVDC power "from"', DeviceType.HVDCLineDevice
    HvdcLoading = 'HVDC loading', DeviceType.HVDCLineDevice
    HvdcPowerTo = 'HVDC power "to"', DeviceType.HVDCLineDevice

    # StochasticPowerFlowDriver
    BusVoltageAverage = 'Bus voltage avg', DeviceType.BusDevice
    BusVoltageStd = 'Bus voltage std', DeviceType.BusDevice
    BusVoltageCDF = 'Bus voltage CDF', DeviceType.BusDevice
    BusPowerCDF = 'Bus power CDF', DeviceType.BusDevice
    BranchPowerAverage = 'Branch power avg', DeviceType.BranchDevice
    BranchPowerStd = 'Branch power std', DeviceType.BranchDevice
    BranchPowerCDF = 'Branch power CDF', DeviceType.BranchDevice
    BranchLoadingAverage = 'loading avg', DeviceType.BranchDevice
    BranchLoadingStd = 'Loading std', DeviceType.BranchDevice
    BranchLoadingCDF = 'Loading CDF', DeviceType.BranchDevice
    BranchLossesAverage = 'Losses avg', DeviceType.BranchDevice
    BranchLossesStd = 'Losses std', DeviceType.BranchDevice
    BranchLossesCDF = 'Losses CDF', DeviceType.BranchDevice

    # PF
    BusVoltageModule = 'V: Voltage module', DeviceType.BusDevice
    BusVoltageAngle = 'θ: Voltage angle', DeviceType.BusDevice
    BusPower = 'Bus power', DeviceType.BusDevice
    BusShadowPrices = 'Nodal shadow prices', DeviceType.BusDevice
    BranchOverloads = 'Branch overloads', DeviceType.BranchDevice
    LoadShedding = 'Load shedding', DeviceType.LoadDevice
    GeneratorShedding = 'Generator shedding', DeviceType.GeneratorDevice
    GeneratorPower = 'Generator power', DeviceType.GeneratorDevice
    GeneratorCost = 'Generator cost', DeviceType.GeneratorDevice
    GeneratorFuels = 'Generator fuels', DeviceType.GeneratorDevice
    GeneratorEmissions = 'Generator emissions', DeviceType.GeneratorDevice
    GeneratorProducing = 'Generator producing', DeviceType.GeneratorDevice
    GeneratorStartingUp = 'Generator starting up', DeviceType.GeneratorDevice
    GeneratorShuttingDown = 'Generator shutting down', DeviceType.GeneratorDevice
    BusVoltagePolarPlot = 'Voltage plot', DeviceType.BusDevice

    # OPF-NTC
    HvdcOverloads = 'HVDC overloads', DeviceType.HVDCLineDevice
    NodeSlacks = 'Nodal slacks', DeviceType.BusDevice
    GenerationDelta = 'Generation deltas', DeviceType.GeneratorDevice
    GenerationDeltaSlacks = 'Generation delta slacks', DeviceType.GeneratorDevice
    InterAreaExchange = 'Inter-Area exchange', DeviceType.NoDevice
    LossesPercentPerArea = 'Losses % per area', DeviceType.NoDevice
    LossesPerArea = 'Losses per area', DeviceType.NoDevice
    ActivePowerFlowPerArea = 'Active power flow per area', DeviceType.NoDevice
    LossesPerGenPerArea = 'Losses per generation unit in area', DeviceType.NoDevice

    SystemFuel = 'System fuel consumption', DeviceType.NoDevice
    SystemEmissions = 'System emissions', DeviceType.NoDevice
    SystemEnergyCost = 'System energy cost', DeviceType.NoDevice

    # NTC TS
    OpfNtcTsContingencyReport = 'Contingency flow report', DeviceType.NoDevice
    OpfNtcTsBaseReport = 'Base flow report', DeviceType.NoDevice

    # Short-circuit
    BusShortCircuitActivePower = 'Short circuit active power', DeviceType.BusDevice
    BusShortCircuitReactivePower = 'Short circuit reactive power', DeviceType.BusDevice

    # PTDF
    PTDF = 'PTDF', DeviceType.BranchDevice
    PTDFBusVoltageSensitivity = 'Bus voltage sensitivity', DeviceType.BusDevice

    LODF = 'LODF', DeviceType.BranchDevice

    MaxOverloads = 'Maximum contingency flow', DeviceType.BranchDevice
    ContingencyFlows = 'Contingency flow', DeviceType.BranchDevice
    ContingencyLoading = 'Contingency loading', DeviceType.BranchDevice
    MaxContingencyFlows = 'Max contingency flow', DeviceType.BranchDevice
    MaxContingencyLoading = 'Max contingency loading', DeviceType.BranchDevice

    ContingencyOverloadSum = 'Contingency overload sum', DeviceType.BranchDevice
    MeanContingencyOverLoading = 'Mean contingency overloading', DeviceType.BranchDevice
    StdDevContingencyOverLoading = 'Std-dev contingency overloading', DeviceType.BranchDevice

    ContingencyFrequency = 'Contingency frequency', DeviceType.BranchDevice
    ContingencyRelativeFrequency = 'Contingency relative frequency', DeviceType.BranchDevice

    SimulationError = 'Error', DeviceType.BusDevice

    OTDFSimulationError = 'Error', DeviceType.BranchDevice

    # contingency analysis
    ContingencyAnalysisReport = 'Contingencies report', DeviceType.NoDevice

    # Srap
    SrapUsedPower = 'Srap used power', DeviceType.NoDevice

    # Hydro OPF
    FluidCurrentLevel = 'Reservoir fluid level', DeviceType.FluidNodeDevice
    FluidFlowIn = 'Flow entering the node', DeviceType.FluidNodeDevice
    FluidFlowOut = 'Flow exiting the node', DeviceType.FluidNodeDevice
    FluidP2XFlow = 'Flow from the P2X', DeviceType.FluidNodeDevice
    FluidSpillage = 'Spillage flow leaving', DeviceType.FluidNodeDevice

    FluidFlowPath = 'Flow in the river', DeviceType.FluidPathDevice
    FluidFlowInjection = 'Flow circulating in the device', DeviceType.FluidInjectionDevice

    # sigma
    SigmaReal = 'Sigma real', DeviceType.BusDevice
    SigmaImag = 'Sigma imaginary', DeviceType.BusDevice
    SigmaDistances = 'Sigma distances', DeviceType.BusDevice
    SigmaPlusDistances = 'Sigma + distances', DeviceType.BusDevice

    # ATC
    AvailableTransferCapacityMatrix = 'Available transfer capacity', DeviceType.BranchDevice
    AvailableTransferCapacity = 'Available transfer capacity (final)', DeviceType.BranchDevice
    AvailableTransferCapacityN = 'Available transfer capacity (N)', DeviceType.BranchDevice
    AvailableTransferCapacityAlpha = 'Sensitivity to the exchange', DeviceType.BranchDevice
    AvailableTransferCapacityAlphaN1 = 'Sensitivity to the exchange (N-1)', DeviceType.BranchDevice
    NetTransferCapacity = 'Net transfer capacity', DeviceType.BranchDevice
    AvailableTransferCapacityReport = 'ATC Report', DeviceType.NoDevice

    # NTC
    # ContingencyFlowsReport = 'Contingency Report', DeviceType.NoDevice
    # ContingencyFlowsBranchReport = 'Contingency Branch Report', DeviceType.NoDevice
    # ContingencyFlowsGenerationReport = 'Contingency Generation Report', DeviceType.NoDevice
    # ContingencyFlowsHvdcReport = 'Contingency Hvdc Report', DeviceType.NoDevice

    BaseFlowReport = 'Ntc: Base flow report', DeviceType.NoDevice
    ContingencyFlowsReport = 'Ntc: Contingency flow report', DeviceType.NoDevice
    ContingencyFlowsBranchReport = 'Ntc: Contingency flow report. (Branch)', DeviceType.NoDevice
    ContingencyFlowsGenerationReport = 'Ntc: Contingency flow report. (Generation)', DeviceType.NoDevice
    ContingencyFlowsHvdcReport = 'Ntc: Contingency flow report. (Hvdc)', DeviceType.NoDevice

    # Time series
    TsBaseFlowReport = 'Time series base flow report', DeviceType.NoDevice
    TsContingencyFlowReport = 'Time series contingency flow report', DeviceType.NoDevice
    TsContingencyFlowBranchReport = 'Time series Contingency flow report (Branches)', DeviceType.NoDevice
    TsContingencyFlowGenerationReport = 'Time series contingency flow report. (Generation)', DeviceType.NoDevice
    TsContingencyFlowHvdcReport = 'Time series contingency flow report. (Hvdc)', DeviceType.NoDevice
    TsGenerationPowerReport = 'Time series generation power report', DeviceType.NoDevice
    TsGenerationDeltaReport = 'Time series generation delta power report', DeviceType.NoDevice
    TsAlphaReport = 'Time series sensitivity to the exchange report', DeviceType.NoDevice
    TsWorstAlphaN1Report = 'Time series worst sensitivity to the exchange report (N-1)', DeviceType.NoDevice
    TsBranchMonitoring = 'Time series branch monitoring logic report', DeviceType.BranchDevice
    TsCriticalBranches = 'Time series critical Branches report', DeviceType.BranchDevice
    TsContingencyBranches = 'Time series contingency Branches report', DeviceType.BranchDevice

    # Clustering
    ClusteringReport = 'Clustering time series report', DeviceType.NoDevice

    # inputs analysis
    ZoneAnalysis = 'Zone analysis', DeviceType.NoDevice
    CountryAnalysis = 'Country analysis', DeviceType.NoDevice
    AreaAnalysis = 'Area analysis', DeviceType.NoDevice

    AreaGenerationAnalysis = 'Area generation analysis', DeviceType.NoDevice
    ZoneGenerationAnalysis = 'Zone generation analysis', DeviceType.NoDevice
    CountryGenerationAnalysis = 'Country generation analysis', DeviceType.NoDevice

    AreaLoadAnalysis = 'Area load analysis', DeviceType.NoDevice
    ZoneLoadAnalysis = 'Zone load analysis', DeviceType.NoDevice
    CountryLoadAnalysis = 'Country load analysis', DeviceType.NoDevice

    AreaBalanceAnalysis = 'Area balance analysis', DeviceType.NoDevice
    ZoneBalanceAnalysis = 'Zone balance analysis', DeviceType.NoDevice
    CountryBalanceAnalysis = 'Country balance analysis', DeviceType.NoDevice

    # Short circuit
    BusVoltageModule0 = 'Voltage module (0)', DeviceType.BusDevice
    BusVoltageAngle0 = 'Voltage angle (0)', DeviceType.BusDevice
    BranchActivePowerFrom0 = 'Branch active power "from" (0)', DeviceType.BranchDevice
    BranchReactivePowerFrom0 = 'Branch reactive power "from" (0)', DeviceType.BranchDevice
    BranchActiveCurrentFrom0 = 'Branch active current "from" (0)', DeviceType.BranchDevice
    BranchReactiveCurrentFrom0 = 'Branch reactive current "from" (0)', DeviceType.BranchDevice
    BranchLoading0 = 'Branch loading (0)', DeviceType.BranchDevice
    BranchActiveLosses0 = 'Branch active losses (0)', DeviceType.BranchDevice
    BranchReactiveLosses0 = 'Branch reactive losses (0)', DeviceType.BranchDevice

    BusVoltageModule1 = 'Voltage module (1)', DeviceType.BusDevice
    BusVoltageAngle1 = 'Voltage angle (1)', DeviceType.BusDevice
    BranchActivePowerFrom1 = 'Branch active power "from" (1)', DeviceType.BranchDevice
    BranchReactivePowerFrom1 = 'Branch reactive power "from" (1)', DeviceType.BranchDevice
    BranchActiveCurrentFrom1 = 'Branch active current "from" (1)', DeviceType.BranchDevice
    BranchReactiveCurrentFrom1 = 'Branch reactive current "from" (1)', DeviceType.BranchDevice
    BranchLoading1 = 'Branch loading (1)', DeviceType.BranchDevice
    BranchActiveLosses1 = 'Branch active losses (1)', DeviceType.BranchDevice
    BranchReactiveLosses1 = 'Branch reactive losses (1)', DeviceType.BranchDevice

    BusVoltageModule2 = 'Voltage module (2)', DeviceType.BusDevice
    BusVoltageAngle2 = 'Voltage angle (2)', DeviceType.BusDevice
    BranchActivePowerFrom2 = 'Branch active power "from" (2)', DeviceType.BranchDevice
    BranchReactivePowerFrom2 = 'Branch reactive power "from" (2)', DeviceType.BranchDevice
    BranchActiveCurrentFrom2 = 'Branch active current "from" (2)', DeviceType.BranchDevice
    BranchReactiveCurrentFrom2 = 'Branch reactive current "from" (2)', DeviceType.BranchDevice
    BranchLoading2 = 'Branch loading (2)', DeviceType.BranchDevice
    BranchActiveLosses2 = 'Branch active losses (2)', DeviceType.BranchDevice
    BranchReactiveLosses2 = 'Branch reactive losses (2)', DeviceType.BranchDevice
    BranchMonitoring = 'Branch monitoring logic', DeviceType.BranchDevice

    ShortCircuitInfo = 'Short-circuit information', DeviceType.NoDevice

    # classifiers
    SystemResults = 'System', DeviceType.NoDevice
    BusResults = 'Bus', DeviceType.NoDevice
    BranchResults = 'Branch', DeviceType.NoDevice
    HvdcResults = 'Hvdc', DeviceType.NoDevice
    AreaResults = 'Area', DeviceType.NoDevice
    InfoResults = 'Information', DeviceType.NoDevice
    ReportsResults = 'Reports', DeviceType.NoDevice
    SlacksResults = 'Slacks', DeviceType.NoDevice
    DispatchResults = 'Dispatch', DeviceType.NoDevice
    FlowReports = 'Flow Reports', DeviceType.NoDevice
    Sensibilities = 'Sensibilities', DeviceType.NoDevice
    SeriesResults = 'Series', DeviceType.NoDevice
    SnapshotResults = 'Snapshot', DeviceType.NoDevice
    NTCResults = 'NTC', DeviceType.NoDevice
    SpecialPlots = 'Special plots', DeviceType.NoDevice
    GeneratorResults = 'Generators', DeviceType.GeneratorDevice
    LoadResults = 'Loads', DeviceType.LoadDevice
    BatteryResults = 'Batteries', DeviceType.BatteryDevice
    StatisticResults = 'Statistics', DeviceType.NoDevice

    # fluid
    FluidNodeResults = 'Fluid nodes', DeviceType.FluidNodeDevice
    FluidPathResults = 'Fluid paths', DeviceType.FluidPathDevice
    FluidInjectionResults = 'Fluid injections', DeviceType.FluidInjectionDevice
    FluidTurbineResults = 'Fluid turbines', DeviceType.FluidTurbineDevice
    FluidPumpResults = 'Fluid pumps', DeviceType.FluidPumpDevice
    FluidP2XResults = 'Fluid P2Xs', DeviceType.FluidP2XDevice

    # investments evaluation
    InvestmentsReportResults = 'Investments evaluation report', DeviceType.NoDevice
    InvestmentsParetoPlot = 'Pareto plot', DeviceType.NoDevice
    InvestmentsIterationsPlot = 'Itertions plot', DeviceType.NoDevice

    def __str__(self):
        return self.value[0]

    def __repr__(self):
        return str(self.value[0])

    @staticmethod
    def argparse(s):
        try:
            return ResultTypes[s]
        except KeyError:
            return s


