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
import numpy as np

from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.Devices.Substation.bus import Bus
from GridCalEngine.enumerations import BuildStatus, DeviceType
from GridCalEngine.Devices.profile import Profile


class FluidNode(EditableDevice):

    def __init__(self,
                 name: str = '',
                 idtag: Union[str, None] = None,
                 code: str = '',
                 min_level: float = 0.0,
                 max_level: float = 0.0,
                 min_soc: float = 0.0,
                 max_soc: float = 1.0,
                 current_level: float = 0.0,
                 spillage_cost: float = 1000.0,
                 inflow: float = 0.0,
                 bus: Union[None, Bus] = None,
                 build_status: BuildStatus = BuildStatus.Commissioned):
        """
        FluidNode
        :param name: name of the node
        :param idtag: UUID
        :param code: secondary code
        :param min_level: Minimum amount of fluid at the node/reservoir [m3]
        :param max_level: Maximum amount of fluid at the node/reservoir [m3]
        :param current_level: Initial level of the node/reservoir [m3]
        :param spillage_cost: Spillage cost [e/(m3/s)]
        :param inflow: Inflow from the rain [m3/s]
        :param bus: electrical bus they are linked with
        :param build_status
        """
        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                code=code,
                                device_type=DeviceType.FluidNodeDevice)

        self.min_level = min_level  # hm3
        self.max_level = max_level  # hm3
        self.max_soc = max_soc  # p.u.
        self.min_soc = min_soc  # p.u.
        self.initial_level = current_level  # hm3
        self.spillage_cost = spillage_cost  # m3/s
        self.inflow = inflow  # m3/s
        self._bus: Bus = bus
        self.build_status = build_status

        self._inflow_prof = Profile(default_value=inflow, data_type=float)  # m3/s
        self._spillage_cost_prof = Profile(default_value=spillage_cost, data_type=float)  # e/(m3/s)

        self._max_soc_prof = Profile(default_value=max_soc, data_type=float)  # p.u.
        self._min_soc_prof = Profile(default_value=min_soc, data_type=float)  # p.u.

        self.register(key='min_level', units='hm3', tpe=float,
                      definition="Minimum amount of fluid at the node/reservoir")

        self.register(key='max_level', units='hm3', tpe=float,
                      definition="Maximum amount of fluid at the node/reservoir")

        self.register(key='min_soc', units='p.u.', tpe=float,
                      definition="Minimum SOC of fluid at the node/reservoir",
                      profile_name='min_soc_prof')

        self.register(key='max_soc', units='p.u.', tpe=float,
                      definition="Maximum SOC of fluid at the node/reservoir",
                      profile_name='max_soc_prof')

        self.register(key='initial_level', units='hm3', tpe=float,
                      definition="Initial level of the node/reservoir")

        self.register(key='bus', units='', tpe=DeviceType.BusDevice,
                      definition='Electrical bus.', editable=False)

        self.register(key='build_status', units='', tpe=BuildStatus,
                      definition='Branch build status. Used in expansion planning.')

        self.register(key='spillage_cost', units='e/(m3/s)', tpe=float,
                      definition='Cost of nodal spillage',
                      profile_name='spillage_cost_prof')

        self.register(key='inflow', units='m3/s', tpe=float,
                      definition='Flow of fluid coming from the rain',
                      profile_name='inflow_prof')

    @property
    def spillage_cost_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._spillage_cost_prof

    @spillage_cost_prof.setter
    def spillage_cost_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._spillage_cost_prof = val
        elif isinstance(val, np.ndarray):
            self._spillage_cost_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a spillage_cost_prof')

    @property
    def inflow_prof(self) -> Profile:
        """
        Cost profile
        :return: Profile
        """
        return self._inflow_prof

    @inflow_prof.setter
    def inflow_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._inflow_prof = val
        elif isinstance(val, np.ndarray):
            self._inflow_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a inflow_prof')

    @property
    def max_soc_prof(self) -> Profile:
        """
        Max soc profile
        :return: Profile
        """
        return self._max_soc_prof

    @max_soc_prof.setter
    def max_soc_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._max_soc_prof = val
        elif isinstance(val, np.ndarray):
            self._max_soc_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a max soc prof')

    @property
    def min_soc_prof(self) -> Profile:
        """
        Min soc profile
        :return: Profile
        """
        return self._min_soc_prof

    @min_soc_prof.setter
    def min_soc_prof(self, val: Union[Profile, np.ndarray]):
        if isinstance(val, Profile):
            self._min_soc_prof = val
        elif isinstance(val, np.ndarray):
            self._min_soc_prof.set(arr=val)
        else:
            raise Exception(str(type(val)) + 'not supported to be set into a min soc prof')

    def copy(self):
        """
        Make a deep copy of this object
        :return: Copy of this object
        """

        # make a new instance (separated object in memory)
        fluid_node = FluidNode()

        fluid_node.min_level = self.min_level  # hm3
        fluid_node.max_level = self.max_level  # hm3
        fluid_node.min_soc = self.min_soc  # p.u.
        fluid_node.max_soc = self.max_soc  # p.u.
        fluid_node.initial_level = self.initial_level  # hm3
        fluid_node.spillage_cost = self.spillage_cost  # m3/s
        fluid_node.inflow = self.inflow  # m3/s
        fluid_node._bus = self._bus
        fluid_node.build_status = self.build_status

        fluid_node.inflow_prof = self.inflow_prof  # m3/s
        fluid_node.spillage_cost_prof = self.spillage_cost_prof  # e/(m3/s)
        fluid_node.max_soc_prof = self.max_soc_prof  # m3
        fluid_node.min_soc_prof = self.min_soc_prof  # m3

        return fluid_node

    @property
    def bus(self) -> Bus:
        """
        Bus getter function
        :return: Bus
        """
        return self._bus

    @bus.setter
    def bus(self, val: Bus):
        """
        bus setter function
        :param val: Bus
        """
        if isinstance(val, Bus):
            self._bus = val
            self._bus.is_internal = True
