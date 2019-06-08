

from enum import Enum


class BusMode(Enum):
    PQ = 1,
    PV = 2,
    REF = 3,
    NONE = 4,
    STO_DISPATCH = 5  # Storage dispatch, in practice it is the same as REF


class OperationalStateSelectionMethods(Enum):
    KNN = 'K-Nearest-Neighbours'
    CDF = 'Cumulative Density Function'


class TimeFrame(Enum):
    ShortTerm = 'Short term'
    LongTerm = 'Long term'
    Historical = 'Historical values'


# arrays to reverse the time frames from their text
__time_frame_lst = [TimeFrame.ShortTerm, TimeFrame.LongTerm, TimeFrame.Historical]
__time_frame_text_dict = {elm.value: elm for elm in __time_frame_lst}


def get_time_frames():
    return __time_frame_lst


def get_time_frame_names():
    return [elm.value for elm in __time_frame_lst]


def reverse_time_frame(text):
    return __time_frame_text_dict[text]


class DeviceType(Enum):
    BusDevice = 1
    BranchDevice = 2
    SolarPlantDevice = 3
    WindPlantDevice = 4
    HydroPlantDevice = 5
    BatteryDevice = 6
    LoadDevice = 7
    RiverSection = 8
    ElectricGridDevice = 9
    ThermalPlantDevice = 10
    ReservoirDevice = 11
    DrainDevice = 12
    RiverSystem = 13
    GeneratorDevice = 14
    PricesDevice = 15
    WaterNodes = 16


class BranchType(Enum):
    Branch = 'branch',
    Line = 'line',
    Transformer = 'transformer',
    Reactance = 'reactance',
    Switch = 'switch'


class ResultTypes(Enum):
    VoltageAngle = 'Voltage angle'
    VoltageModule = 'Voltage module'
    NodePower = 'Nodal power'
    DualPrices = 'Dual Prices'
    BranchLoading = 'Branch loading'
    BranchLosses = 'Branch losses'
    BranchPower = 'Branch power'
    BranchPowerOverload = 'Branch power overload'
    GeneratorPower = 'Generator power'
    GeneratorRampSlacks = 'Generator ramp slack'
    PricePower = 'Price power'
    LoadPower = 'Load power'
    LoadCurtailedPower = 'Load curtailed power'
    AggregatedGeneration = 'Aggregated generation'
    HydroPower = 'Hydro power'
    HydroWater = 'Hydro water'
    HydroWaterSlack = 'Hydro water slack'
    PrimaryReg = 'Primary regulation'
    SecondaryReg = 'Secondary regulation'
    TertiaryReg = 'Tertiary regulation'

