# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from typing import Dict, List, Any
import pandas as pd
from VeraGridEngine.Devices.Aggregation import *
from VeraGridEngine.Devices.Associations import *
from VeraGridEngine.Devices.Branches import *
from VeraGridEngine.Devices.Injections import *
from VeraGridEngine.Devices.Substation import *
from VeraGridEngine.Devices.Fluid import *
from VeraGridEngine.Devices.measurement import *
from VeraGridEngine.Devices.Dynamic import *

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

BRANCH_TEMPLATE_TYPES = Union[
    OverheadLineType,
    UndergroundLineType,
    SequenceLineType,
    TransformerType
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
    BusBar,
    VoltageLevel
]

# MEASUREMENT_TYPES = Union[
#     IfMeasurement,
#     QfMeasurement,
#     PfMeasurement,
#     QtMeasurement,
#     PtMeasurement,
#     QiMeasurement,
#     PiMeasurement,
#     VmMeasurement
# ]


ALL_DEV_TYPES = Union[
    INJECTION_DEVICE_TYPES,
    BRANCH_TYPES,
    FLUID_TYPES,
    SUBSTATION_TYPES,
        # MEASUREMENT_TYPES,
    AREA_TYPES,
    Transformer3W,
    OverheadLineType,
    Wire,
    Area,
    Zone,
    TransformerType,
    EmissionGas,
    BranchGroup,
    LineLocations,
    LineLocation,
    ModellingAuthority,
    Facility,
    Fuel,
    Investment,
    InvestmentsGroup,
    Contingency,
    ContingencyGroup,
    RemedialAction,
    RemedialActionGroup,
    Technology,
    UndergroundLineType,
    SequenceLineType,
    RmsModelTemplate
]

CONNECTION_TYPE = Union[Bus, None]

ASSOCIATION_TYPES = Union[Fuel, Technology, EmissionGas]

# this is the data type of the VeraGrid Json
VERAGRID_FILE_TYPE = Dict[str, Union[str, float, pd.DataFrame, Dict[str, Any], List[Dict[str, Any]]]]
