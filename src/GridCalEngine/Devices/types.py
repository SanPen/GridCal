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
from typing import Union
from GridCalEngine.Devices.Aggregation import *
from GridCalEngine.Devices.Branches import *
from GridCalEngine.Devices.Injections import *
from GridCalEngine.Devices.Substation import *
from GridCalEngine.Devices.Associations import *
from GridCalEngine.Devices.Fluid import *
from GridCalEngine.Devices.measurement import *

INJECTION_DEVICE_TYPES = Union[
    Generator,
    Battery,
    Load,
    ExternalGrid,
    StaticGenerator,
    Shunt,
    ControllableShunt,
    CurrentInjection,
    FluidP2x,
    FluidTurbine,
    FluidPump
]

BRANCH_TYPES = Union[
    Line,
    DcLine,
    Transformer2W,
    HvdcLine,
    VSC,
    UPFC,
    Winding,
    Switch,
    SeriesReactance
]

FLUID_TYPES = Union[
    FluidNode,
    FluidPath,
    FluidP2x,
    FluidTurbine,
    FluidPump
]

AREA_TYPES = Union[
    Country,
    Region,
    Community,
    Municipality,
    Area,
    Zone
]

SUBSTATION_TYPES = Union[
    Substation,
    Bus,
    ConnectivityNode,
    BusBar,
    VoltageLevel
]

MEASUREMENT_TYPES = Union[
    IfMeasurement,
    QfMeasurement,
    PfMeasurement,
    QiMeasurement,
    PiMeasurement,
    VmMeasurement
]

ALL_DEV_TYPES = Union[
    INJECTION_DEVICE_TYPES,
    BRANCH_TYPES,
    FLUID_TYPES,
    SUBSTATION_TYPES,
    MEASUREMENT_TYPES,
    AREA_TYPES,
    Transformer3W,
    OverheadLineType,
    Wire,
    Area,
    Zone,
    TransformerType,
    EmissionGas,
    GeneratorEmission,
    GeneratorFuel,
    GeneratorTechnology,
    BranchGroup,
    LineLocations,
    LineLocation,
    ModellingAuthority,
    Fuel,
    Investment,
    InvestmentsGroup,
    Contingency,
    ContingencyGroup,
    Technology,
    UndergroundLineType,
    SequenceLineType
]
