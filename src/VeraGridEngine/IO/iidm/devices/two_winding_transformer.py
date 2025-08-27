# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from VeraGridEngine.IO.iidm.devices.rte_object import RteObject, Unit


class RatioTapChangerStep(RteObject):
    def __init__(self, rho: float, r: float = 0.0, x: float = 0.0, g: float = 0.0, b: float = 0.0):
        super().__init__("RatioTapChangerStep")
        self.rho = rho
        self.r = r
        self.x = x
        self.g = g
        self.b = b

        self.register_property("rho", "step:rho", float, description="Ratio change factor")
        self.register_property("r", "step:r", float, Unit("Ohm"), description="Step resistance")
        self.register_property("x", "step:x", float, Unit("Ohm"), description="Step reactance")
        self.register_property("g", "step:g", float, Unit("S"), description="Step conductance")
        self.register_property("b", "step:b", float, Unit("S"), description="Step susceptance")


class RatioTapChanger(RteObject):
    def __init__(self, lowTapPosition: int, tapPosition: int,
                 regulationMode: str, regulationValue: float,
                 loadTapChangingCapabilities: bool, regulating: bool, targetDeadband: float):
        super().__init__("RatioTapChanger")
        self.lowTapPosition = lowTapPosition
        self.tapPosition = tapPosition
        self.regulationMode = regulationMode
        self.regulationValue = regulationValue
        self.loadTapChangingCapabilities = loadTapChangingCapabilities
        self.regulating = regulating
        self.targetDeadband = targetDeadband

        self.register_property("lowTapPosition", "tapChanger:lowTapPosition", int, description="Lowest tap position")
        self.register_property("tapPosition", "tapChanger:tapPosition", int, description="Current tap position")
        self.register_property("regulationMode", "tapChanger:regulationMode", str, description="Regulation mode")
        self.register_property("regulationValue", "tapChanger:regulationValue", float,
                               description="Target regulation value")
        self.register_property("loadTapChangingCapabilities", "tapChanger:loadTapChangingCapabilities", bool,
                               description="Is load tap changing enabled")
        self.register_property("regulating", "tapChanger:regulating", bool, description="Is regulating")
        self.register_property("targetDeadband", "tapChanger:targetDeadband", float,
                               description="Deadband for regulation")



class PhaseTapChanger(RteObject):
    def __init__(self, regulationMode: str, tapPosition: int, regulationValue: float, regulating: bool):
        super().__init__("PhaseTapChanger")
        self.regulationMode = regulationMode
        self.tapPosition = tapPosition
        self.regulationValue = regulationValue
        self.regulating = regulating

        self.register_property("regulationMode", "phaseTapChanger:regulationMode", str, description="Regulation mode")
        self.register_property("tapPosition", "phaseTapChanger:tapPosition", int, description="Tap position")
        self.register_property("regulationValue", "phaseTapChanger:regulationValue", float, description="Regulation value")
        self.register_property("regulating", "phaseTapChanger:regulating", bool, description="Is regulating?")



class TwoWindingsTransformer(RteObject):
    def __init__(self, id: str,
                 voltageLevelId1: str, bus1: str,
                 voltageLevelId2: str, bus2: str,
                 r: float, x: float, g: float, b: float,
                 ratedU1: float, ratedU2: float):
        super().__init__("TwoWindingsTransformer")
        self.id = id
        self.voltageLevelId1 = voltageLevelId1
        self.bus1 = bus1
        self.voltageLevelId2 = voltageLevelId2
        self.bus2 = bus2
        self.r = r
        self.x = x
        self.g = g
        self.b = b
        self.ratedU1 = ratedU1
        self.ratedU2 = ratedU2

        self.register_property("id", "transformer:id", str, description="Transformer ID")
        self.register_property("voltageLevelId1", "transformer:voltageLevelId1", str, description="Voltage level 1")
        self.register_property("bus1", "transformer:bus1", str, description="Bus 1")
        self.register_property("voltageLevelId2", "transformer:voltageLevelId2", str, description="Voltage level 2")
        self.register_property("bus2", "transformer:bus2", str, description="Bus 2")
        self.register_property("r", "transformer:r", float, Unit("Ohm"), description="Resistance")
        self.register_property("x", "transformer:x", float, Unit("Ohm"), description="Reactance")
        self.register_property("g", "transformer:g", float, Unit("S"), description="Conductance")
        self.register_property("b", "transformer:b", float, Unit("S"), description="Susceptance")
        self.register_property("ratedU1", "transformer:ratedU1", float, Unit("kV"), description="Rated voltage 1")
        self.register_property("ratedU2", "transformer:ratedU2", float, Unit("kV"), description="Rated voltage 2")
