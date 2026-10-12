# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from enum import Enum, IntEnum


class BusMode(Enum):
    """
    Bus modes
    """
    PQ_tpe = 1  # control P, Q
    PV_tpe = 2  # Control P, Vm
    Slack_tpe = 3  # Control Vm, Va (slack)
    PQV_tpe = 4  # voltage-controlled bus (P, Q, V set, theta computed)
    P_tpe = 5  # voltage-controlling bus (P set, Q, V, theta computed)

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

    @staticmethod
    def as_str(val: int) -> str:
        """
        Get the string representation of the numeric value
        :param val:
        :return:
        """
        if val == 1:
            return "PQ"
        elif val == 2:
            return "PV"
        elif val == 3:
            return "Slack"
        elif val == 4:
            return "PQV"
        elif val == 5:
            return "P"
        else:
            return ""


class BusGraphicType(Enum):
    """
    Bus graphical modes
    """
    BusBar = "BusBar"
    Connectivity = "Connectivity"
    Internal = "Internal"

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
            return BusGraphicType[s]
        except KeyError:
            return s


class SwitchGraphicType(Enum):
    """
    Bus graphical modes
    """
    CircuitBreaker = "CircuitBreaker"
    Disconnector = "Disconnector"

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
            return BusGraphicType[s]
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


class ShuntControlMode(str, Enum):
    """
    Modes of operation of shunt control modes
    """
    Locked = ("Locked", 0)
    Continuous = ("Continuous", 1)
    Discrete = ("Discrete", 2)
    QVDroop = ("QV droop", 3)
    ReactivePower = ("Reactive power", 4)

    def __new__(cls, value: str, code: int) -> "ShuntControlMode":
        """Create one shunt-control selector with its native integer code.

        :param value: Human-readable shunt-control objective.
        :param code: Native integer selector used by the source format.
        :return: Typed shunt-control enumeration member.
        """
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    def idx(self) -> int:
        return self.code

    @staticmethod
    def argparse(s):
        try:
            return ShuntControlMode[s]
        except KeyError:
            return s


class StaticGeneratorControlMode(str, Enum):
    """Reactive-power objectives of a static AC injection."""

    PQ = "PQ"
    QVDroop = "Q-V droop"

    def __str__(self) -> str:
        """Return the GUI label.

        :return: Control objective label.
        """
        return self.value

    @staticmethod
    def argparse(value: str) -> "StaticGeneratorControlMode | str":
        """Read a stored control objective using the existing enum convention.

        :param value: Member name.
        :return: Enum member or the unrecognised input.
        """
        try:
            return StaticGeneratorControlMode[value]
        except KeyError:
            return value


class GeneratorControlMode(str, Enum):
    """
    Modes of operation of generator control modes.
    """

    Q = ("Q", 0)  # Fixed Q, classic PQ node
    V = ("V", 1)  # Fixed V, classic PV node
    QVDroop = ("Q-V", 2)  # Like a PQ node with droop equation update of Q

    def __new__(cls, value: str, code: int) -> "GeneratorControlMode":
        """Create one generator-control selector with its native integer code.

        :param value: Human-readable generator-control objective.
        :param code: Native integer selector used by the source format.
        :return: Typed generator-control enumeration member.
        """
        obj: GeneratorControlMode = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    def idx(self) -> int:
        return self.code

    @staticmethod
    def argparse(s):
        try:
            return GeneratorControlMode[s]
        except KeyError:
            return s


class SynchronousMachineSpeedVariationMode(str, Enum):
    """Rotor-speed treatment in synchronous-machine stator equations."""

    Neglected = ("Neglected", 0)
    Considered = ("Considered", 1)
    PartiallyNeglected = ("Partially neglected", 2)

    def __new__(
            cls,
            value: str,
            code: int,
    ) -> "SynchronousMachineSpeedVariationMode":
        """Build one human-readable mode with its native code.

        :param value: Human-readable mode name.
        :param code: Native PowerFactory ``i_speedVar`` code.
        :return: Constructed enumeration member.
        """
        obj: SynchronousMachineSpeedVariationMode = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def idx(self) -> int:
        """Return the native PowerFactory mode code.

        :return: Native integer selector.
        """
        return self.code


class StationControlMode(str, Enum):
    """Control objective used by a non-physical station controller."""

    Voltage = ("Voltage", 0)
    ReactivePower = ("Reactive power", 1)
    PowerFactor = ("Power factor", 2)
    TanPhi = ("Tan(phi)", 3)

    def __new__(cls, value: str, code: int) -> "StationControlMode":
        """Create one station-control selector with its native integer code.

        :param value: Human-readable station-control objective.
        :param code: Native PowerFactory station-control selector.
        :return: Typed station-control enumeration member.
        """
        obj: StationControlMode = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def idx(self) -> int:
        """Return the native PowerFactory control-mode code."""
        return self.code


class StationControlBusSelection(str, Enum):
    """Describe how a station controller selects its regulated bus."""

    Explicit = ("Explicit controlled bus", 0)
    Automatic = ("Automatic bus search", 1)

    def __new__(cls, value: str, code: int) -> "StationControlBusSelection":
        """Create one humanized selector with its native integer code.

        :param value: Human-readable selector name.
        :param code: Native PowerFactory ``selBus`` code.
        :return: Typed controlled-bus selector.
        """
        obj: StationControlBusSelection = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def idx(self) -> int:
        """Return the native PowerFactory controlled-bus selector code."""
        return self.code


class StationVoltageSetpointMode(str, Enum):
    """Select the voltage target used by a station controller."""

    StationController = ("Station Controller", 0)
    BusTargetVoltage = ("Bus target voltage", 1)

    def __new__(cls, value: str, code: int) -> "StationVoltageSetpointMode":
        """Create one humanized selector with its native integer code.

        :param value: Human-readable PowerFactory selector name.
        :param code: Native PowerFactory ``uset_mode`` code.
        :return: Typed station voltage-setpoint selector.
        """
        obj: StationVoltageSetpointMode = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def idx(self) -> int:
        """Return the native PowerFactory voltage-setpoint selector code."""
        return self.code


class StationTransformerControlSide(str, Enum):
    """Select whether a station controller coordinates step-up transformers."""

    NoControl = ("None", 0)
    HighVoltageSide = ("HV-Side", 1)
    LowVoltageSide = ("LV-Side", 2)

    def __new__(cls, value: str, code: int) -> "StationTransformerControlSide":
        """Create one typed transformer-side selector.

        :param value: Human-readable PowerFactory selector name.
        :param code: Native PowerFactory ``iTrfCtrl`` code.
        :return: Typed transformer control-side selector.
        """
        obj: StationTransformerControlSide = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def idx(self) -> int:
        """Return the native PowerFactory transformer-side selector code."""
        return self.code


class StationReactivePowerDistribution(str, Enum):
    """Describe the native station reactive-distribution selector."""

    AccordingToDispatchedActivePower = ("According to Dispatched Active Power", 0)
    AccordingToRatedPower = ("According to Rated Power", 1)
    IndividualReactivePower = ("Individual Reactive Power", 2)
    MaximiseReactiveReserve = ("Maximise Reactive Reserve", 3)
    VoltageSetpointAdaption = ("Voltage Setpoint Adaption", 4)

    # Keep source-code compatibility while exposing the humanized PowerFactory
    # labels as the canonical enum names shown by the application and templates.
    SourceMode0 = ("According to Dispatched Active Power", 0)
    SourceMode1 = ("According to Rated Power", 1)
    SourceMode2 = ("Individual Reactive Power", 2)
    SourceMode3 = ("Maximise Reactive Reserve", 3)
    SourceMode4 = ("Voltage Setpoint Adaption", 4)

    def __new__(cls, value: str, code: int) -> "StationReactivePowerDistribution":
        """Create one humanized selector with its native integer code.

        :param value: Human-readable PowerFactory selector name.
        :param code: Native PowerFactory distribution code.
        :return: Typed distribution selector.
        """
        obj: StationReactivePowerDistribution = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def idx(self) -> int:
        """Return the native PowerFactory distribution code."""
        return self.code


class ReactivePowerLimitState(str, Enum):
    """Describe an optional initial generator reactive-limit active set."""

    Unknown = ("Unknown", -2)
    AtMinimum = ("At minimum", -1)
    Free = ("Free", 0)
    AtMaximum = ("At maximum", 1)

    def __new__(cls, value: str, code: int) -> "ReactivePowerLimitState":
        """Create one human-readable reactive-limit state.

        :param value: Human-readable state name.
        :param code: Stable numerical active-set code.
        :return: Typed reactive-limit state.
        """
        obj: ReactivePowerLimitState = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def idx(self) -> int:
        """Return the stable numerical active-set code."""
        return self.code


class GeneratorType(str, Enum):
    """
    Machine type of the generator element.
    """
    Synchronous = ("Synchronous", 0)
    Asynchronous = ("Asynchronous", 1)

    def __new__(cls, value: str, code: int):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    def idx(self) -> int:
        return self.code

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return GeneratorType[s]
        except KeyError:
            return s


class InvestmentEvaluationMethod(Enum):
    """
    Investment evaluation methods
    """
    CBA_PINT_TOOT = "CBA PINT-TOOT"
    PINT_TOOT_NSGA3 = "PINT-TOOT NSGA3"
    Hyperopt = "Hyperopt"
    MVRSM = "MVRSM"
    NSGA3 = "NSGA3"
    Random = "Random"
    MixedVariableGA = "Mixed Variable NSGA2"
    FromPlugin = "From plugin"

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


class CandidateKind(Enum):
    """
    Kinds of reinforcement produced by the candidate-investment generator.
    """
    NewLine = "New line"
    Upgrade = "Upgrade"
    ShuntReactor = "Shunt reactor"
    StaticGenerator = "Static generator"
    Battery = "Battery"

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
            return CandidateKind[s]
        except KeyError:
            return s


