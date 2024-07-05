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
import warnings
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Union, Any, Set, Generator
import datetime as dateslib

from GridCalEngine.basic_structures import IntVec, StrVec
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.types import ALL_DEV_TYPES, BRANCH_TYPES, INJECTION_DEVICE_TYPES, FLUID_TYPES
from GridCalEngine.Devices.Parents.editable_device import GCPROP_TYPES
from GridCalEngine.enumerations import DeviceType
from GridCalEngine.basic_structures import Logger
from GridCalEngine.data_logger import DataLogger


def add_devices_list(original_list: List[ALL_DEV_TYPES], new_list: List[ALL_DEV_TYPES]):
    """
    Add a list of devices to another keeping coherence
    :param original_list:
    :param new_list:
    :return:
    """
    existing_uuids = {e.idtag for e in original_list}

    for elm in new_list:
        if elm.idtag in existing_uuids:
            print(elm.name, 'uuid is repeated..generating new one')
            elm.generate_uuid()
        original_list.append(elm)


class Assets:
    """
    Class to store the assets
    """

    def __init__(self):

        # master time profile
        self._time_profile: Union[pd.DatetimeIndex, None] = None

        # snapshot time
        self._snapshot_time: dateslib.datetime = dateslib.datetime.now()  # dateslib.datetime(year=2000, month=1, day=1)

        self._lines: List[dev.Line] = list()

        self._dc_lines: List[dev.DcLine] = list()

        self._transformers2w: List[dev.Transformer2W] = list()

        self._hvdc_lines: List[dev.HvdcLine] = list()

        self._vsc_devices: List[dev.VSC] = list()

        self._upfc_devices: List[dev.UPFC] = list()

        self._switch_devices: List[dev.Switch] = list()

        self._transformers3w: List[dev.Transformer3W] = list()

        self._windings: List[dev.Winding] = list()

        self._series_reactances: List[dev.SeriesReactance] = list()

        # Should accept buses
        self._buses: List[dev.Bus] = list()

        # array of connectivity nodes
        self._connectivity_nodes: List[dev.ConnectivityNode] = list()

        # array of busbars
        self._bus_bars: List[dev.BusBar] = list()

        # array of voltage levels
        self._voltage_levels: List[dev.VoltageLevel] = list()

        # List of loads
        self._loads: List[dev.Load] = list()

        # List of generators
        self._generators: List[dev.Generator] = list()

        # List of External Grids
        self._external_grids: List[dev.ExternalGrid] = list()

        # List of shunts
        self._shunts: List[dev.Shunt] = list()

        # List of batteries
        self._batteries: List[dev.Battery] = list()

        # List of static generators
        self._static_generators: List[dev.StaticGenerator] = list()

        # List of current injections devices
        self._current_injections: List[dev.CurrentInjection] = list()

        # List of linear shunt devices
        self._controllable_shunts: List[dev.ControllableShunt] = list()

        # Lists of measurements
        self._pi_measurements: List[dev.PiMeasurement] = list()
        self._qi_measurements: List[dev.QiMeasurement] = list()
        self._vm_measurements: List[dev.VmMeasurement] = list()
        self._pf_measurements: List[dev.PfMeasurement] = list()
        self._qf_measurements: List[dev.QfMeasurement] = list()
        self._if_measurements: List[dev.IfMeasurement] = list()

        # List of overhead line objects
        self._overhead_line_types: List[dev.OverheadLineType] = list()

        # list of wire types
        self._wire_types: List[dev.Wire] = list()

        # underground cable lines
        self._underground_cable_types: List[dev.UndergroundLineType] = list()

        # sequence modelled lines
        self._sequence_line_types: List[dev.SequenceLineType] = list()

        # List of transformer types
        self._transformer_types: List[dev.TransformerType] = list()

        # list of branch groups
        self._branch_groups: List[dev.BranchGroup] = list()

        # list of substations
        self._substations: List[dev.Substation] = list()  # [self.default_substation]

        # list of areas
        self._areas: List[dev.Area] = list()  # [self.default_area]

        # list of zones
        self._zones: List[dev.Zone] = list()  # [self.default_zone]

        # list of countries
        self._countries: List[dev.Country] = list()  # [self.default_country]

        self._communities: List[dev.Community] = list()

        self._regions: List[dev.Region] = list()

        self._municipalities: List[dev.Municipality] = list()

        # contingencies
        self._contingencies: List[dev.Contingency] = list()

        # contingency group
        self._contingency_groups: List[dev.ContingencyGroup] = list()

        # investments
        self._investments: List[dev.Investment] = list()

        # investments group
        self._investments_groups: List[dev.InvestmentsGroup] = list()

        # technologies
        self._technologies: List[dev.Technology] = list()

        # Modelling authority
        self._modelling_authorities: List[dev.ModellingAuthority] = list()

        # fuels
        self._fuels: List[dev.Fuel] = list()

        # emission gasses
        self._emission_gases: List[dev.EmissionGas] = list()

        # self._generators_technologies: List[dev.GeneratorTechnology] = list()
        #
        # self._generators_fuels: List[dev.GeneratorFuel] = list()
        #
        # self._generators_emissions: List[dev.GeneratorEmission] = list()

        # fluids
        self._fluid_nodes: List[dev.FluidNode] = list()

        # fluid paths
        self._fluid_paths: List[dev.FluidPath] = list()

        # list of turbines
        self._turbines: List[dev.FluidTurbine] = list()

        # list of pumps
        self._pumps: List[dev.FluidPump] = list()

        # list of power to gas devices
        self._p2xs: List[dev.FluidP2x] = list()

        # list of declared diagrams
        self._diagrams: List[Union[dev.MapDiagram, dev.SchematicDiagram]] = list()

        # objects with profiles
        self.objects_with_profiles = {
            "Regions": [
                dev.Country(),
                dev.Community(),
                dev.Region(),
                dev.Municipality(),
                dev.Area(),
                dev.Zone(),
            ],
            "Substation": [
                dev.Substation(),
                dev.VoltageLevel(),
                dev.BusBar(),
                dev.ConnectivityNode(),
                dev.Bus(),
                dev.Switch()
            ],
            "Injections": [
                dev.Generator(),
                dev.Battery(),
                dev.Load(),
                dev.StaticGenerator(),
                dev.ExternalGrid(),
                dev.Shunt(),
                dev.ControllableShunt(),
                dev.CurrentInjection()
            ],
            "Branches": [
                dev.Line(),
                dev.DcLine(),
                dev.Transformer2W(),
                dev.Winding(),
                dev.Transformer3W(),
                dev.SeriesReactance(),
                dev.HvdcLine(),
                dev.VSC(),
                dev.UPFC(),
            ],
            "Fluid": [
                dev.FluidNode(),
                dev.FluidPath(),
                dev.FluidTurbine(),
                dev.FluidPump(),
                dev.FluidP2x(),
            ],
            "Groups": [
                dev.ContingencyGroup(),
                dev.Contingency(),
                dev.InvestmentsGroup(),
                dev.Investment(),
                dev.BranchGroup(),
                dev.ModellingAuthority()
            ],
            "Associations": [
                dev.Technology(),
                dev.Fuel(),
                dev.EmissionGas(),
            ],
            "Catalogue": [
                dev.Wire(),
                dev.OverheadLineType(),
                dev.UndergroundLineType(),
                dev.SequenceLineType(),
                dev.TransformerType()
            ]
        }

        # dictionary of profile magnitudes per object
        self.profile_magnitudes: Dict[str, Tuple[List[str], List[GCPROP_TYPES]]] = dict()

        self.device_type_name_dict: Dict[str, DeviceType] = dict()

        self.device_associations: Dict[str, List[str]] = dict()

        '''
        self.type_name = 'Shunt'

        self.properties_with_profile = ['Y']
        '''
        for key, elm_list in self.objects_with_profiles.items():
            for elm in elm_list:
                if elm.properties_with_profile is not None:
                    key = str(elm.device_type.value)
                    profile_attr = list(elm.properties_with_profile.keys())
                    profile_types = [elm.registered_properties[attr].tpe for attr in profile_attr]
                    associated_props, indices = elm.get_association_properties()
                    self.profile_magnitudes[key] = (profile_attr, profile_types)
                    self.device_type_name_dict[key] = elm.device_type
                    self.device_associations[key] = [prop.name for prop in associated_props]

    # ------------------------------------------------------------------------------------------------------------------
    # Device iterators
    # ------------------------------------------------------------------------------------------------------------------

    def item_types(self) -> Generator[DeviceType, None, None]:
        """
        Iterator of all the objects in the MultiCircuit
        """
        for key, tpe in self.device_type_name_dict.items():
            yield tpe

    def items_declared(self) -> Generator[ALL_DEV_TYPES, None, None]:
        """
        Iterator of the declared objects in the MultiCircuit
        """
        for key, elm_type_list in self.objects_with_profiles.items():
            for elm in elm_type_list:
                yield elm

    def items(self) -> Generator[ALL_DEV_TYPES, None, None]:
        """
        Iterator of all the objects in the MultiCircuit
        """
        for key, tpe in self.device_type_name_dict.items():
            elements = self.get_elements_by_type(device_type=tpe)
            for elm in elements:
                yield elm

    # ------------------------------------------------------------------------------------------------------------------
    # Time profile
    # ------------------------------------------------------------------------------------------------------------------

    def get_time_number(self) -> int:
        """
        Return the number of buses
        :return: number
        """
        if self._time_profile is not None:
            return len(self._time_profile)
        else:
            return 0

    def get_time_array(self) -> pd.DatetimeIndex:
        """
        Get the time array
        :return: pd.DatetimeIndex
        """
        return self._time_profile

    @property
    def time_profile(self) -> pd.DatetimeIndex:
        """
        Get the time array
        :return: pd.DatetimeIndex
        """
        return self._time_profile

    @time_profile.setter
    def time_profile(self, value: pd.DatetimeIndex):
        """
        Set the time array
        :return: pd.DatetimeIndex
        """
        self._time_profile = value

    def get_all_time_indices(self) -> IntVec:
        """
        Get array with all the time steps
        :return: IntVec
        """
        return np.arange(0, self.get_time_number())

    @property
    def has_time_series(self) -> bool:
        """
        Area there time series?
        :return: True / False
        """
        # sanity check
        if len(self._buses) > 0:
            if self._time_profile is not None:
                if self._buses[0].active_prof.size() != self.get_time_number():
                    warnings.warn('The grid has a time signature but the objects do not!')

        return self._time_profile is not None

    def get_unix_time(self) -> IntVec:
        """
        Get the unix time representation of the time
        :return:
        """
        if self.has_time_series:
            return self._time_profile.values.astype(np.int64) // 10 ** 9
        else:
            return np.zeros(0, dtype=np.int64)

    def set_unix_time(self, arr: IntVec):
        """
        Set the time with a unix time
        :param arr: UNIX time iterable
        """
        self._time_profile = pd.to_datetime(arr, unit='s')

    def get_time_profile_as_list(self):
        """
        Get the profiles dictionary
        mainly used in json export
        """
        if self.time_profile is not None:
            # recommended way to get the unix datetimes
            arr = (self.time_profile - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
            # t = (self.time_profile.array.astype(int) * 1e-9).tolist()  # UNIX time in seconds
            return arr.tolist()
        else:
            return list()

    def re_index_time(self, year=None, hours_per_step=1.0):
        """
        Generate sequential time steps to correct the time_profile
        :param year: base year, if None, this year is taken
        :param hours_per_step: number of hours per step, by default 1 hour by step
        """
        if year is None:
            t0 = dateslib.datetime.now()
            year = t0.year

        t0 = dateslib.datetime(year=year, month=1, day=1)
        self.re_index_time2(t0=t0, step_size=hours_per_step, step_unit='h')

    def re_index_time2(self, t0, step_size, step_unit):
        """
        Generate sequential time steps to correct the time_profile
        :param t0: base time
        :param step_size: number of hours per step, by default 1 hour by step
        :param step_unit: 'h', 'm', 's'
        """
        nt = self.get_time_number()

        if step_unit == 'h':
            tm = [t0 + dateslib.timedelta(hours=t * step_size) for t in range(nt)]
        elif step_unit == 'm':
            tm = [t0 + dateslib.timedelta(minutes=t * step_size) for t in range(nt)]
        elif step_unit == 's':
            tm = [t0 + dateslib.timedelta(seconds=t * step_size) for t in range(nt)]
        else:
            raise Exception("Unsupported time unit")

        self._time_profile = pd.to_datetime(tm)

    def create_profiles(self, steps, step_length, step_unit, time_base: dateslib.datetime = dateslib.datetime.now()):
        """
        Set the default profiles in all the objects enabled to have profiles.
        :param steps: Number of time steps
        :param step_length: Time length (1, 2, 15, ...)
        :param step_unit: Unit of the time step ("h", "m" or "s")
        :param time_base: Date to start from
        """

        index = np.empty(steps, dtype=object)
        for i in range(steps):
            if step_unit == 'h':
                index[i] = time_base + dateslib.timedelta(hours=i * step_length)
            elif step_unit == 'm':
                index[i] = time_base + dateslib.timedelta(minutes=i * step_length)
            elif step_unit == 's':
                index[i] = time_base + dateslib.timedelta(seconds=i * step_length)

        index = pd.DatetimeIndex(index)

        self.format_profiles(index)

    def format_profiles(self, index: pd.DatetimeIndex):
        """
        Format the pandas profiles in place using a time index.
        :param index: Time profile
        """

        self.time_profile = pd.to_datetime(index, dayfirst=True)

        for key, tpe in self.device_type_name_dict.items():
            elements = self.get_elements_by_type(device_type=tpe)
            for elm in elements:
                elm.create_profiles(index)

    def set_time_profile(self, unix_data: IntVec):
        """
        Set unix array as time array
        :param unix_data: array of seconds since 1970
        """
        # try parse
        try:
            self.time_profile = pd.to_datetime(np.array(unix_data), unit='s', origin='unix')
        except Exception as e:
            print("Error", e)
            # it may come in nanoseconds instead of seconds...
            self.time_profile = pd.to_datetime(np.array(unix_data) / 1e9, unit='s', origin='unix')

        self.ensure_profiles_exist()

    def ensure_profiles_exist(self) -> None:
        """
        Format the pandas profiles in place using a time index.
        """
        if self.time_profile is None:
            raise Exception('Cannot ensure profiles existence without a time index. Try format_profiles instead')

        for key, tpe in self.device_type_name_dict.items():
            elements = self.get_elements_by_type(device_type=tpe)
            for elm in elements:
                elm.ensure_profiles_exist(self.time_profile)

    def delete_profiles(self):
        """
        Delete the time profiles
        :return:
        """
        for elm in self.items():
            elm.delete_profiles()
        self.time_profile = None

    # ------------------------------------------------------------------------------------------------------------------
    # Snapshot time
    # ------------------------------------------------------------------------------------------------------------------

    def get_snapshot_time_unix(self) -> float:
        """
        Get the unix representation of the snapshot time
        :return: float
        """
        return self.snapshot_time.timestamp()

    def set_snapshot_time_unix(self, val: float) -> None:
        """
        Convert unix datetime to python datetime
        :param val: seconds since 1970-01-01T00:00:00
        """
        self.snapshot_time = dateslib.datetime.fromtimestamp(val)

    @property
    def snapshot_time(self) -> dateslib.datetime:
        """
        Returns the current snapshot time
        :return: Datetime
        """
        return self._snapshot_time

    @snapshot_time.setter
    def snapshot_time(self, val: dateslib.datetime):
        if type(val) is dateslib.datetime:  # isinstance doesn't work for this
            self._snapshot_time = dateslib.datetime(year=val.year,
                                                    month=val.month,
                                                    day=val.day,
                                                    hour=val.hour,
                                                    minute=val.minute,
                                                    second=val.second,
                                                    microsecond=val.microsecond)
        elif type(val) is pd.Timestamp:  # isinstance doesn't work for this
            self._snapshot_time = dateslib.datetime(year=val.year,
                                                    month=val.month,
                                                    day=val.day,
                                                    hour=val.hour,
                                                    minute=val.minute,
                                                    second=val.second,
                                                    microsecond=val.microsecond)
        else:
            raise Exception(f'unsupported value set {val} for snapshot_time')

    # ------------------------------------------------------------------------------------------------------------------
    # AC line
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def lines(self) -> List[dev.Line]:
        """
        get list of ac lines
        :return: list of lines
        """
        return self._lines

    @lines.setter
    def lines(self, value: List[dev.Line]):
        self._lines = value

    def get_lines(self) -> List[dev.Line]:
        """
        get list of ac lines
        :return: list of lines
        """
        return self._lines

    def add_line(self, obj: dev.Line, logger: Union[Logger, DataLogger] = Logger()):
        """
        Add a line object
        :param obj: Line instance
        :param logger: Logger to record events
        """
        if obj.should_this_be_a_transformer():
            tr = obj.get_equivalent_transformer()
            self.add_transformer2w(tr)
            # print('Converted {} ({}) to a transformer'.format(obj.name, obj.idtag))
            logger.add_warning("Converted line to transformer due to excessive nominal voltage difference",
                               device=obj.idtag)
        else:
            if self.time_profile is not None:
                obj.create_profiles(self.time_profile)
            self._lines.append(obj)

        return obj

    def delete_line(self, obj: dev.Line):
        """
        Delete line
        :param obj: Line instance
        """
        self._lines.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # DC Line
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def dc_lines(self) -> List[dev.DcLine]:
        """
        get list of dc lines
        :return:
        """
        return self._dc_lines

    @dc_lines.setter
    def dc_lines(self, value: List[dev.DcLine]):
        self._dc_lines = value

    def get_dc_lines(self) -> List[dev.DcLine]:
        """

        :return:
        """
        return self._dc_lines

    def add_dc_line(self, obj: dev.DcLine):
        """
        Add a line object
        :param obj: Line instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._dc_lines.append(obj)

    def delete_dc_line(self, obj: dev.DcLine):
        """
        Delete line
        :param obj: Line instance
        """
        self._dc_lines.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Transformer 2W
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def transformers2w(self) -> List[dev.Transformer2W]:
        """
        Get list of transformers
        :return:
        """
        return self._transformers2w

    @transformers2w.setter
    def transformers2w(self, value: List[dev.Transformer2W]):
        self._transformers2w = value

    def get_transformers2w(self) -> List[dev.Transformer2W]:
        """
        get list of 2-winding transformers
        :return: list of transformers
        """
        return self._transformers2w

    def get_transformers2w_number(self) -> int:
        """
        get the number of 2-winding transformers
        :return: int
        """
        return len(self._transformers2w)

    def get_transformers2w_names(self) -> List[str]:
        """
        get a list of names of the 2-winding transformers
        :return: list of names
        """
        return [elm.name for elm in self._transformers2w]

    def add_transformer2w(self, obj: dev.Transformer2W):
        """
        Add a transformer object
        :param obj: Transformer2W instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._transformers2w.append(obj)

    def delete_transformer2w(self, obj: dev.Transformer2W):
        """
        Delete transformer
        :param obj: Transformer2W instance
        """
        self._transformers2w.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # HVDC
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def hvdc_lines(self) -> List[dev.HvdcLine]:
        """
        Get list of hvdc lines
        :return:
        """
        return self._hvdc_lines

    @hvdc_lines.setter
    def hvdc_lines(self, value: List[dev.HvdcLine]):
        self._hvdc_lines = value

    def get_hvdc(self) -> List[dev.HvdcLine]:
        """

        :return:
        """
        return self._hvdc_lines

    def get_hvdc_number(self) -> int:
        """

        :return:
        """
        return len(self._hvdc_lines)

    def get_hvdc_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([elm.name for elm in self._hvdc_lines])

    def add_hvdc(self, obj: dev.HvdcLine):
        """
        Add a hvdc line object
        :param obj: HvdcLine instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._hvdc_lines.append(obj)

    def delete_hvdc_line(self, obj: dev.HvdcLine):
        """
        Delete HVDC line
        :param obj:
        """
        self._hvdc_lines.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # VSC
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def vsc_devices(self) -> List[dev.VSC]:
        """
        Get list of vsc devices
        :return:
        """
        return self._vsc_devices

    @vsc_devices.setter
    def vsc_devices(self, value: List[dev.VSC]):
        self._vsc_devices = value

    def get_vsc(self) -> List[dev.VSC]:
        """

        :return:
        """
        return self._vsc_devices

    def get_vsc_number(self) -> int:
        """

        :return:
        """
        return len(self._vsc_devices)

    def add_vsc(self, obj: dev.VSC):
        """
        Add a hvdc line object
        :param obj: HvdcLine instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._vsc_devices.append(obj)

    def delete_vsc_converter(self, obj: dev.VSC):
        """
        Delete VSC
        :param obj: VSC Instance
        """
        self._vsc_devices.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # UPFC
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def upfc_devices(self) -> List[dev.UPFC]:
        """
        Get list of upfc devices
        :return:
        """
        return self._upfc_devices

    @upfc_devices.setter
    def upfc_devices(self, value: List[dev.UPFC]):
        self._upfc_devices = value

    def get_upfc(self) -> List[dev.UPFC]:
        """

        :return:
        """
        return self._upfc_devices

    def add_upfc(self, obj: dev.UPFC):
        """
        Add a UPFC object
        :param obj: UPFC instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._upfc_devices.append(obj)

    def delete_upfc_converter(self, obj: dev.UPFC):
        """
        Delete VSC
        :param obj: VSC Instance
        """
        self._upfc_devices.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Switches
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def switch_devices(self) -> List[dev.Switch]:
        """
        Get list of switch devices
        :return:
        """
        return self._switch_devices

    @switch_devices.setter
    def switch_devices(self, value: List[dev.Switch]):
        self._switch_devices = value

    def get_switches(self) -> List[dev.Switch]:
        """

        :return:
        """
        return self._switch_devices

    def get_switches_number(self) -> int:
        """

        :return:
        """
        return len(self._switch_devices)

    def add_switch(self, obj: dev.Switch):
        """
        Add a Switch object
        :param obj: Switch instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._switch_devices.append(obj)

        return obj

    def delete_switch(self, obj: dev.Switch):
        """
        Delete transformer
        :param obj: Transformer2W instance
        """
        self._switch_devices.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Transformer 3W
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def transformers3w(self) -> List[dev.Transformer3W]:
        """
        Get list of 3W transformers
        :return:
        """
        return self._transformers3w

    @transformers3w.setter
    def transformers3w(self, value: List[dev.Transformer3W]):
        self._transformers3w = value

    def get_transformers3w(self) -> List[dev.Transformer3W]:
        """

        :return:
        """
        return self._transformers3w

    def get_transformers3w_number(self) -> int:
        """

        :return:
        """
        return len(self._transformers3w)

    def get_transformers3w_names(self) -> List[str]:
        """

        :return:
        """
        return [elm.name for elm in self._transformers3w]

    def add_transformer3w(self, obj: dev.Transformer3W, add_middle_bus: bool = True):
        """
        Add a transformer object
        :param obj: Transformer3W instance
        :param add_middle_bus: Add the TR3 middle bus?
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._transformers3w.append(obj)
        if add_middle_bus:
            self.add_bus(obj.bus0)  # add the middle transformer
        self.add_winding(obj.winding1)
        self.add_winding(obj.winding2)
        self.add_winding(obj.winding3)

    def delete_transformer3w(self, obj: dev.Transformer3W):
        """
        Delete transformer
        :param obj: Transformer2W instance
        """
        self._transformers3w.remove(obj)
        self.delete_winding(obj.winding1)
        self.delete_winding(obj.winding2)
        self.delete_winding(obj.winding3)
        self.delete_bus(obj.bus0, delete_associated=True)  # also remove the middle bus

    # ------------------------------------------------------------------------------------------------------------------
    # Windings
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def windings(self) -> List[dev.Winding]:
        """
        Get list of windings
        :return:
        """
        return self._windings

    @windings.setter
    def windings(self, value: List[dev.Winding]):
        self._windings = value

    def get_windings(self) -> List[dev.Winding]:
        """

        :return:
        """
        return self._windings

    def get_windings_number(self) -> int:
        """

        :return:
        """
        return len(self._windings)

    def get_windings_names(self) -> List[str]:
        """

        :return:
        """
        return [elm.name for elm in self._windings]

    def add_winding(self, obj: dev.Winding):
        """
        Add a winding object
        :param obj: Winding instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._windings.append(obj)

    def delete_winding(self, obj: dev.Winding):
        """
        Delete winding
        :param obj: Winding instance
        """
        for tr3 in self._transformers3w:

            if obj == tr3.winding1:
                tr3.bus1 = None
                # tr3.winding1 = None
                # if tr3.graphic_obj is not None:
                #     tr3.graphic_obj.connection_lines[0] = None

            elif obj == tr3.winding2:
                tr3.bus2 = None
                # tr3.winding2 = None
                # if tr3.graphic_obj is not None:
                #     tr3.graphic_obj.connection_lines[1] = None

            if obj == tr3.winding3:
                tr3.bus3 = None
                # tr3.winding3 = None
                # if tr3.graphic_obj is not None:
                #     tr3.graphic_obj.connection_lines[2] = None

        # self.windings.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Series reactance
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def series_reactances(self) -> List[dev.SeriesReactance]:
        """
        Get list of series reactances
        :return:
        """
        return self._series_reactances

    @series_reactances.setter
    def series_reactances(self, value: List[dev.SeriesReactance]):
        self._series_reactances = value

    def get_series_reactances(self) -> List[dev.SeriesReactance]:
        """
        List of series_reactances
        :return: List[dev.SeriesReactance]
        """
        return self._series_reactances

    def get_series_reactances_number(self) -> int:
        """
        Size of the list of series_reactances
        :return: size of series_reactances
        """
        return len(self._series_reactances)

    def get_series_reactance_at(self, i: int) -> dev.SeriesReactance:
        """
        Get series_reactance at i
        :param i: index
        :return: SeriesReactance
        """
        return self._series_reactances[i]

    def get_series_reactance_names(self) -> StrVec:
        """
        Array of series_reactance names
        :return: StrVec
        """
        return np.array([e.name for e in self._series_reactances])

    def add_series_reactance(self, obj: dev.SeriesReactance):
        """
        Add a SeriesReactance object
        :param obj: SeriesReactance instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._series_reactances.append(obj)

    def delete_series_reactance(self, obj: dev.SeriesReactance) -> None:
        """
        Add a SeriesReactance object
        :param obj: SeriesReactance instance
        """

        self._series_reactances.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Buses
    # ------------------------------------------------------------------------------------------------------------------
    @property
    def buses(self) -> List[dev.Bus]:
        """
        Get list of buses
        :return:
        """
        return self._buses

    @buses.setter
    def buses(self, value: List[dev.Bus]):
        self._buses = value

    def get_bus_number(self) -> int:
        """
        Return the number of buses
        :return: number
        """
        return len(self._buses)

    def get_buses(self) -> List[dev.Bus]:
        """
        List of buses
        :return:
        """
        return self._buses

    def get_bus_at(self, i: int) -> dev.Bus:
        """
        List of buses
        :param i: index
        :return:
        """
        return self._buses[i]

    def get_bus_names(self) -> StrVec:
        """
        List of bus names
        :return:
        """
        return np.array([e.name for e in self._buses])

    def get_bus_dict(self, by_idtag=False) -> Dict[str, dev.Bus]:
        """
        Return dictionary of buses
        :param by_idtag if true, the key is the idtag else the key is the name
        :return: dictionary of buses {name:object}
        """
        if by_idtag:
            return {b.idtag: b for b in self._buses}
        else:
            return {b.name: b for b in self._buses}

    def get_bus_index_dict(self) -> Dict[dev.Bus, int]:
        """
        Return dictionary of buses
        :return: dictionary of buses {name:object}
        """
        return {b: i for i, b in enumerate(self._buses)}

    def add_bus(self, obj: Union[None, dev.Bus] = None) -> dev.Bus:
        """
        Add a :ref:`Bus<bus>` object to the grid.

        Arguments:

            **obj** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object
        """
        if obj is None:
            obj = dev.Bus()

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)

        self._buses.append(obj)

        return obj

    def delete_bus(self, obj: dev.Bus, delete_associated=False):
        """
        Delete a :ref:`Bus<bus>` object from the grid.
        :param obj: :ref:`Bus<bus>` object
        :param delete_associated:
        """

        # remove associated Branches in reverse order
        for branch_list in self.get_branch_lists():
            for i in range(len(branch_list) - 1, -1, -1):
                if branch_list[i].bus_from == obj:
                    if delete_associated:
                        self.delete_branch(branch_list[i])
                    else:
                        branch_list[i].bus_from = None
                elif branch_list[i].bus_to == obj:
                    if delete_associated:
                        self.delete_branch(branch_list[i])
                    else:
                        branch_list[i].bus_to = None

        # remove the associated injection devices
        for inj_list in self.get_injection_devices_lists():
            for i in range(len(inj_list) - 1, -1, -1):
                if inj_list[i].bus == obj:
                    if delete_associated:
                        self.delete_injection_device(inj_list[i])
                    else:
                        inj_list[i].bus = None

        # remove associations in bus_bars
        for cn in self._connectivity_nodes:
            if cn.default_bus == obj:
                cn.default_bus = None  # remove the association

        # remove the bus itself
        if obj in self._buses:
            self._buses.remove(obj)

    def get_buses_by(self, filter_elements: List[Union[dev.Area, dev.Country, dev.Zone]]) -> List[dev.Bus]:
        """
        Get a list of buses that can be found in the list of Areas | Zones | Countries
        :param filter_elements: list of Areas | Zones | Countries
        :return: list of buses
        """
        data: List[dev.Bus] = list()

        for bus in self._buses:

            if bus.area in filter_elements or bus.zone in filter_elements or bus.country in filter_elements:
                data.append(bus)

        return data

    # ------------------------------------------------------------------------------------------------------------------
    # Connectivity nodes
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def connectivity_nodes(self) -> List[dev.ConnectivityNode]:
        """
        Get connectivity nodes list
        :return:
        """
        return self._connectivity_nodes

    @connectivity_nodes.setter
    def connectivity_nodes(self, value: List[dev.ConnectivityNode]):
        self._connectivity_nodes = value

    def get_connectivity_nodes(self) -> List[dev.ConnectivityNode]:
        """
        Get all connectivity nodes
        """
        return self._connectivity_nodes

    def get_connectivity_nodes_number(self) -> int:
        """
        Get all connectivity nodes
        """
        return len(self._connectivity_nodes)

    def add_connectivity_node(self, obj: dev.ConnectivityNode):
        """
        Add Substation
        :param obj: BusBar object
        """
        if obj is None:
            obj = dev.ConnectivityNode(name=f"CN{len(self._connectivity_nodes)}")

        self._connectivity_nodes.append(obj)

        return obj

    def delete_connectivity_node(self, obj: dev.ConnectivityNode):
        """
        Delete Substation
        :param obj: Substation object
        """
        for elm in self._bus_bars:
            elm.connectivity_node = None

        self._connectivity_nodes.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Bus bars
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def bus_bars(self) -> List[dev.BusBar]:
        """
        Get the list of BusBars
        :return:
        """
        return self._bus_bars

    @bus_bars.setter
    def bus_bars(self, value: List[dev.BusBar]):
        self._bus_bars = value

    def get_bus_bars(self) -> List[dev.BusBar]:
        """
        Get all bus bars
        """
        return self._bus_bars

    def get_bus_bars_number(self) -> int:
        """
        Get all bus-bars number
        :return:
        """
        return len(self._bus_bars)

    def add_bus_bar(self, obj: dev.BusBar, add_cn: bool = True):
        """
        Add Substation
        :param obj: BusBar object
        :param add_cn: Add the internal CN of the BusBar?
        """
        if obj is None:
            obj = dev.BusBar(name=f"BB{len(self._bus_bars)}")

        self._bus_bars.append(obj)

        # add the internal connectivity node
        if add_cn:
            self.add_connectivity_node(obj.cn)

        return obj

    def delete_bus_bar(self, obj: dev.BusBar):
        """
        Delete Substation
        :param obj: Substation object
        """
        self.delete_connectivity_node(obj=obj.cn)
        self._bus_bars.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Voltage level
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def voltage_levels(self) -> List[dev.VoltageLevel]:
        """
        Get voltage level devices list
        :return:
        """
        return self._voltage_levels

    @voltage_levels.setter
    def voltage_levels(self, value: List[dev.VoltageLevel]):
        self._voltage_levels = value

    def get_voltage_levels(self) -> List[dev.VoltageLevel]:
        """
        List of voltage_levels
        :return: List[dev.VoltageLevel]
        """
        return self._voltage_levels

    def get_voltage_levels_number(self) -> int:
        """
        Size of the list of voltage_levels
        :return: size of voltage_levels
        """
        return len(self._voltage_levels)

    def get_voltage_level_at(self, i: int) -> dev.VoltageLevel:
        """
        Get voltage_level at i
        :param i: index
        :return: VoltageLevel
        """
        return self._voltage_levels[i]

    def get_voltage_level_names(self) -> StrVec:
        """
        Array of voltage_level names
        :return: StrVec
        """
        return np.array([e.name for e in self._voltage_levels])

    def add_voltage_level(self, obj: dev.VoltageLevel):
        """
        Add a VoltageLevel object
        :param obj: VoltageLevel instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._voltage_levels.append(obj)

    def delete_voltage_level(self, obj: dev.VoltageLevel) -> None:
        """
        Add a VoltageLevel object
        :param obj: VoltageLevel instance
        """

        for elm in self._buses:
            if elm.voltage_level == obj:
                elm.voltage_level = None

        self._voltage_levels.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def loads(self) -> List[dev.Load]:
        """
        Get list of loads
        :return:
        """
        return self._loads

    @loads.setter
    def loads(self, value: List[dev.Load]):
        self._loads = value

    def get_loads(self) -> List[dev.Load]:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        return self._loads

    def get_loads_number(self) -> int:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        return len(self._loads)

    def get_load_names(self) -> StrVec:
        """
        Returns a list of :ref:`Load<load>` names.
        """
        return np.array([elm.name for elm in self._loads])

    def add_load(self,
                 bus: Union[None, dev.Bus] = None,
                 api_obj: Union[None, dev.Load] = None,
                 cn: Union[None, dev.ConnectivityNode] = None) -> dev.Load:
        """
        Add a load device
        :param bus: Main bus (optional)
        :param cn:  Main connectivity node (Optional)
        :param api_obj: Device to add (optional)
        :return: Load device passed or created
        """
        if api_obj is None:
            api_obj = dev.Load()
        api_obj.bus = bus
        api_obj.cn = cn

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'Load':
            if bus is not None:
                api_obj.name += '@' + bus.name
            elif cn is not None:
                api_obj.name += '@' + cn.name

        self._loads.append(api_obj)

        return api_obj

    # ------------------------------------------------------------------------------------------------------------------
    # Generator
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def generators(self) -> List[dev.Generator]:
        """
        Get list of generators
        :return:
        """
        return self._generators

    @generators.setter
    def generators(self, value: List[dev.Generator]):
        self._generators = value

    def get_generators(self) -> List[dev.Generator]:
        """
        Returns a list of :ref:`Generator<generator>` objects in the grid.
        """
        return self._generators

    def get_generators_number(self) -> int:
        """
        Get the number of generators
        :return: int
        """
        return len(self._generators)

    def get_generator_names(self) -> StrVec:
        """
        Returns a list of :ref:`Generator<generator>` names.
        """
        return np.array([elm.name for elm in self._generators])

    def add_generator(self,
                      bus: Union[None, dev.Bus] = None,
                      api_obj: Union[None, dev.Generator] = None,
                      cn: Union[None, dev.ConnectivityNode] = None) -> dev.Generator:
        """
        Add a generator
        :param bus: Main bus (optional)
        :param cn:  Main connectivity node (Optional)
        :param api_obj: Generator object (optional)
        :return: Generator object (created if api_obj is None)
        """

        if api_obj is None:
            api_obj = dev.Generator()
        api_obj.bus = bus
        api_obj.cn = cn

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'gen':
            if bus is not None:
                api_obj.name += '@' + bus.name
            elif cn is not None:
                api_obj.name += '@' + cn.name

        self._generators.append(api_obj)

        return api_obj

    def delete_generator(self, obj: dev.Generator):
        """
        Delete a generator
        :param obj:
        :return:
        """
        self._generators.remove(obj)

        elms_to_del = list()
        for elm in self._contingencies:
            if elm.device_idtag == obj.idtag:
                elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

    def get_generator_indexing_dict(self) -> Dict[str, int]:
        """
        Get a dictionary that relates the generator uuid's with their index
        :return: Dict[str, int]
        """
        gen_index_dict: Dict[str, int] = dict()
        for k, elm in enumerate(self.get_generators()):
            gen_index_dict[elm.idtag] = k  # associate the idtag to the index
        return gen_index_dict

    # ------------------------------------------------------------------------------------------------------------------
    # External grid
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def external_grids(self) -> List[dev.ExternalGrid]:
        """
        Get list of external grids
        :return:
        """
        return self._external_grids

    @external_grids.setter
    def external_grids(self, value: List[dev.ExternalGrid]):
        self._external_grids = value

    def get_external_grids(self) -> List[dev.ExternalGrid]:
        """
        Returns a list of :ref:`ExternalGrid<external_grid>` objects in the grid.
        """
        return self._external_grids

    def get_external_grids_number(self) -> int:
        """
        Returns a list of :ref:`ExternalGrid<external_grid>` objects in the grid.
        """
        return len(self._external_grids)

    def get_external_grid_names(self) -> StrVec:
        """
        Returns a list of :ref:`ExternalGrid<external_grid>` names.
        """
        return np.array([elm.name for elm in self._external_grids])

    def add_external_grid(self,
                          bus: Union[None, dev.Bus] = None,
                          api_obj: Union[None, dev.ExternalGrid] = None,
                          cn: Union[None, dev.ConnectivityNode] = None) -> dev.ExternalGrid:
        """
        Add an external grid
        :param bus: Bus object
        :param api_obj: api_obj, if None, create a new one
        :param cn: ConnectivityNode
        :return: ExternalGrid
        """

        if api_obj is None:
            api_obj = dev.ExternalGrid()
        api_obj.bus = bus
        api_obj.cn = cn

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'External grid':
            if bus is not None:
                api_obj.name += '@' + bus.name
            elif cn is not None:
                api_obj.name += '@' + cn.name

        self._external_grids.append(api_obj)

        return api_obj

    # ------------------------------------------------------------------------------------------------------------------
    # Shunt
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def shunts(self) -> List[dev.Shunt]:
        """
        Get list of shunts
        :return:
        """
        return self._shunts

    @shunts.setter
    def shunts(self, value: List[dev.Shunt]):
        self._shunts = value

    def get_shunts(self) -> List[dev.Shunt]:
        """
        Returns a list of :ref:`Shunt<shunt>` objects in the grid.
        """
        return self._shunts

    def get_shunts_number(self) -> int:
        """
        Get the number of shunts
        """
        return len(self._shunts)

    def get_shunt_names(self):
        """
        Returns a list of :ref:`Shunt<shunt>` names.
        """
        return np.array([elm.name for elm in self._shunts])

    def add_shunt(self,
                  bus: Union[None, dev.Bus] = None,
                  api_obj: Union[None, dev.Shunt] = None,
                  cn: Union[None, dev.ConnectivityNode] = None) -> dev.Shunt:
        """
        Add a :ref:`Shunt<shunt>` object to a :ref:`Bus<bus>`.

        Arguments:

            **bus** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object

            **api_obj** (:ref:`Shunt<shunt>`): :ref:`Shunt<shunt>` object
        """
        if api_obj is None:
            api_obj = dev.Shunt()
        api_obj.bus = bus
        api_obj.cn = cn

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'shunt':
            if bus is not None:
                api_obj.name += '@' + bus.name
            elif cn is not None:
                api_obj.name += '@' + cn.name

        self._shunts.append(api_obj)

        return api_obj

    # ------------------------------------------------------------------------------------------------------------------
    # Batteries
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def batteries(self) -> List[dev.Battery]:
        """
        Get list of batteries
        :return:
        """
        return self._batteries

    @batteries.setter
    def batteries(self, value: List[dev.Battery]):
        self._batteries = value

    def get_batteries(self) -> List[dev.Battery]:
        """
        Returns a list of :ref:`Battery<battery>` objects in the grid.
        """
        return self._batteries

    def get_batteries_number(self) -> int:
        """
        Returns a list of :ref:`Battery<battery>` objects in the grid.
        """
        return len(self._batteries)

    def get_battery_names(self) -> StrVec:
        """
        Returns a list of :ref:`Battery<battery>` names.
        """
        return np.array([elm.name for elm in self._batteries])

    def get_battery_capacities(self):
        """
        Returns a list of :ref:`Battery<battery>` capacities.
        """
        return np.array([elm.Enom for elm in self._batteries])

    def add_battery(self,
                    bus: Union[None, dev.Bus] = None,
                    api_obj: Union[None, dev.Battery] = None,
                    cn: Union[None, dev.ConnectivityNode] = None) -> dev.Battery:
        """
        Add battery
        :param bus:
        :param cn:
        :param api_obj:
        :return:
        """
        if api_obj is None:
            api_obj = dev.Battery()
        api_obj.bus = bus
        api_obj.cn = cn

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'batt':
            if bus is not None:
                api_obj.name += '@' + bus.name
            elif cn is not None:
                api_obj.name += '@' + cn.name

        self._batteries.append(api_obj)

        return api_obj

    # ------------------------------------------------------------------------------------------------------------------
    # Static generator
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def static_generators(self) -> List[dev.StaticGenerator]:
        """
        Get lis of static generators
        :return:
        """
        return self._static_generators

    @static_generators.setter
    def static_generators(self, value: List[dev.StaticGenerator]):
        self._static_generators = value

    def get_static_generators(self) -> List[dev.StaticGenerator]:
        """
        Returns a list of :ref:`StaticGenerator<static_generator>` objects in the grid.
        """
        return self._static_generators

    def get_static_generators_number(self) -> int:
        """
        Return number of static generators
        :return:
        """
        return len(self._static_generators)

    def get_static_generators_names(self) -> StrVec:
        """
        Returns a list of :ref:`StaticGenerator<static_generator>` names.
        """
        return np.array([elm.name for elm in self._static_generators])

    def add_static_generator(self,
                             bus: Union[None, dev.Bus] = None,
                             api_obj: Union[None, dev.StaticGenerator] = None,
                             cn: Union[None, dev.ConnectivityNode] = None) -> dev.StaticGenerator:
        """
        Add a static generator
        :param bus: Bus object
        :param cn:  Main connectivity node (Optional)
        :param api_obj: StaticGenerator object
        :return: StaticGenerator object (created if api_obj is None)
        """

        if api_obj is None:
            api_obj = dev.StaticGenerator()
        api_obj.bus = bus
        api_obj.cn = cn

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'StaticGen':
            if bus is not None:
                api_obj.name += '@' + bus.name
            elif cn is not None:
                api_obj.name += '@' + cn.name

        self._static_generators.append(api_obj)

        return api_obj

    # ------------------------------------------------------------------------------------------------------------------
    # Current injection
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def current_injections(self) -> List[dev.CurrentInjection]:
        """
        Get list of current injection devices
        :return:
        """
        return self._current_injections

    @current_injections.setter
    def current_injections(self, value: List[dev.CurrentInjection]):
        self._current_injections = value

    def get_current_injections(self) -> List[dev.CurrentInjection]:
        """
        List of current_injections
        :return: List[dev.CurrentInjection]
        """
        return self._current_injections

    def get_current_injections_number(self) -> int:
        """
        Size of the list of current_injections
        :return: size of current_injections
        """
        return len(self._current_injections)

    def get_current_injection_at(self, i: int) -> dev.CurrentInjection:
        """
        Get current_injection at i
        :param i: index
        :return: CurrentInjection
        """
        return self._current_injections[i]

    def get_current_injection_names(self) -> StrVec:
        """
        Array of current_injection names
        :return: StrVec
        """
        return np.array([e.name for e in self._current_injections])

    def add_current_injection(self,
                              bus: Union[None, dev.Bus] = None,
                              api_obj: Union[None, dev.CurrentInjection] = None,
                              cn: Union[None, dev.ConnectivityNode] = None) -> dev.CurrentInjection:
        """
        Add a CurrentInjection object
        :param bus: Bus
        :param cn: Connectivity node
        :param api_obj: CurrentInjection instance
        """

        if api_obj is None:
            api_obj = dev.CurrentInjection()

        api_obj.bus = bus
        api_obj.cn = cn

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'CInj':
            api_obj.name += '@' + bus.name

        self._current_injections.append(api_obj)

        return api_obj

    def delete_current_injection(self, obj: dev.CurrentInjection) -> None:
        """
        Add a CurrentInjection object
        :param obj: CurrentInjection instance
        """

        self._current_injections.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Controllable shunt
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def controllable_shunts(self) -> List[dev.ControllableShunt]:
        """
        Get list of controllable shunts
        :return:
        """
        return self._controllable_shunts

    @controllable_shunts.setter
    def controllable_shunts(self, value: List[dev.ControllableShunt]):
        self._controllable_shunts = value

    def get_controllable_shunts(self) -> List[dev.ControllableShunt]:
        """
        List of controllable_shunts
        :return: List[dev.LinearShunt]
        """
        return self._controllable_shunts

    def get_controllable_shunts_number(self) -> int:
        """
        Size of the list of controllable_shunts
        :return: size of controllable_shunts
        """
        return len(self._controllable_shunts)

    def get_controllable_shunt_at(self, i: int) -> dev.ControllableShunt:
        """
        Get linear_shunt at i
        :param i: index
        :return: LinearShunt
        """
        return self._controllable_shunts[i]

    def get_controllable_shunt_names(self) -> StrVec:
        """
        Array of linear_shunt names
        :return: StrVec
        """
        return np.array([e.name for e in self._controllable_shunts])

    def add_controllable_shunt(self,
                               bus: Union[None, dev.Bus] = None,
                               api_obj: Union[None, dev.ControllableShunt] = None,
                               cn: Union[None, dev.ConnectivityNode] = None) -> dev.ControllableShunt:
        """
        Add a ControllableShunt object
        :param bus: Main bus (optional)
        :param cn:  Main connectivity node (Optional)
        :param api_obj: ControllableShunt instance
        :return: ControllableShunt
        """

        if api_obj is None:
            api_obj = dev.ControllableShunt()
        api_obj.bus = bus
        api_obj.cn = cn

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'CShutn':
            if bus is not None:
                api_obj.name += '@' + bus.name
            elif cn is not None:
                api_obj.name += '@' + cn.name

        self._controllable_shunts.append(api_obj)

        return api_obj

    def delete_controllable_shunt(self, obj: dev.ControllableShunt) -> None:
        """
        Add a LinearShunt object
        :param obj: LinearShunt instance
        """

        self._controllable_shunts.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # P_i measurement
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def pi_measurements(self) -> List[dev.PiMeasurement]:
        """
        Get list of PiMeasurements
        :return:
        """
        return self._pi_measurements

    @pi_measurements.setter
    def pi_measurements(self, value: List[dev.PiMeasurement]):
        self._pi_measurements = value

    def get_pi_measurements(self) -> List[dev.PiMeasurement]:
        """
        List of pi_measurements
        :return: List[dev.PiMeasurement]
        """
        return self._pi_measurements

    def get_pi_measurements_number(self) -> int:
        """
        Size of the list of pi_measurements
        :return: size of pi_measurements
        """
        return len(self._pi_measurements)

    def get_pi_measurement_at(self, i: int) -> dev.PiMeasurement:
        """
        Get pi_measurement at i
        :param i: index
        :return: PiMeasurement
        """
        return self._pi_measurements[i]

    def get_pi_measurement_names(self) -> StrVec:
        """
        Array of pi_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._pi_measurements])

    def add_pi_measurement(self, obj: dev.PiMeasurement):
        """
        Add a PiMeasurement object
        :param obj: PiMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._pi_measurements.append(obj)

    def delete_pi_measurement(self, obj: dev.PiMeasurement) -> None:
        """
        Add a PiMeasurement object
        :param obj: PiMeasurement instance
        """

        self._pi_measurements.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Q_i measurement
    # ------------------------------------------------------------------------------------------------------------------
    @property
    def qi_measurements(self) -> List[dev.QiMeasurement]:
        """
        Get list of QiMeasurements
        :return:
        """
        return self._qi_measurements

    @qi_measurements.setter
    def qi_measurements(self, value: List[dev.QiMeasurement]):
        self._qi_measurements = value

    def get_qi_measurements(self) -> List[dev.QiMeasurement]:
        """
        List of qi_measurements
        :return: List[dev.QiMeasurement]
        """
        return self._qi_measurements

    def get_qi_measurements_number(self) -> int:
        """
        Size of the list of qi_measurements
        :return: size of qi_measurements
        """
        return len(self._qi_measurements)

    def get_qi_measurement_at(self, i: int) -> dev.QiMeasurement:
        """
        Get qi_measurement at i
        :param i: index
        :return: QiMeasurement
        """
        return self._qi_measurements[i]

    def get_qi_measurement_names(self) -> StrVec:
        """
        Array of qi_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._qi_measurements])

    def add_qi_measurement(self, obj: dev.QiMeasurement):
        """
        Add a QiMeasurement object
        :param obj: QiMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._qi_measurements.append(obj)

    def delete_qi_measurement(self, obj: dev.QiMeasurement) -> None:
        """
        Add a QiMeasurement object
        :param obj: QiMeasurement instance
        """

        self._qi_measurements.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Vm measurement
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def vm_measurements(self) -> List[dev.VmMeasurement]:
        """
        Get list of VmMeasurements
        :return:
        """
        return self._vm_measurements

    @vm_measurements.setter
    def vm_measurements(self, value: List[dev.VmMeasurement]):
        self._vm_measurements = value

    def get_vm_measurements(self) -> List[dev.VmMeasurement]:
        """
        List of vm_measurements
        :return: List[dev.VmMeasurement]
        """
        return self._vm_measurements

    def get_vm_measurements_number(self) -> int:
        """
        Size of the list of vm_measurements
        :return: size of vm_measurements
        """
        return len(self._vm_measurements)

    def get_vm_measurement_at(self, i: int) -> dev.VmMeasurement:
        """
        Get vm_measurement at i
        :param i: index
        :return: VmMeasurement
        """
        return self._vm_measurements[i]

    def get_vm_measurement_names(self) -> StrVec:
        """
        Array of vm_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._vm_measurements])

    def add_vm_measurement(self, obj: dev.VmMeasurement):
        """
        Add a VmMeasurement object
        :param obj: VmMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._vm_measurements.append(obj)

    def delete_vm_measurement(self, obj: dev.VmMeasurement) -> None:
        """
        Add a VmMeasurement object
        :param obj: VmMeasurement instance
        """

        self._vm_measurements.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Pf measurement
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def pf_measurements(self) -> List[dev.PfMeasurement]:
        """
        Get list of PfMeasuremnts
        :return:
        """
        return self._pf_measurements

    @pf_measurements.setter
    def pf_measurements(self, value: List[dev.PfMeasurement]):
        self._pf_measurements = value

    def get_pf_measurements(self) -> List[dev.PfMeasurement]:
        """
        List of pf_measurements
        :return: List[dev.PfMeasurement]
        """
        return self._pf_measurements

    def get_pf_measurements_number(self) -> int:
        """
        Size of the list of pf_measurements
        :return: size of pf_measurements
        """
        return len(self._pf_measurements)

    def get_pf_measurement_at(self, i: int) -> dev.PfMeasurement:
        """
        Get pf_measurement at i
        :param i: index
        :return: PfMeasurement
        """
        return self._pf_measurements[i]

    def get_pf_measurement_names(self) -> StrVec:
        """
        Array of pf_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._pf_measurements])

    def add_pf_measurement(self, obj: dev.PfMeasurement):
        """
        Add a PfMeasurement object
        :param obj: PfMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._pf_measurements.append(obj)

    def delete_pf_measurement(self, obj: dev.PfMeasurement) -> None:
        """
        Add a PfMeasurement object
        :param obj: PfMeasurement instance
        """

        self._pf_measurements.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Qf measurement
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def qf_measurements(self) -> List[dev.QfMeasurement]:
        """
        Get list of Qf measurements
        :return:
        """
        return self._qf_measurements

    @qf_measurements.setter
    def qf_measurements(self, value: List[dev.QfMeasurement]):
        self._qf_measurements = value

    def get_qf_measurements(self) -> List[dev.QfMeasurement]:
        """
        List of qf_measurements
        :return: List[dev.QfMeasurement]
        """
        return self._qf_measurements

    def get_qf_measurements_number(self) -> int:
        """
        Size of the list of qf_measurements
        :return: size of qf_measurements
        """
        return len(self._qf_measurements)

    def get_qf_measurement_at(self, i: int) -> dev.QfMeasurement:
        """
        Get qf_measurement at i
        :param i: index
        :return: QfMeasurement
        """
        return self._qf_measurements[i]

    def get_qf_measurement_names(self) -> StrVec:
        """
        Array of qf_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._qf_measurements])

    def add_qf_measurement(self, obj: dev.QfMeasurement):
        """
        Add a QfMeasurement object
        :param obj: QfMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._qf_measurements.append(obj)

    def delete_qf_measurement(self, obj: dev.QfMeasurement) -> None:
        """
        Add a QfMeasurement object
        :param obj: QfMeasurement instance
        """

        self._qf_measurements.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # If measurement
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def if_measurements(self) -> List[dev.IfMeasurement]:
        """
        Get list of If measurements
        :return:
        """
        return self._if_measurements

    @if_measurements.setter
    def if_measurements(self, value: List[dev.IfMeasurement]):
        self._if_measurements = value

    def get_if_measurements(self) -> List[dev.IfMeasurement]:
        """
        List of if_measurements
        :return: List[dev.IfMeasurement]
        """
        return self._if_measurements

    def get_if_measurements_number(self) -> int:
        """
        Size of the list of if_measurements
        :return: size of if_measurements
        """
        return len(self._if_measurements)

    def get_if_measurement_at(self, i: int) -> dev.IfMeasurement:
        """
        Get if_measurement at i
        :param i: index
        :return: IfMeasurement
        """
        return self._if_measurements[i]

    def get_if_measurement_names(self) -> StrVec:
        """
        Array of if_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._if_measurements])

    def add_if_measurement(self, obj: dev.IfMeasurement):
        """
        Add a IfMeasurement object
        :param obj: IfMeasurement instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._if_measurements.append(obj)

    def delete_if_measurement(self, obj: dev.IfMeasurement) -> None:
        """
        Add a IfMeasurement object
        :param obj: IfMeasurement instance
        """

        self._if_measurements.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Overhead line type
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def overhead_line_types(self) -> List[dev.OverheadLineType]:
        """
        Get
        :return:
        """
        return self._overhead_line_types

    @overhead_line_types.setter
    def overhead_line_types(self, value: List[dev.OverheadLineType]):
        self._overhead_line_types = value

    def add_overhead_line(self, obj: dev.OverheadLineType):
        """
        Add overhead line (tower) template to the collection
        :param obj: Tower instance
        """
        if obj is not None:
            if isinstance(obj, dev.OverheadLineType):
                self._overhead_line_types.append(obj)
            else:
                print('The template is not an overhead line!')

    def delete_line_template_dependency(self, obj):
        """
        Search a branch template from lines and transformers and delete it
        :param obj:
        :return:
        """
        for elm in self._lines:
            if elm.template == obj:
                elm.template = None

    def delete_overhead_line(self, obj: dev.OverheadLineType):
        """
        Delete tower from the collection
        :param obj: OverheadLineType
        """

        self.delete_line_template_dependency(obj=obj)
        self._overhead_line_types.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Wire types
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def wire_types(self) -> List[dev.Wire]:
        """

        :return:
        """
        return self._wire_types

    @wire_types.setter
    def wire_types(self, value: List[dev.Wire]):
        self._wire_types = value

    def add_wire(self, obj: dev.Wire):
        """
        Add Wire to the collection
        :param obj: Wire instance
        """
        if obj is not None:
            if isinstance(obj, dev.Wire):
                self._wire_types.append(obj)
            else:
                print('The template is not a wire!')

    def delete_wire(self, obj: dev.Wire):
        """
        Delete wire from the collection
        :param obj: Wire object
        """
        for tower in self._overhead_line_types:
            for elm in tower.wires_in_tower:
                if elm.template == obj:
                    elm.template = None

        self._wire_types.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Underground cable
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def underground_cable_types(self) -> List[dev.UndergroundLineType]:
        """

        :return:
        """
        return self._underground_cable_types

    @underground_cable_types.setter
    def underground_cable_types(self, value: List[dev.UndergroundLineType]):
        self._underground_cable_types = value

    def add_underground_line(self, obj: dev.UndergroundLineType):
        """
        Add underground line
        :param obj: UndergroundLineType instance
        """
        if obj is not None:
            if isinstance(obj, dev.UndergroundLineType):
                self._underground_cable_types.append(obj)
            else:
                print('The template is not an underground line!')

    def delete_underground_line(self, obj):
        """
        Delete underground line
        :param obj:
        """
        self.delete_line_template_dependency(obj=obj)
        self._underground_cable_types.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Sequence line type
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def sequence_line_types(self) -> List[dev.SequenceLineType]:
        """

        :return:
        """
        return self._sequence_line_types

    @sequence_line_types.setter
    def sequence_line_types(self, value: List[dev.SequenceLineType]):
        self._sequence_line_types = value

    def add_sequence_line(self, obj: dev.SequenceLineType):
        """
        Add sequence line to the collection
        :param obj: SequenceLineType instance
        """
        if obj is not None:
            if isinstance(obj, dev.SequenceLineType):
                self._sequence_line_types.append(obj)
            else:
                print('The template is not a sequence line!')

    def delete_sequence_line(self, obj):
        """
        Delete sequence line from the collection
        :param obj:
        """
        self.delete_line_template_dependency(obj=obj)
        self._sequence_line_types.remove(obj)
        return True

    # ------------------------------------------------------------------------------------------------------------------
    # Transformer type
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def transformer_types(self) -> List[dev.TransformerType]:
        """

        :return:
        """
        return self._transformer_types

    @transformer_types.setter
    def transformer_types(self, value: List[dev.TransformerType]):
        self._transformer_types = value

    def add_transformer_type(self, obj: dev.TransformerType):
        """
        Add transformer template
        :param obj: TransformerType instance
        """
        if obj is not None:
            if isinstance(obj, dev.TransformerType):
                self._transformer_types.append(obj)
            else:
                print('The template is not a transformer!')

    def delete_transformer_template_dependency(self, obj: dev.TransformerType):
        """
        Search a branch template from lines and transformers and delete it
        :param obj:
        :return:
        """
        for elm in self._transformers2w:
            if elm.template == obj:
                elm.template = None

    def delete_transformer_type(self, obj: dev.TransformerType):
        """
        Delete transformer type from the collection
        :param obj
        """
        self.delete_transformer_template_dependency(obj=obj)
        self._transformer_types.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Branch group
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def branch_groups(self) -> List[dev.BranchGroup]:
        """

        :return:
        """
        return self._branch_groups

    @branch_groups.setter
    def branch_groups(self, value: List[dev.BranchGroup]):
        self._branch_groups = value

    def get_branch_groups(self) -> List[dev.BranchGroup]:
        """
        List of branch_groups
        :return: List[dev.BranchGroup]
        """
        return self._branch_groups

    def get_branch_groups_number(self) -> int:
        """
        Size of the list of branch_groups
        :return: size of branch_groups
        """
        return len(self._branch_groups)

    def get_branch_group_at(self, i: int) -> dev.BranchGroup:
        """
        Get branch_group at i
        :param i: index
        :return: BranchGroup
        """
        return self._branch_groups[i]

    def get_branch_group_names(self) -> StrVec:
        """
        Array of branch_group names
        :return: StrVec
        """
        return np.array([e.name for e in self._branch_groups])

    def add_branch_group(self, obj: dev.BranchGroup):
        """
        Add a BranchGroup object
        :param obj: BranchGroup instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._branch_groups.append(obj)

    def delete_branch_group(self, obj: dev.BranchGroup) -> None:
        """
        Add a BranchGroup object
        :param obj: BranchGroup instance
        """

        self._branch_groups.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Substations
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def substations(self) -> List[dev.Substation]:
        """
        Get list of substations
        :return:
        """
        return self._substations

    @substations.setter
    def substations(self, value: List[dev.Substation]):
        self._substations = value

    def get_substations(self) -> List[dev.Substation]:
        """
        Get a list of substations
        :return: List[dev.Substation]
        """
        return self._substations

    def get_substation_number(self) -> int:
        """
        Get number of areas
        :return: number of areas
        """
        return len(self._substations)

    def add_substation(self, obj: dev.Substation):
        """
        Add Substation
        :param obj: Substation object
        """
        self._substations.append(obj)

    def delete_substation(self, obj: dev.Substation):
        """
        Delete Substation
        :param obj: Substation object
        """
        for elm in self._buses:
            if elm.substation == obj:
                elm.substation = None

        for elm in self._voltage_levels:
            if elm.substation == obj:
                elm.substation = None

        self._substations.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Area
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def areas(self) -> List[dev.Area]:
        """
        Get the list of Areas
        :return:
        """
        return self._areas

    @areas.setter
    def areas(self, value: List[dev.Area]):
        self._areas = value

    def get_areas(self) -> List[dev.Area]:
        """
        Get list of areas
        :return: List[dev.Area]
        """
        return self._areas

    def get_area_names(self) -> StrVec:
        """
        Get array of area names
        :return: StrVec
        """
        return np.array([a.name for a in self._areas])

    def get_area_number(self) -> int:
        """
        Get number of areas
        :return: number of areas
        """
        return len(self._areas)

    def add_area(self, obj: dev.Area):
        """
        Add area
        :param obj: Area object
        """
        self._areas.append(obj)

    def delete_area(self, obj: dev.Area):
        """
        Delete area
        :param obj: Area
        """
        for elm in self._buses:
            if elm.area == obj:
                elm.area = None

        for elm in self._substations:
            if elm.area == obj:
                elm.area = None

        for elm in self._zones:
            if elm.area == obj:
                elm.area = None

        self._areas.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # zones
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def zones(self) -> List[dev.Zone]:
        """
        Get list of zones
        :return:
        """
        return self._zones

    @zones.setter
    def zones(self, value: List[dev.Zone]):
        self._zones = value

    def get_zones(self) -> List[dev.Zone]:
        """
        Get list of zones
        :return: List[dev.Zone]
        """
        return self._zones

    def get_zone_number(self) -> int:
        """
        Get number of areas
        :return: number of areas
        """
        return len(self._zones)

    def add_zone(self, obj: dev.Zone):
        """
        Add zone
        :param obj: Zone object
        """
        self._zones.append(obj)

    def delete_zone(self, obj):
        """
        Delete zone
        :param obj: index
        """
        for elm in self._buses:
            if elm.zone == obj:
                elm.zone = None

        for elm in self._substations:
            if elm.zone == obj:
                elm.zone = None

        self._zones.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Countries
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def countries(self) -> List[dev.Country]:
        """

        :return:
        """
        return self._countries

    @countries.setter
    def countries(self, value: List[dev.Country]):
        self._countries = value

    def get_countries(self) -> List[dev.Country]:
        """
        Get all countries
        """
        return self._countries

    def get_country_number(self) -> int:
        """
        Get country number
        :return:
        """
        return len(self._countries)

    def add_country(self, obj: dev.Country):
        """
        Add country
        :param obj:  object
        """
        self._countries.append(obj)

    def delete_country(self, obj):
        """
        Delete country
        :param obj: index
        """
        for elm in self._buses:
            if elm.country == obj:
                elm.country = None

        for elm in self._substations:
            if elm.country == obj:
                elm.country = None

        for elm in self._communities:
            if elm.country == obj:
                elm.country = None

        self._countries.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Communities
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def communities(self) -> List[dev.Community]:
        """

        :return:
        """
        return self._communities

    @communities.setter
    def communities(self, value: List[dev.Community]):
        self._communities = value

    def get_communities(self) -> List[dev.Community]:
        """
        List of communities
        :return: List[dev.Community]
        """
        return self._communities

    def get_communities_number(self) -> int:
        """
        Size of the list of communities
        :return: size of communities
        """
        return len(self._communities)

    def get_community_at(self, i: int) -> dev.Community:
        """
        Get community at i
        :param i: index
        :return: Community
        """
        return self._communities[i]

    def get_community_names(self) -> StrVec:
        """
        Array of community names
        :return: StrVec
        """
        return np.array([e.name for e in self._communities])

    def add_community(self, obj: dev.Community):
        """
        Add a Community object
        :param obj: Community instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._communities.append(obj)

    def delete_community(self, obj: dev.Community) -> None:
        """
        Add a Community object
        :param obj: Community instance
        """

        for elm in self._substations:
            if elm.community == obj:
                elm.community = None

        for elm in self._regions:
            if elm.community == obj:
                elm.community = None

        self._communities.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Regions
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def regions(self) -> List[dev.Region]:
        """

        :return:
        """
        return self._regions

    @regions.setter
    def regions(self, value: List[dev.Region]):
        self._regions = value

    def get_regions(self) -> List[dev.Region]:
        """
        List of regions
        :return: List[dev.Region]
        """
        return self._regions

    def get_regions_number(self) -> int:
        """
        Size of the list of regions
        :return: size of regions
        """
        return len(self._regions)

    def get_region_at(self, i: int) -> dev.Region:
        """
        Get region at i
        :param i: index
        :return: Region
        """
        return self._regions[i]

    def get_region_names(self) -> StrVec:
        """
        Array of region names
        :return: StrVec
        """
        return np.array([e.name for e in self._regions])

    def add_region(self, obj: dev.Region):
        """
        Add a Region object
        :param obj: Region instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._regions.append(obj)

    def delete_region(self, obj: dev.Region) -> None:
        """
        Add a Region object
        :param obj: Region instance
        """

        for elm in self._municipalities:
            if elm.region == obj:
                elm.region = None

        self._regions.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Municipalities
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def municipalities(self) -> List[dev.Municipality]:
        """
        Get list of Municipalities
        :return:
        """
        return self._municipalities

    @municipalities.setter
    def municipalities(self, value: List[dev.Municipality]):
        self._municipalities = value

    def get_municipalities(self) -> List[dev.Municipality]:
        """
        List of municipalities
        :return: List[dev.Municipality]
        """
        return self._municipalities

    def get_municipalities_number(self) -> int:
        """
        Size of the list of municipalities
        :return: size of municipalities
        """
        return len(self._municipalities)

    def get_municipality_at(self, i: int) -> dev.Municipality:
        """
        Get municipality at i
        :param i: index
        :return: Municipality
        """
        return self._municipalities[i]

    def get_municipality_names(self) -> StrVec:
        """
        Array of municipality names
        :return: StrVec
        """
        return np.array([e.name for e in self._municipalities])

    def add_municipality(self, obj: dev.Municipality):
        """
        Add a Municipality object
        :param obj: Municipality instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._municipalities.append(obj)

    def delete_municipality(self, obj: dev.Municipality) -> None:
        """
        Add a Municipality object
        :param obj: Municipality instance
        """

        for elm in self._substations:
            if elm.municipality == obj:
                elm.municipality = None

        self._municipalities.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Contingency
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def contingencies(self) -> List[dev.Contingency]:
        """
        Get list of contingencies
        :return:
        """
        return self._contingencies

    @contingencies.setter
    def contingencies(self, value: List[dev.Contingency]):
        self._contingencies = value

    def get_contingency_number(self) -> int:
        """
        Get number of contingencies
        :return:
        """
        return len(self._contingencies)

    def add_contingency(self, obj: dev.Contingency):
        """
        Add a contingency
        :param obj: Contingency
        """
        self._contingencies.append(obj)

    def delete_contingency(self, obj):
        """
        Delete zone
        :param obj: index
        """
        self._contingencies.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Continegency group
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def contingency_groups(self) -> List[dev.ContingencyGroup]:
        """
        Get list of contingency groups
        :return:
        """
        return self._contingency_groups

    @contingency_groups.setter
    def contingency_groups(self, value: List[dev.ContingencyGroup]):
        self._contingency_groups = value

    def get_contingency_groups(self) -> List[dev.ContingencyGroup]:
        """
        Get contingency_groups
        :return:List[dev.ContingencyGroup]
        """
        return self._contingency_groups

    def add_contingency_group(self, obj: dev.ContingencyGroup):
        """
        Add contingency group
        :param obj: ContingencyGroup
        """
        self._contingency_groups.append(obj)

    def delete_contingency_group(self, obj: dev.ContingencyGroup):
        """
        Delete contingency group
        :param obj: ContingencyGroup
        """
        self._contingency_groups.remove(obj)

        to_del = [con for con in self._contingencies if con.group == obj]
        for con in to_del:
            self.delete_contingency(con)

    def get_contingency_group_names(self) -> List[str]:
        """
        Get list of contingency group names
        :return:
        """
        return [e.name for e in self._contingency_groups]

    def get_contingency_group_dict(self) -> Dict[str, List[dev.Contingency]]:
        """
        Get a dictionary of group idtags related to list of contingencies
        :return:
        """
        d = dict()

        for cnt in self._contingencies:
            if cnt.group.idtag not in d:
                d[cnt.group.idtag] = [cnt]
            else:
                d[cnt.group.idtag].append(cnt)

        return d

    def set_contingencies(self, contingencies: List[dev.Contingency]):
        """
        Set contingencies and contingency groups to circuit
        :param contingencies: List of contingencies
        :return:
        """
        devices = self.get_contingency_devices()
        groups = dict()

        devices_code_dict = {d.code: d for d in devices}
        devices_key_dict = {d.idtag: d for d in devices}
        devices_dict = {**devices_code_dict, **devices_key_dict}

        logger = Logger()

        for contingency in contingencies:
            if contingency.code in devices_dict.keys() or contingency.idtag in devices_dict.keys():
                # ensure proper device_idtag and code
                element = devices_dict[contingency.code]
                contingency.device_idtag = element.idtag
                contingency.code = element.code

                self._contingencies.append(contingency)

                if contingency.group.idtag not in groups.keys():
                    groups[contingency.group.idtag] = contingency.group
            else:
                logger.add_info(
                    msg='Contingency element not found in circuit',
                    device=contingency.code,
                )

        for group in groups.values():
            self._contingency_groups.append(group)

        return logger

    def get_contingency_groups_in(self,
                                  grouping_elements: List[Union[dev.Area, dev.Country, dev.Zone]]
                                  ) -> List[dev.ContingencyGroup]:
        """
        Get a filtered set of ContingencyGroups
        :param grouping_elements: list of zones, areas or countries where to locate the contingencies
        :return: Sorted group filtered ContingencyGroup elements
        """

        # declare the reults
        filtered_groups_idx: Set[int] = set()

        group2index = {g: i for i, g in enumerate(self._contingency_groups)}

        # get a dictionary of all objects
        all_devices = self.get_all_elements_dict()

        # get the buses that match the filtering
        buses = self.get_buses_by(filter_elements=grouping_elements)

        for contingency in self._contingencies:

            group_idx = group2index[contingency.group]

            if group_idx not in filtered_groups_idx:

                # get the contingency device
                contingency_device = all_devices.get(contingency.device_idtag, None)

                if contingency_device is not None:

                    if hasattr(contingency_device, "bus_from"):
                        # it is likely a branch
                        if contingency_device.bus_from in buses or contingency_device.bus_to in buses:
                            filtered_groups_idx.add(group_idx)

                    elif hasattr(contingency_device, "bus"):
                        # it is likely an injection
                        if contingency_device.bus in buses:
                            filtered_groups_idx.add(group_idx)

        return [self._contingency_groups[i] for i in sorted(filtered_groups_idx)]

    # ------------------------------------------------------------------------------------------------------------------
    # Investment
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def investments(self) -> List[dev.Investment]:
        """

        :return:
        """
        return self._investments

    @investments.setter
    def investments(self, value: List[dev.Investment]):
        self._investments = value

    def add_investment(self, obj: dev.Investment):
        """
        Add investment
        :param obj: Investment
        """
        self._investments.append(obj)

    def delete_investment(self, obj: dev.Investment):
        """
        Delete zone
        :param obj: index
        """
        self._investments.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Investment group
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def investments_groups(self) -> List[dev.InvestmentsGroup]:
        """

        :return:
        """
        return self._investments_groups

    @investments_groups.setter
    def investments_groups(self, value: List[dev.InvestmentsGroup]):
        self._investments_groups = value

    def get_investment_groups_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([e.name for e in self._investments_groups])

    def add_investments_group(self, obj: dev.InvestmentsGroup):
        """
        Add investments group
        :param obj: InvestmentsGroup
        """
        self._investments_groups.append(obj)

    def delete_investment_groups(self, obj: dev.InvestmentsGroup):
        """
        Delete zone
        :param obj: index
        """
        self._investments_groups.remove(obj)

        to_del = [invst for invst in self._investments if invst.group == obj]
        for invst in to_del:
            self.delete_investment(invst)

    def get_investmenst_by_groups(self) -> List[Tuple[dev.InvestmentsGroup, List[dev.Investment]]]:
        """
        Get a dictionary of investments goups and their
        :return: list of investment groups and their list of associated investments
        """
        d = {e: list() for e in self._investments_groups}

        for inv in self._investments:
            inv_list = d.get(inv.group, None)

            if inv_list is not None:
                inv_list.append(inv)

        # second pass, sort it
        res = list()
        for inv_group in self._investments_groups:

            inv_list = d.get(inv_group, None)

            if inv_list is not None:
                res.append((inv_group, inv_list))
            else:
                res.append((inv_group, list()))

        return res

    def get_investmenst_by_groups_index_dict(self) -> Dict[int, List[dev.Investment]]:
        """
        Get a dictionary of investments goups and their
        :return: Dict[investment group index] = list of investments
        """
        d = {e: idx for idx, e in enumerate(self._investments_groups)}

        res = dict()
        for inv in self._investments:
            inv_group_idx = d.get(inv.group, None)
            inv_list = res.get(inv_group_idx, None)
            if inv_list is None:
                res[inv_group_idx] = [inv]
            else:
                inv_list.append(inv)

        return res

    # ------------------------------------------------------------------------------------------------------------------
    # Technology
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def technologies(self) -> List[dev.Technology]:
        """
        Get list of technologies
        :return:
        """
        return self._technologies

    @technologies.setter
    def technologies(self, value: List[dev.Technology]):
        self._technologies = value

    def add_technology(self, obj: dev.Technology):
        """
        Add technology
        :param obj: Technology
        """
        self._technologies.append(obj)

    def delete_technology(self, obj):
        """
        Delete zone
        :param obj: index
        """

        for elm_list in self.get_injection_devices_lists():
            for elm in elm_list:
                to_del = list()
                for assoc in elm.technologies:
                    if assoc.api_object == obj:
                        to_del.append(assoc)

                for assoc in to_del:
                    elm.technologies.remove(assoc)

        self._technologies.remove(obj)

    def get_technology_indexing_dict(self) -> Dict[str, int]:
        """
        Get a dictionary that relates the fuel uuid's with their index
        :return: Dict[str, int]
        """
        index_dict: Dict[str, int] = dict()
        for k, elm in enumerate(self._technologies):
            index_dict[elm.idtag] = k  # associate the idtag to the index
        return index_dict

    # ------------------------------------------------------------------------------------------------------------------
    # Modelling authority
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def modelling_authorities(self) -> List[dev.ModellingAuthority]:
        """

        :return:
        """
        return self._modelling_authorities

    @modelling_authorities.setter
    def modelling_authorities(self, value: List[dev.ModellingAuthority]):
        self._modelling_authorities = value

    def get_modelling_authorities(self) -> List[dev.ModellingAuthority]:
        """
        List of modelling_authorities
        :return: List[dev.ModellingAuthority]
        """
        return self._modelling_authorities

    def get_modelling_authorities_number(self) -> int:
        """
        Size of the list of modelling_authorities
        :return: size of modelling_authorities
        """
        return len(self._modelling_authorities)

    def get_modelling_authority_at(self, i: int) -> dev.ModellingAuthority:
        """
        Get modelling_authority at i
        :param i: index
        :return: ModellingAuthority
        """
        return self._modelling_authorities[i]

    def get_modelling_authority_names(self) -> StrVec:
        """
        Array of modelling_authority names
        :return: StrVec
        """
        return np.array([e.name for e in self._modelling_authorities])

    def add_modelling_authority(self, obj: dev.ModellingAuthority):
        """
        Add a ModellingAuthority object
        :param obj: ModellingAuthority instance
        """

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)
        self._modelling_authorities.append(obj)

    def delete_modelling_authority(self, obj: dev.ModellingAuthority) -> None:
        """
        Add a ModellingAuthority object
        :param obj: ModellingAuthority instance
        """

        self._modelling_authorities.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Fuels
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def fuels(self) -> List[dev.Fuel]:
        """
        Get list of fuels
        :return:
        """
        return self._fuels

    @fuels.setter
    def fuels(self, value: List[dev.Fuel]):
        self._fuels = value

    def get_fuels(self) -> List[dev.Fuel]:
        """

        :return:
        """
        return self._fuels

    def get_fuel_number(self) -> int:
        """

        :return:
        """
        return len(self._fuels)

    def get_fuel_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([elm.name for elm in self._fuels])

    def add_fuel(self, obj: dev.Fuel):
        """
        Add Fuel
        :param obj: Fuel object
        """
        self._fuels.append(obj)

    def delete_fuel(self, obj):
        """
        Delete Fuel
        :param obj: index
        """

        for elm_list in [self._generators]:
            for elm in elm_list:
                to_del = list()
                for assoc in elm.fuels:
                    if assoc.api_object == obj:
                        to_del.append(assoc)

                for assoc in to_del:
                    elm.fuels.remove(assoc)

        self._fuels.remove(obj)

    def get_fuel_indexing_dict(self) -> Dict[str, int]:
        """
        Get a dictionary that relates the fuel uuid's with their index
        :return: Dict[str, int]
        """
        index_dict: Dict[str, int] = dict()
        for k, elm in enumerate(self.get_fuels()):
            index_dict[elm.idtag] = k  # associate the idtag to the index
        return index_dict

    # ------------------------------------------------------------------------------------------------------------------
    # Emission gasses
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def emission_gases(self) -> List[dev.EmissionGas]:
        """
        Get list of emission gases
        :return:
        """
        return self._emission_gases

    @emission_gases.setter
    def emission_gases(self, value: List[dev.EmissionGas]):
        self._emission_gases = value

    def get_emissions(self) -> List[dev.EmissionGas]:
        """

        :return:
        """
        return self._emission_gases

    def get_emission_number(self) -> int:
        """

        :return:
        """
        return len(self._emission_gases)

    def get_emission_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([elm.name for elm in self._emission_gases])

    def add_emission_gas(self, obj: dev.EmissionGas):
        """
        Add EmissionGas
        :param obj: EmissionGas object
        """
        self._emission_gases.append(obj)

    def delete_emission_gas(self, obj: dev.EmissionGas):
        """
        Delete Substation
        :param obj: index
        """
        # store the associations
        for elm_list in [self._generators]:
            for elm in elm_list:
                to_del = list()
                for assoc in elm.emissions:
                    if assoc.api_object == obj:
                        to_del.append(assoc)

                for assoc in to_del:
                    elm.emissions.remove(assoc)

        # delete the gas
        self._emission_gases.remove(obj)

    def get_emissions_indexing_dict(self) -> Dict[str, int]:
        """
        Get a dictionary that relates the fuel uuid's with their index
        :return: Dict[str, int]
        """
        index_dict: Dict[str, int] = dict()
        for k, elm in enumerate(self.get_emissions()):
            index_dict[elm.idtag] = k  # associate the idtag to the index
        return index_dict

    # ------------------------------------------------------------------------------------------------------------------
    # Generator - Technology
    # ------------------------------------------------------------------------------------------------------------------

    # @property
    # def generators_technologies(self) -> List[dev.GeneratorTechnology]:
    #     """
    #     Get list of GeneratorTechnology association objects
    #     :return:
    #     """
    #     return self._generators_technologies
    #
    # @generators_technologies.setter
    # def generators_technologies(self, value: List[dev.GeneratorTechnology]):
    #     self._generators_technologies = value
    #
    # def add_generator_technology(self, obj: dev.GeneratorTechnology):
    #     """
    #     Add GeneratorTechnology
    #     :param obj: GeneratorTechnology object
    #     """
    #     self._generators_technologies.append(obj)
    #
    # def delete_generator_technology(self, obj: dev.GeneratorTechnology):
    #     """
    #     Delete GeneratorTechnology
    #     :param obj: GeneratorTechnology
    #     """
    #     # store the associations
    #     rels = list()
    #     for elm in self._generators_technologies:
    #         if elm.technology == obj:
    #             rels.append(elm)
    #
    #     # delete the associations
    #     for elm in rels:
    #         self.delete_generator_technology(elm)
    #
    #     # delete the technology
    #     self._generators_technologies.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Generotor - Fuels
    # ------------------------------------------------------------------------------------------------------------------

    # @property
    # def generators_fuels(self) -> List[dev.GeneratorFuel]:
    #     """
    #     Get list of Generator fuels associations
    #     :return:
    #     """
    #     return self._generators_fuels
    #
    # @generators_fuels.setter
    # def generators_fuels(self, value: List[dev.GeneratorFuel]):
    #     self._generators_fuels = value
    #
    # def add_generator_fuel(self, obj: dev.GeneratorFuel):
    #     """
    #     Add GeneratorFuel
    #     :param obj: GeneratorFuel object
    #     """
    #     self._generators_fuels.append(obj)
    #
    # def delete_generator_fuel(self, obj: dev.GeneratorFuel):
    #     """
    #     Delete GeneratorFuel
    #     :param obj: GeneratorFuel
    #     """
    #     # store the associations
    #     rels = list()
    #     for elm in self._generators_fuels:
    #         if elm.fuel == obj:
    #             rels.append(elm)
    #
    #     # delete the assciations
    #     for elm in rels:
    #         self.delete_generator_fuel(elm)
    #
    #     # delete the fuel
    #     self._generators_fuels.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Generator - Emissions
    # ------------------------------------------------------------------------------------------------------------------

    # @property
    # def generators_emissions(self) -> List[dev.GeneratorEmission]:
    #     """
    #     Get list of generator associations
    #     :return:
    #     """
    #     return self._generators_emissions
    #
    # @generators_emissions.setter
    # def generators_emissions(self, value: List[dev.GeneratorEmission]):
    #     self._generators_emissions = value
    #
    # def add_generator_emission(self, obj: dev.GeneratorEmission):
    #     """
    #     Add GeneratorFuel
    #     :param obj: GeneratorFuel object
    #     """
    #     self._generators_emissions.append(obj)
    #
    # def delete_generator_emission(self, obj: dev.GeneratorEmission):
    #     """
    #     Delete GeneratorFuel
    #     :param obj: GeneratorFuel
    #     """
    #     self._generators_emissions.remove(obj)

    # ------------------------------------------------------------------------------------------------------------------
    # Fluid nodes
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def fluid_nodes(self) -> List[dev.FluidNode]:
        """
        Get list of the fluid nodes
        :return:
        """
        return self._fluid_nodes

    @fluid_nodes.setter
    def fluid_nodes(self, value: List[dev.FluidNode]):
        self._fluid_nodes = value

    def add_fluid_node(self, obj: dev.FluidNode):
        """
        Add fluid node
        :param obj: FluidNode
        """
        self._fluid_nodes.append(obj)

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)

    def delete_fluid_node(self, obj: dev.FluidNode):
        """
        Delete fluid node
        :param obj: FluidNode
        """
        # delete dependencies
        for fluid_path in reversed(self._fluid_paths):
            if fluid_path.source == obj or fluid_path.target == obj:
                self.delete_fluid_path(fluid_path)

        self._fluid_nodes.remove(obj)

    def get_fluid_nodes(self) -> List[dev.FluidNode]:
        """

        :return:
        """
        return self._fluid_nodes

    def get_fluid_nodes_number(self) -> int:
        """

        :return:
        """
        return len(self._fluid_nodes)

    def get_fluid_node_names(self) -> StrVec:
        """
        List of fluid node names
        :return:
        """
        return np.array([e.name for e in self._fluid_nodes])

    # ------------------------------------------------------------------------------------------------------------------
    # Fluid paths
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def fluid_paths(self) -> List[dev.FluidPath]:
        """
        Get list of fluid path devices
        :return:
        """
        return self._fluid_paths

    @fluid_paths.setter
    def fluid_paths(self, value: List[dev.FluidPath]):
        self._fluid_paths = value

    def add_fluid_path(self, obj: dev.FluidPath):
        """
        Add fluid path
        :param obj:FluidPath
        """
        self._fluid_paths.append(obj)

        if self.time_profile is not None:
            obj.create_profiles(self.time_profile)

    def delete_fluid_path(self, obj: dev.FluidPath):
        """
        Delete fuid path
        :param obj: FluidPath
        """
        self._fluid_paths.remove(obj)

    def get_fluid_paths(self) -> List[dev.FluidPath]:
        """

        :return:
        """
        return self._fluid_paths

    def get_fluid_path_names(self) -> StrVec:
        """
        List of fluid paths names
        :return:
        """
        return np.array([e.name for e in self._fluid_paths])

    def get_fluid_paths_number(self) -> int:
        """

        :return:
        """
        return len(self._fluid_paths)

    # ------------------------------------------------------------------------------------------------------------------
    # turbines
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def turbines(self) -> List[dev.FluidTurbine]:
        """
        Get list of fluid turbines
        :return:
        """
        return self._turbines

    @turbines.setter
    def turbines(self, value: List[dev.FluidTurbine]):
        self._turbines = value

    def add_fluid_turbine(self,
                          node: Union[None, dev.FluidNode] = None,
                          api_obj: Union[dev.FluidTurbine, None] = None) -> dev.FluidTurbine:
        """
        Add fluid turbine
        :param node: Fluid node to add to
        :param api_obj: FluidTurbine
        """

        if api_obj is None:
            api_obj = dev.FluidTurbine()
        api_obj.plant = node

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        self._turbines.append(api_obj)

        return api_obj

    def delete_fluid_turbine(self, obj: dev.FluidTurbine):
        """
        Delete fuid turbine
        :param obj: FluidTurbine
        """
        self._turbines.remove(obj)

    def get_fluid_turbines(self) -> List[dev.FluidTurbine]:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        return self._turbines.copy()

    def get_fluid_turbines_number(self) -> int:
        """
        :return: number of total turbines in the network
        """
        return len(self._turbines)

    def get_fluid_turbines_names(self) -> StrVec:
        """
        Returns a list of :ref:`Turbine<turbine>` names.
        """
        return np.array([elm.name for elm in self._turbines])

    # ------------------------------------------------------------------------------------------------------------------
    # Pumps
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def pumps(self) -> List[dev.FluidPump]:
        """
        Get the list of fluid pumps
        :return:
        """
        return self._pumps

    @pumps.setter
    def pumps(self, value: List[dev.FluidPump]):
        self._pumps = value

    def add_fluid_pump(self,
                       node: Union[None, dev.FluidNode] = None,
                       api_obj: Union[dev.FluidPump, None] = None) -> dev.FluidPump:
        """
        Add fluid pump
        :param node: Fluid node to add to
        :param api_obj:FluidPump
        """
        if api_obj is None:
            api_obj = dev.FluidTurbine()
        api_obj.plant = node

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        self._pumps.append(api_obj)

        return api_obj

    def delete_fluid_pump(self, obj: dev.FluidPump):
        """
        Delete fuid pump
        :param obj: FluidPump
        """
        self._pumps.remove(obj)

    def get_fluid_pumps(self) -> List[dev.FluidPump]:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        return self._pumps

    def get_fluid_pumps_number(self) -> int:
        """
        :return: number of total pumps in the network
        """
        return len(self._pumps)

    def get_fluid_pumps_names(self) -> StrVec:
        """
        Returns a list of :ref:`Pump<pump>` names.
        """
        return np.array([elm.name for elm in self._pumps])

    # ------------------------------------------------------------------------------------------------------------------
    # Power-to-X
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def p2xs(self) -> List[dev.FluidP2x]:
        """
        Get list of power-to-x devices
        :return:
        """
        return self._p2xs

    @p2xs.setter
    def p2xs(self, value: List[dev.FluidP2x]):
        self._p2xs = value

    def add_fluid_p2x(self,
                      node: Union[None, dev.FluidNode] = None,
                      api_obj: Union[dev.FluidP2x, None] = None) -> dev.FluidP2x:
        """
        Add power to x
        :param node: Fluid node to add to
        :param api_obj:FluidP2x
        """
        if api_obj is None:
            api_obj = dev.FluidTurbine()
        api_obj.plant = node

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        self._p2xs.append(api_obj)

        return api_obj

    def delete_fluid_p2x(self, obj: dev.FluidP2x):
        """
        Delete fuid pump
        :param obj: FluidP2x
        """
        self._p2xs.remove(obj)

    def get_fluid_p2xs(self) -> List[dev.FluidP2x]:
        """
        Returns a list of :ref:`Load<load>` objects in the grid.
        """
        return self._p2xs

    def get_fluid_p2xs_number(self) -> int:
        """
        :return: number of total pumps in the network
        """
        return len(self._p2xs)

    def get_fluid_p2xs_names(self) -> StrVec:
        """
        Returns a list of :ref:`P2X<P2X>` names.
        """
        return np.array([elm.name for elm in self._p2xs])

    # ------------------------------------------------------------------------------------------------------------------
    # Diagrams
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def diagrams(self) -> List[Union[dev.MapDiagram, dev.SchematicDiagram]]:
        """
        Get the list of diagrams
        :return:
        """
        return self._diagrams

    @diagrams.setter
    def diagrams(self, value: List[Union[dev.MapDiagram, dev.SchematicDiagram]]):
        self._diagrams = value

    def get_diagrams(self) -> List[Union[dev.MapDiagram, dev.SchematicDiagram]]:
        """
        Get list of diagrams
        :return: MapDiagram, SchematicDiagram device
        """
        return self.diagrams

    def has_diagrams(self) -> bool:
        """
        Check if there are diagrams stored
        :return:
        """
        return len(self.diagrams) > 0

    def add_diagram(self, diagram: Union[dev.MapDiagram, dev.SchematicDiagram]):
        """
        Add diagram
        :param diagram: MapDiagram, SchematicDiagram device
        :return:
        """
        self.diagrams.append(diagram)

    def remove_diagram(self, diagram: Union[dev.MapDiagram, dev.SchematicDiagram]):
        """
        Remove diagrams
        :param diagram: MapDiagram, SchematicDiagram device
        """
        self.diagrams.remove(diagram)

    # ------------------------------------------------------------------------------------------------------------------
    #
    #
    # Functions of aggregations of devices
    #
    #
    # ------------------------------------------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------------------------------------------
    # Branch
    # ------------------------------------------------------------------------------------------------------------------
    def add_branch(self, obj: Union[BRANCH_TYPES, dev.Branch]) -> None:
        """
        Add any branch object (it's type will be infered here)
        :param obj: any class inheriting from ParentBranch
        """

        if obj.device_type == DeviceType.LineDevice:
            self.add_line(obj)

        elif obj.device_type == DeviceType.DCLineDevice:
            self.add_dc_line(obj)

        elif obj.device_type == DeviceType.Transformer2WDevice:
            self.add_transformer2w(obj)

        elif obj.device_type == DeviceType.HVDCLineDevice:
            self.add_hvdc(obj)

        elif obj.device_type == DeviceType.VscDevice:
            self.add_vsc(obj)

        elif obj.device_type == DeviceType.UpfcDevice:
            self.add_upfc(obj)

        elif obj.device_type == DeviceType.WindingDevice:
            self.add_winding(obj)

        elif obj.device_type == DeviceType.SwitchDevice:
            self.add_switch(obj)

        elif obj.device_type == DeviceType.BranchDevice:

            if obj.should_this_be_a_transformer():
                self.add_transformer2w(obj.get_equivalent_transformer())
            else:
                self.add_line(obj.get_equivalent_line())
        else:
            raise Exception(f'Unrecognized branch type {obj.device_type.value}')

    def delete_branch(self, obj: BRANCH_TYPES):
        """
        Delete a :ref:`Branch<branch>` object from the grid.

        Arguments:

            **obj** (:ref:`Branch<branch>`): :ref:`Branch<branch>` object
        """
        for branch_list in self.get_branch_lists():
            try:
                branch_list.remove(obj)
            except ValueError:  # element not found ...
                pass

    def get_branches_wo_hvdc(self) -> list[BRANCH_TYPES]:
        """
        Return all the branch objects.
        :return: lines + transformers 2w + hvdc
        """
        lst = list()
        for dev_list in self.get_branch_lists_wo_hvdc():
            lst += dev_list
        return lst

    def get_branches_wo_hvdc_names(self) -> List[str]:
        """
        Get the non HVDC branches' names
        :return: list of names
        """
        return [e.name for e in self.get_branches_wo_hvdc()]

    def get_branches(self) -> List[BRANCH_TYPES]:
        """
        Return all the branch objects
        :return: lines + transformers 2w + hvdc
        """
        return self.get_branches_wo_hvdc() + self._hvdc_lines

    def get_branches_wo_hvdc_index_dict(self) -> Dict[BRANCH_TYPES, int]:
        """
        Get the branch to index dictionary
        :return:
        """
        return {b: i for i, b in enumerate(self.get_branches_wo_hvdc())}

    def get_branch_lists_wo_hvdc(self) -> List[List[BRANCH_TYPES]]:
        """
        Get list of the branch lists
        :return: List[List[BRANCH_TYPES]]
        """

        # This order must be respected durng the compilation

        return [
            self._lines,
            self._dc_lines,
            self._transformers2w,
            self._windings,
            self._vsc_devices,
            self._upfc_devices,
            self._series_reactances
        ]

    def get_branch_names_wo_hvdc(self) -> StrVec:
        """
        Get all branch names without HVDC devices
        :return: StrVec
        """
        names = list()
        for lst in self.get_branch_lists_wo_hvdc():
            for elm in lst:
                names.append(elm.name)
        return np.array(names)

    def get_branch_lists(self) -> List[List[BRANCH_TYPES]]:
        """
        Get list of the branch lists
        :return: list of lists
        """
        lst = self.get_branch_lists_wo_hvdc()
        lst.append(self._hvdc_lines)
        return lst

    def get_branch_number(self) -> int:
        """
        return the number of Branches (of all types)
        :return: number
        """
        m = 0
        for branch_list in self.get_branch_lists():
            m += len(branch_list)
        return m

    def get_branch_names(self) -> StrVec:
        """
        Get array of all branch names
        :return: StrVec
        """

        names = list()
        for lst in self.get_branch_lists():
            for elm in lst:
                names.append(elm.name)
        return np.array(names)

    def get_branch_number_wo_hvdc(self) -> int:
        """
        return the number of Branches (of all types)
        :return: number
        """
        count = 0
        for branch_list in self.get_branch_lists_wo_hvdc():
            count += len(branch_list)
        return count

    def get_branches_wo_hvdc_dict(self) -> Dict[str, int]:
        """
        Get dictionary of branches (excluding HVDC)
        the key is the idtag, the value is the branch position
        :return: Dict[str, int]
        """
        return {e.idtag: ei for ei, e in enumerate(self.get_branches_wo_hvdc())}

    def get_branch_number_wo_hvdc_FT(self) -> Tuple[IntVec, IntVec]:
        """
        get the from and to arrays of indices
        :return: IntVec, IntVec
        """
        devices = self.get_branches_wo_hvdc()
        m = len(devices)
        F = np.zeros(m, dtype=int)
        T = np.zeros(m, dtype=int)
        bus_dict = self.get_bus_index_dict()
        for i, elm in enumerate(devices):
            F[i] = bus_dict[elm.bus_from]
            T[i] = bus_dict[elm.bus_to]
        return F, T

    def get_hvdc_FT(self) -> Tuple[IntVec, IntVec]:
        """
        get the from and to arrays of indices of HVDC lines
        :return: IntVec, IntVec
        """
        m = len(self._hvdc_lines)
        F = np.zeros(m, dtype=int)
        T = np.zeros(m, dtype=int)
        bus_dict = self.get_bus_index_dict()
        for i, elm in enumerate(self._hvdc_lines):
            F[i] = bus_dict[elm.bus_from]
            T[i] = bus_dict[elm.bus_to]
        return F, T

    # ------------------------------------------------------------------------------------------------------------------
    # Injections
    # ------------------------------------------------------------------------------------------------------------------

    def delete_injection_device(self, obj: INJECTION_DEVICE_TYPES):
        """
        Delete a :ref:`Branch<branch>` object from the grid.

        Arguments:

            **obj** (:ref:`Branch<branch>`): :ref:`Branch<branch>` object
        """
        for inj_list in self.get_injection_devices_lists():
            try:
                inj_list.remove(obj)
            except ValueError:  # element not found ...
                pass

    def get_injection_devices_lists(self) -> List[List[INJECTION_DEVICE_TYPES]]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        return [self.get_generators(),
                self.get_batteries(),
                self.get_loads(),
                self.get_external_grids(),
                self.get_static_generators(),
                self.get_shunts(),
                self.get_controllable_shunts(),
                self.get_current_injections()]

    def get_injection_devices(self) -> List[INJECTION_DEVICE_TYPES]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """

        elms = list()
        for lst in self.get_injection_devices_lists():
            elms += lst
        return elms

    # ------------------------------------------------------------------------------------------------------------------
    # Load-like devices
    # ------------------------------------------------------------------------------------------------------------------
    def get_load_like_devices_lists(self) -> List[List[INJECTION_DEVICE_TYPES]]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        return [self.loads,
                self.static_generators,
                self.external_grids,
                self.current_injections]

    def get_load_like_devices(self) -> List[INJECTION_DEVICE_TYPES]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        elms = list()
        for lst in self.get_load_like_devices_lists():
            elms += lst
        return elms

    def get_load_like_device_number(self) -> int:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        n = 0
        for lst in self.get_load_like_devices_lists():
            n += len(lst)

        return n

    # ------------------------------------------------------------------------------------------------------------------
    # Shunt-like devices
    # ------------------------------------------------------------------------------------------------------------------
    def get_shunt_like_devices_lists(self) -> List[List[INJECTION_DEVICE_TYPES]]:
        """
        Get a list of all devices that behave like a shunt
        :return: List of Lists of Shunt devices
        """
        return [self.shunts,
                self.controllable_shunts]

    def get_shunt_like_devices(self) -> List[INJECTION_DEVICE_TYPES]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of Shunt devices
        """
        elms = list()
        for lst in self.get_shunt_like_devices_lists():
            elms += lst
        return elms

    def get_shunt_like_device_number(self) -> int:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        n = 0
        for lst in self.get_shunt_like_devices_lists():
            n += len(lst)

        return n

    # ------------------------------------------------------------------------------------------------------------------
    # Generation like devices
    # ------------------------------------------------------------------------------------------------------------------
    def get_generation_like_lists(self) -> List[List[INJECTION_DEVICE_TYPES]]:
        """
        Get a list with the fluid injections lists
        :return:
        """
        return [self._generators, self._batteries]

    def get_generation_like_number(self) -> int:
        """
        Get number of fluid injections
        :return: int
        """
        count = 0
        for lst in self.get_generation_like_lists():
            count += len(lst)
        return count

    def get_generation_like_names(self) -> StrVec:
        """
        Returns a list of :ref:`Injection<Injection>` names.
        Sort by order: turbines, pumps, p2xs
        """
        names = list()
        for lst in self.get_generation_like_lists():
            for elm in lst:
                names.append(elm.name)
        return np.array(names)

    def get_generation_like_devices(self) -> List[INJECTION_DEVICE_TYPES]:
        """
        Returns a list of :ref:`Injection<Injection>` names.
        Sort by order: turbines, pumps, p2xs
        """
        elms = list()
        for lst in self.get_generation_like_lists():
            elms += lst
        return elms

    # ------------------------------------------------------------------------------------------------------------------
    # Fluid injections
    # ------------------------------------------------------------------------------------------------------------------
    def get_fluid_injection_lists(self) -> List[List[FLUID_TYPES]]:
        """
        Get a list with the fluid injections lists
        :return:
        """
        return [self._turbines, self._pumps, self._p2xs]

    def get_fluid_injection_number(self) -> int:
        """
        Get number of fluid injections
        :return: int
        """
        count = 0
        for lst in self.get_fluid_injection_lists():
            count += len(lst)
        return count

    def get_fluid_injection_names(self) -> StrVec:
        """
        Returns a list of :ref:`Injection<Injection>` names.
        Sort by order: turbines, pumps, p2xs
        """
        names = list()
        for lst in self.get_fluid_injection_lists():
            for elm in lst:
                names.append(elm.name)
        return np.array(names)

    def get_fluid_injections(self) -> List[FLUID_TYPES]:
        """
        Returns a list of :ref:`Injection<Injection>` names.
        Sort by order: turbines, pumps, p2xs
        """
        elms = list()
        for lst in self.get_fluid_injection_lists():
            elms += lst
        return elms

    # ------------------------------------------------------------------------------------------------------------------
    # Contingency devices
    # ------------------------------------------------------------------------------------------------------------------

    def get_contingency_devices(self) -> List[ALL_DEV_TYPES]:
        """
        Get a list of devices susceptible to be included in contingencies
        :return: list of devices
        """
        return self.get_branches() + self.get_injection_devices()

    # ------------------------------------------------------------------------------------------------------------------
    #
    #
    # General functions of the class
    #
    #
    # ------------------------------------------------------------------------------------------------------------------

    def get_elements_by_type(self, device_type: DeviceType) -> Union[pd.DatetimeIndex, List[ALL_DEV_TYPES]]:
        """
        Get set of elements and their parent nodes
        :param device_type: DeviceTYpe instance
        :return: List of elements, it raises an exception if the elements are unknown
        """

        if device_type == DeviceType.LoadDevice:
            return self.get_loads()

        elif device_type == DeviceType.StaticGeneratorDevice:
            return self.get_static_generators()

        elif device_type == DeviceType.GeneratorDevice:
            return self.get_generators()

        elif device_type == DeviceType.BatteryDevice:
            return self.get_batteries()

        elif device_type == DeviceType.ShuntDevice:
            return self.get_shunts()

        elif device_type == DeviceType.ExternalGridDevice:
            return self.get_external_grids()

        elif device_type == DeviceType.CurrentInjectionDevice:
            return self.get_current_injections()

        elif device_type == DeviceType.ControllableShuntDevice:
            return self.get_controllable_shunts()

        elif device_type == DeviceType.LineDevice:
            return self._lines

        elif device_type == DeviceType.LineLocation:
            locations = list()
            branches_w_locations = [self._lines, self._dc_lines, self._hvdc_lines, self._fluid_paths]
            for lst in branches_w_locations:
                for line in lst:
                    locations += line.locations.data
            return locations

        elif device_type == DeviceType.Transformer2WDevice:
            return self._transformers2w

        elif device_type == DeviceType.Transformer3WDevice:
            return self._transformers3w

        elif device_type == DeviceType.WindingDevice:
            return self._windings

        elif device_type == DeviceType.SeriesReactanceDevice:
            return self._series_reactances

        elif device_type == DeviceType.HVDCLineDevice:
            return self._hvdc_lines

        elif device_type == DeviceType.UpfcDevice:
            return self._upfc_devices

        elif device_type == DeviceType.VscDevice:
            return self._vsc_devices

        elif device_type == DeviceType.BranchGroupDevice:
            return self._branch_groups

        elif device_type == DeviceType.BusDevice:
            return self._buses

        elif device_type == DeviceType.OverheadLineTypeDevice:
            return self._overhead_line_types

        elif device_type == DeviceType.TransformerTypeDevice:
            return self._transformer_types

        elif device_type == DeviceType.UnderGroundLineDevice:
            return self._underground_cable_types

        elif device_type == DeviceType.SequenceLineDevice:
            return self._sequence_line_types

        elif device_type == DeviceType.WireDevice:
            return self._wire_types

        elif device_type == DeviceType.DCLineDevice:
            return self._dc_lines

        elif device_type == DeviceType.SwitchDevice:
            return self._switch_devices

        elif device_type == DeviceType.SubstationDevice:
            return self._substations

        elif device_type == DeviceType.VoltageLevelDevice:
            return self._voltage_levels

        elif device_type == DeviceType.ConnectivityNodeDevice:
            return self._connectivity_nodes

        elif device_type == DeviceType.BusBarDevice:
            return self._bus_bars

        elif device_type == DeviceType.AreaDevice:
            return self._areas

        elif device_type == DeviceType.ZoneDevice:
            return self._zones

        elif device_type == DeviceType.CountryDevice:
            return self._countries

        elif device_type == DeviceType.CommunityDevice:
            return self._communities

        elif device_type == DeviceType.RegionDevice:
            return self._regions

        elif device_type == DeviceType.MunicipalityDevice:
            return self._municipalities

        elif device_type == DeviceType.ContingencyDevice:
            return self._contingencies

        elif device_type == DeviceType.ContingencyGroupDevice:
            return self._contingency_groups

        elif device_type == DeviceType.Technology:
            return self._technologies

        elif device_type == DeviceType.InvestmentDevice:
            return self._investments

        elif device_type == DeviceType.InvestmentsGroupDevice:
            return self._investments_groups

        elif device_type == DeviceType.FuelDevice:
            return self._fuels

        elif device_type == DeviceType.EmissionGasDevice:
            return self._emission_gases

        # elif device_type == DeviceType.GeneratorTechnologyAssociation:
        #     return self._generators_technologies
        #
        # elif device_type == DeviceType.GeneratorFuelAssociation:
        #     return self._generators_fuels
        #
        # elif device_type == DeviceType.GeneratorEmissionAssociation:
        #     return self._generators_emissions

        elif device_type == DeviceType.ConnectivityNodeDevice:
            return self._connectivity_nodes

        elif device_type == DeviceType.FluidNodeDevice:
            return self._fluid_nodes

        elif device_type == DeviceType.FluidPathDevice:
            return self._fluid_paths

        elif device_type == DeviceType.FluidTurbineDevice:
            return self._turbines

        elif device_type == DeviceType.FluidPumpDevice:
            return self._pumps

        elif device_type == DeviceType.FluidP2XDevice:
            return self._p2xs

        elif device_type == DeviceType.PiMeasurementDevice:
            return self.get_pi_measurements()

        elif device_type == DeviceType.QiMeasurementDevice:
            return self.get_qi_measurements()

        elif device_type == DeviceType.PfMeasurementDevice:
            return self.get_pf_measurements()

        elif device_type == DeviceType.QfMeasurementDevice:
            return self.get_qf_measurements()

        elif device_type == DeviceType.VmMeasurementDevice:
            return self.get_vm_measurements()

        elif device_type == DeviceType.IfMeasurementDevice:
            return self.get_if_measurements()

        elif device_type == DeviceType.LoadLikeDevice:
            return self.get_load_like_devices()

        elif device_type == DeviceType.BranchDevice:
            return self.get_branches_wo_hvdc()

        elif device_type == DeviceType.NoDevice:
            return list()

        elif device_type == DeviceType.TimeDevice:
            return self.get_time_array()

        elif device_type == DeviceType.ModellingAuthority:
            return self.get_modelling_authorities()

        else:
            raise Exception('Element type not understood ' + str(device_type))

    def set_elements_list_by_type(self, device_type: DeviceType,
                                  devices: List[ALL_DEV_TYPES],
                                  logger: Logger = Logger()):
        """
        Set a list of elements all at once
        :param device_type: DeviceType
        :param devices: list of devices
        :param logger: Logger
        """
        if device_type == DeviceType.LoadDevice:
            self._loads = devices

        elif device_type == DeviceType.StaticGeneratorDevice:
            self._static_generators = devices

        elif device_type == DeviceType.GeneratorDevice:
            self._generators = devices

        elif device_type == DeviceType.BatteryDevice:
            self._batteries = devices

        elif device_type == DeviceType.ShuntDevice:
            self._shunts = devices

        elif device_type == DeviceType.ExternalGridDevice:
            self._external_grids = devices

        elif device_type == DeviceType.CurrentInjectionDevice:
            self._current_injections = devices

        elif device_type == DeviceType.ControllableShuntDevice:
            self._controllable_shunts = devices

        elif device_type == DeviceType.LineDevice:
            for d in devices:
                # this is done to detect those lines that should be transformers
                self.add_line(d, logger=logger)

        elif device_type == DeviceType.Transformer2WDevice:
            self._transformers2w = devices

        elif device_type == DeviceType.Transformer3WDevice:
            self._transformers3w = devices

        elif device_type == DeviceType.WindingDevice:
            self._windings = devices

        elif device_type == DeviceType.SeriesReactanceDevice:
            self._series_reactances = devices

        elif device_type == DeviceType.HVDCLineDevice:
            self._hvdc_lines = devices

        elif device_type == DeviceType.UpfcDevice:
            self._upfc_devices = devices

        elif device_type == DeviceType.VscDevice:
            for elm in devices:
                elm.correct_buses_connection()
            self._vsc_devices = devices

        elif device_type == DeviceType.BranchGroupDevice:
            self._branch_groups = devices

        elif device_type == DeviceType.BusDevice:
            self._buses = devices

        elif device_type == DeviceType.OverheadLineTypeDevice:
            self._overhead_line_types = devices

        elif device_type == DeviceType.TransformerTypeDevice:
            self._transformer_types = devices

        elif device_type == DeviceType.UnderGroundLineDevice:
            self._underground_cable_types = devices

        elif device_type == DeviceType.SequenceLineDevice:
            self._sequence_line_types = devices

        elif device_type == DeviceType.WireDevice:
            self._wire_types = devices

        elif device_type == DeviceType.DCLineDevice:
            self._dc_lines = devices

        elif device_type == DeviceType.SwitchDevice:
            self._switch_devices = devices

        elif device_type == DeviceType.SubstationDevice:
            self._substations = devices

        elif device_type == DeviceType.VoltageLevelDevice:
            self._voltage_levels = devices

        elif device_type == DeviceType.ConnectivityNodeDevice:
            self._connectivity_nodes = devices

        elif device_type == DeviceType.BusBarDevice:
            self._bus_bars = devices

        elif device_type == DeviceType.AreaDevice:
            self._areas = devices

        elif device_type == DeviceType.ZoneDevice:
            self._zones = devices

        elif device_type == DeviceType.CountryDevice:
            self._countries = devices

        elif device_type == DeviceType.CommunityDevice:
            self._communities = devices

        elif device_type == DeviceType.RegionDevice:
            self._regions = devices

        elif device_type == DeviceType.MunicipalityDevice:
            self._municipalities = devices

        elif device_type == DeviceType.ContingencyDevice:
            self._contingencies = devices

        elif device_type == DeviceType.ContingencyGroupDevice:
            self._contingency_groups = devices

        elif device_type == DeviceType.Technology:
            self._technologies = devices

        elif device_type == DeviceType.InvestmentDevice:
            self._investments = devices

        elif device_type == DeviceType.InvestmentsGroupDevice:
            self._investments_groups = devices

        elif device_type == DeviceType.FuelDevice:
            self._fuels = devices

        elif device_type == DeviceType.EmissionGasDevice:
            self._emission_gases = devices

        # elif device_type == DeviceType.GeneratorTechnologyAssociation:
        #     self._generators_technologies = devices
        #
        # elif device_type == DeviceType.GeneratorFuelAssociation:
        #     self._generators_fuels = devices
        #
        # elif device_type == DeviceType.GeneratorEmissionAssociation:
        #     self._generators_emissions = devices

        elif device_type == DeviceType.ConnectivityNodeDevice:
            self._connectivity_nodes = devices

        elif device_type == DeviceType.FluidNodeDevice:
            self._fluid_nodes = devices

        elif device_type == DeviceType.FluidPathDevice:
            self._fluid_paths = devices

        elif device_type == DeviceType.FluidTurbineDevice:
            self._turbines = devices

        elif device_type == DeviceType.FluidPumpDevice:
            self._pumps = devices

        elif device_type == DeviceType.FluidP2XDevice:
            self._p2xs = devices

        elif device_type == DeviceType.BranchDevice:
            for d in devices:
                self.add_branch(d)  # each branch needs to be converted accordingly

        elif device_type == DeviceType.PiMeasurementDevice:
            self._pi_measurements = devices

        elif device_type == DeviceType.QiMeasurementDevice:
            self._qi_measurements = devices

        elif device_type == DeviceType.PfMeasurementDevice:
            self._pf_measurements = devices

        elif device_type == DeviceType.QfMeasurementDevice:
            self._qf_measurements = devices

        elif device_type == DeviceType.VmMeasurementDevice:
            self._vm_measurements = devices

        elif device_type == DeviceType.IfMeasurementDevice:
            self._if_measurements = devices

        elif device_type == DeviceType.ModellingAuthority:
            self._modelling_authorities = devices

        else:
            raise Exception('Element type not understood ' + str(device_type))

    def add_element(self, obj: ALL_DEV_TYPES) -> None:
        """
        Add a device in its corresponding list
        :param obj: device object to add
        :return: Nothing
        """

        if obj.device_type == DeviceType.LoadDevice:
            self.add_load(api_obj=obj, bus=obj.bus, cn=obj.cn)

        elif obj.device_type == DeviceType.StaticGeneratorDevice:
            self.add_static_generator(api_obj=obj, bus=obj.bus, cn=obj.cn)

        elif obj.device_type == DeviceType.GeneratorDevice:
            self.add_generator(api_obj=obj, bus=obj.bus, cn=obj.cn)

        elif obj.device_type == DeviceType.BatteryDevice:
            self.add_battery(api_obj=obj, bus=obj.bus, cn=obj.cn)

        elif obj.device_type == DeviceType.ShuntDevice:
            self.add_shunt(api_obj=obj, bus=obj.bus, cn=obj.cn)

        elif obj.device_type == DeviceType.ExternalGridDevice:
            self.add_external_grid(api_obj=obj, bus=obj.bus, cn=obj.cn)

        elif obj.device_type == DeviceType.CurrentInjectionDevice:
            self.add_current_injection(api_obj=obj, bus=obj.bus, cn=obj.cn)

        elif obj.device_type == DeviceType.ControllableShuntDevice:
            self.add_controllable_shunt(api_obj=obj, bus=obj.bus, cn=obj.cn)

        elif obj.device_type == DeviceType.LineDevice:
            self.add_line(obj=obj)

        elif obj.device_type == DeviceType.Transformer2WDevice:
            self.add_transformer2w(obj=obj)

        elif obj.device_type == DeviceType.Transformer3WDevice:
            self.add_transformer3w(obj=obj)

        elif obj.device_type == DeviceType.WindingDevice:
            self.add_winding(obj=obj)

        elif obj.device_type == DeviceType.SeriesReactanceDevice:
            self.add_series_reactance(obj=obj)

        elif obj.device_type == DeviceType.HVDCLineDevice:
            self.add_hvdc(obj=obj)

        elif obj.device_type == DeviceType.UpfcDevice:
            self.add_upfc(obj=obj)

        elif obj.device_type == DeviceType.VscDevice:
            self.add_vsc(obj=obj)

        elif obj.device_type == DeviceType.BusDevice:
            self.add_bus(obj=obj)

        elif obj.device_type == DeviceType.ConnectivityNodeDevice:
            self.add_connectivity_node(obj=obj)

        elif obj.device_type == DeviceType.BranchGroupDevice:
            self.add_branch_group(obj=obj)

        elif obj.device_type == DeviceType.BusBarDevice:
            self.add_bus_bar(obj=obj)

        elif obj.device_type == DeviceType.OverheadLineTypeDevice:
            self.add_overhead_line(obj=obj)

        elif obj.device_type == DeviceType.TransformerTypeDevice:
            self.add_transformer_type(obj=obj)

        elif obj.device_type == DeviceType.UnderGroundLineDevice:
            self.add_underground_line(obj=obj)

        elif obj.device_type == DeviceType.SequenceLineDevice:
            self.add_sequence_line(obj=obj)

        elif obj.device_type == DeviceType.WireDevice:
            self.add_wire(obj=obj)

        elif obj.device_type == DeviceType.DCLineDevice:
            self.add_dc_line(obj=obj)

        elif obj.device_type == DeviceType.SubstationDevice:
            self.add_substation(obj=obj)

        elif obj.device_type == DeviceType.VoltageLevelDevice:
            self.add_voltage_level(obj=obj)

        elif obj.device_type == DeviceType.AreaDevice:
            self.add_area(obj=obj)

        elif obj.device_type == DeviceType.ZoneDevice:
            self.add_zone(obj=obj)

        elif obj.device_type == DeviceType.CountryDevice:
            self.add_country(obj=obj)

        elif obj.device_type == DeviceType.CommunityDevice:
            self.add_community(obj=obj)

        elif obj.device_type == DeviceType.RegionDevice:
            self.add_region(obj=obj)

        elif obj.device_type == DeviceType.MunicipalityDevice:
            self.add_municipality(obj=obj)

        elif obj.device_type == DeviceType.ContingencyDevice:
            self.add_contingency(obj=obj)

        elif obj.device_type == DeviceType.ContingencyGroupDevice:
            self.add_contingency_group(obj=obj)

        elif obj.device_type == DeviceType.Technology:
            self.add_technology(obj=obj)

        elif obj.device_type == DeviceType.InvestmentDevice:
            self.add_investment(obj=obj)

        elif obj.device_type == DeviceType.InvestmentsGroupDevice:
            self.add_investments_group(obj=obj)

        elif obj.device_type == DeviceType.FuelDevice:
            self.add_fuel(obj=obj)

        elif obj.device_type == DeviceType.EmissionGasDevice:
            self.add_emission_gas(obj=obj)

        # elif obj.device_type == DeviceType.GeneratorTechnologyAssociation:
        #     self.add_generator_technology(obj=obj)
        #
        # elif obj.device_type == DeviceType.GeneratorFuelAssociation:
        #     self.add_generator_fuel(obj=obj)
        #
        # elif obj.device_type == DeviceType.GeneratorEmissionAssociation:
        #     self.add_generator_emission(obj=obj)

        elif obj.device_type == DeviceType.FluidNodeDevice:
            self.add_fluid_node(obj=obj)

        elif obj.device_type == DeviceType.FluidTurbineDevice:
            self.add_fluid_turbine(api_obj=obj)

        elif obj.device_type == DeviceType.FluidP2XDevice:
            self.add_fluid_p2x(api_obj=obj)

        elif obj.device_type == DeviceType.FluidPumpDevice:
            self.add_fluid_pump(api_obj=obj)

        elif obj.device_type == DeviceType.FluidPathDevice:
            self.add_fluid_path(obj=obj)

        elif obj.device_type == DeviceType.PiMeasurementDevice:
            self.add_pi_measurement(obj=obj)

        elif obj.device_type == DeviceType.QiMeasurementDevice:
            self.add_qi_measurement(obj=obj)

        elif obj.device_type == DeviceType.PfMeasurementDevice:
            self.add_pf_measurement(obj=obj)

        elif obj.device_type == DeviceType.QfMeasurementDevice:
            self.add_qf_measurement(obj=obj)

        elif obj.device_type == DeviceType.VmMeasurementDevice:
            self.add_vm_measurement(obj=obj)

        elif obj.device_type == DeviceType.IfMeasurementDevice:
            self.add_if_measurement(obj=obj)

        elif obj.device_type == DeviceType.ModellingAuthority:
            self.add_modelling_authority(obj=obj)

        else:
            raise Exception('Element type not understood ' + str(obj.device_type))

    def delete_element(self, obj: ALL_DEV_TYPES) -> None:
        """
        Get set of elements and their parent nodes
        :param obj: device object to delete
        :return: Nothing
        """

        if obj.device_type == DeviceType.LoadDevice:
            self._loads.remove(obj)

        elif obj.device_type == DeviceType.StaticGeneratorDevice:
            self._static_generators.remove(obj)

        elif obj.device_type == DeviceType.GeneratorDevice:
            self._generators.remove(obj)

        elif obj.device_type == DeviceType.BatteryDevice:
            self._batteries.remove(obj)

        elif obj.device_type == DeviceType.ShuntDevice:
            self._shunts.remove(obj)

        elif obj.device_type == DeviceType.ExternalGridDevice:
            self._external_grids.remove(obj)

        elif obj.device_type == DeviceType.CurrentInjectionDevice:
            self._current_injections.remove(obj)

        elif obj.device_type == DeviceType.ControllableShuntDevice:
            self._controllable_shunts.remove(obj)

        elif obj.device_type == DeviceType.LineDevice:
            self.delete_line(obj)

        elif obj.device_type == DeviceType.Transformer2WDevice:
            self.delete_transformer2w(obj)

        elif obj.device_type == DeviceType.Transformer3WDevice:
            self.delete_transformer3w(obj)

        elif obj.device_type == DeviceType.WindingDevice:
            self.delete_winding(obj)

        elif obj.device_type == DeviceType.SeriesReactanceDevice:
            self.delete_series_reactance(obj)

        elif obj.device_type == DeviceType.HVDCLineDevice:
            self.delete_hvdc_line(obj)

        elif obj.device_type == DeviceType.UpfcDevice:
            self.delete_upfc_converter(obj)

        elif obj.device_type == DeviceType.VscDevice:
            self.delete_vsc_converter(obj)

        elif obj.device_type == DeviceType.BusDevice:
            self.delete_bus(obj, delete_associated=True)

        elif obj.device_type == DeviceType.ConnectivityNodeDevice:
            self.delete_connectivity_node(obj)

        elif obj.device_type == DeviceType.BranchGroupDevice:
            self.delete_branch_group(obj)

        elif obj.device_type == DeviceType.BusBarDevice:
            self.delete_bus_bar(obj)

        elif obj.device_type == DeviceType.OverheadLineTypeDevice:
            self.delete_overhead_line(obj)

        elif obj.device_type == DeviceType.TransformerTypeDevice:
            self.delete_transformer_type(obj)

        elif obj.device_type == DeviceType.UnderGroundLineDevice:
            self.delete_underground_line(obj)

        elif obj.device_type == DeviceType.SequenceLineDevice:
            self.delete_sequence_line(obj)

        elif obj.device_type == DeviceType.WireDevice:
            self.delete_wire(obj)

        elif obj.device_type == DeviceType.DCLineDevice:
            self.delete_dc_line(obj)

        elif obj.device_type == DeviceType.SubstationDevice:
            self.delete_substation(obj)

        elif obj.device_type == DeviceType.VoltageLevelDevice:
            self.delete_voltage_level(obj)

        elif obj.device_type == DeviceType.AreaDevice:
            self.delete_area(obj)

        elif obj.device_type == DeviceType.ZoneDevice:
            self.delete_zone(obj)

        elif obj.device_type == DeviceType.CountryDevice:
            self.delete_country(obj)

        elif obj.device_type == DeviceType.CommunityDevice:
            self.delete_community(obj)

        elif obj.device_type == DeviceType.RegionDevice:
            self.delete_region(obj)

        elif obj.device_type == DeviceType.MunicipalityDevice:
            self.delete_municipality(obj)

        elif obj.device_type == DeviceType.ContingencyDevice:
            self.delete_contingency(obj)

        elif obj.device_type == DeviceType.ContingencyGroupDevice:
            self.delete_contingency_group(obj)

        elif obj.device_type == DeviceType.Technology:
            self.delete_technology(obj)

        elif obj.device_type == DeviceType.InvestmentDevice:
            self.delete_investment(obj)

        elif obj.device_type == DeviceType.InvestmentsGroupDevice:
            self.delete_investment_groups(obj)

        elif obj.device_type == DeviceType.FuelDevice:
            self.delete_fuel(obj)

        elif obj.device_type == DeviceType.EmissionGasDevice:
            self.delete_emission_gas(obj)

        # elif obj.device_type == DeviceType.GeneratorTechnologyAssociation:
        #     self.delete_generator_technology(obj)
        #
        # elif obj.device_type == DeviceType.GeneratorFuelAssociation:
        #     self.delete_generator_fuel(obj)
        #
        # elif obj.device_type == DeviceType.GeneratorEmissionAssociation:
        #     self.delete_generator_emission(obj)

        elif obj.device_type == DeviceType.FluidNodeDevice:
            self.delete_fluid_node(obj)

        elif obj.device_type == DeviceType.FluidTurbineDevice:
            self.delete_fluid_turbine(obj)

        elif obj.device_type == DeviceType.FluidP2XDevice:
            self.delete_fluid_p2x(obj)

        elif obj.device_type == DeviceType.FluidPumpDevice:
            self.delete_fluid_pump(obj)

        elif obj.device_type == DeviceType.FluidPathDevice:
            self.delete_fluid_path(obj)

        elif obj.device_type == DeviceType.PiMeasurementDevice:
            self.delete_pi_measurement(obj)

        elif obj.device_type == DeviceType.QiMeasurementDevice:
            self.delete_qi_measurement(obj)

        elif obj.device_type == DeviceType.PfMeasurementDevice:
            self.delete_pf_measurement(obj)

        elif obj.device_type == DeviceType.QfMeasurementDevice:
            self.delete_qf_measurement(obj)

        elif obj.device_type == DeviceType.VmMeasurementDevice:
            self.delete_vm_measurement(obj)

        elif obj.device_type == DeviceType.IfMeasurementDevice:
            self.delete_if_measurement(obj)

        elif obj.device_type == DeviceType.ModellingAuthority:
            self.delete_modelling_authority(obj)

        else:
            raise Exception('Element type not understood ' + str(obj.device_type))

    def add_or_replace_object(self, api_obj: ALL_DEV_TYPES, logger: Logger) -> bool:
        """
        Add or replace an object based on the UUID
        :param api_obj: Any asset
        :param logger: Logger object
        :return: replaced?
        """

        object_type_list: List[ALL_DEV_TYPES] = self.get_elements_by_type(device_type=api_obj.device_type)

        found = False
        found_idx = -1
        for i, obj in enumerate(object_type_list):
            if obj.idtag == api_obj.idtag:
                found = True
                found_idx = i
                break

        if found:
            # replace
            object_type_list[found_idx] = api_obj

            logger.add_info("Element replaced",
                            device_class=api_obj.device_type.value,
                            device=api_obj.name)

        else:
            # add
            self.add_element(obj=api_obj)

            logger.add_info("Element added",
                            device_class=api_obj.device_type.value,
                            device=api_obj.name)

        return found

    def get_all_elements_dict(self) -> dict[str, ALL_DEV_TYPES]:
        """
        Get a dictionary of all elements
        :return: Dict[idtag] -> object
        """
        data = dict()
        for key, tpe in self.device_type_name_dict.items():
            elements = self.get_elements_by_type(device_type=tpe)

            for elm in elements:
                data[elm.idtag] = elm

        return data

    def get_all_elements_dict_by_type(self,
                                      add_locations: bool = False) -> dict[str, Union[dict[str, ALL_DEV_TYPES], Any]]:
        """
        Get a dictionary of all elements by type
        :return:
        """

        data = dict()
        for key, tpe in self.device_type_name_dict.items():
            data[tpe.value] = self.get_elements_dict_by_type(element_type=tpe,
                                                             use_secondary_key=False)

        # add locations
        if add_locations:
            data[DeviceType.LineLocation.value] = self.get_elements_dict_by_type(element_type=DeviceType.LineLocation,
                                                                                 use_secondary_key=False)

        return data

    def get_elements_dict_by_type(self, element_type: DeviceType,
                                  use_secondary_key=False) -> Dict[str, ALL_DEV_TYPES]:
        """
        Get dictionary of elements
        :param element_type: element type (Bus, Line, etc...)
        :param use_secondary_key: use the code as dictionary key? otherwise the idtag is used
        :return: Dict[str, dev.EditableDevice]
        """

        if use_secondary_key:
            return {elm.code: elm for elm in self.get_elements_by_type(element_type)}
        else:
            return {elm.idtag: elm for elm in self.get_elements_by_type(element_type)}

    def clear(self) -> None:
        """
        Clear the multi-circuit (remove the bus and branch objects)
        """

        for key, elm_list in self.objects_with_profiles.items():
            for elm in elm_list:
                self.get_elements_by_type(device_type=elm.device_type).clear()
