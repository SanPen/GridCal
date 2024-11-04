# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Union
import numpy as np
from GridCalEngine.Devices.Parents.physical_device import PhysicalDevice
from GridCalEngine.Devices.Fluid.fluid_node import FluidNode
from GridCalEngine.Devices.Injections.generator import Generator
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.Aggregation.facility import Facility
from GridCalEngine.enumerations import BuildStatus, DeviceType


class FluidInjectionTemplate(PhysicalDevice):

    def __init__(self,
                 name: str = '',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 efficiency: float = 1.0,
                 max_flow_rate: float = 0.0,
                 plant: FluidNode = None,
                 generator: Generator = None,
                 device_type: DeviceType = DeviceType.FluidTurbineDevice,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """
        Fluid turbine
        :param name: name
        :param idtag: UUID code
        :param code: secondary code
        :param efficiency: energy consumption per fluid unit (MWh/m3)
        :param max_flow_rate: maximum fluid flow (m3/s)
        :param plant: Connection reservoir/node
        :param generator: electrical machine connected
        :param device_type: type of machine (turbine, pump, p2x)
        :param build_status: status if the plant is built, planned, etc.
        """
        PhysicalDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=device_type)

        self.active = True
        self._active_prof = Profile(default_value=self.active, data_type=bool)

        self.efficiency = float(efficiency)  # MWh/m3
        self.max_flow_rate = float(max_flow_rate)  # m3/s
        self._plant: FluidNode = plant
        self._generator: Generator = generator
        self.build_status = build_status

        self.facility: Facility | None = None

        self.register(key='active', units='', tpe=bool, definition='Is the load active?', profile_name='active_prof')

        self.register(key='efficiency', units="MWh/m3", tpe=float,
                      definition="Power plant energy production per fluid unit")
        self.register(key='max_flow_rate', units="m3/s", tpe=float, definition="maximum fluid flow")
        self.register(key='plant', units="", tpe=DeviceType.FluidNodeDevice, definition="Connection reservoir/node",
                      editable=False)
        self.register(key='generator', units="", tpe=DeviceType.GeneratorDevice, definition="Electrical machine",
                      editable=False)
        self.register(key='build_status', units='', tpe=BuildStatus,
                      definition='Branch build status. Used in expansion planning.')

        self.register(key='facility', units='', tpe=DeviceType.FacilityDevice,
                      definition='Facility where this is located', editable=True)

    @property
    def plant(self) -> FluidNode:
        """
        Plant getter
        :return: FluidNode
        """
        return self._plant

    @plant.setter
    def plant(self, val: FluidNode):
        """

        :param val: FluidNode
        :return:
        """
        if isinstance(val, FluidNode):
            self._plant = val

    @property
    def generator(self) -> Generator:
        """
        Generator getter
        :return: Generator
        """
        return self._generator

    @generator.setter
    def generator(self, val: Generator):
        """
        generator setter
        :param val: Generator
        """
        if isinstance(val, Generator):
            self._generator = val

    @property
    def active_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._active_prof

    @active_prof.setter
    def active_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._active_prof = val
        elif isinstance(val, np.ndarray):
            self._active_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a active_prof')