class CableResistanceInput(str, Enum):
    """Common input method for a cable's core and sheath resistances."""

    Resistivity = "Resistivity and filling factor"
    DcResistance = "DC resistance"

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return CableResistanceInput[s]
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
    algorithms supported by **VeraGrid**.
    """

    NR = 'Newton Raphson'
    NR_PC = 'Newton Raphson Predictor-Corrector'
    GAUSS = 'Gauss-Seidel'
    Decoupled_LU = 'Decoupled-LU Decomposition'
    GN = "Gauss-Newton"
    Linear = 'Linear'
    HELM = 'Holomorphic Embedding'
    # ZBUS = 'Z-Gauss-Seidel'
    PowellDogLeg = "Powell's Dog Leg"
    IWAMOTO = 'Iwamoto-Newton-Raphson'
    CONTINUATION_NR = 'Continuation-Newton-Raphson'

    LM = 'Levenberg-Marquardt'
    FASTDECOUPLED = 'Fast decoupled'
    LACPF = 'Linear AC'
    LINEAR_OPF = 'Linear OPF'
    NONLINEAR_OPF = 'Nonlinear OPF'
    GREEDY_DISPATCH_OPF = 'Greedy dispatch'
    Proportional_OPF = 'Proportional OPF'

    BFS = 'Backwards-Forward substitution'  # for PGM
    BFS_linear = 'Backwards-Forward substitution (linear)'  # for PGM
    Constant_Impedance_linear = 'Constant impedance linear'  # for PGM
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
    VeraGrid = 'VeraGrid'
    PGM = 'Power Grid Model'
    GSLV = "gslv"

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


class FmuTemplateDomain(Enum):
    """
    Available VeraGrid domains for reusable FMU templates.
    """

    RMS = "rms"
    EMT = "emt"


class FmuTemplateMode(Enum):
    """
    FMI 2.0 execution modes supported by the FMU template catalogue.
    """

    CO_SIMULATION = "CoSimulation"
    MODEL_EXCHANGE = "ModelExchange"


class NativeModelInterface(Enum):
    """Native manufacturer model interfaces recognized by VeraGrid."""

    IEEE_CIGRE_V1_1 = "ieee_cigre_v1_1"
    IEEE_CIGRE_V1_0 = "ieee_cigre_v1_0"
    IEC_ESE = "iec_ese"

    def __str__(self) -> str:
        """Return the persistent interface identifier.

        :return: Persistent interface identifier.
        """

        return str(self.value)


class NativeCompilerFramework(Enum):
    """Native compiler providers supported by VeraGrid build consumers."""

    LOCAL_LLVM = "local_llvm"

    def __str__(self) -> str:
        """Return the stable provider identifier.

        :return: Stable provider identifier.
        """

        return str(self.value)


class NativeSampleTimeSource(Enum):
    """Origin of the effective sample time used by a native model."""

    MANUFACTURER_DECLARED = "manufacturer_declared"

    def __str__(self) -> str:
        """Return the persistent sample-time source identifier.

        :return: Persistent sample-time source identifier.
        """

        return str(self.value)


class IeeeCigreDllPlatform(Enum):
    """Qualified host platforms for IEEE/CIGRE manufacturer libraries."""

    WINDOWS_X86 = "windows_x86"
    WINDOWS_X64 = "windows_x64"
    LINUX_X64 = "linux_x64"

    def __str__(self) -> str:
        """Return the persistent platform identifier.

        :return: Persistent platform identifier.
        """

        return str(self.value)


class IeeeCigreDllDataType(Enum):
    """Primitive data types declared by the IEEE/CIGRE V1.1 ABI."""

    CHAR = 1
    INT8 = 2
    UINT8 = 3
    INT16 = 4
    UINT16 = 5
    INT32 = 6
    UINT32 = 7
    REAL32 = 8
    REAL64 = 9
    C_STRING = 10


class IeeeCigreDllModelMode(Enum):
    """Simulation domains declared by an IEEE/CIGRE model."""

    UNSPECIFIED = 0
    EMT = 1
    RMS = 2
    EMT_AND_RMS = 3


class IeeeCigreDllVerificationStatus(Enum):
    """Verification state for one manufacturer binary variant."""

    UNVERIFIED = "unverified"
    DECLARED_AND_QUALIFIED = "declared_and_qualified"
    REJECTED = "rejected"

    def __str__(self) -> str:
        """Return the persistent verification state.

        :return: Persistent verification state.
        """

        return str(self.value)


class FmiVersion(str, Enum):
    """FMI specification families recognized by VeraGrid.

    Maintenance documents do not necessarily define a new XML version or ABI.
    FMI 1.0.1 and FMI 2.0.x therefore remain in the 1.0 and 2.0 families,
    while stable FMI 3.0.x declarations remain in the 3.0 family. Recognizing
    a family does not imply that every importer, runtime, or exporter supports
    every interface in that family.
    """

    FMI_1_0 = "1.0"
    FMI_2_0 = "2.0"
    FMI_3_0 = "3.0"


class FmuInterfaceMode(str, Enum):
    """Execution interfaces currently represented by the FMU importer."""

    CO_SIMULATION = "CoSimulation"
    MODEL_EXCHANGE = "ModelExchange"


class FmuVariableType(str, Enum):
    """Primitive variable types recognized in FMI model descriptions."""

    REAL = "Real"
    INTEGER = "Integer"
    BOOLEAN = "Boolean"
    STRING = "String"
    ENUMERATION = "Enumeration"
    FLOAT32 = "Float32"
    FLOAT64 = "Float64"
    INT8 = "Int8"
    UINT8 = "UInt8"
    INT16 = "Int16"
    UINT16 = "UInt16"
    INT32 = "Int32"
    UINT32 = "UInt32"
    INT64 = "Int64"
    UINT64 = "UInt64"
    BINARY = "Binary"
    UNKNOWN = "Unknown"


class FmiThreeVariableCausality(str, Enum):
    """Variable causalities defined by the FMI 3 model-description schema."""

    STRUCTURAL_PARAMETER = "structuralParameter"
    PARAMETER = "parameter"
    CALCULATED_PARAMETER = "calculatedParameter"
    INPUT = "input"
    OUTPUT = "output"
    LOCAL = "local"
    INDEPENDENT = "independent"


class FmuSourceKind(str, Enum):
    """Kinds of FMU source accepted at the import boundary."""

    ZIP = "zip"
    DIRECTORY = "directory"


class FmuBinaryInterface(Enum):
    """Native FMI binary entry-point family required by one FMU."""

    FMI_ONE_CO_SIMULATION = "fmi_one_co_simulation"
    FMI_ONE_MODEL_EXCHANGE = "fmi_one_model_exchange"
    FMI_TWO_CO_SIMULATION = "fmi_two_co_simulation"
    FMI_TWO_MODEL_EXCHANGE = "fmi_two_model_exchange"
    FMI_THREE_CO_SIMULATION = "fmi_three_co_simulation"
    FMI_THREE_MODEL_EXCHANGE = "fmi_three_model_exchange"


class InterfaceType(str, Enum):
    """FMI interface selected when exporting a VeraGrid model."""

    CO_SIMULATION = "co-simulation"
    MODEL_EXCHANGE = "model-exchange"


class IntegrationMethod(str, Enum):
    """Numerical integration schemes supported by generated FMU code."""

    BACKWARD_EULER = "backward_euler"
    TRAPEZOIDAL = "trapezoidal"
    BDF2 = "bdf2"


class TargetPlatform(str, Enum):
    """Native platform directory supported by an FMU binary."""

    WIN64 = "win64"
    LINUX64 = "linux64"
    DARWIN64 = "darwin64"
    DARWIN_ARM64 = "darwin64-arm64"


class VariableCategory(str, Enum):
    """Internal variable categories used by both FMU export modes."""

    STATE = "state"
    DERIVATIVE = "derivative"
    DIFF = "diff"
    ALGEBRAIC = "algebraic"
    INPUT = "input"
    CONST_PARAM = "const_param"
    RUNTIME_PARAM = "runtime_param"


class RuntimeGroup(str, Enum):
    """Runtime event or mode group assigned to an FMU parameter."""

    EVENT = "event"
    MODE = "mode"


class EquationGroup(str, Enum):
    """Equation sections emitted by the FMU export pipeline."""

    STATE = "state"
    DERIVATIVE = "derivative"
    ALGEBRAIC = "algebraic"
    RUNTIME_INIT = "runtime_init"
    INIT = "init"
    DIFF_INIT = "diff_init"


class StorageSegment(str, Enum):
    """Generated runtime storage segments addressed by exported variables."""

    STATES = "states"
    DERIVATIVES = "derivatives"
    ALGEBRAICS = "algebraics"
    INPUTS = "inputs"
    CONST_PARAMS = "const_params"
    RUNTIME_PARAMS = "runtime_params"


class Precedence(IntEnum):
    """C expression precedence levels used by FMU code generation."""

    COMPARISON = 1
    ADDITIVE = 2
    MULTIPLICATIVE = 3
    UNARY = 4
    CALL = 5
    ATOM = 6


class FmuBindingDirection(str, Enum):
    """Direction of a VeraGrid-to-FMU signal binding."""

    INPUT = "input"
    OUTPUT = "output"
    PARAMETER = "parameter"


class FmuDeviceDomain(str, Enum):
    """VeraGrid simulation domain hosting an FMU device."""

    RMS = "rms"
    EMT = "emt"


class FmiThreeWorkerFloat64Profile(Enum):
    """Supported FMI 3 Float64 variable shapes for a worker."""

    SCALAR = 1
    CONSTANT_ARRAY = 2
    CONFIGURABLE_ARRAY = 3


class FmiThreeWorkerProtocolVersion(IntEnum):
    """FMI 3 worker wire-protocol versions recognized by VeraGrid."""

    VERSION_THREE = 3
    VERSION_FOUR = 4
    VERSION_FIVE = 5
    VERSION_SIX = 6
    VERSION_SEVEN = 7
    VERSION_EIGHT = 8
    VERSION_NINE = 9
    VERSION_TEN = 10
    VERSION_ELEVEN = 11


class FmiThreeWorkerFrameDirection(IntEnum):
    """Direction of one FMI 3 worker protocol frame."""

    REQUEST = 1
    RESPONSE = 2


class FmiThreeWorkerRequestKind(IntEnum):
    """Operations accepted by the FMI 3 worker."""

    START = 1
    INITIALIZE = 2
    CLOSE = 3
    SET_FLOAT64 = 4
    GET_FLOAT64 = 5
    DO_STEP = 6
    CONFIGURE_FLOAT64 = 7
    CONFIGURE_UINT64 = 8
    SET_TIME = 9
    SET_CONTINUOUS_STATES = 10
    GET_CONTINUOUS_STATES = 11
    GET_DERIVATIVES = 12
    COMPLETED_INTEGRATOR_STEP = 13
    ENTER_EVENT_MODE = 14
    UPDATE_DISCRETE_STATES = 15
    ENTER_CONTINUOUS_TIME_MODE = 16
    GET_EVENT_INDICATORS = 17
    GET_NOMINALS_OF_CONTINUOUS_STATES = 18
    SAVE_CHECKPOINT = 19
    RESTORE_CHECKPOINT = 20
    DISCARD_CHECKPOINT = 21
    EVALUATE_MODEL_EXCHANGE = 22
    SET_INT32 = 23
    GET_INT32 = 24


class FmiThreeWorkerResponseKind(IntEnum):
    """Successful and failed outcomes returned by the FMI 3 worker."""

    READY = 1
    INITIALIZED = 2
    CLOSED = 3
    FLOAT64_SET = 4
    FLOAT64_VALUES = 5
    STEP_COMPLETED = 6
    CONFIGURED = 7
    TIME_SET = 8
    CONTINUOUS_STATES_SET = 9
    CONTINUOUS_STATES_VALUES = 10
    DERIVATIVE_VALUES = 11
    INTEGRATOR_STEP_COMPLETED = 12
    EVENT_MODE_ENTERED = 13
    DISCRETE_STATES_UPDATED = 14
    CONTINUOUS_TIME_MODE_ENTERED = 15
    EVENT_INDICATOR_VALUES = 16
    CONTINUOUS_STATE_NOMINAL_VALUES = 17
    CHECKPOINT_SAVED = 18
    CHECKPOINT_RESTORED = 19
    CHECKPOINT_DISCARDED = 20
    MODEL_EXCHANGE_EVALUATED = 21
    INT32_SET = 22
    INT32_VALUES = 23
    ERROR = 255


class FmiThreeWorkerFailureKind(IntEnum):
    """Stable failure categories returned by the FMI 3 worker."""

    PROTOCOL = 1
    DEPENDENCY = 2
    ARCHIVE = 3
    LIFECYCLE = 4
    NATIVE = 5
    VARIABLE_ACCESS = 6


class FmiThreeWorkerHostState(Enum):
    """Lifecycle state of the parent-side FMI 3 worker host."""

    CREATED = 1
    STARTING = 2
    READY = 3
    CONFIGURING = 4
    INITIALIZING = 5
    INITIALIZED = 6
    INPUT_VALUES_PENDING_STEP = 7
    TERMINATION_REQUESTED = 8
    EVENT_MODE_REQUESTED = 9
    CONTINUOUS_TIME = 10
    EVENT_MODE = 11
    STOPPING = 12
    CLOSED = 13
    FAILED = 14


class MIPSolvers(Enum):
    """
    MIP solvers enumeration
    """
    HIGHS = 'HIGHS'
    SCIP = 'SCIP'
    CPLEX = 'CPLEX'
    GUROBI = 'GUROBI'
    XPRESS = 'XPRESS'
    CBC = 'CBC'
    PDLP = 'PDLP'
    CUOPT = "CUOPT"
    COPT = "COPT"

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
            return MIPSolvers.HIGHS


class MIPFramework(Enum):
    """
    MIP framework enumeration
    """
    OrTools = 'or-tools'
    PuLP = 'PuLP'

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
            return MIPFramework[s]
        except KeyError:
            return MIPFramework.PuLP


class SolutionState(Enum):
    """
    Quality of an NTC solution: strictly optimal, optimal but with relaxed (slacked)
    limits, or not solved to optimality at all
    """
    Optimal = 'Optimal'
    Relaxed = 'Optimal with relaxed limits'
    NotOptimal = 'Not optimal'

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
            return SolutionState[s]
        except KeyError:
            return SolutionState.NotOptimal


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
    Linear = 'Linear'
    PTDF_scan = "PTDF Scan"

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
        return list(enum_item.value for enum_item in cls)


class SchematicBranchEndpoint(Enum):
    """
    Schematic branch endpoint identifiers.
    """
    FROM = "from"
    TO = "to"

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
            return SchematicBranchEndpoint[s]
        except KeyError:
            return s


class SchematicAttachmentSide(Enum):
    """
    Schematic attachment-side identifiers.
    """
    DEFAULT = "default"
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"

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
            return SchematicAttachmentSide[s]
        except KeyError:
            return s


class SchematicAttachmentOwnerKind(Enum):
    """
    Schematic attachment owner kinds.
    """
    BUS = "bus"
    FLUID = "fluid"

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
            return SchematicAttachmentOwnerKind[s]
        except KeyError:
            return s


class SchematicRouteKind(Enum):
    """
    Schematic route kinds.
    """
    ORTHOGONAL = "orthogonal"
    AUTO = "auto"
    AUTO_ORTHOGONAL = "auto-orthogonal"
    AUTO_POLYLINE = "auto-polyline"
    MANUAL_ORTHOGONAL = "manual-orthogonal"
    MANUAL_POLYLINE = "manual-polyline"

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
            return SchematicRouteKind[s]
        except KeyError:
            return s


class SchematicAutoRouteStyle(Enum):
    """
    Schematic automatic route styles.
    """
    RETICULAR = "reticular"
    STRAIGHT = "straight"

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
            return SchematicAutoRouteStyle[s]
        except KeyError:
            return s


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
        return list(enum_item.value for enum_item in cls)


class TapModuleControl(str, Enum):
    """
    Tap module control types
    """
    fixed = ('Fixed', 0)
    Vm = ('Vm', 1)
    Qf = ('Qf', 2)
    Qt = ('Qt', 3)

    def __new__(cls, value: str, code: int):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    def idx(self) -> int:
        return self.code

    @staticmethod
    def argparse(s):
        try:
            return TapModuleControl[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class TapPhaseControl(str, Enum):
    """
    Tap angle control types
    """
    fixed = ('Fixed', 0)
    Pf = ('Pf', 1)
    Pt = ('Pt', 2)

    # Droop = "Droop"

    def __new__(cls, value: str, code: int):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    def idx(self) -> int:
        return self.code

    @staticmethod
    def argparse(s):
        try:
            return TapPhaseControl[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class ConverterControlType(str, Enum):
    """
    Converter control types
    """
    Vm_dc = ('Vm_dc', 1)
    Vm_ac = ('Vm_ac', 2)
    Va_ac = ('Va_ac', 3)
    Qac = ('Q_ac', 4)
    Pdc = ('P_dc', 5)
    Pac = ('P_ac', 6)
    Pdc_angle_droop = ('P_dc_angle_droop', 7)  # PMODE3
    Pdc_droop = ('P_dc_droop', 8)  # DC power / DC voltage droop: Pdc = Pdc* + Pdroop * (Vdc* - Vdc)
    Q_droop = ("Q_droop", 9)
    P_droop = ("P_droop", 10)
    Imax = ('Imax', 11)
    Fault1 = ('Fault1', 12)
    Fault2 = ('Fault2', 13)

    def __new__(cls, value: str, code: int):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    def idx(self) -> int:
        return self.code

    @staticmethod
    def argparse(s):
        try:
            return ConverterControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class ValveEmtType(Enum):
    """
    Enumeration of EMT valve physical types.
    """

    Diode = "Diode"
    Igbt = "IGBT"
    Thyristor = "Thyristor"

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        """Return the stable display representation of the EMT valve type.

        :return: Human-readable EMT valve-type value.
        """
        return str(self)

    @staticmethod
    def argparse(s):
        """
        :param s:
        :return:
        """
        try:
            return ValveEmtType[s]
        except KeyError:
            return s


class ValveEmtModelVariant(Enum):
    """
    Enumeration of EMT valve modelling variants.
    """

    Ideal = "Ideal"
    Complete = "Complete"

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def argparse(s):
        """
        :param s:
        :return:
        """
        try:
            return ValveEmtModelVariant[s]
        except KeyError:
            return s


class ValveInitializationState(Enum):
    """
    Enumeration of valve initialization states.
    """

    FromPowerFlow = "From power flow"
    Blocked = "Blocked"
    ForwardConducting = "Forward conducting"
    ReverseConducting = "Reverse conducting"

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def argparse(s):
        """
        :param s:
        :return:
        """
        try:
            return ValveInitializationState[s]
        except KeyError:
            return s


class HvdcControlType(str, Enum):
    """
    Simple HVDC control types
    """
    type_0_free = ('0:Free', 0)
    type_1_Pset = ('1:Pdc', 1)

    def __new__(cls, value: str, code: int):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    def idx(self) -> int:
        return self.code

    @staticmethod
    def argparse(s):
        try:
            return HvdcControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


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


class ConverterFaultControlType(str, Enum):
    """
    Converter fault control types
    """
    Standard = ('Standard', 0)
    WECC_WT_Type_4B = ('WECC_WT_Type_4B', 1)

    def __new__(cls, value: str, code: int):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    def idx(self) -> int:
        return self.code

    @staticmethod
    def argparse(s):
        try:
            return ConverterFaultControlType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class FaultType(Enum):
    """
    Short circuit type
    """
    LG = 'LG'
    LL = 'LL'
    LLG = 'LLG'
    LLL = 'LLL'
    LLLG = 'LLLG'

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
        return list(enum_item.value for enum_item in cls)


class EmtFaultPlacementSide(Enum):
    """
    Internal EMT fault placement side within one composed branch model.
    """
    FromSide = 'FromSide'
    ToSide = 'ToSide'

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
            return EmtFaultPlacementSide[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class MethodShortCircuit(Enum):
    """
    Short circuit type
    """
    sequences = 'sequences'
    sequences_vsc = 'sequences_vsc'
    phases = 'phases'

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
            return MethodShortCircuit[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """
        :return:
        """
        return list(enum_item.value for enum_item in cls)


class PhasesShortCircuit(Enum):
    """
    Short circuit type
    """
    abc = 'abc'
    ab = 'ab'
    bc = 'bc'
    ca = 'ca'
    a = 'a'
    b = 'b'
    c = 'c'

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
            return PhasesShortCircuit[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """
        :return:
        """
        return list(enum_item.value for enum_item in cls)


class WindingsConnection(str, Enum):
    """
    Transformer windings connection types
    """
    # G: grounded star
    # S: ungrounded star
    # D: delta
    GG = ('GG', 0)
    GS = ('GS', 1)
    GD = ('GD', 2)
    SS = ('SS', 3)
    SD = ('SD', 4)
    DD = ('DD', 5)

    def __new__(cls, value: str, code: int):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    def idx(self) -> int:
        return self.code

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
        return list(enum_item.value for enum_item in cls)


class TerminalType(Enum):
    """
    Terminal types
    """
    # AC: AC converter side
    # DC+: DC+ converter side
    # DC-: DC- converter side
    # OTHER: Other terminal type such as in transformer3w
    AC = 'AC'
    DC_P = 'DC+'
    DC_N = 'DC-'
    OTHER = 'Other'

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
            return TerminalType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class WaveformSequenceType(Enum):
    """
        Squence points type
    """


class V_I_CurveSequenceType(Enum):
    """
        Squence points type
    """


class X_Y_SequenceType(Enum):
    """
        Squence points type
    """


class X_Y_Z_Matrix(Enum):
    """
        Squence points type
    """


class WindingType(str, Enum):
    """
    Transformer windings connection types
    """
    NeutralStar = ("Yn", 0)
    FloatingStar = ("Y", 1)
    GroundedStar = ("Yg", 2)
    Delta = ("D", 3)
    NeutralZigZag = ("Zn", 4)
    FloatingZigZag = ("Z", 4)
    GroundedZigZag = ("Zg", 4)

    def __new__(cls, value: str, code: int):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    def idx(self) -> int:
        return self.code

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return WindingType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class ShuntConnectionType(str, Enum):
    """
    Loads, shunts, etc.. connection types
    """
    NeutralStar = ("Yn", 0)
    GroundedStar = ("Yg", 1)
    Delta = ("D", 2)
    FloatingStar = ("Y", 3)

    def __new__(cls, value: str, code: int):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.code = code
        return obj

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    def idx(self) -> int:
        return self.code

    @staticmethod
    def argparse(s):
        """

        :param s:
        :return:
        """
        try:
            return ShuntConnectionType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


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
        return list(enum_item.value for enum_item in cls)


class PrpCat(Enum):
    """
    ActionType
    """
    All = 'All'
    MT = 'Metadata'
    TP = 'Topology'
    PF = 'Power flow'
    PF3 = 'Power flow (unbalanced)'
    SC = "Short Circuit"
    OPF = 'Optimal Power flow'
    CON = "Contingencies"
    REL = 'Reliability'
    NTC = 'Net Transfer Capacity'
    INV = "Investments"
    RMS = 'RMS'
    EMT = 'EMT'

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
        return list(enum_item.value for enum_item in cls)


# class GpfControlType(Enum):
#     """
#     GENERALISED PF Control types
#     """
#     type_None = '0:None'
#     type_Vm = '1:Vm'
#     type_Va = '2:Va'
#     type_Pzip = '3:Pzip'
#     type_Qzip = '4:Qzip'
#     type_Pf = '5:Pf'
#     type_Qf = '6:Qf'
#     type_Pt = '7:Pt'
#     type_Qt = '8:Qt'
#     type_TapMod = '9:m'
#     type_TapAng = '10:tau'
#
#     def __str__(self) -> str:
#         return str(self.value)
#
#     def __repr__(self):
#         return str(self)
#
#     @staticmethod
#     def argparse(s):
#         """
#         :param s:
#         :return:
#         """
#         try:
#             return GpfControlType[s]
#         except KeyError:
#             return s
#
#     @classmethod
#     def list(cls):
#         """
#         :return:
#         """
#         return list(enum_item.value for enum_item in cls)


