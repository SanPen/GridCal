# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Union
from GridCalEngine.Devices.Fluid.fluid_node import FluidNode
from GridCalEngine.Devices.Fluid.fluid_injection_template import FluidInjectionTemplate
from GridCalEngine.Devices.Injections.generator import Generator
from GridCalEngine.enumerations import BuildStatus, DeviceType


class FluidTurbine(FluidInjectionTemplate):

    def __init__(self,
                 name: str = '',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 efficiency: float = 1.0,
                 max_flow_rate: float = 0.0,
                 plant: FluidNode = None,
                 generator: Generator = None):
        """
        Fluid turbine
        :param name: name
        :param idtag: UUID code
        :param code: secondary code
        :param efficiency: energy consumption per fluid unit (MWh/m3)
        :param max_flow_rate: maximum fluid flow (m3/s)
        :param plant: Connection reservoir/node
        :param generator: electrical machine connected
        """
        FluidInjectionTemplate.__init__(self,
                                        name=name,
                                        idtag=idtag,
                                        code=code,
                                        efficiency=efficiency,
                                        max_flow_rate=max_flow_rate,
                                        plant=plant,
                                        generator=generator,
                                        device_type=DeviceType.FluidTurbineDevice)