class DgsDynamicAssociationRole(Enum):
    """Define the physical or logical role of one DGS composite relation."""

    __slots__ = ()

    CompositeController = "CompositeController"
    ControllerModel = "ControllerModel"
    PhysicalHost = "PhysicalHost"
    Measurement = "Measurement"
    SwitchActuator = "SwitchActuator"
    ValveActuator = "ValveActuator"
    PassiveActuator = "PassiveActuator"
    Unknown = "Unknown"

    def __str__(self) -> str:
        """Return the persistent enum value."""
        return str(self.value)

    def __repr__(self) -> str:
        """Return the persistent enum representation."""
        return str(self)


class DeviceType(Enum):
    """
    Device types
    """
    NoDevice = 'NoDevice'
    PhysicalDeviceType = 'PhysicalDeviceType'

    TimeDevice = 'Time'
    CircuitDevice = 'Circuit'
    BusDevice = 'Bus'
    BranchDevice = 'Branch'
    BranchTypeDevice = 'Branch template'
    LineDevice = 'Line'
    LineTypeDevice = 'Line Template'
    Transformer2WDevice = 'Transformer'
    Transformer3WDevice = 'Transformer3W'
    TransformerNwDevice = 'TransformerNw'
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
    ShuntLikeDevice = 'Shunt like devices'
    UpfcDevice = 'UPFC'  # unified power flow controller
    ExternalGridDevice = 'External grid'
    LoadLikeDevice = 'Load like'
    BranchGroupDevice = 'Branch group'
    LambdaDevice = r"Loading from the base situation ($\lambda$)"
    ExciterDevice = "Exciter"
    GovernorDevice = "Governor"
    StabilizerDevice = "Stabilizer"

    PiMeasurementDevice = 'Pi Measurement'
    QiMeasurementDevice = 'Qi Measurement'
    PgMeasurementDevice = 'Pg Measurement'
    QgMeasurementDevice = 'Qg Measurement'
    PfMeasurementDevice = 'Pf Measurement'
    QfMeasurementDevice = 'Qf Measurement'
    PtMeasurementDevice = 'Pt Measurement'
    QtMeasurementDevice = 'Qt Measurement'
    VmMeasurementDevice = 'Vm Measurement'
    VaMeasurementDevice = 'Va Measurement'
    IfMeasurementDevice = 'If Measurement'
    ItMeasurementDevice = 'It Measurement'

    WireDevice = 'Wire'
    UndergroundCableTypeDevice = 'Underground cable'
    DcCableTypeDevice = 'DC cable type'
    SequenceLineDevice = 'Sequence line'
    UnderGroundLineDevice = 'Underground line'
    OverheadLineTypeDevice = 'Tower'
    AnyLineTemplateDevice = "Any line template"
    TransformerTypeDevice = 'Transformer type'
    SwitchDevice = 'Switch'

    GenericArea = 'Generic Area'
    SubstationDevice = 'Substation'
    AreaDevice = 'Area'
    ZoneDevice = 'Zone'
    CountryDevice = 'Country'
    CommunityDevice = 'Community'
    RegionDevice = 'Region'
    MunicipalityDevice = 'Municipality'
    BusBarDevice = 'BusBar'
    VoltageLevelDevice = 'Voltage level'
    VoltageLevelTemplate = 'Voltage level template'

    Technology = 'Technology'
    TechnologyGroup = 'Technology Group'
    TechnologyCategory = 'Technology Category'
    Owner = 'Owner'

    ContingencyDevice = 'Contingency'
    ContingencyGroupDevice = 'Contingency Group'

    RemedialActionDevice = 'Remedial action'
    RemedialActionGroupDevice = 'Remedial action Group'

    ShortCircuitEvent = 'Short circuit event'

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

    FacilityDevice = "Facility"

    MarketUnitsGroupDevice = "Market units group"
    MarketUnitDevice = "Market unit"

    SimulationOptionsDevice = "SimulationOptionsDevice"

    InterAggregationInfo = "InterAggregationInfo"

    BusOrBranch = "BusOrBranch"

    DynamicModelHostDevice = "Dynamic Model Host"

    RmsModelTemplateDevice = "RMS template"
    ManufacturerNativeModelDevice = "Manufacturer native model"
    FmuTemplateDevice = "FMU template"
    RmsEventDevice = "Rms Event"
    RmsEventsGroupDevice = "Rms Events Group"

    EmtModelTemplateDevice = "EMT template"
    EmtEventDevice = "Emt Event"
    EmtEventsGroupDevice = "Emt Events Group"

    DynamicPlotEntry = "Plot Event"
    DynamicPlotGroupDevice = "Plot Group"

    ControlPc = "Control PC"

    VarFactory = "Var Factory"

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
        return list(enum_item.value for enum_item in cls)


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
    ListOfWires = 'ListOfWires'
    ListOfCables = 'ListOfCables'
    AdmittanceMatrix = "Admittance Matrix"
    ImpedanceTripletList = "Impedance Triplet List"
    DaeBlockType = "DaeBlock"
    VarType = "VarType"
    ConstType = "ConstType"
    MergeInformation = "MergeInformation"
    ManufacturerNativeModelInfo = "IEEE CIGRE DLL ModelInfo"

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
        return list(enum_item.value for enum_item in cls)


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
        return list(enum_item.value for enum_item in cls)


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
        return list(enum_item.value for enum_item in cls)


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
    NodeGroups = 'NodeGroups'
    StochasticPowerFlow = 'StochasticPowerFlow'
    RmsSimulation = "RmsSimulation"
    EmtSimulation = "EmtSimulation"
    SmallSignalStability = "SmallSignalStability"

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
        return list(enum_item.value for enum_item in cls)


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
        return list(enum_item.value for enum_item in cls)


class InvestmentsEvaluationObjectives(Enum):
    """
    Types of investment optimization objectives
    """
    PowerFlow = 'PowerFlow'
    TimeSeriesPowerFlow = 'TimeSeriesPowerFlow'
    LinearOptimalPowerFlowTimeSeries = 'Linear OPF time series'
    OptimalPowerFlowThenPowerFlowTimeSeries = 'Linear OPF + Power flow time series'
    GenerationAdequacy = "Adequacy"
    SimpleDispatch = "Simple dispatch"
    FromPlugin = 'From Plugin'

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
        return list(enum_item.value for enum_item in cls)


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


class FileType(Enum):
    """
    Enumeration of logs severities
    """
    VeraGrid = "VeraGrid"
    VeraGridScenario = "VeraGrid Scenario"
    VeraGrid_xlsx1 = "VeraGrid Excel 1"
    VeraGrid_xlsx2 = "VeraGrid Excel 2"
    VeraGrid_xlsx3 = "VeraGrid Excel 3"
    VeraGrid_xlsx4 = "VeraGrid Excel 4"
    VeraGrid_delta = "VeraGrid Delta"
    VeraGrid_sqlite = "VeraGrid SQLite"
    VeraGrid_h5 = "VeraGrid H5"
    VeraGrid_json = "VeraGrid Json"
    VeraGrid_ejson3 = "Ejson3"
    Matpower = "Matpower"
    DPX = "DPX"
    PWF = "PWF"
    EPC = "EPC"
    PyPsa_h5 = "PyPSA H5"
    PyPsa = "PyPsa"
    PandaPower = "Pandapower"
    Iidm = "Iidm"
    Eurostag = "Eurostag"
    PSSE_raw = "PSS/e raw"
    PSSE_rawx = "PSS/e rawx"
    DGS = "DGS"
    CGMES = 'CGMES'
    CIM = "CIM"
    UCTE = 'UCTE'
    RTE_xml = "RTE_XML"
    IPA = "IPA"
    PGM = "Power grid models"
    generic_excel = "Generic Excel"

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
            return FileType[s]
        except KeyError:
            return s


class PsseTopologyExportMode(Enum):
    """
    Enumeration of PSSE RAW topology export strategies.
    """
    BusBranch = "BusBranch"
    NodeBreaker = "NodeBreaker"

    def __str__(self):
        """
        Return the display string of the enumeration.

        :return: Display string.
        """
        return self.value

    def __repr__(self):
        """
        Return the representation string of the enumeration.

        :return: Representation string.
        """
        return str(self)

    @staticmethod
    def argparse(s):
        """
        Parse a command-line value into the enumeration.

        :param s: Input string.
        :return: Parsed enumeration or original input.
        """
        try:
            return PsseTopologyExportMode[s]
        except KeyError:
            return s


class PsseExportMode(Enum):
    """
    Enumeration of PSSE export output strategies.
    """
    SingleFile = "Single file"
    BatchZip = "Batch zip package"

    def __str__(self):
        """
        Return the display string of the enumeration.

        :return: Display string.
        """
        return self.value

    def __repr__(self):
        """
        Return the representation string of the enumeration.

        :return: Representation string.
        """
        return str(self)

    @staticmethod
    def argparse(s):
        """
        Parse a command-line value into the enumeration.

        :param s: Input string.
        :return: Parsed enumeration or original input.
        """
        try:
            return PsseExportMode[s]
        except KeyError:
            return s


class DgsExportMode(Enum):
    """
    Enumeration of DGS export output strategies.
    """
    SingleFile = "Single file"
    BatchZip = "Batch zip package"

    def __str__(self):
        """
        Return the display string of the enumeration.

        :return: Display string.
        """
        return self.value

    def __repr__(self):
        """
        Return the representation string of the enumeration.

        :return: Representation string.
        """
        return str(self)

    @staticmethod
    def argparse(s):
        """
        Parse a command-line value into the enumeration.

        :param s: Input string.
        :return: Parsed enumeration or original input.
        """
        try:
            return DgsExportMode[s]
        except KeyError:
            return s


class MatpowerExportMode(Enum):
    """
    Enumeration of MATPOWER export output strategies.
    """
    SingleFile = "Single file"
    BatchZip = "Batch zip package"

    def __str__(self):
        """
        Return the display string of the enumeration.

        :return: Display string.
        """
        return self.value

    def __repr__(self):
        """
        Return the representation string of the enumeration.

        :return: Representation string.
        """
        return str(self)

    @staticmethod
    def argparse(s):
        """
        Parse a command-line value into the enumeration.

        :param s: Input string.
        :return: Parsed enumeration or original input.
        """
        try:
            return MatpowerExportMode[s]
        except KeyError:
            return s


class UcteExportMode(Enum):
    """
    Enumeration of UCTE export output strategies.
    """
    SingleFile = "Single file"
    BatchZip = "Batch zip package"

    def __str__(self):
        """
        Return the display string of the enumeration.

        :return: Display string.
        """
        return self.value

    def __repr__(self):
        """
        Return the representation string of the enumeration.

        :return: Representation string.
        """
        return str(self)

    @staticmethod
    def argparse(s):
        """
        Parse a command-line value into the enumeration.

        :param s: Input string.
        :return: Parsed enumeration or original input.
        """
        try:
            return UcteExportMode[s]
        except KeyError:
            return s


class CgmesExportMode(Enum):
    """
    Enumeration of CGMES export output strategies.
    """
    SingleFile = "Single file"
    BatchZip = "Batch zip package"

    def __str__(self):
        """
        Return the display string of the enumeration.

        :return: Display string.
        """
        return self.value

    def __repr__(self):
        """
        Return the representation string of the enumeration.

        :return: Representation string.
        """
        return str(self)

    @staticmethod
    def argparse(s):
        """
        Parse a command-line value into the enumeration.

        :param s: Input string.
        :return: Parsed enumeration or original input.
        """
        try:
            return CgmesExportMode[s]
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


class CgmesTopologyMode(Enum):
    """
    Topology conversion mode for CGMES imports.
    """
    Auto = "Auto"
    ConnectivityNode = "ConnectivityNode"
    TopologicalNode = "TopologicalNode"

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
            return CgmesTopologyMode[s]
        except KeyError:
            return s


class CgmesBoundaryPlaceholderMode(Enum):
    """
    Boundary placeholder creation mode for CGMES conversion.
    """
    Always = "Always"
    KnownBoundaryOnly = "KnownBoundaryOnly"
    Never = "Never"

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
            return CgmesBoundaryPlaceholderMode[s]
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
    BusActivePower = 'P: Active power'

    BusActivePowerA = 'PA: Active power A'
    BusActivePowerB = 'PB: Active power B'
    BusActivePowerC = 'PC: Active power C'

    BusReactivePower = 'Q: Reactive power'

    BusReactivePowerA = 'QA: Reactive power A'
    BusReactivePowerB = 'QB: Reactive power B'
    BusReactivePowerC = 'QC: Reactive power C'

    BusActivePowerIncrement = "ΔP: Active power increment"

    BranchActivePowerFromBase = 'Pf: Active power "from" base case'
    BranchActivePowerFrom = 'Pf: Active power "from"'
    BranchActivePowerFromA = 'PfA: Active power "from" A'
    BranchActivePowerFromB = 'PfB: Active power "from" B'
    BranchActivePowerFromC = 'PfC: Active power "from" C'

    BranchReactivePowerFrom = 'Qf: Reactive power "from"'
    BranchReactivePowerFromA = 'QfA: Reactive power "from" A'
    BranchReactivePowerFromB = 'QfB: Reactive power "from" B'
    BranchReactivePowerFromC = 'QfC: Reactive power "from" C'

    BranchActivePowerTo = 'Pt: Active power "to"'
    BranchActivePowerToA = 'Pt: Active power "to" A'
    BranchActivePowerToB = 'Pt: Active power "to" B'
    BranchActivePowerToC = 'Pt: Active power "to" C'

    BranchReactivePowerTo = 'Qt: Reactive power "to"'
    BranchReactivePowerToA = 'Qt: Reactive power "to" A'
    BranchReactivePowerToB = 'Qt: Reactive power "to" B'
    BranchReactivePowerToC = 'Qt: Reactive power "to" C'

    BranchActiveCurrentFrom = 'Irf: Active current "from"'
    BranchActiveCurrentFromA = 'Irf: Active current "from" A'
    BranchActiveCurrentFromB = 'Irf: Active current "from" B'
    BranchActiveCurrentFromC = 'Irf: Active current "from" C'

    BranchReactiveCurrentFrom = 'Iif: Reactive current "from"'
    BranchReactiveCurrentFromA = 'Iif: Reactive current "from" A'
    BranchReactiveCurrentFromB = 'Iif: Reactive current "from" B'
    BranchReactiveCurrentFromC = 'Iif: Reactive current "from" C'

    BranchActiveCurrentTo = 'Irt: Active current "to"'
    BranchActiveCurrentToA = 'Irt: Active current "to" A'
    BranchActiveCurrentToB = 'Irt: Active current "to" B'
    BranchActiveCurrentToC = 'Irt: Active current "to" C'

    BranchReactiveCurrentTo = 'Iit: Reactive current "to"'
    BranchReactiveCurrentToA = 'Iit: Reactive current "to" A'
    BranchReactiveCurrentToB = 'Iit: Reactive current "to" B'
    BranchReactiveCurrentToC = 'Iit: Reactive current "to" C'

    BranchTapModule = 'm: Tap module'
    BranchTapAngle = '𝜏: Tap angle'
    BranchBeq = 'Beq: Equivalent susceptance'

    BranchLoading = 'Branch Loading'
    BranchLoadingA = 'Branch Loading A'
    BranchLoadingB = 'Branch Loading B'
    BranchLoadingC = 'Branch Loading C'

    BranchVoltage = 'ΔV: Voltage modules drop'
    BranchVoltageA = 'ΔV: Voltage modules drop A'
    BranchVoltageB = 'ΔV: Voltage modules drop B'
    BranchVoltageC = 'ΔV: Voltage modules drop C'

    BranchAngles = 'Δθ: Voltage angles drop'
    BranchAnglesA = 'Δθ: Voltage angles drop A'
    BranchAnglesB = 'Δθ: Voltage angles drop B'
    BranchAnglesC = 'Δθ: Voltage angles drop C'

    BranchLosses = 'Branch losses'

    BranchActiveLosses = 'Pl: Active losses'
    BranchActiveLossesA = 'Pl: Active losses A'
    BranchActiveLossesB = 'Pl: Active losses B'
    BranchActiveLossesC = 'Pl: Active losses C'

    BranchReactiveLosses = 'Ql: Reactive losses'
    BranchReactiveLossesA = 'Ql: Reactive losses A'
    BranchReactiveLossesB = 'Ql: Reactive losses B'
    BranchReactiveLossesC = 'Ql: Reactive losses C'

    BranchActiveLossesPercentage = 'Pl: Active losses (%)'
    BranchActiveLossesPercentageA = 'Pl: Active losses (%) A'
    BranchActiveLossesPercentageB = 'Pl: Active losses (%) B'
    BranchActiveLossesPercentageC = 'Pl: Active losses (%) C'

    BatteryPower = 'Battery power'
    BatteryEnergy = 'Battery energy'

    HvdcLosses = 'HVDC losses'
    HvdcLoading = 'HVDC loading'

    HvdcPowerFrom = 'HVDC power "from"'
    HvdcPowerFromA = 'HVDC power "from" A'
    HvdcPowerFromB = 'HVDC power "from" B'
    HvdcPowerFromC = 'HVDC power "from" C'

    HvdcPowerTo = 'HVDC power "to"'
    HvdcPowerToA = 'HVDC power "to" A'
    HvdcPowerToB = 'HVDC power "to" B'
    HvdcPowerToC = 'HVDC power "to" C'

    VscLosses = 'Vsc losses'
    VscPowerFromPositive = 'Vsc power "from" positive pole'
    VscPowerFromNegative = 'Vsc power "from" negative pole'
    VscPdc = 'Vsc Pdc'
    VscVdc = 'Vsc Vdc'
    VscLoading = 'Vsc loading'

    VscPowerTo = 'Vsc power "to"'
    VscPowerToA = 'Vsc power "to" A'
    VscPowerToB = 'Vsc power "to" B'
    VscPowerToC = 'Vsc power "to" C'

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

    BusVoltageModuleA = 'VA: Voltage module A'
    BusVoltageModuleB = 'VB: Voltage module B'
    BusVoltageModuleC = 'VC: Voltage module C'

    BusVoltageAngle = 'θ: Voltage angle'

    BusVoltageAngleA = 'θA: Voltage angle A'
    BusVoltageAngleB = 'θB: Voltage angle B'
    BusVoltageAngleC = 'θC: Voltage angle C'

    BusPower = 'Bus power'
    BusShadowPrices = 'Nodal shadow prices'
    BranchOverloads = 'Branch overloads'
    BranchOverloadsCost = 'Branch overloads cost'

    LoadPower = 'Load power'
    LoadShedding = 'Load shedding'
    LoadSheddingCost = "Load shedding cost"
    LoadNeutralVoltage = 'Load neutral voltage'

    GeneratorShedding = 'Generator shedding'
    GeneratorPower = 'Generator power'

    GeneratorReactivePower = 'Generator reactive power'
    GeneratorReactivePowerA = 'Generator reactive power A'
    GeneratorReactivePowerB = 'Generator reactive power B'
    GeneratorReactivePowerC = 'Generator reactive power C'

    GeneratorCost = 'Generator cost'
    GeneratorReserve = 'Generator reserve'
    GeneratorFuels = 'Generator fuels'
    GeneratorEmissions = 'Generator emissions'
    GeneratorProducing = 'Generator producing'
    GeneratorStartingUp = 'Generator starting up'
    GeneratorShuttingDown = 'Generator shutting down'
    GeneratorInvested = 'Generator invested'

    BatteryReactivePower = 'Battery reactive power'
    BatteryReactivePowerA = 'Battery reactive power A'
    BatteryReactivePowerB = 'Battery reactive power B'
    BatteryReactivePowerC = 'Battery reactive power C'

    BatteryInvested = 'Battery invested'

    ShuntReactivePower = 'Shunt reactive power'
    ShuntReactivePowerA = 'Shunt reactive power A'
    ShuntReactivePowerB = 'Shunt reactive power B'
    ShuntReactivePowerC = 'Shunt reactive power C'
    ShuntNeutralVoltage = 'Shunt neutral voltage'

    BusVoltagePolarPlot = 'Voltage plot'
    BusNodalCapacity = "Bus nodal capacity"

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
    InterSpaceBranchPower = "Inter-space branch power"
    InterSpaceBranchLoading = "Inter-space branch loading"

    SystemFuel = 'System fuel consumption'
    SystemEmissions = 'System emissions'
    SystemEnergyCost = 'System energy cost'
    SystemEnergyTotalCost = "System energy total cost"
    PowerByTechnology = "Power by technology"

    # NTC TS
    OpfNtcTsContingencyReport = 'Contingency flow report'
    OpfNtcTsBaseReport = 'Base flow report'

    # Short-circuit
    BusShortCircuitActivePower = 'Short circuit active power'
    BusShortCircuitActivePowerA = 'Short circuit active power A'
    BusShortCircuitActivePowerB = 'Short circuit active power B'
    BusShortCircuitActivePowerC = 'Short circuit active power C'

    BusShortCircuitReactivePower = 'Short circuit reactive power'
    BusShortCircuitReactivePowerA = 'Short circuit reactive power A'
    BusShortCircuitReactivePowerB = 'Short circuit reactive power B'
    BusShortCircuitReactivePowerC = 'Short circuit reactive power C'

    BusShortCircuitActiveCurrent = 'Short circuit active current'
    BusShortCircuitActiveCurrentA = 'Short circuit active current A'
    BusShortCircuitActiveCurrentB = 'Short circuit active current B'
    BusShortCircuitActiveCurrentC = 'Short circuit active current C'

    BusShortCircuitReactiveCurrent = 'Short circuit reactive current'
    BusShortCircuitReactiveCurrentA = 'Short circuit reactive current A'
    BusShortCircuitReactiveCurrentB = 'Short circuit reactive current B'
    BusShortCircuitReactiveCurrentC = 'Short circuit reactive current C'

    # PTDF
    PTDF = 'PTDF'
    PTDFBusVoltageSensitivity = 'Bus voltage sensitivity'
    LODF = 'LODF'
    HvdcPTDF = "HVDC PTDF"
    HvdcODF = "HVDC ODF"
    VscPTDF = "Vsc PTDF"
    VscODF = "Vsc ODF"

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
    FluidValue = 'Fluid value'
    FluidFlowIn = 'Flow entering the node'
    FluidFlowOut = 'Flow exiting the node'
    FluidP2XFlow = 'Flow from the P2X'
    FluidSpillage = 'Spillage flow leaving'

    FluidFlowPath = 'Flow in the river'
    FluidFlowInjection = 'Flow circulating in the device'

    # OPF plots
    OpfBalancePlot = "Balance plot"
    OpfTechnologyPlot = "Technology plot"

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
    NetTransferCapacitySlack = 'Net transfer capacity slack'
    NetTransferCapacityStatus = 'Net transfer capacity status'
    AvailableTransferCapacityReport = 'ATC Report'

    BaseFlowReport = 'Ntc: Base flow report'
    ContingencyFlowsReport = 'Ntc: Contingency flow report'
    ContingencyFlowsRepresentativeReport = 'Ntc: Representative hours contingency flow report'
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
    ClusteringMembershipReport = 'Clustering hour assignments report'

    # RMS Simulation

    RmsSimulationReport = 'Rms time series report'
    RmsPlotResults = 'Rms plot results'

    # when categorizing results
    RmsGeneratorResults = 'Rms Generator results'
    RmsLineResults = 'Rms Line results'
    RmsLoadResults = 'Rms load results'

    RmsGeneratorOmegaResults = 'Rms Genqec omega results'
    RmsGeneratorDeltaResults = 'Rms Genqec delta results'

    RmsLoadPResults = 'Rms Load P results'
    RmsLoadQResults = 'Rms Load Q results'

    RmsLinePResults = 'Rms Simple Line P results'
    RmsLineQResults = 'Rms Simple Line Q results'

    # Small Signal Stability
    ParticipationFactors = "Participation Factors"
    StateMatrix = "State Matrix"
    Modes = "Modes"
    RightEigenvectors = "Right Eigenvectors"
    SDomainPlot = "S-Domain Plot"
    SDomainPlotHz = "S-Domain Plot in Hz"

    # inputs analysis
    ZoneAnalysis = 'Zone analysis'
    CountryAnalysis = 'Country analysis'
    AreaAnalysis = 'Area analysis'
    SubstationAnalysis = 'Substation analysis'
    VoltageLevelAnalysis = 'Voltage level analysis'
    CommunityAnalysis = 'Community analysis'
    RegionAnalysis = 'Region analysis'
    MunicipalityAnalysis = 'Municipality analysis'

    AreaGenerationAnalysis = 'Area generation analysis'
    ZoneGenerationAnalysis = 'Zone generation analysis'
    SubstationGenerationAnalysis = 'Substation generation analysis'
    VoltageLevelGenerationAnalysis = 'Voltage level generation analysis'
    CountryGenerationAnalysis = 'Country generation analysis'
    CommunityGenerationAnalysis = 'Community generation analysis'
    RegionGenerationAnalysis = 'Region generation analysis'
    MunicipalityGenerationAnalysis = 'Municipality generation analysis'

    AreaLoadAnalysis = 'Area load analysis'
    ZoneLoadAnalysis = 'Zone load analysis'
    SubstationLoadAnalysis = 'Substation load analysis'
    VoltageLevelLoadAnalysis = 'Voltage level load analysis'
    CountryLoadAnalysis = 'Country load analysis'
    CommunityLoadAnalysis = 'Community load analysis'
    RegionLoadAnalysis = 'Region load analysis'
    MunicipalityLoadAnalysis = 'Municipality load analysis'

    AreaBalanceAnalysis = 'Area balance analysis'
    ZoneBalanceAnalysis = 'Zone balance analysis'
    SubstationBalanceAnalysis = 'Substation balance analysis'
    VoltageLevelBalanceAnalysis = 'Voltage level balance analysis'
    CountryBalanceAnalysis = 'Country balance analysis'
    CommunityBalanceAnalysis = 'Community balance analysis'
    RegionBalanceAnalysis = 'Region balance analysis'
    MunicipalityBalanceAnalysis = 'Municipality balance analysis'

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

    # BusVoltageModuleA = 'Voltage module (A)'
    # BusVoltageAngleA = 'Voltage angle (A)'
    # BranchActivePowerFromA = 'Branch active power "from" (A)'
    # BranchReactivePowerFromA = 'Branch reactive power "from" (A)'
    # BranchActiveCurrentFromA = 'Branch active current "from" (A)'
    # BranchReactiveCurrentFromA = 'Branch reactive current "from" (A)'
    # BranchLoadingA = 'Branch loading (A)'
    # BranchActiveLossesA = 'Branch active losses (A)'
    # BranchReactiveLossesA = 'Branch reactive losses (A)'
    #
    # BusVoltageModuleB = 'Voltage module (B)'
    # BusVoltageAngleB = 'Voltage angle (B)'
    # BranchActivePowerFromB = 'Branch active power "from" (B)'
    # BranchReactivePowerFromB = 'Branch reactive power "from" (B)'
    # BranchActiveCurrentFromB = 'Branch active current "from" (B)'
    # BranchReactiveCurrentFromB = 'Branch reactive current "from" (B)'
    # BranchLoadingB = 'Branch loading (B)'
    # BranchActiveLossesB = 'Branch active losses (B)'
    # BranchReactiveLossesB = 'Branch reactive losses (B)'
    #
    # BusVoltageModuleC = 'Voltage module (C)'
    # BusVoltageAngleC = 'Voltage angle (C)'
    # BranchActivePowerFromC = 'Branch active power "from" (C)'
    # BranchReactivePowerFromC = 'Branch reactive power "from" (C)'
    # BranchActiveCurrentFromC = 'Branch active current "from" (C)'
    # BranchReactiveCurrentFromC = 'Branch reactive current "from" (C)'
    # BranchLoadingC = 'Branch loading (C)'
    # BranchActiveLossesC = 'Branch active losses (C)'
    # BranchReactiveLossesC = 'Branch reactive losses (C)'

    ShortCircuitInfo = 'Short-circuit information'

    # classifiers
    SystemResults = 'System'
    BusResults = 'Bus'
    BranchResults = 'Branch'
    HvdcResults = 'Hvdc'
    VscResults = 'Vsc'
    AreaResults = 'Area'
    ZoneResults = 'Zone'
    SubstationResults = 'Substation'
    VoltageLevelResults = 'Voltage level'
    CountryResults = 'Country'
    CommunityResults = 'Community'
    RegionResults = 'Region'
    MunicipalityResults = 'Municipality'
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
    ShuntResults = 'Shunt like devices'
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
    InvestmentsParetoPlotNSGA2 = 'Pareto plot NSGA2'
    InvestmentsWhenToMakePlot = "When to make them plot"

    # reliability
    ReliabilityLOLEResults = "LOLE"
    ReliabilityENSResults = "ENS"
    ReliabilityLOLFResults = "LOLF"
    ReliabilityLOLETResults = "LOLET"
    ReliabilityLOLFTResults = "LOLFT"
    ReliabilitySAIDIResults = "SAIDI"
    ReliabilitySAIFIResults = "SAIFI"
    ReliabilityCAIDIResults = "CAIDI"

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
    DesignView = 'Design View'
    TemplateDriver = 'Template'
    PowerFlow_run = 'Power flow'
    PowerFlow3ph_run = 'Power flow 3ph'
    PowerFlowTimeSeries3ph_run = 'Power flow time series 3ph'
    StateEstimation_run = 'State estimation'
    ShortCircuit_run = 'Short circuit'
    MonteCarlo_run = 'Monte Carlo'
    PowerFlowTimeSeries_run = 'Power flow time series'
    ClusteringAnalysis_run = 'Clustering Analysis'
    CleanRoom_run = 'Clean room'
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
    CatalogueOptimization_run = 'Catalogue optimization'
    TopologyProcessor_run = 'Topology Processor'
    NodalCapacity_run = 'Nodal capacity'
    NodalCapacityTimeSeries_run = 'Nodal capacity time series'
    Reliability_run = "Reliability"
    RmsDynamic_run = "RMS Dynamic"
    RmsSmallSignal_run = "RMS Small Signal stability"
    EmtDynamic_run = "EMT Dynamic"
    EmtSmallSignal_run = "EMT Small Signal stability"

    FileOpen = "file open"
    FileSave = "file save"
    ExportAll = "export all"

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
    AllActive = "All active contingencies"
    Country = "Country"
    Community = "Community"
    Region = "Region"
    Municipality = "Municipality"
    Zone = "Zone"
    Area = "Area"
    SensitiveToMonitored = "Sensitive to monitored"

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
    """
    Available colormaps
    """
    VeraGrid = 'VeraGrid'
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


class VoltageLevelTypes(Enum):
    """
    Types of substation types
    """
    SingleBar = 'Single bar'
    SingleBarWithBypass = 'Single bar with bypass'
    SingleBarWithSplitter = 'Single bar with splitter'
    DoubleBar = "Double bar"
    DoubleBarWithBypass = "Double bar with bypass"
    DoubleBarWithTransference = "Double bar with transference bar"
    DoubleBarDuplex = "Double bar duplex"
    Ring = 'Ring'
    BreakerAndAHalf = 'Breaker and a half'

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
            return VoltageLevelTypes[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class ContingencyOperationTypes(Enum):
    """
    Types of contingency operations
    """
    Active = 'active'
    PowerPercentage = '%'

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
        if s == 'status':
            return ContingencyOperationTypes.Active

        try:
            return ContingencyOperationTypes[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class BranchGroupTypes(Enum):
    """
    Branch group types
    """
    LineSegmentsGroup = 'Line segments group'
    TransformerGroup = 'Transformer group'
    GenericGroup = "Generic group"

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
            return BranchGroupTypes[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class CascadeType(Enum):
    PowerFlow = "PowerFlow",
    LatinHypercube = "LHS"

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
            return CascadeType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class DynamicIntegrationMethod(Enum):
    """
    Dynamic integration methods.
    """
    # Implicit time-stepping (DAE form)
    DaeTrapezoidal = "DAE_Trapezoidal"
    DaeBackEuler = "DAE_BackEuler"
    DaeBDF2 = "DAE_bdf2"
    DaeContinuous = "DAE_Continuous"

    # Explicit time-stepping (ODE form)
    OdeRungeKutta4 = "ODE_Runge_Kutta 4"
    OdeEuler = "ODE_Euler"

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return DynamicIntegrationMethod[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(enum_item.value for enum_item in cls)


class DynamicEventTransitionType(Enum):
    """
    Transition profile used by one dynamic runtime event.
    """

    Step = "step"
    Ramp = "ramp"

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return DynamicEventTransitionType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(enum_item.value for enum_item in cls)


class EmtSolverTypes(Enum):
    """
    Jacobian construction backends for implicit solvers.
    """
    Symbolic = "symbolic"  # Symbolic differentiation (SD)
    Automatic = "automatic"  # Sparse forward-mode AD + graph coloring
    StructuralAD = "structuralAD"  # Sparse structural automatic differentiation
    StructuralCompiled = "structuralCompiled"  # Eager structural kernels + reusable buffers

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
            return EmtSolverTypes[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class RmsProblemTypes(Enum):
    Tensygrid = "Tensygrid"
    PowerBalance = "RmsProblemDae"
    PowerBalanceVectorized = "RmsProblemDaeVectorized"
    PowerBalanceFullVectorized = "RmsProblemDaeFullVectorized"
    CurrentBalance = "RmsProblemPhasor"
    Multilinear = "RmsProblemMultilinear"

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
            return RmsProblemTypes[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class EmtProblemTypes(Enum):
    CurrentBalance = "EmtProblemDae"
    Multilinear = "EmtProblemMultilinear"

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
            return EmtProblemTypes[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class SmallSignalEmtBuildTypes(Enum):
    """
    Jacobian construction backends for implicit solvers.
    """
    Arnoldi = "Arnoldi"
    HybridArnoldi = "Hybrid Arnoldi"

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
            return SmallSignalEmtBuildTypes[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class EraSvdSolverType(Enum):
    """
    Enumeration for the SVD solver backend.
    """
    FullSvd = 0
    TruncatedRandomized = 1

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
            return EraSvdSolverType[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class RmsInitializationMethod(Enum):
    Explicit = "Explicit"
    ReducedExplicit = "ReducedExplicit"
    ConsistentNewton = "ConsistentNewton"
    PseudoTransient = "PseudoTransient"
    Auto = "Auto"
    CustomValues = "CustomValues"

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
            return RmsInitializationMethod[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class EmtInitializationMethod(Enum):
    """
    EMT initialization workflow options.
    """

    Explicit = "Explicit"
    ConsistentNewton = "ConsistentNewton"
    PseudoTransient = "PseudoTransient"
    Auto = "Auto"

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
            return EmtInitializationMethod[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """

        :return:
        """
        return list(enum_item.value for enum_item in cls)


class GridReductionMethod(Enum):
    """
    GridReductionMethod
    """
    Ward = "Ward"
    DiShi = "DiShi"
    WardLinear = "Ward linear"
    PTDF = "PTDF"
    PTDFProjected = "PTDF projected"

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
            return GridReductionMethod[s]
        except KeyError:
            return s


class BusReductionMethod(Enum):
    """
    GridReductionMethod
    """
    Reduce = "Reduce"
    Keep = "Keep"

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
            return BusReductionMethod[s]
        except KeyError:
            return s


class VarPowerFlowReferenceType(Enum):
    """
    VarPowerFlowReferenceType
    """
    NOTHING = "nothing"
    Vm = "Vm"  # Bus voltage module in p.u.
    Va = "Va"  # Bus voltage angle in rad
    Vmf = "Vmf"  # Bus voltage module in p.u.
    Vaf = "Vaf"  # Bus voltage angle in rad
    Vmt = "Vmt"  # Bus voltage module in p.u.
    Vat = "Vat"  # Bus voltage angle in rad
    P = "P"  # Bus active power in p.u.
    Q = "Q"  # Bus reactive power in p.u.
    Pf = "Pf"  # Branch active power from in p.u.
    Qf = "Qf"  # Branch reactive power from in p.u.
    Pt = "Pt"  # Branch active power to in p.u.
    Qt = "Qt"  # Branch reactive power to in p.u.
    Im = "Im"  # Converter current magnitude in p.u.

    # HVDC
    Pf_hvdc = "Pf_hvdc"
    Pt_hvdc = "Pt_hvdc"

    # VSC
    Pfp_vsc = "Pfp_vsc"
    Pfn_vsc = "Pfn_vsc"
    St_vsc = "St_vsc"
    If_vsc = "If_vsc"
    It_vsc = "It_vsc"

    # Phasor current references for RMS formulation
    Ir = "Ir"  # Real part of bus injection current
    Ii = "Ii"  # Imaginary part of bus injection current
    Irf = "Irf"  # Real current at branch from end
    Iif = "Iif"  # Imaginary current at branch from end
    Irt = "Irt"  # Real current at branch to end
    Iit = "Iit"  # Imaginary current at branch to end

    Vdc = "Vdc"  # Bus voltage for DC voltage in p.u.
    d_Vdc = "d_Vdc"  # Bus DC-voltage derivative in p.u. per second.
    Vf_dc = "Vf_dc"  # Branch from-side DC voltage in p.u.
    Vt_dc = "Vt_dc"  # Branch to-side DC voltage in p.u.
    DcPathModeSeed = "DcPathModeSeed"  # PF-derived discrete conduction seed for DC branch EMT devices.
    Idc = "Idc"  # Bus current for DC Bus in p.u.

    If_dc = "If_dc"  # Branch from current for DC Bus in p.u.
    It_dc = "It_dc"  # Branch from current for DC Bus in p.u.

    # from Power Flow 3ph
    v_N = "v_N"  # Bus voltage at phase N.
    v_A = "v_A"  # Bus voltage at phase A.
    v_B = "v_B"  # Bus voltage at phase B.
    v_C = "v_C"  # Bus voltage at phase C.
    d_v_N = "d_v_N"  # Bus voltage derivative at phase N.
    d_v_A = "d_v_A"  # Bus voltage derivative at phase A.
    d_v_B = "d_v_B"  # Bus voltage derivative at phase B.
    d_v_C = "d_v_C"  # Bus voltage derivative at phase C.

    vf_N = "vf_N"  # From Bus voltage at phase N.
    vf_A = "vf_A"  # From Bus voltage at phase A.
    vf_B = "vf_B"  # From Bus voltage at phase B.
    vf_C = "vf_C"  # From Bus voltage at phase C.

    vt_N = "vt_N"  # To Bus voltage at phase N.
    vt_A = "vt_A"  # To Bus voltage at phase A.
    vt_B = "vt_B"  # To Bus voltage at phase B.
    vt_C = "vt_C"  # To Bus voltage at phase C.

    d_v_N_f = "d_v_N_f"  # From bus voltage derivative at phase N.
    d_v_A_f = "d_v_A_f"  # From bBus voltage derivative at phase A.
    d_v_B_f = "d_v_B_f"  # From bus voltage derivative at phase B.
    d_v_C_f = "d_v_C_f"  # From bus voltage derivative at phase C.

    d_v_N_t = "d_v_N_t"  # To bus voltage derivative at phase N.
    d_v_A_t = "d_v_A_t"  # To bBus voltage derivative at phase A.
    d_v_B_t = "d_v_B_t"  # To bus voltage derivative at phase B.
    d_v_C_t = "d_v_C_t"  # To bus voltage derivative at phase C.

    i_N = "i_N"  # Injection current at phase N in p.u.
    i_A = "i_A"  # Injection current at phase A in p.u.
    i_B = "i_B"  # Injection current at phase B in p.u.
    i_C = "i_C"  # Injection current at phase C in p.u.
    phi_v = "phi_v"  # voltage angle in the network
    phi = "phi"  # network angle
    Vpk = "Vpk"  # rms peak value of voltage in p.u.
    Ipk = "Ipk"  # rms peak value of current in p.u.

    P_N = "P_N"  # Bus active power in phase N in p.u.
    P_A = "P_A"  # Bus active power in phase A in p.u.
    P_B = "P_B"  # Bus active power in phase B in p.u.
    P_C = "P_C"  # Bus active power in phase C in p.u.
    Q_N = "Q_N"  # Bus reactive power in phase N in p.u.
    Q_A = "Q_A"  # Bus reactive power in phase A in p.u.
    Q_B = "Q_B"  # Bus reactive power in phase B in p.u.
    Q_C = "Q_C"  # Bus reactive power in phase C in p.u.

    Sf_A = "Sf_A"  # Branch power from in phase A in p.u.
    Sf_B = "Sf_B"  # Branch power from in phase B in p.u.
    Sf_C = "Sf_C"  # Branch power from in phase C in p.u.
    St_A = "St_A"  # Branch power from in phase A in p.u.
    St_B = "St_B"  # Branch power from in phase B in p.u.
    St_C = "St_C"  # Branch power from in phase C in p.u.

    if_N = "if_N"  # Branch current from in phase N in p.u.
    if_A = "if_A"  # Branch current from in phase A in p.u.
    if_B = "if_B"  # Branch current from in phase B in p.u.
    if_C = "if_C"  # Branch current from in phase C in p.u.
    it_N = "it_N"  # Branch current to in phase N in p.u.
    it_A = "it_A"  # Branch current to in phase A in p.u.
    it_B = "it_B"  # Branch current to in phase B in p.u.
    it_C = "it_C"  # Branch current to in phase C in p.u.

    # Phasor representation (real/imaginary components)
    Vr = "Vr"  # Bus voltage real part in p.u.
    Vi = "Vi"  # Bus voltage imaginary part in p.u.
    Vrf = "Vrf"  # From-bus voltage real part in p.u.
    Vif = "Vif"  # From-bus voltage imaginary part in p.u.
    Vrt = "Vrt"  # To-bus voltage real part in p.u.
    Vit = "Vit"  # To-bus voltage imaginary part in p.u.

    # Complex phasor representation (single complex variable)
    V_complex = "V_complex"  # Complex voltage phasor V = Vr + j*Vi
    Vf_complex = "Vf_complex"  # Complex voltage at from bus
    Vt_complex = "Vt_complex"  # Complex voltage at to bus
    I_complex = "I_complex"  # Complex current phasor I = Ir + j*Ii
    If_complex = "If_complex"  # Complex current at from bus
    It_complex = "It_complex"  # Complex current at to bus
    S_complex = "S_complex"  # Complex power S = P + j*Q
    Sf_complex = "Sf_complex"  # Complex power at from bus
    St_complex = "St_complex"  # Complex power at to bus

    UR = "UR"
    UI = "UI"
    U = "U"
    U2R = "U2R"
    U2I = "U2I"
    U2 = "U2"
    U0R = "U0R"
    U0I = "U0I"
    U0 = "U0"
    FREF = "FREF"
    FE = "FE"
    DU = "DU"
    DUR = "DUR"
    DUI = "DUI"
    DU2 = "DU2"
    DU2R = "DU2R"
    DU2I = "DU2I"
    DU0 = "DU0"
    DU0R = "DU0R"
    DU0I = "DU0I"
    UR_A = "UR_A"
    UR_B = "UR_B"
    UR_C = "UR_C"
    UI_A = "UI_A"
    UI_B = "UI_B"
    UI_C = "UI_C"
    DUR_A = "DUR_A"
    DUR_B = "DUR_B"
    DUR_C = "DUR_C"
    DUI_A = "DUI_A"
    DUI_B = "DUI_B"
    DUI_C = "DUI_C"

    IR = "IR"
    II = "II"
    I = "I"
    IA = "IA"
    I2R = "I2R"
    I2I = "I2I"
    I2 = "I2"
    I0R = "I0R"
    I0I = "I0"
    IR_A = "IR_A"
    IR_B = "IR_B"
    IR_C = "IR_C"
    II_A = "II_A"
    II_B = "II_B"
    II_C = "II_C"

    I_DC = "I_DC"

    VD = "VD"
    VQ = "VQ"

    ID = "ID"
    IQ = "IQ"

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
            return VarPowerFlowReferenceType[s]
        except KeyError:
            return s


class ParamPowerFlowReferenceType(Enum):
    """
    ParamPowerFlowReferenceType
    """
    NOTHING = "nothing"
    # General
    dt = "dt"  # time step for dynamic simulations

    # Branch / load parameters
    g = "g"  # Branch conductance in per unit
    b = "b"  # Branch susceptance in per unit
    bsh = "bsh"  # Branch shunt susceptance in per unit
    gFe = "gFe"  # Branch magnetizing conductance in per unit
    vtap_f = "vtap_f"  # Virtual tap at from-side
    vtap_t = "vtap_t"  # Virtual tap at to-side
    tap_module = 'tap_module'  # Transformer tap module
    tap_phase = 'tap_phase'  # Transformer tap phase
    r = "r"  # Branch resistance in per unit
    x = "x"  # Branch reactance in per unit
    l = "l"  # Branch inductance in per unit
    Pl0 = "Pl0"  # Load active power
    Ql0 = "Ql0"  # Load reactive power

    # Phasor current parameters for current balance formulation
    Ir0 = "Ir0"  # Load real current injection
    Ii0 = "Ii0"  # Load imaginary current injection

    # 3phase load power
    Pl0_A = "Pl0_A"  # Load active power phase A
    Ql0_A = "Ql0_A"  # Load reactive power phase A
    Pl0_B = "Pl0_B"  # Load active power phase B
    Ql0_B = "Ql0_B"  # Load reactive power phase B
    Pl0_C = "Pl0_C"  # Load active power phase C
    Ql0_C = "Ql0_C"  # Load reactive power phase C

    # Three-phase line coupled R L and C
    Rnn = "Rnn"  # N-N line series resistance
    Rna = "Rna"  # N-A line series resistance
    Rnb = "Rnb"  # N-B line series resistance
    Rnc = "Rnc"  # N-C line series resistance
    Ran = "Ran"  # A-N line series resistance
    Raa = "Raa"  # A-A line series resistance
    Rab = "Rab"  # A-B line series resistance
    Rac = "Rac"  # A-C line series resistance
    Rbn = "Rbn"  # B-N line series resistance
    Rba = "Rba"  # B-A line series resistance
    Rbb = "Rbb"  # B-B line series resistance
    Rbc = "Rbc"  # B-C line series resistance
    Rcn = "Rcn"  # C-N line series resistance
    Rca = "Rca"  # C-A line series resistance
    Rcb = "Rcb"  # C-B line series resistance
    Rcc = "Rcc"  # C-C line series resistance

    Linv_nn = "Linv_nn"  # N-N line inverse series inductance
    Linv_na = "Linv_na"  # N-A line inverse series inductance
    Linv_nb = "Linv_nb"  # N-B line inverse series inductance
    Linv_nc = "Linv_nc"  # N-C line inverse series inductance
    Linv_an = "Linv_an"  # A-N line inverse series inductance
    Linv_aa = "Linv_aa"  # A-A line inverse series inductance
    Linv_ab = "Linv_ab"  # A-B line inverse series inductance
    Linv_ac = "Linv_ac"  # A-C line inverse series inductance
    Linv_bn = "Linv_bn"  # B-N line inverse series inductance
    Linv_ba = "Linv_ba"  # B-A line inverse series inductance
    Linv_bb = "Linv_bb"  # B-B line inverse series inductance
    Linv_bc = "Linv_bc"  # B-C line inverse series inductance
    Linv_cn = "Linv_cn"  # C-N line inverse series inductance
    Linv_ca = "Linv_ca"  # C-A line inverse series inductance
    Linv_cb = "Linv_cb"  # C-B line inverse series inductance
    Linv_cc = "Linv_cc"  # C-C line inverse series inductance

    Gnn = "Gnn"  # N-N per-terminal physical shunt conductance
    Gna = "Gna"  # N-A per-terminal physical shunt conductance
    Gnb = "Gnb"  # N-B per-terminal physical shunt conductance
    Gnc = "Gnc"  # N-C per-terminal physical shunt conductance
    Gan = "Gan"  # A-N per-terminal physical shunt conductance
    Gaa = "Gaa"  # A-A per-terminal physical shunt conductance
    Gab = "Gab"  # A-B per-terminal physical shunt conductance
    Gac = "Gac"  # A-C per-terminal physical shunt conductance
    Gbn = "Gbn"  # B-N per-terminal physical shunt conductance
    Gba = "Gba"  # B-A per-terminal physical shunt conductance
    Gbb = "Gbb"  # B-B per-terminal physical shunt conductance
    Gbc = "Gbc"  # B-C per-terminal physical shunt conductance
    Gcn = "Gcn"  # C-N per-terminal physical shunt conductance
    Gca = "Gca"  # C-A per-terminal physical shunt conductance
    Gcb = "Gcb"  # C-B per-terminal physical shunt conductance
    Gcc = "Gcc"  # C-C per-terminal physical shunt conductance

    Cnn = "Cnn"  # N-N line shunt capacitance
    Cna = "Cna"  # N-A line shunt capacitance
    Cnb = "Cnb"  # N-B line shunt capacitance
    Cnc = "Cnc"  # N-C line shunt capacitance
    Can = "Can"  # A-N line shunt capacitance
    Caa = "Caa"  # A-A line shunt capacitance
    Cab = "Cab"  # A-B line shunt capacitance
    Cac = "Cac"  # A-C line shunt capacitance
    Cbn = "Cbn"  # B-N line shunt capacitance
    Cba = "Cba"  # B-A line shunt capacitance
    Cbb = "Cbb"  # B-B line shunt capacitance
    Cbc = "Cbc"  # B-C line shunt capacitance
    Ccn = "Ccn"  # C-N line shunt capacitance
    Cca = "Cca"  # C-A line shunt capacitance
    Ccb = "Ccb"  # C-B line shunt capacitance
    Ccc = "Ccc"  # C-C line shunt capacitance

    # Transformer EMT mapped parameters
    transformer_winding1_resistance_pu = "transformer_winding1_resistance_pu"
    transformer_winding2_resistance_pu = "transformer_winding2_resistance_pu"
    transformer_winding1_inductance_pu_s = "transformer_winding1_inductance_pu_s"
    transformer_winding2_inductance_pu_s = "transformer_winding2_inductance_pu_s"
    transformer_mutual_inductance_pu_s = "transformer_mutual_inductance_pu_s"
    transformer_magnetizing_conductance_pu = "transformer_magnetizing_conductance_pu"

    transformer_rated_power_mva = "transformer_rated_power_mva"
    transformer_winding1_rated_voltage_ll_kv = "transformer_winding1_rated_voltage_ll_kv"
    transformer_winding2_rated_voltage_ll_kv = "transformer_winding2_rated_voltage_ll_kv"
    transformer_connection_clock = "transformer_connection_clock"
    transformer_open_circuit_current_pct = "transformer_open_circuit_current_pct"
    transformer_open_circuit_loss_kw = "transformer_open_circuit_loss_kw"
    transformer_short_circuit_voltage_pct = "transformer_short_circuit_voltage_pct"
    transformer_short_circuit_resistance_pct = "transformer_short_circuit_resistance_pct"
    transformer_short_circuit_loss_kw = "transformer_short_circuit_loss_kw"
    transformer_tap_ratio = "transformer_tap_ratio"
    transformer_nominal_voltage_ratio = "transformer_nominal_voltage_ratio"
    transformer_total_voltage_ratio = "transformer_total_voltage_ratio"
    transformer_terminal_capacitance_pu_s = "transformer_terminal_capacitance_pu_s"
    transformer_linear_core_inductance_pu_s = "transformer_linear_core_inductance_pu_s"
    transformer_core_curve_a_prime = "transformer_core_curve_a_prime"
    transformer_core_curve_b_prime = "transformer_core_curve_b_prime"
    transformer_use_linear_core = "transformer_use_linear_core"

    transformer_from_connection_aa = "transformer_from_connection_aa"
    transformer_from_connection_ab = "transformer_from_connection_ab"
    transformer_from_connection_ac = "transformer_from_connection_ac"
    transformer_from_connection_ba = "transformer_from_connection_ba"
    transformer_from_connection_bb = "transformer_from_connection_bb"
    transformer_from_connection_bc = "transformer_from_connection_bc"
    transformer_from_connection_ca = "transformer_from_connection_ca"
    transformer_from_connection_cb = "transformer_from_connection_cb"
    transformer_from_connection_cc = "transformer_from_connection_cc"

    transformer_to_connection_aa = "transformer_to_connection_aa"
    transformer_to_connection_ab = "transformer_to_connection_ab"
    transformer_to_connection_ac = "transformer_to_connection_ac"
    transformer_to_connection_ba = "transformer_to_connection_ba"
    transformer_to_connection_bb = "transformer_to_connection_bb"
    transformer_to_connection_bc = "transformer_to_connection_bc"
    transformer_to_connection_ca = "transformer_to_connection_ca"
    transformer_to_connection_cb = "transformer_to_connection_cb"
    transformer_to_connection_cc = "transformer_to_connection_cc"

    # Active phases in a branch
    phN = "phN"  # 1 if the N wire is active, else 0.
    phA = "phA"  # 1 if the A wire is active, else 0.
    phB = "phB"  # 1 if the B wire is active, else 0.
    phC = "phC"  # 1 if the C wire is active, else 0.

    # Machine / power flow parameters
    ws = "ws"
    M = "M"
    D = "D"
    Rs = "Rs"
    Ra = "Ra"

    # Reactances
    Xd = "Xd"
    Xq = "Xq"
    Xd_prime = "Xd_prime"
    Xq_prime = "Xq_prime"
    Xd_2prime = "Xd_2prime"
    Xq_2prime = "Xq_2prime"
    Xl = "Xl"

    # Time constants
    Td0_prime = "Td0_prime"
    Tq0_prime = "Tq0_prime"
    Td0_2prime = "Td0_2prime"
    Tq0_2prime = "Tq0_2prime"

    # Auxiliary parameters
    Xd_prime_minus_Xl = "Xd_prime_minus_Xl"
    Xq_prime_minus_Xl = "Xq_prime_minus_Xl"
    Xdaux = "Xdaux"
    Xdaux2 = "Xdaux2"
    Xdaux3 = "Xdaux3"
    Xqaux = "Xqaux"
    Xqaux2 = "Xqaux2"
    Xqaux3 = "Xqaux3"

    # Control / extra parameters
    A = "A"
    B = "B"

    # Governor / control gains and limits
    K = "K"  # governor gain (inverse droop)
    Pmax = "Pmax"  # max mechanical power (pu)
    Pmin = "Pmin"  # min mechanical power (pu)
    Uc = "Uc"  # max valve closing rate (pu/s)
    Uo = "Uo"  # max valve opening rate (pu/s)
    T_aux = "T_aux"

    # Control parameters
    Kp = "Kp"
    Ki = "Ki"
    omega_ref = "omega_ref"
    p0 = "p0"
    P0 = "P0"

    # Electrical / additional machine parameters
    R1 = "R1"
    X1 = "X1"
    X0 = "X0"
    freq = "freq"  # corresponds to Var("frequ")
    vf = "vf"
    tm0 = "tm0"

    # VSC loss parameters
    alpha1 = 'alpha1'
    alpha2 = 'alpha2'
    alpha3 = 'alpha3'

    converter_loss_power_0 = "converter_loss_power_0"
    converter_control_mode_1 = "converter_control_mode_1"
    converter_control_mode_2 = "converter_control_mode_2"
    converter_control_target_1 = "converter_control_target_1"
    converter_control_target_2 = "converter_control_target_2"

    omega_base = "omega_base"  # in rad/s
    Sbase = "Sbase"  # in MVA

    generator_share_enable = "generator_share_enable"
    generator_share_p_ref = "generator_share_p_ref"
    generator_share_q_ref = "generator_share_q_ref"

    # Static EMT-readable common device flags
    device_active = "device_active"

    # Injection-parent static parameters
    injection_connection_type = "injection_connection_type"

    # Branch-parent static parameters
    branch_rate_mva = "branch_rate_mva"
    branch_temp_base_deg_c = "branch_temp_base_deg_c"
    branch_temp_oper_deg_c = "branch_temp_oper_deg_c"
    branch_alpha_per_deg_c = "branch_alpha_per_deg_c"

    # Load static parameters in p.u. on grid Sbase unless noted otherwise
    load_g_pu = "load_g_pu"
    load_b_pu = "load_b_pu"
    load_ga_pu = "load_ga_pu"
    load_gb_pu = "load_gb_pu"
    load_gc_pu = "load_gc_pu"
    load_ba_pu = "load_ba_pu"
    load_bb_pu = "load_bb_pu"
    load_bc_pu = "load_bc_pu"
    load_ir_pu = "load_ir_pu"
    load_ii_pu = "load_ii_pu"
    load_ira_pu = "load_ira_pu"
    load_irb_pu = "load_irb_pu"
    load_irc_pu = "load_irc_pu"
    load_iia_pu = "load_iia_pu"
    load_iib_pu = "load_iib_pu"
    load_iic_pu = "load_iic_pu"
    load_contract_power_pu = "load_contract_power_pu"

    # Generator static parameters
    generator_p_pu = "generator_p_pu"
    generator_q_pu = "generator_q_pu"
    generator_qmin_pu = "generator_qmin_pu"
    generator_qmax_pu = "generator_qmax_pu"
    generator_power_factor = "generator_power_factor"
    generator_vset_pu = "generator_vset_pu"
    generator_snom_mva = "generator_snom_mva"
    generator_r0_pu = "generator_r0_pu"
    generator_r2_pu = "generator_r2_pu"
    generator_x2_pu = "generator_x2_pu"
    generator_control_mode = "generator_control_mode"
    generator_enabled_dispatch = "generator_enabled_dispatch"
    generator_must_run = "generator_must_run"
    generator_use_reactive_power_curve = "generator_use_reactive_power_curve"
    generator_device_sbase_mva = "generator_device_sbase_mva"

    # PV EMT parameters derived from the owning static generator
    pv_rated_power_pu = "pv_rated_power_pu"

    # Battery static parameters
    battery_enom_mwh = "battery_enom_mwh"
    battery_soc_0_pu = "battery_soc_0_pu"
    battery_max_soc_pu = "battery_max_soc_pu"
    battery_min_soc_pu = "battery_min_soc_pu"
    battery_charge_efficiency_pu = "battery_charge_efficiency_pu"
    battery_discharge_efficiency_pu = "battery_discharge_efficiency_pu"
    battery_charge_per_cycle_pu = "battery_charge_per_cycle_pu"
    battery_discharge_per_cycle_pu = "battery_discharge_per_cycle_pu"

    # Static generator static parameters
    static_generator_snom_mva = "static_generator_snom_mva"

    # External grid static parameters
    external_grid_vm_pu = "external_grid_vm_pu"
    external_grid_va_rad = "external_grid_va_rad"
    external_grid_mode_code = "external_grid_mode_code"

    # Shunt static parameters in p.u. on grid Sbase unless noted otherwise
    shunt_g_pu = "shunt_g_pu"
    shunt_b_pu = "shunt_b_pu"
    shunt_g0_pu = "shunt_g0_pu"
    shunt_b0_pu = "shunt_b0_pu"
    shunt_ga_pu = "shunt_ga_pu"
    shunt_gb_pu = "shunt_gb_pu"
    shunt_gc_pu = "shunt_gc_pu"
    shunt_ba_pu = "shunt_ba_pu"
    shunt_bb_pu = "shunt_bb_pu"
    shunt_bc_pu = "shunt_bc_pu"

    # Controllable shunt static parameters
    controllable_shunt_step = "controllable_shunt_step"
    controllable_shunt_vset_pu = "controllable_shunt_vset_pu"
    controllable_shunt_vmin_pu = "controllable_shunt_vmin_pu"
    controllable_shunt_vmax_pu = "controllable_shunt_vmax_pu"
    controllable_shunt_gmin_pu = "controllable_shunt_gmin_pu"
    controllable_shunt_gmax_pu = "controllable_shunt_gmax_pu"
    controllable_shunt_bmin_pu = "controllable_shunt_bmin_pu"
    controllable_shunt_bmax_pu = "controllable_shunt_bmax_pu"
    controllable_shunt_control_mode_code = "controllable_shunt_control_mode_code"

    # Current injection static parameters in p.u. on grid Sbase
    current_injection_ir_pu = "current_injection_ir_pu"
    current_injection_ii_pu = "current_injection_ii_pu"
    current_injection_ira_pu = "current_injection_ira_pu"
    current_injection_irb_pu = "current_injection_irb_pu"
    current_injection_irc_pu = "current_injection_irc_pu"
    current_injection_iia_pu = "current_injection_iia_pu"
    current_injection_iib_pu = "current_injection_iib_pu"
    current_injection_iic_pu = "current_injection_iic_pu"

    # AC and DC line static parameters
    line_length_km = "line_length_km"
    dc_line_length_km = "dc_line_length_km"
    dc_line_r_pu = "dc_line_r_pu"
    dc_line_l_pu_seconds = "dc_line_l_pu_seconds"

    # VSC static parameters
    vsc_kdp_pu = "vsc_kdp_pu"
    vsc_min_ac_voltage_pu = "vsc_min_ac_voltage_pu"

    def is_runtime_parameter_reference(self) -> bool:
        """Return whether this key identifies a special runtime operating value.

        Generator sharing targets and converter operating controls depend on
        the initialized operating point and use dedicated runtime initialization
        paths. This classification does not decide whether a general API mapping
        target belongs to ``Block.parameters`` or ``Block.event_dict``; that role
        is declared by the target block itself.

        :return: Whether the key uses a special operating-point runtime path.
        """
        if self == ParamPowerFlowReferenceType.generator_share_enable:
            result: bool = True
        elif self == ParamPowerFlowReferenceType.generator_share_p_ref:
            result = True
        elif self == ParamPowerFlowReferenceType.generator_share_q_ref:
            result = True
        elif self == ParamPowerFlowReferenceType.P0:
            result = True
        elif self == ParamPowerFlowReferenceType.converter_control_mode_1:
            result = True
        elif self == ParamPowerFlowReferenceType.converter_control_mode_2:
            result = True
        elif self == ParamPowerFlowReferenceType.converter_control_target_1:
            result = True
        elif self == ParamPowerFlowReferenceType.converter_control_target_2:
            result = True
        else:
            result = False
        return result

    def is_legacy_governor_dynamic_reference(self) -> bool:
        """Return whether this key could identify an old governor dynamic value.

        Historical governor files wrote editable model parameters to both
        ``Block.event_dict`` and ``Block.api_obj_mapping``. These references are
        retained in the enumeration so those files remain readable. The parser
        must additionally verify the complete legacy governor mapping signature,
        because ``P0`` is also a runtime operating-point reference in converter
        models.

        :return: Whether this reference can identify an old governor dynamic value.
        """
        if self == ParamPowerFlowReferenceType.K:
            result: bool = True
        elif self == ParamPowerFlowReferenceType.Uc:
            result = True
        elif self == ParamPowerFlowReferenceType.Uo:
            result = True
        elif self == ParamPowerFlowReferenceType.T_aux:
            result = True
        elif self == ParamPowerFlowReferenceType.Kp:
            result = True
        elif self == ParamPowerFlowReferenceType.Ki:
            result = True
        elif self == ParamPowerFlowReferenceType.omega_ref:
            result = True
        elif self == ParamPowerFlowReferenceType.p0:
            result = True
        elif self == ParamPowerFlowReferenceType.P0:
            result = True
        else:
            result = False
        return result

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
            return ParamPowerFlowReferenceType[s]
        except KeyError:
            return s


class ReliabilityMode(Enum):
    """
    ReliabilityMode
    """
    GenerationAdequacy = "Generation Adequacy"
    GridMetrics = "Grid Metrics"

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
            return ReliabilityMode[s]
        except KeyError:
            return s


class OpfDispatchMode(Enum):
    """
    OpfGenerationMode
    """
    Normal = "Normal"
    InterAreaRedispatch = "Inter-area redispatch"
    UnitCommitment = "Unit commitment"
    NodalCapacity = "Nodal capacity"
    GenerationExpansionPlanning = "Generation expansion planning"

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
            return OpfDispatchMode[s]
        except KeyError:
            return s


class TimeSeriesSearchPoint(Enum):
    """
    TimeSeriesSearchPoint
    """
    HighestLoad = "Highest Load"
    LowestLoad = "Lowest load"

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
            return TimeSeriesSearchPoint[s]
        except KeyError:
            return s


class EmtLineTypes(Enum):
    """
    EmtLineTypes
    """
    Bergeron = "Bergeron"
    J_Marti = "J_Marti"
    PI = "Pi"

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
            return EmtLineTypes[s]
        except KeyError:
            return s


class DynamicSimulationMode(Enum):
    """
    Dynamic simulation domains supported by VeraGrid.
    """

    RMS = "RMS"
    EMT = "EMT"

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        """Return the stable dynamic-simulation domain representation.

        :return: Human-readable dynamic-simulation domain value.
        """
        return str(self)

    @staticmethod
    def argparse(s: str) -> "DynamicSimulationMode | str":
        """
        :param s:
        :return:
        """
        try:
            return DynamicSimulationMode[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """
        :return:
        """
        return list(map(lambda c: c.value, cls))


class PlotSimulationType(Enum):
    """
    Simulation family used by persistent dynamic plot definitions and handlers.
    """

    RMS = "RMS"
    EMT = "EMT"

    def __str__(self) -> str:
        """
        Return the persistent label used by dynamic plot assets.

        :return: Persistent simulation-family label.
        """
        return self.value


class ResultTablePlotType(Enum):
    """
    Plot representation used by a results table.

    The representation describes how table dimensions map to graphical
    coordinates without coupling the generic results infrastructure to a
    particular simulation.
    """

    SERIES = "SERIES"
    XY = "XY"
    POLAR = "POLAR"
    COMPLEX_POINTS = "COMPLEX_POINTS"
    COMPLEX_VECTORS = "COMPLEX_VECTORS"

    def __str__(self) -> str:
        """
        Return the persistent plot-representation label.

        :return: Persistent plot-representation label.
        """
        return self.value


class DynamicPlotMode(Enum):
    """
    Plotting mode used by persistent dynamic plot definitions.
    """

    TIME_SERIES = "TIME_SERIES"
    XY = "XY"

    def __str__(self) -> str:
        """
        Return the persistent label used by dynamic plot assets.

        :return: Persistent plotting-mode label.
        """
        return self.value


class DynamicPlotEntryRole(Enum):
    """
    Semantic role played by one persistent dynamic plot entry.
    """

    CURVE = "CURVE"
    X_AXIS = "X_AXIS"
    Y_AXIS = "Y_AXIS"

    def __str__(self) -> str:
        """
        Return the persistent label used by dynamic plot entries.

        :return: Persistent entry-role label.
        """
        return self.value


class BlockScopeMode(Enum):
    """
    Block extraction scope modes for DGS block parsing.
    """
    InternalOnly = "InternalOnly"
    DownstreamOnly = "DownstreamOnly"
    UpstreamOnly = "UpstreamOnly"
    FullDependency = "FullDependency"

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
            return BlockScopeMode[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        """
        :return:
        """
        return list(enum_item.value for enum_item in cls)


class DynamicTemplateCategory(Enum):
    """Identify how one reusable dynamic template may be used."""

    DEVICE = "device"
    COMPONENT = "component"
    MEASUREMENT = "measurement"


class DynamicBlockVisualRole(Enum):
    """Identify the semantic palette of one dynamic-editor block."""

    CONTROL = 0
    MEASUREMENT = 1
    DEVICE_TEMPLATE = 2


class DynamicProjectionLayoutRole(Enum):
    """Identify one stable item in a derived dynamic-editor projection."""

    LOCAL_MEASUREMENTS = 0
    PHYSICAL_DEVICE = 1
    NETWORK_EXCHANGE = 2
    FROM_TAG = 3
    GOTO_TAG = 4
    MEASUREMENT_STATION_FROM = 5
    MEASUREMENT_STATION_TO = 6


class ProjectionTagConnectionSide(Enum):
    """Identify the real endpoint represented by a transient signal tag."""

    SOURCE = 0
    TARGET = 1


class RmsVectorizedNodalBalanceKind(Enum):
    """Identify how one compiled RMS nodal row is evaluated."""

    ACTIVE_POWER = 1
    REACTIVE_POWER = 2
    CAPACITIVE_DC_POWER = 3


class RmsTerminalSide(Enum):
    """Identify one physical RMS network terminal of a device."""

    BUS = "bus"
    FROM = "from"
    TO = "to"


class RmsPhysicalMeterKind(Enum):
    """Identify the physical quantity selected by one RMS meter."""

    VOLTAGE = "voltage"
    CURRENT = "current"
    POWER = "power"
    PHASE_LOCKED_LOOP = "phase_locked_loop"


class EmtTerminalSide(Enum):
    """Identify one physical EMT network terminal of a device."""

    BUS = "bus"
    FROM = "from"
    TO = "to"


class EmtTerminalConductor(Enum):
    """Identify one instantaneous EMT terminal conductor."""

    DC = "dc"
    NEUTRAL = "neutral"
    PHASE_A = "phase_a"
    PHASE_B = "phase_b"
    PHASE_C = "phase_c"


class DynamicDeviceTemplateType(Enum):
    """Identify one built-in complete dynamic-device template."""

    RMS_COMPLETE_GENERATOR = "rms:get_complete_generator_template_rms"
    RMS_GENCLS = "rms:get_gencls_rms_template"
    RMS_GENQEC = "rms:get_genqec_rms"
    RMS_GENROW = "rms:get_genrow_rms_template"
    RMS_LINE = "rms:get_line_rms_template"
    RMS_DC_LINE = "rms:build_dc_line_rms_v2"
    RMS_LOAD = "rms:get_load_rms_template"
    RMS_TRANSFORMER_2W = "rms:get_transformer2w_rms"
    RMS_SHUNT = "rms:get_shunt_template"
    RMS_PVD1 = "rms:get_pvd1_rms_template"
    RMS_PVD1_COMPLETE = "rms:get_pvd1_complete_rms_template"
    RMS_PVD1_DC_MPPT = "rms:get_pvd1_dc_mppt_rms_template"
    RMS_PVD1_DC_LINK_MPPT = "rms:get_pvd1_dc_link_mppt_rms_template"
    RMS_PVD1_DC_LINK_BESS = "rms:get_pvd1_dc_link_bess_rms_template"
    RMS_ESD1 = "rms:get_esd1_rms_template"
    RMS_VOLTAGE_SOURCE = "rms:VoltageSourceBuild"
    RMS_GFL_CONVERTER = "rms:get_gfl_converter_rms"
    RMS_HVDC_VSC_GFL = "rms:build_hvdc_vsc_gfl_rms"

    EMT_COMPLETE_GENERATOR = "emt:get_complete_generator_template_emt"
    EMT_THEVENIN_GENERATOR = "emt:get_generator_thevenin_rl_emt_template_with_ref"
    EMT_IDEAL_CONVERTER = "emt:get_emt_ideal_converter"
    EMT_FULL_PSEUDO_CONVERTER = "emt:get_full_pseudo_emt_converter"
    EMT_SWITCHED_CONVERTER = "emt:get_switched_emt_converter"
    EMT_DC_LOAD = "emt:get_dc_load_emt_template"
    EMT_DC_LINE = "emt:get_dc_line_emt_template"
    EMT_TRANSFORMER = "emt:get_transformer_emt_template"
    EMT_XFMR = "emt:get_xfmr_emt_template"
    EMT_SHUNT_C_ABC = "emt:get_shunt_c_emt_template:abc"
    EMT_SHUNT_L_ABC = "emt:get_shunt_l_emt_template:abc"
    EMT_SHUNT_R_ABC = "emt:get_shunt_r_emt_template:abc"
    EMT_EXPONENTIAL_LOAD_ABC = "emt:get_exponential_load_emt:abc"
    EMT_ZIP_LOAD_ABC = "emt:get_load_ZIP_emt_template:abc"
    EMT_PI_LINE_ABC = "emt:get_pi_line_emt_template:abc"
    EMT_BERGERON_LINE_ABC = "emt:get_bergeron_line_emt_template:abc"
    EMT_SINGLE_CAGE_INDUCTION_MOTOR = "emt:get_induction_motor_single_cage_emt_template:abc"
    EMT_DOUBLE_CAGE_INDUCTION_MOTOR = "emt:get_induction_motor_double_cage_emt_template:abc"
    EMT_BESS = "emt:get_bess_avm_grid_following_emt_template:abc"
    EMT_PV_GRID_FOLLOWING = "emt:get_pv_avm_grid_following_emt_template:abc"
    EMT_GFM = "emt:get_gfm_emt_template"


class BlockType(Enum):
    """
    this class contains the existing types of blocks
    """

    # tools
    FROM_GOTO = "FROM_GOTO"

    # inputs and outputs
    INPUT_CONN = "Bus Connection"
    OUTPUT_CONN = "EXTERNAL_MAPPING"

    # generic
    GENERIC = "Generic"
    PROCEDURAL_LOGIC = "PROCEDURAL_LOGIC"

    # common basic maths
    CONST = "CONST"
    GAIN = "GAIN"
    SUM = "SUM"
    DIVIDE = "Divide"
    PRODUCT = "PRODUCT"
    ABS = "Abs"
    INTEGRATOR = "Integrator"
    POWER = "Power"
    SIN = "Sin"
    COS = "Cos"
    TAN = "Tan"
    EXP = "Exp"
    LOG = "Log"
    LOG10 = "Log10"
    SQRT = "Sqrt"
    ASIN = "Asin"
    ACOS = "Acos"
    ATAN = "Atan"
    SINH = "Sinh"
    COSH = "Cosh"
    TANH = "Tanh"
    FLOOR = "Floor"
    CEIL = "Ceil"
    ROUND = "Round"
    REAL = "Real"
    IMAG = "Imag"
    CONJ = "Conj"
    ANGLE = "Angle"
    HEAVISIDE = "Heaviside"
    RAND = "Rand"
    ATAN2 = "Atan2"
    MIN = "Min"
    MAX = "Max"

    NOTYPE = "Notype"

    # common basic arrays and matrices

    INVERSE_LOOKUP_ARRAY = "INVERSE_LOOKUP_ARRAY"
    INVERSE_LOOKUP_ARRAY_OBJECT = "INVERSE_LOOKUP_ARRAY_OBJECT"
    INVERSE_LOOKUP_ARRAY_LINEAR_NOCLIPPING = "INVERSE_LOOKUP_ARRAY_LINEAR_NOCLIPPING"
    LOOKUP_ARRAY_LINEAR = "LOOKUP_ARRAY_LINEAR"
    LOOKUP_ARRAY_SPLINE = "LOOKUP_ARRAY_SPLINE"
    LOOKUP_ARRAY_LINEAR_FIXED = "LOOKUP_ARRAY_LINEAR_FIXED"
    LOOKUP_ARRAY_LINEAR_VARIABLE = "LOOKUP_ARRAY_LINEAR_VARIABLE"
    LOOKUP_ARRAY_OBJECT_LINEAR_NOCLIPPING = "LOOKUP_ARRAY_OBJECT_LINEAR_NOCLIPPING"
    LOOKUP_ARRAY_OBJECT = "LOOKUP_ARRAY_OBJECT"
    LOOKUP_ARRAY_OBJECT_SPLINE = "LOOKUP_MATRIX_LINEAR"
    LOOKUP_MATRIX_LINEAR = "LOOKUP_MATRIX_LINEAR"
    LOOKUP_MATRIX_SPLINE = "LOOKUP_MATRIX_SPLINE"
    LOOKUP_MATRIX_LINEAR_OBJECT = "LOOKUP_MATRIX_LINEAR_OBJECT"
    LOOKUP_MATRIX_SPLINE_OBJECT = "LOOKUP_MATRIX_SPLINE_OBJECT"

    # RMS
    GENRAW = "GENRAW"
    GENQEC = "GENQEC"
    GOV_RMS = "GOVERNOR_RMS"
    STAB_RMS = "STABILIZER_RMS"
    EXCITER_RMS = "EXCITER_RMS"
    LINE_RMS = "Line_RMS"
    LOAD_RMS = "Load_RMS"
    GFL_VSC_RMS = "GFL_VSC_RMS"
    DC_PV_SOURCE_RMS = "DC_PV_SOURCE_RMS"
    PLL_TRANSFORM_RMS = "Pll_transform_rms"
    PI_CURRENT_CONTROLLER = "Pi_current_controller"
    PI_POWER_CONTROLLER = "Pi_power_controller"
    GFL_CONVERTER_RMS = "GFL_converter_rms"
    GFL_VSC_HVDC_RMS = "GFL_vsc_hvdc"
    VSC_PLL_RMS = "VSC_PLL_RMS"
    VSC_ELECTRICAL_RMS = "VSC_ELECTRICAL_RMS"
    VSC_ACTIVE_CONTROL_RMS = "VSC_ACTIVE_CONTROL_RMS"
    VSC_REACTIVE_CONTROL_RMS = "VSC_REACTIVE_CONTROL_RMS"
    VSC_CURRENT_LIMITER_RMS = "VSC_CURRENT_LIMITER_RMS"
    VSC_VD_HAT_RMS = "VSC_VD_HAT_RMS"
    VSC_VQ_HAT_RMS = "VSC_VQ_HAT_RMS"
    VSC_DC_LINK_RMS = "VSC_DC_LINK_RMS"
    VOLTAGE_SOURCE_RMS = "Voltage_source_rms"
    TRANSFORMER_2W_RMS = "Transformer_2w_rms"
    DC_LINE_RMS = "DC_line_rms"

    # RMS - International standards
    AC1A = 'ac1a'
    AC1C = 'ac1c'
    AC6A = 'ac6a'
    AC6C = 'ac6c'
    AC7B = 'ac7b'
    AC7C = 'ac7c'
    AC8B = 'ac8b'
    AC8C = 'ac8c'
    BBSEX1 = 'bbsex1'
    BESSCBCURRENTSOURCENOPLANTCONTROL = 'besscbcurrentsourcenoplantcontrol'
    DC1A = 'dc1a'
    DC1C = 'dc1c'
    EXAC1 = 'exac1'
    GOVHYDRO4 = 'govhydro4'
    GOVSTEAM1 = 'govsteam1'
    GOVSTEAMEU = 'govsteameu'
    IEEEG1 = 'ieeeg1'
    IEEEG2 = 'ieeeg2'
    IEEET1 = 'ieeet1'
    IEEEX2 = 'ieeex2'
    IEEX2A = 'ieex2a'
    MAXEX2 = 'maxex2'
    OEL2C = 'oel2c'
    OEL3C = 'oel3c'
    OEL4C = 'oel4c'
    OEL5C = 'oel5c'
    PSS1AOMEGA = 'pss1aomega'
    PSS1APGEN = 'pss1apgen'
    PSS2A = 'pss2a'
    PSS2B = 'pss2b'
    PSS2C = 'pss2c'
    PSS3B = 'pss3b'
    PSS3C = 'pss3c'
    PSS6C = 'pss6c'
    PSSKUNDUR = 'psskundur'
    PVCURRENTSOURCEBNOPLANTCONTROL = 'pvcurrentsourcebnoplantcontrol'
    PVVOLTAGESOURCEANOPLANTCONTROL = 'pvvoltagesourceanoplantcontrol'
    PVVOLTAGESOURCEBNOPLANTCONTROL = 'pvvoltagesourcebnoplantcontrol'
    REECB = 'reecb'
    REECC = 'reecc'
    REGCBCS = 'regcbcs'
    REPCA = 'repca'
    SCL1C = 'scl1c'
    SCL2C = 'scl2c'
    SCRX = 'scrx'
    SEXS = 'sexs'
    ST1A = 'st1a'
    ST1C = 'st1c'
    ST4B = 'st4b'
    ST4C = 'st4c'
    ST5B = 'st5b'
    ST5C = 'st5c'
    ST6B = 'st6b'
    ST6C = 'st6c'
    ST7B = 'st7b'
    ST7C = 'st7c'
    ST9C = 'st9c'
    TGOV3 = 'tgov3'
    UEL1 = 'uel1'
    UEL2C = 'uel2c'
    VRKUNDUR = 'vrkundur'
    WPP4BCURRENTSOURCE2020 = 'wpp4bcurrentsource2020'
    WT4ACURRENTSOURCE = 'wt4acurrentsource'
    WT4ACURRENTSOURCE2020 = 'wt4acurrentsource2020'
    WT4BCURRENTSOURCE2020 = 'wt4bcurrentsource2020'
    WT4BCURRENTSOURCE = 'wt4bcurrentsource'
    WT4INJECTOR = 'wt4injector'
    WTG4ACURRENTSOURCE = 'wtg4acurrentsource'
    WTG4BCURRENTSOURCE = 'wtg4bcurrentsource'
    IEEEVC_1981 = 'ieeevc_1981'
    ESDC2A = 'esdc2a'
    FRQTPA = 'frqtpa'
    VTGTPA = 'vtgtpa'
    CIMTR1 = 'cimtr1'
    CIMW = 'cimw'
    GENSAL = 'gensal'
    GENROU = 'genrou'
    GGOV1 = 'ggov1'
    HYGOV = 'hygov'
    IEEL = 'ieel'
    TGOV1 = 'tgov1'

    # EMT
    EMT_GENERATOR = "EMT_GENERATOR"
    GOV_EMT = "GOVERNOR_EMT"
    STAB_EMT = "STABILIZER_EMT"
    EXCITER_EMT = "EXCITER_EMT"
    EMT_PI_LINE = "EMT_PI_LINE"
    EMT_BERGERON_LINE = "EMT_BERGERON_LINE"
    EMT_JMARTI_LINE = "EMT_JMARTI_LINE"
    EMT_DC_LINE = "EMT_DC_LINE"
    VOLTAGE_SOURCE_EMT = "VOLTAGE_SOURCE_EMT"
    CURRENT_SOURCE_EMT = "CURRENT_SOURCE_EMT"
    CONTROLLED_VOLTAGE_SOURCE_EMT = "CONTROLLED_VOLTAGE_SOURCE_EMT"
    CONTROLLED_CURRENT_SOURCE_EMT = "CONTROLLED_CURRENT_SOURCE_EMT"
    DC_VOLTAGE_SOURCE_EMT = "DC_VOLTAGE_SOURCE_EMT"
    DC_CURRENT_SOURCE_EMT = "DC_CURRENT_SOURCE_EMT"
    CONTROLLED_DC_VOLTAGE_SOURCE_EMT = "CONTROLLED_DC_VOLTAGE_SOURCE_EMT"
    CONTROLLED_DC_CURRENT_SOURCE_EMT = "CONTROLLED_DC_CURRENT_SOURCE_EMT"
    BALANCED_3PH_VOLTAGE_SOURCE_EMT = "BALANCED_3PH_VOLTAGE_SOURCE_EMT"
    BALANCED_3PH_CURRENT_SOURCE_EMT = "BALANCED_3PH_CURRENT_SOURCE_EMT"
    CONTROLLED_BALANCED_3PH_VOLTAGE_SOURCE_EMT = "CONTROLLED_BALANCED_3PH_VOLTAGE_SOURCE_EMT"
    CONTROLLED_BALANCED_3PH_CURRENT_SOURCE_EMT = "CONTROLLED_BALANCED_3PH_CURRENT_SOURCE_EMT"
    ARBITRARY_WAVEFORM_VOLTAGE_SOURCE_EMT = "ARBITRARY_WAVEFORM_VOLTAGE_SOURCE_EMT"
    ARBITRARY_WAVEFORM_CURRENT_SOURCE_EMT = "ARBITRARY_WAVEFORM_CURRENT_SOURCE_EMT"
    STEP_VOLTAGE_SOURCE_EMT = "STEP_VOLTAGE_SOURCE_EMT"
    STEP_CURRENT_SOURCE_EMT = "STEP_CURRENT_SOURCE_EMT"
    RAMP_VOLTAGE_SOURCE_EMT = "RAMP_VOLTAGE_SOURCE_EMT"
    RAMP_CURRENT_SOURCE_EMT = "RAMP_CURRENT_SOURCE_EMT"
    DOUBLE_EXPONENTIAL_CURRENT_SOURCE_EMT = "DOUBLE_EXPONENTIAL_CURRENT_SOURCE_EMT"
    HEIDLER_CURRENT_SOURCE_EMT = "HEIDLER_CURRENT_SOURCE_EMT"
    CIGRE_SURGE_CURRENT_SOURCE_EMT = "CIGRE_SURGE_CURRENT_SOURCE_EMT"
    SWITCH_EMT = "SWITCH_EMT"
    FAULT_EMT = "FAULT_EMT"
    GROUND_EMT = "GROUND_EMT"
    GROUNDING_LINK_EMT = "GROUNDING_LINK_EMT"
    NONLINEAR_RESISTOR_EMT = "NONLINEAR_RESISTOR_EMT"
    RLC_COMBO_EMT = "RLC_COMBO_EMT"
    R_LOAD_EMT = "R_LOAD_EMT"
    L_LOAD_EMT = "L_LOAD_EMT"
    C_LOAD_EMT = "C_LOAD_EMT"
    EXP_LOAD_EMT = "EXP_LOAD_EMT"
    ZIP_LOAD_EMT = "ZIP_LOAD_EMT"
    DC_LOAD_EMT = "DC_LOAD_EMT"
    EMT_THEVENIN = "EMT_THEVENIN"
    EMT_LOAD = "EMT_LOAD"
    TRAFO_EMT = "TRAFO_EMT"
    XFMR_TRANSFORMER = "XFMR_TRANSFORMER"
    INDUCTION_MOTOR_EMT = "INDUCTION_MOTOR_EMT"
    PV_POWER_PLANT_EMT = "PV_POWER_PLANT_EMT"
    PV_EMT = "PV_EMT"
    BESS_EMT = "BESS_EMT"
    BATTERY_EMT = "BATTERY_EMT"
    COMPLETE_PSEUDO_VSC_EMT = "COMPLETE_PSEUDO_VSC_EMT"

    MEASUREMENTS_VOLTAGE_ANGLE = "MEASUREMENTS_VOLTAGE_ANGLE"
    MEASUREMENTS_P_Q = "MEASUREMENTS_P_Q"
    MEASUREMENTS_VOLTAGE_FROM_POLAR = "MEASUREMENTS_VOLTAGE_FROM_POLAR"
    MEASUREMENTS_VOLTAGE_FROM_DC = "MEASUREMENTS_VOLTAGE_FROM_DC"
    MEASUREMENTS_CURRENT_FROM_PQ = "MEASUREMENTS_CURRENT_FROM_PQ"
    MEASUREMENTS_CURRENT_FROM_DC = "MEASUREMENTS_CURRENT_FROM_DC"
    MEASUREMENTS_CURRENT_PARK = "MEASUREMENTS_CURRENT_PARK"
    MEASUREMENTS_PLL = "MEASUREMENTS_PLL"

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
            return BlockType[s]
        except KeyError:
            return s


class BlockSymbolKind(Enum):
    """Editable primary role of one dynamic-block symbol."""

    INPUT = "Input"
    ALGEBRAIC = "Algebraic"
    STATE = "State"
    DIFFERENTIAL = "Differential"
    PARAMETER = "Parameter"
    EVENT_PARAMETER = "Dynamic parameter"
    MODE_PARAMETER = "Mode parameter"
    OUTPUT_ONLY = "Output only (legacy)"


class BlockSymbolCategory(Enum):
    """Visible symbol group used to filter dynamic-block symbol tables."""

    GENERAL = "General structure"
    VARIABLES = "Variables"
    PARAMETERS = "Parameters"
    RETAINED_MODES = "Retained modes"


class DynamicEditorMimeType(Enum):
    """MIME identifiers used by Dynamic Model Editor drag-and-drop workflows."""

    TAB = "application/x-veragrid-dynamic-editor-tab"


class EquationExportSection(Enum):
    """Dynamic equation groups that users can select independently for export."""

    STATE = "State equations"
    ALGEBRAIC = "Algebraic equations"
    INITIALIZATION = "Initialization equations"
    DERIVATIVE_INITIALIZATION = "Derivative initialization equations"


class ValidationFilterType(Enum):
    """Available scopes for a grouped validation result collection."""

    ALL_CHECKS = "All checks"
    ISSUES_ONLY = "Issues only"
    SECTION = "Section"


class JMartiDataSourceMode(Enum):
    """Available sources for the offline JMarti frequency-domain fit."""

    AUTOMATIC_TEMPLATE = "Auto from attached template"
    IMPORT_FREQUENCY_SAMPLES = "Import NPZ frequency samples"


class ProceduralFieldType(Enum):
    """Semantic editor kind for one procedural-logic field."""

    EXPRESSION = "Expression"
    MODE_REFERENCE = "Retained mode"
    VARIABLE_REFERENCE = "DAE variable"
    RUNTIME_REFERENCE = "Runtime parameter"
    TARGET_REFERENCE = "Mutable target"
    FLOAT = "Number"
    OPTIONAL_FLOAT = "Optional number"
    TEXT = "Text"
    REQUIRED_TEXT = "Required text"
    INTEGER = "Integer"
    BOOLEAN = "Boolean"


class RoutingNodeKind(Enum):
    """Topological roles supported by an orthogonal routing graph."""

    PORT = "port"
    STUB = "stub"
    ELBOW = "elbow"


class ProceduralGridMethods(Enum):
    """
    this class contains the existing types of blocks
    """
    SteinerAlone = "Steiner tree"
    SteinerAndOptimization = "Steiner tree + optimization"
    CatalogueOptimizationOnly = "Catalogue optimization only"

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
            return ProceduralGridMethods[s]
        except KeyError:
            return s


class ProceduralLogicType(Enum):
    """
    Enumeration of procedural logic entry kinds.
    """

    Base = "base"
    FixedSample = "fixed_sample"
    SampledValue = "sampled_value"
    HardSaturation = "hard_saturation"
    FlipFlop = "flipflop"
    AnalogFlipFlop = "analog_flipflop"
    PickupDropoff = "pickup_dropoff"
    ResetOnRisingEdge = "reset_on_rising_edge"
    TimeDelay = "time_delay"
    MovingAverage = "moving_average"
    GradientLimiter = "gradient_limiter"
    ConditionalDiagnostic = "conditional_diagnostic"
    DelayedSwitchEvent = "delayed_switch_event"
    DelayedThresholdLatch = "delayed_threshold_latch"
    StartupHandover = "startup_handover"
    ValveState = "valve_state"
    ThreePhaseCarrierPwm = "three_phase_carrier_pwm"
    ThreePhaseCarrierSampledModulation = "three_phase_carrier_sampled_modulation"
    ManufacturerNativeController = "manufacturer_native_controller"

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def argparse(s):
        """
        :param s:
        :return:
        """
        try:
            return ProceduralLogicType[s]
        except KeyError:
            return s


class InternationalStandardModel(Enum):
    """Identify every supported international-standard dynamic model."""

    AC1A = 'ac1a'
    AC1C = 'ac1c'
    AC6A = 'ac6a'
    AC6C = 'ac6c'
    AC7B = 'ac7b'
    AC7C = 'ac7c'
    AC8B = 'ac8b'
    AC8C = 'ac8c'
    BBSEX1 = 'bbsex1'
    BESSCBCURRENTSOURCENOPLANTCONTROL = 'besscbcurrentsourcenoplantcontrol'
    DC1A = 'dc1a'
    DC1C = 'dc1c'
    EXAC1 = 'exac1'
    GOVHYDRO4 = 'govhydro4'
    GOVSTEAM1 = 'govsteam1'
    GOVSTEAMEU = 'govsteameu'
    IEEEG1 = 'ieeeg1'
    IEEEG2 = 'ieeeg2'
    IEEET1 = 'ieeet1'
    IEEEX2 = 'ieeex2'
    IEEX2A = 'ieex2a'
    MAXEX2 = 'maxex2'
    OEL2C = 'oel2c'
    OEL3C = 'oel3c'
    OEL4C = 'oel4c'
    OEL5C = 'oel5c'
    PSS1AOMEGA = 'pss1aomega'
    PSS1APGEN = 'pss1apgen'
    PSS2A = 'pss2a'
    PSS2B = 'pss2b'
    PSS2C = 'pss2c'
    PSS3B = 'pss3b'
    PSS3C = 'pss3c'
    PSS6C = 'pss6c'
    PSSKUNDUR = 'psskundur'
    PVCURRENTSOURCEBNOPLANTCONTROL = 'pvcurrentsourcebnoplantcontrol'
    PVVOLTAGESOURCEANOPLANTCONTROL = 'pvvoltagesourceanoplantcontrol'
    PVVOLTAGESOURCEBNOPLANTCONTROL = 'pvvoltagesourcebnoplantcontrol'
    REECB = 'reecb'
    REECC = 'reecc'
    REGCBCS = 'regcbcs'
    REPCA = 'repca'
    SCL1C = 'scl1c'
    SCL2C = 'scl2c'
    SCRX = 'scrx'
    SEXS = 'sexs'
    ST1A = 'st1a'
    ST1C = 'st1c'
    ST4B = 'st4b'
    ST4C = 'st4c'
    ST5B = 'st5b'
    ST5C = 'st5c'
    ST6B = 'st6b'
    ST6C = 'st6c'
    ST7B = 'st7b'
    ST7C = 'st7c'
    ST9C = 'st9c'
    TGOV3 = 'tgov3'
    UEL1 = 'uel1'
    UEL2C = 'uel2c'
    VRKUNDUR = 'vrkundur'
    WPP4BCURRENTSOURCE2020 = 'wpp4bcurrentsource2020'
    WT4ACURRENTSOURCE = 'wt4acurrentsource'
    WT4ACURRENTSOURCE2020 = 'wt4acurrentsource2020'
    WT4BCURRENTSOURCE2020 = 'wt4bcurrentsource2020'
    WT4BCURRENTSOURCE = 'wt4bcurrentsource'
    WT4INJECTOR = 'wt4injector'
    WTG4ACURRENTSOURCE = 'wtg4acurrentsource'
    WTG4BCURRENTSOURCE = 'wtg4bcurrentsource'
    IEEEVC_1981 = 'ieeevc_1981'
    ESDC2A = 'esdc2a'
    FRQTPA = 'frqtpa'
    VTGTPA = 'vtgtpa'
    CIMTR1 = 'cimtr1'
    CIMW = 'cimw'
    GENSAL = 'gensal'
    GENROU = 'genrou'
    GGOV1 = 'ggov1'
    HYGOV = 'hygov'
    IEEL = 'ieel'
    TGOV1 = 'tgov1'


class EmtInitializationStatus(Enum):
    """Enumeration to track the progress of the initialization solver."""
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def argparse(s):
        """
        :param s:
        :return:
        """
        try:
            return EmtInitializationStatus[s]
        except KeyError:
            return s


class DynamicPlotEntryKind(Enum):
    """
    Semantic kind of one persistent dynamic plot entry.
    """

    VARIABLE = "VARIABLE"
    PARAMETER = "PARAMETER"

    def __str__(self) -> str:
        """
        Return the persistent label used by dynamic plot entries.

        :return: Persistent entry-kind label.
        """
        return self.value


class DynamicEntrySection:
    """
    Stable source-tree section labels used for dynamic entries.
    """

    __slots__ = tuple()

    VARIABLES: str = "Variables"
    PARAMETERS: str = "Parameters"


class TreeStateNodeKind(Enum):
    """
    Stable semantic node kinds used to preserve tree-view state.
    """

    ROOT = "root"
    DEVICE_TYPE = "device_type"
    DEVICE = "device"
    SECTION = "section"
    VARIABLE = "variable"
    PARAMETER = "parameter"
    SOURCE = "source"
    PLOT_GROUP = "plot_group"
    PLOT_ENTRY = "plot_entry"


class DynamicTableModelMode(Enum):
    """
    Modes to define data table in block editor
    """

    VARIABLES = "variables"
    PARAMETERS = "parameters"
    EQUATIONS = "equations"


class DynEditorGraphicsModes(Enum):
    """
    Modes to definr editor colouring
    """
    DARK = "Dark"
    LIGHT = "Light"


class RoutingAxis(Enum):
    """
    Enumerate the only valid orthogonal segment axes.

    :returns: Enumeration values describing orthogonal axes.
    """

    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


class RoutingPortSide(Enum):
    """
    Enumerate the physical block side where one routing port is attached.

    :returns: Enumeration values describing the physical port side.
    """

    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


class RoutingValidationMessageLevel(Enum):
    """
    Enumerate validation message severities.

    :returns: Enumeration values describing validation severity levels.
    """

    ERROR = "error"
    WARNING = "warning"


class SampledValueEvaluationMode(Enum):
    """Select the numerical boundary that owns a sampled-value update."""

    AcceptedBoundary = "accepted_boundary"
    ImplicitIterate = "implicit_iterate"


class VoltageDependentPowerModel(Enum):
    """Select the physical voltage law of a static RMS power injection."""

    ConstantCurrent = "ConstantCurrent"
    ConstantImpedance = "ConstantImpedance"


class InductionMachineRole(Enum):
    """Identify whether the shared induction equations inject or consume power."""

    GENERATOR = "generator"
    MOTOR = "motor"


class MeasurementVarType(Enum):
    """
    this class contains the existing measurement variables
    """
    UR = "UR"
    UI = "UI"
    U = "U"
    U2R = "U2R"
    U2I = "U2I"
    U2 = "U2"
    U0R = "U0R"
    U0I = "U0I"
    U0 = "U0"
    FREF = "FREF"
    FE = "FE"
    DU = "DU"
    DUR = "DUR"
    DUI = "DUI"
    DU2 = "DU2"
    DU2R = "DU2R"
    DU2I = "DU2I"
    DU0 = "DU0"
    DU0R = "DU0R"
    DU0I = "DU0I"
    UR_A = "UR_A"
    UR_B = "UR_B"
    UR_C = "UR_C"
    UI_A = "UI_A"
    UI_B = "UI_B"
    UI_C = "UI_C"
    DUR_A = "DUR_A"
    DUR_B = "DUR_B"
    DUR_C = "DUR_C"
    DUI_A = "DUI_A"
    DUI_B = "DUI_B"
    DUI_C = "DUI_C"

    IR = "IR"
    II = "II"
    I = "I"
    IA = "IA"
    I2R = "I2R"
    I2I = "I2I"
    I2 = "I2"
    I0R = "I0R"
    I0I = "I0"
    IR_A = "IR_A"
    IR_B = "IR_B"
    IR_C = "IR_C"
    II_A = "II_A"
    II_B = "II_B"
    II_C = "II_C"

    I_DC = "I_DC"

    VD = "VD"
    VQ = "VQ"

    ID = "ID"
    IQ = "IQ"


class DynamicEditorContentType(Enum):
    """Identify the kind of content hosted by a dynamic workspace tab."""

    MODEL = "Model"
    EVENTS = "Events"


class OperatingSystem(Enum):
    """Operating systems supported by native compiler selection."""

    LINUX = "linux"
    MACOS = "darwin"
    WINDOWS = "windows"


class CompilerName(Enum):
    """Native compiler toolchains supported by the engine."""

    GCC = "gcc"
    CLANG = "clang"
    MSVC = "msvc"
