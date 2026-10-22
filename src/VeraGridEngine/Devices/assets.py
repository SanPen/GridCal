# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import hashlib
import json
import warnings
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Union, Any, Set, Generator, Sequence, Optional
import datetime as dateslib

from VeraGridEngine.basic_structures import IntVec, StrVec, Vec, Mat, ObjVec, BoolVec
import VeraGridEngine.Devices as dev
import VeraGridEngine.Templates as tem
from VeraGridEngine.Devices.types import ALL_DEV_TYPES, BRANCH_TYPES, INJECTION_DEVICE_TYPES, FLUID_TYPES
from VeraGridEngine.Devices.Parents.editable_device import GCPROP_TYPES
from VeraGridEngine.Devices.Parents.pointer_device_parent import PointerDeviceParent
from VeraGridEngine.Utils.procedural_logic import (
    IeeeCigreDllParameterOverride,
    IeeeCigreDllSignalBinding,
    ManufacturerNativeControllerLogic,
    ManufacturerNativeRebindPlan,
    ProceduralLogicBase,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Devices.Dynamic.template_classification import (
    classify_dynamic_template_block,
)
from VeraGridEngine.enumerations import (
    ActionType,
    DeviceType,
    DynamicTemplateCategory,
    FmuTemplateDomain,
    IeeeCigreDllModelMode,
    ParamPowerFlowReferenceType,
)
from VeraGridEngine.basic_structures import Logger, ListSet
from VeraGridEngine.data_logger import DataLogger


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


def _matches_dynamic_template_device_type(requested_tpe: DeviceType, template_tpe: DeviceType) -> bool:
    """
    Return whether one reusable dynamic template is compatible with a host device type.

    Generic templates are intentionally exposed to every dynamic editor so they can
    be reused as sub-blocks inside arbitrary device models.

    :param requested_tpe: Device type being edited.
    :param template_tpe: Device type declared by the reusable template.
    :return: ``True`` when the template must appear in the editor catalogue.
    """
    if template_tpe == requested_tpe:
        return True
    else:
        pass

    if template_tpe == DeviceType.NoDevice:
        return True
    else:
        pass

    if template_tpe == DeviceType.DynamicModelHostDevice:
        return True
    else:
        pass

    return False


class Assets:
    """
    Class to store the assets
    """

    __slots__ = (
        '_time_profile',
        '_snapshot_time',
        '_lines',
        '_dc_lines',
        '_transformers2w',
        '_hvdc_lines',
        '_vsc_devices',
        '_upfc_devices',
        '_switch_devices',
        '_transformers3w',
        '_transformers_nw',
        '_windings',
        '_series_reactances',
        '_buses',
        '_bus_bars',
        '_voltage_levels',
        '_loads',
        '_generators',
        '_external_grids',
        '_shunts',
        '_batteries',
        '_static_generators',
        '_current_injections',
        '_controllable_shunts',
        '_pi_measurements',
        '_qi_measurements',
        '_pg_measurements',
        '_qg_measurements',
        '_vm_measurements',
        '_va_measurements',
        '_pf_measurements',
        '_pt_measurements',
        '_qf_measurements',
        '_qt_measurements',
        '_if_measurements',
        '_it_measurements',
        '_overhead_line_types',
        '_wire_types',
        '_underground_cable_constructions',
        '_underground_cable_types',
        '_sequence_line_types',
        '_transformer_types',
        '_branch_groups',
        '_substations',
        '_areas',
        '_zones',
        '_countries',
        '_communities',
        '_regions',
        '_municipalities',
        '_contingencies',
        '_contingency_groups',
        '_remedial_actions',
        '_remedial_action_groups',
        '_short_circuit_events',
        '_investments',
        '_investments_groups',
        '_technologies',
        '_owners',
        '_modelling_authorities',
        '_fuels',
        '_emission_gases',
        '_facilities',
        '_market_unit_groups',
        '_market_units',
        '_fluid_nodes',
        '_fluid_paths',
        '_turbines',
        '_pumps',
        '_p2xs',
        '_diagrams',
        '_manufacturer_native_models',
        '_rms_models',
        '_emt_models',
        '_fmu_templates',
        '_control_pcs',
        'template_objects_dict',
        'profile_magnitudes',
        'device_type_name_dict',
        'device_associations',
        '_rms_events',
        '_rms_events_groups',
        '_emt_events',
        '_emt_events_groups',
        '_dynamic_plots',
        '_dynamic_plot_entries',
        '_var_factory',
    )

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

        self._transformers_nw: List[dev.TransformerNW] = list()

        self._windings: List[dev.Winding] = list()

        self._series_reactances: List[dev.SeriesReactance] = list()

        # Should accept buses
        self._buses: List[dev.Bus] = ListSet()

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

        # List of events
        self._rms_events: List[dev.RmsEvent] = list()

        # List of events group
        self._rms_events_groups: List[dev.RmsEventsGroup] = list()

        # List of EMT events
        self._emt_events: List[dev.EmtEvent] = list()

        # List of EMT events groups
        self._emt_events_groups: List[dev.EmtEventsGroup] = list()

        # List of dynamic plots
        self._dynamic_plots: List[dev.DynamicPlot] = list()

        # List of dynamic plot entries
        self._dynamic_plot_entries: List[dev.DynamicPlotEntry] = list()

        # Lists of measurements
        self._pi_measurements: List[dev.PiMeasurement] = list()
        self._qi_measurements: List[dev.QiMeasurement] = list()
        self._pg_measurements: List[dev.PgMeasurement] = list()
        self._qg_measurements: List[dev.QgMeasurement] = list()
        self._vm_measurements: List[dev.VmMeasurement] = list()
        self._va_measurements: List[dev.VaMeasurement] = list()
        self._pf_measurements: List[dev.PfMeasurement] = list()
        self._pt_measurements: List[dev.PtMeasurement] = list()
        self._qf_measurements: List[dev.QfMeasurement] = list()
        self._qt_measurements: List[dev.QtMeasurement] = list()
        self._if_measurements: List[dev.IfMeasurement] = list()
        self._it_measurements: List[dev.ItMeasurement] = list()

        # List of overhead line objects
        self._overhead_line_types: List[dev.OverheadLineType] = list()

        # list of wire types
        self._wire_types: List[dev.Wire] = list()

        # physical single-core underground cable constructions
        self._underground_cable_constructions: List[dev.UndergroundCableType] = list()

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

        # remedial actions
        self._remedial_actions: List[dev.RemedialAction] = list()

        # remedial actions group
        self._remedial_action_groups: List[dev.RemedialActionGroup] = list()

        # Short circuit definition
        self._short_circuit_events: List[dev.ShortCircuitEvent] = list()

        # investments
        self._investments: List[dev.Investment] = list()

        # investments group
        self._investments_groups: List[dev.InvestmentsGroup] = list()

        # technologies
        self._technologies: List[dev.Technology] = list()

        # owners
        self._owners: List[dev.Owner] = list()

        # Modeling authority
        self._modelling_authorities: List[dev.ModellingAuthority] = list()

        # fuels
        self._fuels: List[dev.Fuel] = list()

        # emission gasses
        self._emission_gases: List[dev.EmissionGas] = list()

        # list of facilities
        self._facilities: List[dev.Facility] = list()

        # list of market units
        self._market_unit_groups: List[dev.MarketUnitsGroup] = list()

        # list of market units
        self._market_units: List[dev.MarketUnit] = list()

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

        # Manufacturer native providers precede every Block consumer.
        self._manufacturer_native_models: List[dev.ManufacturerNativeModel] = list()

        # list of RMS models
        self._rms_models: List[dev.RmsModelTemplate] = list()

        # list of EMT models
        self._emt_models: List[dev.EmtModelTemplate] = list()

        # list of reusable FMU templates
        self._fmu_templates: List[dev.FmuTemplate] = list()

        # list of control PCs
        self._control_pcs: List[dev.ControlPc] = list()

        # list of declared diagrams
        self._diagrams: dev.DiagramTree = dev.DiagramTree()

        # Class to handle the dynamic Vars and Consts
        self._var_factory: dev.VarFactory = dev.VarFactory()

        # objects with profiles
        self.template_objects_dict = {
            "Regions": [
                dev.Country(),
                dev.Community(),
                dev.Region(),
                dev.Municipality(),
                dev.Area(),
                dev.Zone(),
            ],
            "Associations": [
                dev.Technology(),
                dev.Fuel(),
                dev.EmissionGas(),
                dev.Owner(),
            ],
            "Substation": [
                dev.Substation(),
                dev.VoltageLevel(),
                dev.BusBar(),
                dev.Bus(),
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
                dev.Winding(),
                dev.Transformer2W(),
                dev.Transformer3W(),
                dev.TransformerNW(),
                dev.SeriesReactance(),
                dev.HvdcLine(),
                dev.VSC(),
                dev.UPFC(),
                dev.Switch()
            ],
            "Fluid": [
                dev.FluidNode(),
                dev.FluidPath(),
                dev.FluidTurbine(),
                dev.FluidPump(),
                dev.FluidP2x(),
            ],
            "Groups": [
                dev.BranchGroup(),
                dev.ModellingAuthority(),
                dev.Facility(),
            ],
            "Contingencies": [
                dev.ContingencyGroup(),
                dev.Contingency(),
                dev.RemedialActionGroup(),
                dev.RemedialAction(),
                dev.ShortCircuitEvent()
            ],
            "Investments": [
                dev.InvestmentsGroup(),
                dev.Investment(),
            ],
            "Market": [
                dev.MarketUnitsGroup(),
                dev.MarketUnit()
            ],
            "Dynamic": [
                dev.ControlPc(),
                dev.RmsEventsGroup(),
                dev.RmsEvent(),
                dev.EmtEventsGroup(),
                dev.EmtEvent(),
                # dev.DynamicPlotEntry()
                # dev.DynamicPlot(),
            ],
            "Templates": [
                dev.ManufacturerNativeModel(),
                dev.RmsModelTemplate(),
                dev.EmtModelTemplate(),
                dev.FmuTemplate(),
            ],
            "Catalogue": [
                dev.Wire(),
                dev.OverheadLineType(),
                dev.UndergroundCableType(),
                dev.UndergroundLineType(),
                dev.SequenceLineType(),
                dev.TransformerType(),
            ],
            "Measurements": [
                dev.PiMeasurement(),
                dev.QiMeasurement(),
                dev.PfMeasurement(),
                dev.QfMeasurement(),
                dev.IfMeasurement(),
                dev.PtMeasurement(),
                dev.QtMeasurement(),
                dev.ItMeasurement(),
                dev.VmMeasurement(),
                dev.VaMeasurement(),
                dev.PgMeasurement(),
                dev.QgMeasurement(),
            ]

        }

        # dictionary of profile magnitudes per object
        self.profile_magnitudes: Dict[DeviceType, Tuple[List[str], List[GCPROP_TYPES]]] = dict()

        self.device_type_name_dict: Dict[DeviceType, DeviceType] = dict()

        self.device_associations: Dict[DeviceType, List[str]] = dict()

        """
        self.type_name = 'Shunt'

        self.properties_with_profile = ['Y']
        """
        for key, elm_list in self.template_objects_dict.items():
            for elm in elm_list:

                key: DeviceType = elm.device_type

                associated_props, indices = elm.get_association_properties()
                self.device_type_name_dict[key] = elm.device_type
                self.device_associations[key] = [prop.name for prop in associated_props]

                if elm.properties_with_profile is not None:
                    profile_attr = list(elm.properties_with_profile.keys())
                    profile_types = [elm.registered_properties[attr].tpe for attr in profile_attr]
                    self.profile_magnitudes[key] = (profile_attr, profile_types)

    # ------------------------------------------------------------------------------------------------------------------
    # Device iterators
    # ------------------------------------------------------------------------------------------------------------------

    def item_types(self) -> Generator[DeviceType, None, None]:
        """
        Iterator of all the objects in the MultiCircuit
        """
        for key, tpe in self.device_type_name_dict.items():
            yield tpe

    def template_items(self) -> Generator[ALL_DEV_TYPES, None, None]:
        """
        Iterator of the declared objects in the MultiCircuit.
        These are the object types that you see in the App DataBase tree
        """
        for key, elm_type_list in self.template_objects_dict.items():
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
        if self._time_profile is None or self._time_profile is pd.NaT:
            return 0
        else:
            return len(self._time_profile)

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
        if isinstance(value, pd.DatetimeIndex):
            self._time_profile = value
        else:
            if value is None or value is pd.NaT:
                if self._time_profile is None:
                    # the time profile is None al ready
                    pass
                else:
                    raise ValueError("Cannot set the time profile to None because it is already not None")
            else:
                try:
                    self._time_profile = pd.to_datetime(value)
                except TypeError:
                    warnings.warn(f"Trying to set time profile with something else {type(value)}")

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
            # resolution-independent: time_profile may be datetime64[ns] or [us] depending on pandas
            return ((self._time_profile - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")).values.astype(np.int64)
        else:
            return np.zeros(0, dtype=np.int64)

    def set_unix_time(self, arr: IntVec):
        """
        Set the time with a unix time
        :param arr: UNIX time iterable
        """
        self._time_profile = pd.to_datetime(arr, unit='s')

    def get_time_deltas_in_hours(self) -> Vec:
        """
        Get the time increments in hours
        :return: array of time deltas where the first delta is 1
        """
        return np.r_[1.0, np.diff(self.get_unix_time() / 3600)]

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

    def re_index_time2(self,
                       t0: dateslib.datetime | None = None,
                       step_size: float = 1.0,
                       step_unit: str = "h"):
        """
        Generate sequential time steps to correct the time_profile
        :param t0: base time
        :param step_size: number of hours per step, by default 1 hour by step
        :param step_unit: 'h', 'm', 's'
        """
        nt = self.get_time_number()

        if t0 is None:
            t0 = dateslib.datetime.now()
        else:
            pass
        t0 = t0.replace(second=0, microsecond=0)

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

        index: ObjVec = np.empty(steps, dtype=object)
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
        Format the profiles in place using a time index.
        :param index: Time profile
        """

        self.time_profile = pd.to_datetime(index, dayfirst=True)

        for key, tpe in self.device_type_name_dict.items():
            elements = self.get_elements_by_type(device_type=tpe)
            for elm in elements:
                elm.ensure_profiles_exist(index, set_profile_default_as_snapshot=True)

    def format_profiles2(self, nt: int) -> None:
        """
        Format the profiles in place using a simple number of time steps.
        :param nt: number of time steps
        :return: None
        """
        now = dateslib.datetime.now()
        dt0 = dateslib.datetime(year=now.year, month=1, day=1)
        dates = pd.DatetimeIndex([dt0 + dateslib.timedelta(hours=1) for i in range(nt)])
        self.format_profiles(index=dates)

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

        for elm in self.items():
            elm.ensure_profiles_exist(self.time_profile)

    def delete_profiles(self):
        """
        Delete the time profiles
        :return:
        """
        for elm in self.items():
            elm.delete_profiles()
        self._time_profile = None

    def resample_profiles(self, indices: IntVec):
        """
        resample the given profiles to the indices
        :param indices: array of indices to keep
        """
        self.time_profile = pd.DatetimeIndex([self.time_profile[i] for i in indices])

        for elm in self.items():
            elm.resample_profiles(indices=indices)

    def resample_profiles2(self, t0: int, t1: int):
        """
        Resample profiles
        :param t0: first time index
        :param t1: second time index
        """
        indices = np.arange(t0, t1)
        self.resample_profiles(indices=indices)

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
    # Var Factory
    # ------------------------------------------------------------------------------------------------------------------
    @property
    def var_factory(self) -> dev.VarFactory:
        """
        Get the RMS VarFactory object
        :return: VarFactory
        """
        return self._var_factory

    @var_factory.setter
    def var_factory(self, value: dev.VarFactory):
        self._var_factory = value

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

    def get_lines_number(self) -> int:
        """

        :return:
        """
        return len(self._lines)

    def get_lines(self) -> List[dev.Line]:
        """
        get list of ac lines
        :return: list of lines
        """
        return self._lines

    def add_line(self, obj: dev.Line, logger: Union[Logger, DataLogger] = Logger()) -> dev.Line:
        """
        Add a line object
        :param obj: Line instance
        :param logger: Logger to record events
        """
        if obj.should_this_be_a_transformer(branch_connection_voltage_tolerance=0.1, logger=logger):
            tr = obj.get_equivalent_transformer(index=self.time_profile)
            self.add_transformer2w(tr)
        else:
            if self.time_profile is not None:
                obj.ensure_profiles_exist(self.time_profile)
            self._lines.append(obj)

        obj.set_var_factory(self._var_factory)

        return obj

    def delete_line(self, obj: dev.Line):
        """
        Delete line
        :param obj: Line instance
        """
        try:
            self._lines.remove(obj)

            self.delete_groupings_with_object(obj=obj)

        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

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
            obj.ensure_profiles_exist(self.time_profile)
        self._dc_lines.append(obj)

        obj.set_var_factory(self._var_factory)

    def delete_dc_line(self, obj: dev.DcLine):
        """
        Delete line
        :param obj: Line instance
        """
        try:
            self._dc_lines.remove(obj)
            self.delete_groupings_with_object(obj=obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

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

    def add_transformer2w(self, obj: dev.Transformer2W) -> dev.Transformer2W:
        """
        Add a transformer object
        :param obj: Transformer2W instance
        """

        if self.time_profile is not None:
            obj.ensure_profiles_exist(self.time_profile)

        self._transformers2w.append(obj)
        obj.set_var_factory(self._var_factory)

        return obj

    def delete_transformer2w(self, obj: dev.Transformer2W):
        """
        Delete transformer
        :param obj: Transformer2W instance
        """
        try:
            self._transformers2w.remove(obj)
            self.delete_groupings_with_object(obj=obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

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

    def get_hvdc_actives(self, t_idx: int | None = None) -> IntVec:
        """
        get a vector of actives
        :return: Array of bus active
        """
        data: IntVec = np.zeros(len(self._hvdc_lines), dtype=int)
        for i, b in enumerate(self._hvdc_lines):
            data[i] = b.active if t_idx is None else b.active_prof[t_idx]
        return data

    def add_hvdc(self, obj: dev.HvdcLine):
        """
        Add a hvdc line object
        :param obj: HvdcLine instance
        """

        if self.time_profile is not None:
            obj.ensure_profiles_exist(self.time_profile)

        obj.set_var_factory(self._var_factory)
        self._hvdc_lines.append(obj)

    def delete_hvdc_line(self, obj: dev.HvdcLine):
        """
        Delete HVDC line
        :param obj:
        """
        try:
            self._hvdc_lines.remove(obj)
            self.delete_groupings_with_object(obj=obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

    def get_hvdc_dict(self) -> Dict[str, dev.HvdcLine]:
        """
        Get dictionary of HVDC lines
        :return: idtag -> HvdcLine
        """
        return {elm.idtag: elm for elm in self.hvdc_lines}

    def get_hvdc_index_dict(self) -> Dict[str, int]:
        """
        Get dictionary of HVDC lines
        :return: idtag -> HvdcLine
        """
        return {elm.idtag: i for i, elm in enumerate(self.hvdc_lines)}

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

    def get_vsc_names(self) -> StrVec:
        """
        Get Vsc names
        """
        return np.array([e.name for e in self.vsc_devices])

    def get_vsc_actives(self, t_idx: int | None = None) -> IntVec:
        """
        get a vector of actives
        :return: Array of bus active
        """
        data: IntVec = np.zeros(len(self._vsc_devices), dtype=int)
        for i, b in enumerate(self._vsc_devices):
            data[i] = b.active if t_idx is None else b.active_prof[t_idx]
        return data

    def add_vsc(self, obj: dev.VSC):
        """
        Add a hvdc line object
        :param obj: HvdcLine instance
        """

        if self.time_profile is not None:
            obj.ensure_profiles_exist(self.time_profile)

        self._vsc_devices.append(obj)
        obj.set_var_factory(self._var_factory)

    def delete_vsc_converter(self, obj: dev.VSC):
        """
        Delete VSC
        :param obj: VSC Instance
        """
        try:
            self._vsc_devices.remove(obj)
            self.delete_groupings_with_object(obj=obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

    def get_vsc_dict(self) -> Dict[str, dev.VSC]:
        """
        Get dictionary of VSC converters
        :return: idtag -> VSC
        """
        return {elm.idtag: elm for elm in self.vsc_devices}

    def get_vsc_index_dict(self) -> Dict[str, int]:
        """
        Get index dictionary of VSC lines
        :return: idtag -> i
        """
        return {elm.idtag: i for i, elm in enumerate(self.vsc_devices)}

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
            obj.ensure_profiles_exist(self.time_profile)

        obj.set_var_factory(self._var_factory)
        self._upfc_devices.append(obj)

    def delete_upfc_converter(self, obj: dev.UPFC):
        """
        Delete VSC
        :param obj: VSC Instance
        """
        try:
            self._upfc_devices.remove(obj)
            self.delete_groupings_with_object(obj=obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

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
            obj.ensure_profiles_exist(self.time_profile)
        self._switch_devices.append(obj)
        obj.set_var_factory(self._var_factory)

        return obj

    def delete_switch(self, obj: dev.Switch):
        """
        Delete transformer
        :param obj: Transformer2W instance
        """
        try:
            self._switch_devices.remove(obj)
            self.delete_groupings_with_object(obj=obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

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
            obj.ensure_profiles_exist(self.time_profile)
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
        try:
            self._transformers3w.remove(obj)
        except ValueError:
            pass

        self.delete_winding(obj.winding1)
        self.delete_winding(obj.winding2)
        self.delete_winding(obj.winding3)
        self.delete_bus(obj.bus0, delete_associated=True)  # also delete the middle bus

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

    # ------------------------------------------------------------------------------------------------------------------
    # Transformer NW
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def transformers_nw(self) -> List[dev.TransformerNW]:
        """
        Get list of N-winding transformers
        :return:
        """
        return self._transformers_nw

    @transformers_nw.setter
    def transformers_nw(self, value: List[dev.TransformerNW]):
        self._transformers_nw = value

    def get_transformers_nw(self) -> List[dev.TransformerNW]:
        """

        :return:
        """
        return self._transformers_nw

    def get_transformers_nw_number(self) -> int:
        """

        :return:
        """
        return len(self._transformers_nw)

    def get_transformers_nw_names(self) -> List[str]:
        """

        :return:
        """
        return [elm.name for elm in self._transformers_nw]

    def add_transformer_nw(self, obj: dev.TransformerNW, add_middle_bus: bool = True):
        """
        Add an N-winding transformer object
        :param obj: TransformerNW instance
        :param add_middle_bus: Add the internal star bus?
        """

        if self.time_profile is not None:
            obj.ensure_profiles_exist(self.time_profile)
        self._transformers_nw.append(obj)
        if add_middle_bus:
            self.add_bus(obj.bus0)
        for winding in obj.windings:
            if winding.bus_from is not None:
                self.add_winding(winding)

    def delete_transformer_nw(self, obj: dev.TransformerNW):
        """
        Delete N-winding transformer
        :param obj: TransformerNW instance
        """
        try:
            self._transformers_nw.remove(obj)
        except ValueError:
            pass

        winding_list: list[dev.Winding] = list(obj.windings)
        for winding in winding_list:
            self.delete_winding(winding)

        winding_count_to_clear: int = len(obj.windings)
        for winding_index in range(winding_count_to_clear):
            obj.delete_winding(0)

        self.delete_bus(obj.bus0, delete_associated=True)

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

    def delete_associated_multi_winding_transformers(self, buses_to_remove: Set[dev.Bus]) -> None:
        """
        Delete multi-winding transformers connected to any bus being removed.

        :param buses_to_remove: Buses requested for deletion.
        :type buses_to_remove: Set[dev.Bus]
        :return: None
        :rtype: None
        """
        transformers3w_to_delete: List[dev.Transformer3W] = list()
        transformers_nw_to_delete: List[dev.TransformerNW] = list()

        # Transformer windings are stored as branch devices, but the transformer parent also has to disappear.
        for transformer3w in self._transformers3w:
            if (transformer3w.bus0 in buses_to_remove
                    or transformer3w.bus1 in buses_to_remove
                    or transformer3w.bus2 in buses_to_remove
                    or transformer3w.bus3 in buses_to_remove):
                transformers3w_to_delete.append(transformer3w)
            else:
                pass

        # N-winding transformers need the same parent cleanup for their internal and terminal buses.
        for transformer_nw in self._transformers_nw:
            delete_transformer: bool = transformer_nw.bus0 in buses_to_remove

            if delete_transformer:
                pass
            else:
                for bus in transformer_nw.buses:
                    if bus in buses_to_remove:
                        delete_transformer = True
                    else:
                        pass

            if delete_transformer:
                transformers_nw_to_delete.append(transformer_nw)
            else:
                pass

        for transformer3w in transformers3w_to_delete:
            self.delete_transformer3w(obj=transformer3w)

        for transformer_nw in transformers_nw_to_delete:
            self.delete_transformer_nw(obj=transformer_nw)

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
            obj.ensure_profiles_exist(self.time_profile)

        obj.set_var_factory(self._var_factory)

        self._windings.append(obj)

    def delete_winding(self, obj: dev.Winding):
        """
        Delete winding
        :param obj: Winding instance
        """
        for tr3 in self._transformers3w:

            if obj == tr3.winding1:
                tr3.bus1 = None

            elif obj == tr3.winding2:
                tr3.bus2 = None

            if obj == tr3.winding3:
                tr3.bus3 = None

        for tr_nw in self._transformers_nw:
            for i, winding in enumerate(tr_nw.windings):
                if obj == winding:
                    tr_nw.delete_winding(i)
                    break

        try:
            self._windings.remove(obj)
            self.delete_groupings_with_object(obj=obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

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
            obj.ensure_profiles_exist(self.time_profile)

        obj.set_var_factory(self._var_factory)
        self._series_reactances.append(obj)

    def delete_series_reactance(self, obj: dev.SeriesReactance) -> None:
        """
        Add a SeriesReactance object
        :param obj: SeriesReactance instance
        """
        try:
            self._series_reactances.remove(obj)
        except ValueError:
            pass

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
        self._buses = ListSet(value)

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

    def get_bus_idtag_index_dict(self) -> Dict[str, int]:
        """
        Return dictionary of buses
        :return: dictionary of buses {name:object}
        """
        return {b.idtag: i for i, b in enumerate(self._buses)}

    def get_bus_actives(self, t_idx: int | None = None) -> IntVec:
        """
        get a vector of actives
        :return: Array of bus active
        """
        data: IntVec = np.zeros(len(self._buses), dtype=int)
        for i, b in enumerate(self._buses):
            data[i] = b.active if t_idx is None else b.active_prof[t_idx]
        return data

    def add_bus(self, obj: Union[None, dev.Bus] = None) -> dev.Bus:
        """
        Add a :ref:`Bus<bus>` object to the grid.

        Arguments:

            **obj** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object
        """
        if obj is None:
            obj = dev.Bus()

        if self.time_profile is not None:
            obj.ensure_profiles_exist(self.time_profile)

        self._buses.append(obj)

        obj.set_var_factory(self._var_factory)

        return obj

    def delete_bus(self, obj: dev.Bus, delete_associated=False):
        """
        Delete a :ref:`Bus<bus>` object from the grid.
        :param obj: :ref:`Bus<bus>` object
        :param delete_associated: Delete the associated branches and injections
        """

        # Multi-winding transformer parents must be deleted before their winding branches are removed.
        if delete_associated:
            self.delete_associated_multi_winding_transformers(buses_to_remove={obj})
        else:
            pass

        # delete associated Branches in reverse order
        for branch_list in self.get_branch_lists(add_vsc=True, add_hvdc=True, add_switch=True):
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

        # delete the associated injection devices
        for inj_list in self.get_injection_devices_lists():
            for i in range(len(inj_list) - 1, -1, -1):
                if inj_list[i].bus == obj:
                    if delete_associated:
                        self.delete_injection_device(inj_list[i])
                    else:
                        inj_list[i].bus = None

        # delete the bus itself
        # Use list comprehension for faster removal (avoids ValueError if already removed)
        self._buses = ListSet([b for b in self._buses if b != obj])

    def delete_branches_with_sets(self, buses_to_remove: Set[dev.Bus], delete_associated: bool = False):
        """
        Delete branch objects that may contain contingencies, remedial actions, or investments
        Used when you delete buses connected to branches
        :param buses_to_remove: Set of buses to remove
        :param delete_associated: Delete the associated branches
        :return: None
        """

        branches_to_delete = list()

        # First find branches to delete from the passed buses
        for branch_list in self.get_branch_lists(add_vsc=True, add_hvdc=True, add_switch=True):
            for i in range(len(branch_list) - 1, -1, -1):
                if branch_list[i].bus_from in buses_to_remove:
                    if delete_associated:
                        branches_to_delete.append(branch_list[i])
                    else:
                        branch_list[i].bus_from = None
                elif branch_list[i].bus_to in buses_to_remove:
                    if delete_associated:
                        branches_to_delete.append(branch_list[i])
                    else:
                        branch_list[i].bus_to = None

        # Optimized branch removal by creating a set for faster lookups
        branches_to_delete_set = set(branches_to_delete)

        # Remove branches directly from lists in one pass
        # This is more efficient than calling delete_branch for each
        for branch_list in self.get_branch_lists(add_vsc=True, add_hvdc=True, add_switch=True):
            # Use list comprehension to not consider branches to delete
            # This is faster than the multiple remove() calls we had before
            branch_list[:] = [b for b in branch_list if b not in branches_to_delete_set]

        # Batch process groupings, faster than calling delete_groupings_with_object for each branch
        if branches_to_delete:
            branch_idtags = {b.idtag for b in branches_to_delete}  # all idtags to consider

            # Process contingencies in batch. Remove all at once, then check for empty groups
            contingencies_to_delete = [elm for elm in self.contingencies if elm.device_idtag in branch_idtags]
            if contingencies_to_delete:
                contingencies_to_delete_set = set(contingencies_to_delete)
                # Remove all contingencies in one pass
                self._contingencies = [c for c in self._contingencies if c not in contingencies_to_delete_set]
                # Check which groups are now empty (only check once, not per deletion)
                groups_in_use = {c.group for c in self._contingencies}
                groups_to_delete = [g for g in self._contingency_groups if g not in groups_in_use]
                for grp in groups_to_delete:
                    self.delete_contingency_group(grp)

            # Process remedial actions in batch. Remove all at once, then check for empty groups
            remedial_actions_to_delete = [elm for elm in self.remedial_actions if elm.device_idtag in branch_idtags]
            if remedial_actions_to_delete:
                remedial_actions_to_delete_set = set(remedial_actions_to_delete)
                # Remove all remedial actions in one pass
                self._remedial_actions = [r for r in self._remedial_actions if r not in remedial_actions_to_delete_set]
                # Check which groups are now empty (only check once, not per deletion)
                groups_in_use = {r.group for r in self._remedial_actions}
                groups_to_delete = [g for g in self._remedial_action_groups if g not in groups_in_use]
                for grp in groups_to_delete:
                    self.delete_remedial_action_group(grp)

            # Process investments in batch. Remove all at once, then check for empty groups
            investments_to_delete = [elm for elm in self.investments if elm.device_idtag in branch_idtags]
            if investments_to_delete:
                investments_to_delete_set = set(investments_to_delete)
                # Remove all investments in one pass
                self._investments = [i for i in self._investments if i not in investments_to_delete_set]
                # Check which groups are now empty (only check once, not per deletion)
                groups_in_use = {i.group for i in self._investments}
                groups_to_delete = [g for g in self._investments_groups if g not in groups_in_use]
                for grp in groups_to_delete:
                    self.delete_investment_groups(grp)

        return None

    def delete_buses(self, lst: Sequence[dev.Bus], delete_associated=False):
        """
        Delete a :ref:`Bus<bus>` object from the grid.
        :param lst: Array of objects to remove
        :param delete_associated: Delete the associated branches and injections
        """
        buses_to_remove = set(lst)
        injections_to_delete = list()

        # Multi-winding transformer parents must be deleted before their winding branches are removed.
        if delete_associated:
            self.delete_associated_multi_winding_transformers(buses_to_remove=buses_to_remove)
        else:
            pass

        # We delete the associated branches by knowing the buses to remove
        self.delete_branches_with_sets(buses_to_remove, delete_associated)

        # delete the associated injection devices
        for inj_list in self.get_injection_devices_lists():
            for i in range(len(inj_list) - 1, -1, -1):
                if inj_list[i].bus in buses_to_remove:
                    if delete_associated:
                        injections_to_delete.append(inj_list[i])
                    else:
                        inj_list[i].bus = None

        # Optimized batch deletion of injection devices
        if injections_to_delete:
            injections_to_delete_set = set(injections_to_delete)
            for inj_list in self.get_injection_devices_lists():
                # Use list comprehension to filter out injections we have to delete
                inj_list[:] = [inj for inj in inj_list if inj not in injections_to_delete_set]
        else:
            # No injections to delete, so nothing to be done
            pass

        # delete the bus itself - use set difference for faster removal
        # Remove all buses in one pass using list comprehension (faster and avoids ValueError)
        buses_to_remove_set = buses_to_remove
        self._buses = ListSet([b for b in self._buses if b not in buses_to_remove_set])

    def get_buses_by(self, filter_elements: List[Union[dev.Area, dev.Zone,
    dev.Country, dev.Community,
    dev.Region, dev.Municipality]]) -> List[dev.Bus]:
        """
        Get a list of buses that can be found in the list of Areas | Zones | Countries
        :param filter_elements: list of Areas | Zones | Countries
        :return: list of buses
        """
        data: List[dev.Bus] = list()
        filter_elements_set = set(filter_elements)

        for bus in self._buses:

            ok = bus.area in filter_elements_set
            ok = ok or bus.zone in filter_elements_set
            ok = ok or bus.country in filter_elements_set

            if bus.substation is not None:
                ok = ok or bus.substation.municipality in filter_elements_set

                if bus.substation.municipality is not None:
                    ok = ok or bus.substation.municipality.region in filter_elements_set

                    if bus.substation.municipality.region is not None:
                        ok = ok or bus.substation.municipality.region.community in filter_elements_set

            if ok:
                data.append(bus)

        return data

    def get_bus_devices(self, bus: dev.Bus) -> Tuple[List[BRANCH_TYPES], List[INJECTION_DEVICE_TYPES]]:
        """
        Get the list of associated branches and the list of associated injections
        :param bus:
        :return: associated_branches, associated_injections
        """
        associated_branches = list()
        for elm in self.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
            if elm.bus_from == bus or elm.bus_to == bus:
                associated_branches.append(elm)

        associated_injections = list()
        for elm in self.get_injection_devices_iter():
            if elm.bus == bus:
                associated_injections.append(elm)

        return associated_branches, associated_injections

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

    def add_bus_bar(self, obj: dev.BusBar):
        """
        Add Substation
        :param obj: BusBar object
        """
        if obj is None:
            obj = dev.BusBar(name=f"BB{len(self._bus_bars)}")

        self._bus_bars.append(obj)

        return obj

    def delete_bus_bar(self, obj: dev.BusBar):
        """
        Delete Substation
        :param obj: Substation object
        """

        # remove pointers
        for bus in self.buses:
            if bus.bus_bar == obj:
                bus.bus_bar = None

        try:
            self._bus_bars.remove(obj)
        except ValueError:
            pass

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
            obj.ensure_profiles_exist(self.time_profile)
        self._voltage_levels.append(obj)

    def delete_voltage_level(self, obj: dev.VoltageLevel) -> None:
        """
        Add a VoltageLevel object
        :param obj: VoltageLevel instance
        """

        for elm in self._buses:
            if elm.voltage_level == obj:
                elm.voltage_level = None

        try:
            self._voltage_levels.remove(obj)
        except ValueError:
            pass

    def get_voltage_level_buses(self, vl: dev.VoltageLevel) -> List[dev.Bus]:
        """
        Get the list of buses of this substation
        :param vl:
        :return:
        """
        lst: List[dev.Bus] = list()

        for bus in self.buses:
            if bus.voltage_level == vl:
                lst.append(bus)

        return lst

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
                 api_obj: Union[None, dev.Load] = None) -> dev.Load:
        """
        Add a load device
        :param bus: Main bus (optional)
        :param api_obj: Device to add (optional)
        :return: Load device passed or created
        """
        if api_obj is None:
            api_obj = dev.Load()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'Load':
            if bus is not None:
                api_obj.name += '@' + bus.name

        self._loads.append(api_obj)

        api_obj.set_var_factory(self._var_factory)

        return api_obj

    def delete_load(self, obj: dev.Load):
        """
        Delete a load
        :param obj:
        :return:
        """
        try:
            self._loads.remove(obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

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
                      api_obj: Union[None, dev.Generator] = None) -> dev.Generator:
        """
        Add a generator
        :param bus: Main bus (optional)
        :param api_obj: Generator object (optional)
        :return: Generator object (created if api_obj is None)
        """

        if api_obj is None:
            api_obj = dev.Generator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'gen':
            if bus is not None:
                api_obj.name += '@' + bus.name

        self._generators.append(api_obj)

        api_obj.set_var_factory(self._var_factory)

        return api_obj

    def delete_generator(self, obj: dev.Generator):
        """
        Delete a generator
        :param obj:
        :return:
        """
        try:
            self._generators.remove(obj)
            print("")
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._contingencies, self._remedial_actions, self._rms_events, self._emt_events]:
            for elm in lst:
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

    def get_generator_bus_index_dict(self, bus_index_dict: Dict[dev.Bus, int] = None):
        """
        Get a dictionary of generators related to their bus index
        :param bus_index_dict: bus object to bus index dictionary (optional)
        :return: generator object to bus index dictionary

        """
        if bus_index_dict is None:
            bus_index_dict = self.get_bus_index_dict()

        return {g.idtag: bus_index_dict[g.bus] for g in self.get_generators() if g.bus is not None}

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
                          api_obj: Union[None, dev.ExternalGrid] = None) -> dev.ExternalGrid:
        """
        Add an external grid
        :param bus: Bus object
        :param api_obj: api_obj, if None, create a new one
        :return: ExternalGrid
        """

        if api_obj is None:
            api_obj = dev.ExternalGrid()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'External grid':
            if bus is not None:
                api_obj.name += '@' + bus.name

        self._external_grids.append(api_obj)
        api_obj.set_var_factory(self._var_factory)

        return api_obj

    def delete_external_grid(self, obj: dev.ExternalGrid):
        """
        Delete a external grid
        :param obj:
        :return:
        """
        try:
            self._external_grids.remove(obj)
        except ValueError:
            pass

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
                  api_obj: Union[None, dev.Shunt] = None) -> dev.Shunt:
        """
        Add a :ref:`Shunt<shunt>` object to a :ref:`Bus<bus>`.

        Arguments:

            **bus** (:ref:`Bus<bus>`): :ref:`Bus<bus>` object

            **api_obj** (:ref:`Shunt<shunt>`): :ref:`Shunt<shunt>` object
        """
        if api_obj is None:
            api_obj = dev.Shunt()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'shunt':
            if bus is not None:
                api_obj.name += '@' + bus.name

        self._shunts.append(api_obj)
        api_obj.set_var_factory(self._var_factory)

        return api_obj

    def delete_shunt(self, obj: dev.Shunt):
        """
        Delete a shunt
        :param obj:
        :return:
        """
        try:
            self._shunts.remove(obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

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
                    api_obj: Union[None, dev.Battery] = None) -> dev.Battery:
        """
        Add battery
        :param bus:
        :param api_obj:
        :return:
        """
        if api_obj is None:
            api_obj = dev.Battery()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'batt':
            if bus is not None:
                api_obj.name += '@' + bus.name

        self._batteries.append(api_obj)

        api_obj.set_var_factory(self._var_factory)
        return api_obj

    def delete_battery(self, obj: dev.Battery):
        """
        Delete a battery
        :param obj:
        :return:
        """
        try:
            self._batteries.remove(obj)
        except ValueError:
            pass

    def get_batteries_indexing_dict(self) -> Dict[str, int]:
        """
        Get a dictionary that relates the battery uuid's with their index
        :return: Dict[str, int]
        """
        gen_index_dict: Dict[str, int] = dict()
        for k, elm in enumerate(self.batteries):
            gen_index_dict[elm.idtag] = k  # associate the idtag to the index
        return gen_index_dict

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
                             api_obj: Union[None, dev.StaticGenerator] = None) -> dev.StaticGenerator:
        """
        Add a static generator
        :param bus: Bus object
        :param api_obj: StaticGenerator object
        :return: StaticGenerator object (created if api_obj is None)
        """

        if api_obj is None:
            api_obj = dev.StaticGenerator()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'StaticGen':
            if bus is not None:
                api_obj.name += '@' + bus.name

        self._static_generators.append(api_obj)

        api_obj.set_var_factory(self._var_factory)

        return api_obj

    def delete_static_generator(self, obj: dev.StaticGenerator):
        """
        Delete a static generators
        :param obj:
        :return:
        """
        try:
            self._static_generators.remove(obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

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
                              api_obj: Union[None, dev.CurrentInjection] = None) -> dev.CurrentInjection:
        """
        Add a CurrentInjection object
        :param bus: Bus
        :param api_obj: CurrentInjection instance
        """

        if api_obj is None:
            api_obj = dev.CurrentInjection()

        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'CInj':
            api_obj.name += '@' + bus.name

        self._current_injections.append(api_obj)
        api_obj.set_var_factory(self._var_factory)

        return api_obj

    def delete_current_injection(self, obj: dev.CurrentInjection) -> None:
        """
        Add a CurrentInjection object
        :param obj: CurrentInjection instance
        """
        try:
            self._current_injections.remove(obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

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
                               api_obj: Union[None, dev.ControllableShunt] = None) -> dev.ControllableShunt:
        """
        Add a ControllableShunt object
        :param bus: Main bus (optional)
        :param api_obj: ControllableShunt instance
        :return: ControllableShunt
        """

        if api_obj is None:
            api_obj = dev.ControllableShunt()
        api_obj.bus = bus

        if self.time_profile is not None:
            api_obj.ensure_profiles_exist(self.time_profile)

        if api_obj.name == 'CShunt':
            if bus is not None:
                api_obj.name += '@' + bus.name

        self._controllable_shunts.append(api_obj)
        api_obj.set_var_factory(self._var_factory)

        return api_obj

    def delete_controllable_shunt(self, obj: dev.ControllableShunt) -> None:
        """
        Add a LinearShunt object
        :param obj: LinearShunt instance
        """
        try:
            self._controllable_shunts.remove(obj)
        except ValueError:
            pass

        elms_to_del = list()
        for lst in [self._rms_events, self._emt_events]:
            for elm in lst:
                if elm.device_idtag == obj.idtag:
                    elms_to_del.append(elm)

        for elm in elms_to_del:
            self.delete_element(elm)

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

    def get_p_measurements(self) -> List[dev.PiMeasurement]:
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
            obj.ensure_profiles_exist(self.time_profile)
        self._pi_measurements.append(obj)

    def delete_pi_measurement(self, obj: dev.PiMeasurement) -> None:
        """
        Add a PiMeasurement object
        :param obj: PiMeasurement instance
        """
        try:
            self._pi_measurements.remove(obj)
        except ValueError:
            pass

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

    def get_q_measurements(self) -> List[dev.QiMeasurement]:
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
            obj.ensure_profiles_exist(self.time_profile)
        self._qi_measurements.append(obj)

    def delete_qi_measurement(self, obj: dev.QiMeasurement) -> None:
        """
        Add a QiMeasurement object
        :param obj: QiMeasurement instance
        """
        try:
            self._qi_measurements.remove(obj)
        except ValueError:
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # P_g measurement
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def pg_measurements(self) -> List[dev.PgMeasurement]:
        """
        Get list of PiMeasurements
        :return:
        """
        return self._pg_measurements

    @pg_measurements.setter
    def pg_measurements(self, value: List[dev.PgMeasurement]):
        self._pg_measurements = value

    def get_pg_measurements(self) -> List[dev.PgMeasurement]:
        """
        List of pg_measurements
        :return: List[dev.PgMeasurement]
        """
        return self._pg_measurements

    def get_pg_measurements_number(self) -> int:
        """
        Size of the list of pg_measurements
        :return: size of pg_measurements
        """
        return len(self._pg_measurements)

    def get_pg_measurement_at(self, i: int) -> dev.PgMeasurement:
        """
        Get pg_measurement at i
        :param i: index
        :return: PgMeasurement
        """
        return self._pg_measurements[i]

    def get_pg_measurement_names(self) -> StrVec:
        """
        Array of pi_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._pg_measurements])

    def add_pg_measurement(self, obj: dev.PgMeasurement):
        """
        Add a PgMeasurement object
        :param obj: PgMeasurement instance
        """

        if self.time_profile is not None:
            obj.ensure_profiles_exist(self.time_profile)
        self._pg_measurements.append(obj)

    def delete_pg_measurement(self, obj: dev.PgMeasurement) -> None:
        """
        Add a PiMeasurement object
        :param obj: PiMeasurement instance
        """
        try:
            self._pg_measurements.remove(obj)
        except ValueError:
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # Q_g measurement
    # ------------------------------------------------------------------------------------------------------------------
    @property
    def qg_measurements(self) -> List[dev.QgMeasurement]:
        """
        Get list of QgMeasurements
        :return:
        """
        return self._qg_measurements

    @qg_measurements.setter
    def qg_measurements(self, value: List[dev.QgMeasurement]):
        self._qg_measurements = value

    def get_qg_measurements(self) -> List[dev.QgMeasurement]:
        """
        List of qg_measurements
        :return: List[dev.QgMeasurement]
        """
        return self._qg_measurements

    def get_qg_measurements_number(self) -> int:
        """
        Size of the list of qg_measurements
        :return: size of qg_measurements
        """
        return len(self._qg_measurements)

    def get_qg_measurement_at(self, i: int) -> dev.QgMeasurement:
        """
        Get qg_measurement at i
        :param i: index
        :return: QgMeasurement
        """
        return self._qg_measurements[i]

    def get_qg_measurement_names(self) -> StrVec:
        """
        Array of qg_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._qg_measurements])

    def add_qg_measurement(self, obj: dev.QgMeasurement):
        """
        Add a QiMeasurement object
        :param obj: QiMeasurement instance
        """

        if self.time_profile is not None:
            obj.ensure_profiles_exist(self.time_profile)
        self._qg_measurements.append(obj)

    def delete_qg_measurement(self, obj: dev.QgMeasurement) -> None:
        """
        Add a QgMeasurement object
        :param obj: QgMeasurement instance
        """
        try:
            self._qg_measurements.remove(obj)
        except ValueError:
            pass

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
            obj.ensure_profiles_exist(self.time_profile)
        self._vm_measurements.append(obj)

    def delete_vm_measurement(self, obj: dev.VmMeasurement) -> None:
        """
        Add a VmMeasurement object
        :param obj: VmMeasurement instance
        """
        try:
            self._vm_measurements.remove(obj)
        except ValueError:
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # Va measurement
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def va_measurements(self) -> List[dev.VaMeasurement]:
        """
        Get list of VaMeasurements
        :return:
        """
        return self._va_measurements

    @va_measurements.setter
    def va_measurements(self, value: List[dev.VaMeasurement]):
        self._va_measurements = value

    def get_va_measurements(self) -> List[dev.VaMeasurement]:
        """
        List of va_measurements
        :return: List[dev.VaMeasurement]
        """
        return self._va_measurements

    def get_va_measurements_number(self) -> int:
        """
        Size of the list of va_measurements
        :return: size of va_measurements
        """
        return len(self._va_measurements)

    def get_va_measurement_at(self, i: int) -> dev.VaMeasurement:
        """
        Get va_measurement at i
        :param i: index
        :return: VaMeasurement
        """
        return self._va_measurements[i]

    def get_va_measurement_names(self) -> StrVec:
        """
        Array of va_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._va_measurements])

    def add_va_measurement(self, obj: dev.VaMeasurement):
        """
        Add a VaMeasurement object
        :param obj: VmMeasurement instance
        """
        if self.time_profile is not None:
            obj.ensure_profiles_exist(self.time_profile)
        self._va_measurements.append(obj)

    def delete_va_measurement(self, obj: dev.VaMeasurement) -> None:
        """
        Add a VaMeasurement object
        :param obj: VaMeasurement instance
        """
        try:
            self._va_measurements.remove(obj)
        except ValueError:
            pass

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
            obj.ensure_profiles_exist(self.time_profile)
        self._pf_measurements.append(obj)

    def delete_pf_measurement(self, obj: dev.PfMeasurement) -> None:
        """
        Add a PfMeasurement object
        :param obj: PfMeasurement instance
        """
        try:
            self._pf_measurements.remove(obj)
        except ValueError:
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # Pt measurement
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def pt_measurements(self) -> List[dev.PtMeasurement]:
        """
        Get list of PtMeasuremnts
        :return:
        """
        return self._pt_measurements

    @pt_measurements.setter
    def pt_measurements(self, value: List[dev.PtMeasurement]):
        self._pt_measurements = value

    def get_pt_measurements(self) -> List[dev.PtMeasurement]:
        """
        List of pt_measurements
        :return: List[dev.PtMeasurement]
        """
        return self._pt_measurements

    def get_pt_measurements_number(self) -> int:
        """
        Size of the list of pt_measurements
        :return: size of pt_measurements
        """
        return len(self._pt_measurements)

    def get_pt_measurement_at(self, i: int) -> dev.PtMeasurement:
        """
        Get pt_measurement at i
        :param i: index
        :return: PfMeasurement
        """
        return self._pt_measurements[i]

    def get_pt_measurement_names(self) -> StrVec:
        """
        Array of pt_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._pt_measurements])

    def add_pt_measurement(self, obj: dev.PtMeasurement):
        """
        Add a PfMeasurement object
        :param obj: PfMeasurement instance
        """

        if self.time_profile is not None:
            obj.ensure_profiles_exist(self.time_profile)
        self._pt_measurements.append(obj)

    def delete_pt_measurement(self, obj: dev.PtMeasurement) -> None:
        """
        Add a PtMeasurement object
        :param obj: PtMeasurement instance
        """
        try:
            self._pt_measurements.remove(obj)
        except ValueError:
            pass

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
            obj.ensure_profiles_exist(self.time_profile)
        self._qf_measurements.append(obj)

    def delete_qf_measurement(self, obj: dev.QfMeasurement) -> None:
        """
        Add a QfMeasurement object
        :param obj: QfMeasurement instance
        """
        try:
            self._qf_measurements.remove(obj)
        except ValueError:
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # Qt measurement
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def qt_measurements(self) -> List[dev.QtMeasurement]:
        """
        Get list of Qt measurements
        :return:
        """
        return self._qt_measurements

    @qt_measurements.setter
    def qt_measurements(self, value: List[dev.QtMeasurement]):
        self._qt_measurements = value

    def get_qt_measurements(self) -> List[dev.QtMeasurement]:
        """
        List of qt_measurements
        :return: List[dev.QtMeasurement]
        """
        return self._qt_measurements

    def get_qt_measurements_number(self) -> int:
        """
        Size of the list of qt_measurements
        :return: size of qt_measurements
        """
        return len(self._qt_measurements)

    def get_qt_measurement_at(self, i: int) -> dev.QtMeasurement:
        """
        Get qt_measurement at i
        :param i: index
        :return: QtMeasurement
        """
        return self._qt_measurements[i]

    def get_qt_measurement_names(self) -> StrVec:
        """
        Array of qt_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._qt_measurements])

    def add_qt_measurement(self, obj: dev.QtMeasurement):
        """
        Add a QtMeasurement object
        :param obj: QtMeasurement instance
        """

        if self.time_profile is not None:
            obj.ensure_profiles_exist(self.time_profile)
        self._qt_measurements.append(obj)

    def delete_qt_measurement(self, obj: dev.QtMeasurement) -> None:
        """
        Add a QtMeasurement object
        :param obj: QtMeasurement instance
        """
        try:
            self._qt_measurements.remove(obj)
        except ValueError:
            pass

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
            obj.ensure_profiles_exist(self.time_profile)
        self._if_measurements.append(obj)

    def delete_if_measurement(self, obj: dev.IfMeasurement) -> None:
        """
        Add a IfMeasurement object
        :param obj: IfMeasurement instance
        """
        try:
            self._if_measurements.remove(obj)
        except ValueError:
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # It measurement
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def it_measurements(self) -> List[dev.ItMeasurement]:
        """
        Get list of It measurements
        :return:
        """
        return self._it_measurements

    @it_measurements.setter
    def it_measurements(self, value: List[dev.ItMeasurement]):
        self._it_measurements = value

    def get_it_measurements(self) -> List[dev.ItMeasurement]:
        """
        List of it_measurements
        :return: List[dev.ItMeasurement]
        """
        return self._it_measurements

    def get_it_measurements_number(self) -> int:
        """
        Size of the list of it_measurements
        :return: size of it_measurements
        """
        return len(self._it_measurements)

    def get_it_measurement_at(self, i: int) -> dev.ItMeasurement:
        """
        Get it_measurement at i
        :param i: index
        :return: ItMeasurement
        """
        return self._it_measurements[i]

    def get_it_measurement_names(self) -> StrVec:
        """
        Array of it_measurement names
        :return: StrVec
        """
        return np.array([e.name for e in self._it_measurements])

    def add_it_measurement(self, obj: dev.ItMeasurement):
        """
        Add a ItMeasurement object
        :param obj: ItMeasurement instance
        """

        if self.time_profile is not None:
            obj.ensure_profiles_exist(self.time_profile)
        self._it_measurements.append(obj)

    def delete_it_measurement(self, obj: dev.ItMeasurement) -> None:
        """
        Add a ItMeasurement object
        :param obj: ItMeasurement instance
        """
        try:
            self._it_measurements.remove(obj)
        except ValueError:
            pass

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
                obj.set_var_factory(self._var_factory)
            else:
                print('The template is not an overhead line!')

    def delete_line_template_dependency(self, obj):
        """
        Search a branch template from lines and transformers and delete_with_dialogue it
        :param obj:
        :return:
        """
        for elm in self._lines:
            if elm.template == obj:
                elm.template = None

        for elm in self._dc_lines:
            if elm.template == obj:
                elm.template = None

    def delete_overhead_line(self, obj: dev.OverheadLineType):
        """
        Delete tower from the collection
        :param obj: OverheadLineType
        """

        self.delete_line_template_dependency(obj=obj)

        try:
            self._overhead_line_types.remove(obj)
        except ValueError:
            pass

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
            for elm in tower.wires_in_tower.data:
                if elm.wire == obj:
                    elm.wire = None
        try:
            self._wire_types.remove(obj)
        except ValueError:
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # Underground cable physical types
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def underground_cable_constructions(self) -> List[dev.UndergroundCableType]:
        """Return the physical single-core cable catalogue.

        :return: Physical cable catalogue.
        """
        return self._underground_cable_constructions

    @underground_cable_constructions.setter
    def underground_cable_constructions(self, value: List[dev.UndergroundCableType]) -> None:
        """Replace the physical single-core cable catalogue.

        :param value: New physical cable catalogue.
        :return: None.
        """
        self._underground_cable_constructions = value

    def add_underground_cable(self, obj: dev.UndergroundCableType) -> None:
        """Add one physical cable construction.

        :param obj: Cable construction to add.
        :return: None.
        """
        if isinstance(obj, dev.UndergroundCableType):
            self._underground_cable_constructions.append(obj)
        else:
            print('The catalogue entry is not an underground cable type!')

    def delete_underground_cable(self, obj: dev.UndergroundCableType) -> None:
        """Delete one physical cable and clear system references to it.

        :param obj: Cable construction to delete.
        :return: None.
        """
        system: dev.UndergroundLineType
        relationship: dev.CableInSystem
        for system in self._underground_cable_types:
            for relationship in system.cables_in_system.data:
                if relationship.cable == obj:
                    relationship.cable = None
                else:
                    pass
        try:
            self._underground_cable_constructions.remove(obj)
        except ValueError:
            pass

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
                obj.set_var_factory(self._var_factory)
            else:
                print('The template is not an underground line!')

    def delete_underground_line(self, obj):
        """
        Delete underground line
        :param obj:
        """
        self.delete_line_template_dependency(obj=obj)

        try:
            self._underground_cable_types.remove(obj)
        except ValueError:
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # DC cable type
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def dc_cable_types(self) -> List[dev.UndergroundLineType]:
        """Deprecated alias of the common Cable System catalogue (AC and DC)."""
        return self.underground_cable_types

    @dc_cable_types.setter
    def dc_cable_types(self, value: List[dev.UndergroundLineType]) -> None:
        self.underground_cable_types = value

    def add_dc_cable_type(self, obj: dev.UndergroundLineType) -> None:
        """Compatibility alias; register the object in Cable System."""
        self.add_underground_line(obj)

    def delete_dc_cable_type(self, obj: dev.UndergroundLineType) -> None:
        """Compatibility alias; clear AC/DC references and remove the system."""
        self.delete_underground_line(obj)

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
                obj.set_var_factory(self._var_factory)
            else:
                print('The template is not a sequence line!')

    def delete_sequence_line(self, obj):
        """
        Delete sequence line from the collection
        :param obj:
        """
        self.delete_line_template_dependency(obj=obj)

        try:
            self._sequence_line_types.remove(obj)
        except ValueError:
            pass

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
                obj.set_var_factory(self._var_factory)
            else:
                print('The template is not a transformer!')

    def delete_transformer_template_dependency(self, obj: dev.TransformerType):
        """
        Search a branch template from lines and transformers and delete_with_dialogue it
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

        try:
            self._transformer_types.remove(obj)
        except ValueError:
            pass

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
            obj.ensure_profiles_exist(self.time_profile)
        self._branch_groups.append(obj)

    def delete_branch_group(self, obj: dev.BranchGroup) -> None:
        """
        Add a BranchGroup object
        :param obj: BranchGroup instance
        """
        try:
            self._branch_groups.remove(obj)
        except ValueError:
            pass

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

        try:
            self._substations.remove(obj)
        except ValueError:
            pass

    def merge_substations(self, selected_objects: List[dev.Substation]):
        """
        Merge selected substations into the first one
        :param selected_objects:
        :return:
        """
        if len(selected_objects) > 1:
            # delete the first SE from the list and keep it
            base = selected_objects.pop(0)

            for elm in self.voltage_levels:
                if elm.substation in selected_objects:
                    elm.substation = base

            for elm in self.buses:
                if elm.substation in selected_objects:
                    elm.substation = base

            for obj in selected_objects:
                self.delete_substation(obj=obj)

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

        try:
            self._areas.remove(obj)
        except ValueError:
            pass

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

        try:
            self._zones.remove(obj)
        except ValueError:
            pass

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

        try:
            self._countries.remove(obj)
        except ValueError:
            pass

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
            obj.ensure_profiles_exist(self.time_profile)
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

        try:
            self._communities.remove(obj)
        except ValueError:
            pass

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
            obj.ensure_profiles_exist(self.time_profile)
        self._regions.append(obj)

    def delete_region(self, obj: dev.Region) -> None:
        """
        Add a Region object
        :param obj: Region instance
        """

        for elm in self._municipalities:
            if elm.region == obj:
                elm.region = None

        try:
            self._regions.remove(obj)
        except ValueError:
            pass

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
            obj.ensure_profiles_exist(self.time_profile)
        self._municipalities.append(obj)

    def delete_municipality(self, obj: dev.Municipality) -> None:
        """
        Add a Municipality object
        :param obj: Municipality instance
        """

        for elm in self._substations:
            if elm.municipality == obj:
                elm.municipality = None

        try:
            self._municipalities.remove(obj)
        except ValueError:
            pass

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

    def delete_contingency(self, obj, del_group: bool = False):
        """
        Delete zone
        :param obj: index
        :param del_group: Delete group if empty?
        """
        try:
            self._contingencies.remove(obj)
        except ValueError:
            pass

        if del_group:
            to_del = list()
            for grp in self.contingency_groups:
                found = False
                for elm in self.contingencies:
                    if elm.group == grp:
                        found = True

                if not found:
                    to_del.append(grp)

            for grp in to_del:
                self.delete_contingency_group(grp)

    def get_contingencies_by_group(self) -> Dict[dev.ContingencyGroup, List[dev.Contingency]]:
        """
        Get a dictionary of contingency groups as keys and a list of contingencies as value
        :return: dict[contingency group] -> [contingencies list]
        """
        d: Dict[dev.ContingencyGroup, List[dev.Contingency]] = dict()

        for con in self.contingencies:
            lst = d.get(con.group, None)

            if lst is None:
                d[con.group] = [con]
            else:
                lst.append(con)

        return d

    def get_contingency_branch_indices_by_group(
            self,
            add_vsc: bool = True,
            add_hvdc: bool = True,
            add_switch: bool = False) -> Dict[dev.ContingencyGroup, List[int]]:
        """
        Get a dictionary of contingency groups as keys and a list of contingencies as value
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: dict[contingency group] -> [contingencies list]
        """
        d: Dict[dev.ContingencyGroup, List[int]] = dict()

        br_idtag_dict = self.get_branches_idtag_index_dict(add_vsc=add_vsc,
                                                           add_hvdc=add_hvdc,
                                                           add_switch=add_switch)

        for con in self.contingencies:

            idx = br_idtag_dict.get(con.device_idtag, None)

            if idx is not None:
                lst = d.get(con.group, None)

                if lst is None:
                    d[con.group] = [idx]
                else:
                    lst.append(idx)

        return d

    # ------------------------------------------------------------------------------------------------------------------
    # Contingency group
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

    def get_contingency_groups_active(self) -> List[dev.ContingencyGroup]:
        """
        Get contingency_groups
        :return:List[dev.ContingencyGroup]
        """
        return [e for e in self._contingency_groups if e.active]

    def get_contingency_groups_number(self) -> int:
        """

        :return:
        """
        return len(self._contingency_groups)

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
        try:
            self._contingency_groups.remove(obj)
        except ValueError:
            pass

        # delete_with_dialogue references in the remedial action groups
        for rag in self._remedial_action_groups:
            if rag.conn_group is not None:
                if rag.conn_group == obj:
                    rag.conn_group = None

        to_del = [con for con in self._contingencies if con.group == obj]
        for con in to_del:
            self.delete_contingency(con)

    def get_contingency_group_names(self) -> StrVec:
        """
        Get list of contingency group names
        :return:
        """
        return np.array([e.name for e in self._contingency_groups])

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
                                  grouping_elements: List[Union[dev.Area, dev.Zone,
                                  dev.Country, dev.Community, dev.Region, dev.Municipality]]
                                  ) -> List[dev.ContingencyGroup]:
        """
        Get a filtered set of ContingencyGroups
        :param grouping_elements: list of zones, areas or countries where to locate the contingencies
        :return: Sorted group filtered ContingencyGroup elements
        """

        # declare the results
        filtered_groups_idx: Set[int] = set()

        group2index = {g: i for i, g in enumerate(self._contingency_groups)}

        # get a dictionary of all objects
        all_devices, dict_ok = self.get_all_elements_dict()

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

    def get_contingency_groups_sensitive_to_monitoring(self, LODF: Mat, threshold: float) -> BoolVec:
        """
        Get a list of contingency groups that are sensitive to the monitoring rule
        :param LODF: LODF matrix (nbr, nbr)
        :param threshold: LODF threshold
        :return: vector of sensitive status
        """

        d = self.get_contingency_branch_indices_by_group()
        sensitive: BoolVec = np.zeros(self.get_contingency_groups_number(), dtype=bool)

        for cg_idx, con_group in enumerate(self.contingency_groups):  # for every contingency group

            # get the branch indices of this contingency group
            branch_indices = d[con_group]

            sensitive[cg_idx] = False

            if con_group.active:
                i = 0
                for elm in self.get_branches_iter(add_vsc=False, add_hvdc=False, add_switch=True):  # for every branch

                    if elm.monitor_loading:  # if monitored

                        # check if any contingency branch is sensitive to the monitored branch

                        for j in branch_indices:
                            if abs(LODF[i, j]) >= threshold:
                                sensitive[cg_idx] = True

                    i += 1

        return sensitive

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
        try:
            self._investments_groups.remove(obj)
        except ValueError:
            pass

        to_del = [invst for invst in self._investments if invst.group == obj]
        for invst in to_del:
            self.delete_investment(invst)

    def get_investments_by_groups(self) -> List[Tuple[dev.InvestmentsGroup, List[dev.Investment]]]:
        """
        Get a dictionary of investments groups and their
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

    def get_investment_by_groups_index_dict(self) -> Dict[int, List[dev.Investment]]:
        """
        Get a dictionary of investments groups
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

    def get_investment_by_groups_dict(self) -> Dict[dev.InvestmentsGroup, List[dev.Investment]]:
        """
        Get a dictionary of investments groups
        :return: Dict[investment group index] = list of investments
        """

        res: Dict[dev.InvestmentsGroup, List[dev.Investment]] = dict()
        for inv in self._investments:
            if inv.group is not None:
                inv_list = res.get(inv.group, None)
                if inv_list is None:
                    res[inv.group] = [inv]
                else:
                    inv_list.append(inv)

        return res

    def get_capex_by_investment_group(self) -> Vec:
        """
        Get array of CAPEX costs per investment group
        :return:
        """

        # we initialize with the capex of the group, then we add the capex of the individual investments
        capex: Vec = np.array([elm.CAPEX for elm in self.investments_groups])

        # pre-compute the capex of each investment group
        d = self.get_investment_by_groups_index_dict()

        for i, investments in d.items():
            for investment in investments:
                capex[i] += investment.CAPEX

        return capex

    def restore_investments(self):
        """
        Restore investments to the circuit by removing them one by one. This is useful to restore the dependencies of
        the investments with the devices after a copy or a load.
        """

        for inv in self.investments:
            if inv.device is not None:
                inv.device.active = False
                inv.device.active_prof.fill(False)

    def apply_investments_group(
            self,
            inv_group: dev.InvestmentsGroup,
            inv_groups_dict: Dict[dev.InvestmentsGroup, List[dev.Investment]] | None = None) -> Logger:
        """
        Apply the investments that shall be in operation at the model date
        :param inv_group:
        :param inv_groups_dict:
        :return: Logger
        """
        logger = Logger()

        # get the model unix timestamp
        model_unix = self.snapshot_time.timestamp()

        logger.add_info(msg="Model date", value=str(self.snapshot_time))

        if inv_groups_dict is None:
            inv_groups_dict = self.get_investment_by_groups_dict()

        investments = inv_groups_dict[inv_group]

        for investment in investments:
            if investment.commissioning_date <= model_unix <= investment.decommissioning_date:
                self.apply_investment(investment=investment, logger=logger)

        return logger

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

    def delete_investment(self, obj: dev.Investment, del_group: bool = False):
        """
        Delete zone
        :param obj: index
        :param del_group: delete_with_dialogue the group?
        """
        try:
            self._investments.remove(obj)
        except ValueError:
            pass

        if del_group:
            to_del = list()
            for grp in self.investments_groups:
                found = False
                for elm in self.investments:
                    if elm.group == grp:
                        found = True

                if not found:
                    to_del.append(grp)

            for grp in to_del:
                self.delete_investment_groups(grp)

    def apply_investment(self, investment: dev.Investment, logger: Logger):
        """
        Apply investment
        :param investment:
        :param logger:
        :return:
        """
        if investment.device is None:
            logger.add_error(msg="No device",
                             device_class="Investment",
                             device_property="device")
        else:
            prp = investment.device.get_property_by_name(investment.prop)
            try:
                val = prp.tpe(investment.value)
                investment.device.set_value(prop=prp, t_idx=None, value=val)
                logger.add_info(msg="Activated",
                                device_class="Investment",
                                device=investment.name,
                                value=investment.device.name)
            except ValueError as e:
                logger.add_error(msg="Cannot cast value",
                                 device_class="Investment",
                                 device_property="device")

    def apply_all_relevant_investments(self) -> Logger:
        """
        Apply the investments that shall be in operation at the model date
        :return: Logger
        """
        logger = Logger()

        # get the model unix timestamp
        model_unix = self.snapshot_time.timestamp()

        logger.add_info(msg="Model date", value=str(self.snapshot_time))

        for investment in self.investments:
            if investment.commissioning_date <= model_unix <= investment.decommissioning_date:
                self.apply_investment(investment=investment, logger=logger)

        # TODO: apply to the time series values

        return logger

    # ------------------------------------------------------------------------------------------------------------------
    # Rms Events group
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def rms_events_groups(self) -> List[dev.RmsEventsGroup]:
        """

        :return:
        """
        return self._rms_events_groups

    @rms_events_groups.setter
    def rms_events_groups(self, value: List[dev.RmsEventsGroup]):
        self._rms_events_groups = value

    def get_rms_events_groups_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([e.name for e in self._rms_events_groups])

    def add_rms_events_group(self, obj: dev.RmsEventsGroup):
        """
        Add rms events group
        :param obj: RmsEventsGroup
        """
        self._rms_events_groups.append(obj)

    def delete_rms_events_group(self, obj: dev.RmsEventsGroup):
        """
        Delete zone
        :param obj: index
        """
        try:
            self._rms_events_groups.remove(obj)
        except ValueError:
            pass

        to_del = [evt for evt in self._rms_events if evt.group == obj]
        for evt in to_del:
            self.delete_rms_event(evt)

    def get_rms_event_by_groups(self) -> List[Tuple[dev.RmsEventsGroup, List[dev.RmsEvent]]]:
        """
        Get a dictionary of RMS event groups and their
        :return: list of RMS event groups and their list of associated RMS events
        """
        d = {e: list() for e in self._rms_events_groups}

        for evt in self._rms_events:
            evt_list = d.get(evt.group, None)

            if evt_list is not None:
                evt_list.append(evt)

        # second pass, sort it
        res = list()
        for evt_group in self._rms_events_groups:

            inv_list = d.get(evt_group, None)

            if inv_list is not None:
                res.append((evt_group, inv_list))
            else:
                res.append((evt_group, list()))

        return res

    def get_rms_event_by_groups_index_dict(self) -> Dict[int, List[dev.RmsEvent]]:
        """
        Get a dictionary of investments groups
        :return: Dict[investment group index] = list of investments
        """
        d = {e: idx for idx, e in enumerate(self._rms_events_groups)}

        res = dict()
        for evt in self._rms_events:
            inv_group_idx = d.get(evt.group, None)
            inv_list = res.get(inv_group_idx, None)
            if inv_list is None:
                res[inv_group_idx] = [evt]
            else:
                inv_list.append(evt)

        return res

    # ------------------------------------------------------------------------------------------------------------------
    # RmsEvent
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def rms_events(self) -> List[dev.RmsEvent]:
        """

        :return:
        """
        return self._rms_events

    @rms_events.setter
    def rms_events(self, value: List[dev.RmsEvent]):
        self._rms_events = value

    def add_rms_event(self, obj: dev.RmsEvent):
        """
        Add rms_event
        :param obj: RmsEvent
        """
        self._rms_events.append(obj)

    def delete_rms_event(self, obj: dev.RmsEvent, del_group: bool = False):
        """
        Delete zone
        :param obj: index
        :param del_group: delete_with_dialogue the group?
        """
        try:
            self._rms_events.remove(obj)
        except ValueError:
            pass

        if del_group:
            to_del = list()
            for grp in self.rms_events_groups:
                found = False
                for elm in self.rms_events:
                    if elm.group == grp:
                        found = True

                if not found:
                    to_del.append(grp)

            for grp in to_del:
                self.delete_rms_events_group(grp)

    # ------------------------------------------------------------------------------------------------------------------
    # Emt Events group
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def emt_events_groups(self) -> List[dev.EmtEventsGroup]:
        """

        :return:
        """
        return self._emt_events_groups

    @emt_events_groups.setter
    def emt_events_groups(self, value: List[dev.EmtEventsGroup]):
        self._emt_events_groups = value

    def get_emt_events_groups_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([e.name for e in self._emt_events_groups])

    def add_emt_events_group(self, obj: dev.EmtEventsGroup):
        """
        Add emt events group
        :param obj: EmtEventsGroup
        """
        self._emt_events_groups.append(obj)

    def delete_emt_events_group(self, obj: dev.EmtEventsGroup):
        """
        Delete zone
        :param obj: index
        """
        try:
            self._emt_events_groups.remove(obj)
        except ValueError:
            pass

        to_del = [evt for evt in self._emt_events if evt.group == obj]
        for evt in to_del:
            self.delete_emt_event(evt)

    def get_emt_event_by_groups(self) -> List[Tuple[dev.EmtEventsGroup, List[dev.EmtEvent]]]:
        """
        Get a dictionary of EMT event groups and their
        :return: list of EMT event groups and their list of associated EMT events
        """
        d = {e: list() for e in self._emt_events_groups}

        for evt in self._emt_events:
            evt_list = d.get(evt.group, None)

            if evt_list is not None:
                evt_list.append(evt)

        res = list()
        for evt_group in self._emt_events_groups:

            inv_list = d.get(evt_group, None)

            if inv_list is not None:
                res.append((evt_group, inv_list))
            else:
                res.append((evt_group, list()))

        return res

    def get_emt_event_by_groups_index_dict(self) -> Dict[int, List[dev.EmtEvent]]:
        """
        Get a dictionary of EMT event groups
        :return: Dict[EMT event group index] = list of EMT events
        """
        d = {e: idx for idx, e in enumerate(self._emt_events_groups)}

        res = dict()
        for evt in self._emt_events:
            inv_group_idx = d.get(evt.group, None)
            inv_list = res.get(inv_group_idx, None)
            if inv_list is None:
                res[inv_group_idx] = [evt]
            else:
                inv_list.append(evt)

        return res

    # ------------------------------------------------------------------------------------------------------------------
    # EmtEvent
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def emt_events(self) -> List[dev.EmtEvent]:
        """

        :return:
        """
        return self._emt_events

    @emt_events.setter
    def emt_events(self, value: List[dev.EmtEvent]):
        self._emt_events = value

    def add_emt_event(self, obj: dev.EmtEvent):
        """
        Add emt_event
        :param obj: EmtEvent
        """
        self._emt_events.append(obj)

    def delete_emt_event(self, obj: dev.EmtEvent, del_group: bool = False):
        """
        Delete zone
        :param obj: index
        :param del_group: delete_with_dialogue the group?
        """
        try:
            self._emt_events.remove(obj)
        except ValueError:
            pass

        if del_group:
            to_del = list()
            for grp in self.emt_events_groups:
                found = False
                for elm in self.emt_events:
                    if elm.group == grp:
                        found = True

                if not found:
                    to_del.append(grp)

            for grp in to_del:
                self.delete_emt_events_group(grp)

    # ------------------------------------------------------------------------------------------------------------------
    # Dynamic Plot
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def dynamic_plots(self) -> List[dev.DynamicPlot]:
        """

        :return:
        """
        return self._dynamic_plots

    @dynamic_plots.setter
    def dynamic_plots(self, value: List[dev.DynamicPlot]):
        self._dynamic_plots = value

    def get_dynamic_plots_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([e.name for e in self._dynamic_plots])

    def add_dynamic_plot(self, obj: dev.DynamicPlot):
        """
        Add dynamic plot
        :param obj: DynamicPlot
        """
        self._dynamic_plots.append(obj)

    def delete_dynamic_plot(self, obj: dev.DynamicPlot):
        """
        Delete dynamic plot
        :param obj: index
        """
        try:
            self._dynamic_plots.remove(obj)
        except ValueError:
            pass

        to_del = [entry for entry in self._dynamic_plot_entries if entry.plot == obj]
        for entry in to_del:
            self.delete_dynamic_plot_entry(entry)

    def get_dynamic_plot_entries_by_plot(self) -> List[Tuple[dev.DynamicPlot, List[dev.DynamicPlotEntry]]]:
        """
        Get a dictionary of dynamic plots and their
        :return: list of dynamic plots and their list of associated plot entries
        """
        d = {e: list() for e in self._dynamic_plots}

        for entry in self._dynamic_plot_entries:
            entry_list = d.get(entry.plot, None)

            if entry_list is not None:
                entry_list.append(entry)

        res = list()
        for plot in self._dynamic_plots:

            inv_list = d.get(plot, None)

            if inv_list is not None:
                res.append((plot, inv_list))
            else:
                res.append((plot, list()))

        return res

    def get_dynamic_plot_entries_by_plot_index_dict(self) -> Dict[int, List[dev.DynamicPlotEntry]]:
        """
        Get a dictionary of dynamic plots
        :return: Dict[dynamic plot index] = list of dynamic plot entries
        """
        d = {e: idx for idx, e in enumerate(self._dynamic_plots)}

        res = dict()
        for entry in self._dynamic_plot_entries:
            inv_group_idx = d.get(entry.plot, None)
            inv_list = res.get(inv_group_idx, None)
            if inv_list is None:
                res[inv_group_idx] = [entry]
            else:
                inv_list.append(entry)

        return res

    # ------------------------------------------------------------------------------------------------------------------
    # DynamicPlotEntry
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def dynamic_plot_entries(self) -> List[dev.DynamicPlotEntry]:
        """

        :return:
        """
        return self._dynamic_plot_entries

    @dynamic_plot_entries.setter
    def dynamic_plot_entries(self, value: List[dev.DynamicPlotEntry]):
        self._dynamic_plot_entries = value

    def add_dynamic_plot_entry(self, obj: dev.DynamicPlotEntry):
        """
        Add dynamic plot entry
        :param obj: DynamicPlotEntry
        """
        self._dynamic_plot_entries.append(obj)

    def delete_dynamic_plot_entry(self, obj: dev.DynamicPlotEntry):
        """
        Delete dynamic plot entry
        :param obj: index
        """
        try:
            self._dynamic_plot_entries.remove(obj)
        except ValueError:
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # Remedial action
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def remedial_actions(self) -> List[dev.RemedialAction]:
        """
        Get list of remedial actions
        :return:
        """
        return self._remedial_actions

    @remedial_actions.setter
    def remedial_actions(self, value: List[dev.RemedialAction]):
        self._remedial_actions = value

    def get_remedial_action_number(self) -> int:
        """
        Get number of remedial actions
        :return:
        """
        return len(self._remedial_actions)

    def add_remedial_action(self, obj: dev.RemedialAction):
        """
        Add a remedial actions
        :param obj: RemedialAction
        """
        self._remedial_actions.append(obj)

    def delete_remedial_action(self, obj, del_group: bool = False):
        """
        Delete RemedialAction
        :param del_group: Delete the group?
        :param obj: index
        """
        try:
            self._remedial_actions.remove(obj)
        except ValueError:
            pass

        if del_group:
            to_del = list()
            for grp in self.remedial_action_groups:
                found = False
                for elm in self.remedial_actions:
                    if elm.group == grp:
                        found = True

                if not found:
                    to_del.append(grp)

            for grp in to_del:
                self.delete_remedial_action_group(grp)

    # ------------------------------------------------------------------------------------------------------------------
    # Remedial Actions group
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def remedial_action_groups(self) -> List[dev.RemedialActionGroup]:
        """
        Get list of contingency groups
        :return:
        """
        return self._remedial_action_groups

    @remedial_action_groups.setter
    def remedial_action_groups(self, value: List[dev.RemedialActionGroup]):
        self._remedial_action_groups = value

    def get_remedial_action_groups(self) -> List[dev.RemedialActionGroup]:
        """
        Get contingency_groups
        :return:List[dev.ContingencyGroup]
        """
        return self._remedial_action_groups

    def get_remedial_action_groups_number(self) -> int:
        """

        :return:
        """
        return len(self._remedial_action_groups)

    def add_remedial_action_group(self, obj: dev.RemedialActionGroup):
        """
        Add _remedial_action group
        :param obj: ContingencyGroup
        """
        self._remedial_action_groups.append(obj)

    def delete_remedial_action_group(self, obj: dev.RemedialActionGroup):
        """
        Delete contingency group
        :param obj: ContingencyGroup
        """
        try:
            self._remedial_action_groups.remove(obj)
        except ValueError:
            pass

        to_del = [con for con in self._contingencies if con.group == obj]
        for con in to_del:
            self.delete_contingency(con)

    def get_remedial_action_group_names(self) -> List[str]:
        """
        Get list of contingency group names
        :return:
        """
        return [e.name for e in self._remedial_action_groups]

    def get_remedial_action_groups_dict(self) -> Dict[str, List[dev.RemedialAction]]:
        """
        Get a dictionary of group idtags related to list of contingencies
        :return:
        """
        d = dict()

        for cnt in self._remedial_actions:
            if cnt.group.idtag not in d:
                d[cnt.group.idtag] = [cnt]
            else:
                d[cnt.group.idtag].append(cnt)

        return d

    def set_remedial_actions(self, remedial_actions: List[dev.RemedialAction]):
        """
        Set contingencies and contingency groups to circuit
        :param remedial_actions: List of contingencies
        :return:
        """

        # Get a list of devices susceptible to be included in contingencies / remedial actions
        devices = self.get_contingency_devices()
        groups = dict()

        devices_code_dict = {d.code: d for d in devices}
        devices_key_dict = {d.idtag: d for d in devices}
        devices_dict = {**devices_code_dict, **devices_key_dict}

        logger = Logger()

        for ra in remedial_actions:
            if ra.code in devices_dict.keys() or ra.idtag in devices_dict.keys():
                # ensure proper device_idtag and code
                element = devices_dict[ra.code]
                ra.device_idtag = element.idtag
                ra.code = element.code

                self._remedial_actions.append(ra)

                if ra.group.idtag not in groups.keys():
                    groups[ra.group.idtag] = ra.group
            else:
                logger.add_info(
                    msg='Remedial action element not found in circuit',
                    device=ra.code,
                )

        for group in groups.values():
            self._remedial_action_groups.append(group)

        return logger

    def get_remedial_action_groups_in(
            self,
            grouping_elements: List[Union[dev.Area, dev.Country, dev.Zone]]
    ) -> List[dev.RemedialActionGroup]:
        """
        Get a filtered set of ContingencyGroups
        :param grouping_elements: list of zones, areas or countries where to locate the contingencies
        :return: Sorted group filtered ContingencyGroup elements
        """

        # declare the reults
        filtered_groups_idx: Set[int] = set()

        group2index = {g: i for i, g in enumerate(self._remedial_action_groups)}

        # get a dictionary of all objects
        all_devices, dict_ok = self.get_all_elements_dict()

        # get the buses that match the filtering
        buses = self.get_buses_by(filter_elements=grouping_elements)

        for contingency in self._remedial_actions:

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

        return [self._remedial_action_groups[i] for i in sorted(filtered_groups_idx)]

    # ------------------------------------------------------------------------------------------------------------------
    # Short Circuit Events
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def short_circuit_event(self) -> List[dev.ShortCircuitEvent]:
        """
        Get list of ShortCircuitDefinition
        :return:
        """
        return self._short_circuit_events

    @short_circuit_event.setter
    def short_circuit_event(self, value: List[dev.ShortCircuitEvent]):
        self._short_circuit_events = value

    def add_short_circuit_event(self, obj: dev.ShortCircuitEvent):
        """
        Add short_circuit_definitions
        :param obj: ShortCircuitDefinition
        """
        self._short_circuit_events.append(obj)

    def delete_short_circuit_event(self, obj: dev.ShortCircuitEvent):
        """
        Delete ShortCircuitDefinition
        :param obj: index
        """

        try:
            self._short_circuit_events.remove(obj)
        except ValueError:
            pass

    def get_short_circuit_event_names(self) -> StrVec:
        """
        Get the short circuit definition names
        :return: Names
        """
        return np.array([elm.name for elm in self._short_circuit_events])

    def get_short_circuit_event_number(self) -> int:
        """
        Get the short circuit definition names
        :return: Names
        """
        return len(self._short_circuit_events)

    def short_circuit_event_exist(self, scd: dev.ShortCircuitEvent) -> bool:
        """
        Check if a short circuit definition has been added already
        :param scd: ShortCircuitDefinition
        :return: Bool
        """
        for elm in self._short_circuit_events:
            if elm.device_idtag == scd.device_idtag and elm.fault_type == scd.fault_type:
                return True
        return False

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

    def delete_technology(self, obj: dev.Technology):
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

        try:
            self._technologies.remove(obj)
        except ValueError:
            pass

    def get_technology_indexing_dict(self) -> Dict[str, int]:
        """
        Get a dictionary that relates the fuel uuid's with their index
        :return: Dict[str, int]
        """
        index_dict: Dict[str, int] = dict()
        for k, elm in enumerate(self._technologies):
            index_dict[elm.idtag] = k  # associate the idtag to the index
        return index_dict

    def get_technology_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([elm.name for elm in self._technologies])

    # ------------------------------------------------------------------------------------------------------------------
    # Owners
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def owners(self) -> List[dev.Owner]:
        """
        Get list of owners
        :return:
        """
        return self._owners

    @owners.setter
    def owners(self, value: List[dev.Owner]):
        self._owners = value

    def add_owner(self, obj: dev.Owner):
        """
        Add owner
        :param obj: Owner
        """
        self._owners.append(obj)

    def delete_owner(self, obj: dev.Owner):
        """
        Delete owner
        :param obj: index
        """

        for elm_list in self.get_injection_devices_lists():
            for elm in elm_list:
                to_del = list()
                for assoc in elm.owners:
                    if assoc.api_object == obj:
                        to_del.append(assoc)

                for assoc in to_del:
                    elm.owners.remove(assoc)

        try:
            self._owners.remove(obj)
        except ValueError:
            pass

    def get_owner_indexing_dict(self) -> Dict[str, int]:
        """
        Get a dictionary that relates the fuel uuid's with their index
        :return: Dict[str, int]
        """
        index_dict: Dict[str, int] = dict()
        for k, elm in enumerate(self._owners):
            index_dict[elm.idtag] = k  # associate the idtag to the index
        return index_dict

    def get_owner_names(self) -> StrVec:
        """

        :return:
        """
        return np.array([elm.name for elm in self._owners])

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
            obj.ensure_profiles_exist(self.time_profile)
        self._modelling_authorities.append(obj)

    def delete_modelling_authority(self, obj: dev.ModellingAuthority) -> None:
        """
        Add a ModellingAuthority object
        :param obj: ModellingAuthority instance
        """
        try:
            self._modelling_authorities.remove(obj)
        except ValueError:
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # Facility
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def facilities(self) -> List[dev.Facility]:
        """
        Get the list of facilities
        :return:
        """
        return self._facilities

    @facilities.setter
    def facilities(self, value: List[dev.Facility]):
        self._facilities = value

    def get_facilities(self) -> List[dev.Facility]:
        """
        Get list of areas
        :return: List[dev.Facility]
        """
        return self._facilities

    def get_facility_names(self) -> StrVec:
        """
        Get array of area names
        :return: StrVec
        """
        return np.array([a.name for a in self._facilities])

    def get_facility_number(self) -> int:
        """
        Get number of facilities
        :return: number of facilities
        """
        return len(self._facilities)

    def add_facility(self, obj: dev.Facility):
        """
        Add facility
        :param obj: Facility object
        """
        self._facilities.append(obj)

    def delete_facility(self, obj: dev.Facility):
        """
        Delete area
        :param obj: Area
        """
        for elm in self.get_injection_devices_iter():
            if elm.facility == obj:
                elm.facility = None

        try:
            self._facilities.remove(obj)
        except ValueError:
            pass

    # ------------------------------------------------------------------------------------------------------------------
    # Market unit groups
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def market_unit_groups(self) -> List[dev.MarketUnitsGroup]:
        """
        Get the list of market unit groups
        :return:
        """
        return self._market_unit_groups

    @market_unit_groups.setter
    def market_unit_groups(self, value: List[dev.MarketUnitsGroup]):
        self._market_unit_groups = value

    def get_market_unit_groups(self) -> List[dev.MarketUnitsGroup]:
        """
        Get list of market unit groups
        :return: List[dev.MarketUnitsGroup]
        """
        return self._market_unit_groups

    def get_market_unit_group_names(self) -> StrVec:
        """
        Get array of market unit group names
        :return: StrVec
        """
        return np.array([a.name for a in self._market_unit_groups])

    def get_market_unit_groups_names(self) -> StrVec:
        """
        Get array of market unit group names
        :return: StrVec
        """
        return self.get_market_unit_group_names()

    def get_market_unit_group_number(self) -> int:
        """
        Get number of market unit groups
        :return: number of market unit groups
        """
        return len(self._market_unit_groups)

    def get_market_unit_groups_number(self) -> int:
        """
        Get number of market unit groups
        :return: number of market unit groups
        """
        return len(self._market_unit_groups)

    def add_market_unit_group(self, obj: dev.MarketUnitsGroup):
        """
        Add market unit group
        :param obj: MarketUnitsGroup object
        """
        self._market_unit_groups.append(obj)

    def delete_market_unit_group(self, obj: dev.MarketUnitsGroup):
        """
        Delete market unit group
        :param obj: MarketUnitsGroup
        """
        for elm in self._market_units:
            if elm.group == obj:
                elm.group = None

        try:
            self._market_unit_groups.remove(obj)
        except ValueError:
            pass

    def delete_market_unit_groups(self, obj: dev.MarketUnitsGroup):
        """
        Delete market unit group
        :param obj: MarketUnitsGroup
        """
        self.delete_market_unit_group(obj)

    def get_market_units_by_groups(self) -> List[Tuple[dev.MarketUnitsGroup, List[dev.MarketUnit]]]:
        """
        Get a list of market unit groups and their associated market units
        :return: list of market unit groups and their list of associated market units
        """
        d = {e: list() for e in self._market_unit_groups}

        for mu in self._market_units:
            mu_list = d.get(mu.group, None)
            if mu_list is not None:
                mu_list.append(mu)

        res = list()
        for mu_group in self._market_unit_groups:
            mu_list = d.get(mu_group, None)
            if mu_list is not None:
                res.append((mu_group, mu_list))
            else:
                res.append((mu_group, list()))

        return res

    def get_market_units_by_groups_index_dict(self) -> Dict[int, List[dev.MarketUnit]]:
        """
        Get a dictionary of market unit groups index to list of market units
        :return: Dict[market unit group index] = list of market units
        """
        d = {e: idx for idx, e in enumerate(self._market_unit_groups)}

        res = dict()
        for mu in self._market_units:
            group_idx = d.get(mu.group, None)
            if group_idx is not None:
                mu_list = res.get(group_idx, None)
                if mu_list is None:
                    res[group_idx] = [mu]
                else:
                    mu_list.append(mu)

        return res

    def get_market_unit_group_dict(self) -> Dict[str, List[dev.MarketUnit]]:
        """
        Get a dictionary of group idtags related to list of market units
        :return: Dict[str, List[dev.MarketUnit]]
        """
        d = {e.idtag: list() for e in self._market_unit_groups}

        for mu in self._market_units:
            if mu.group is not None:
                mu_list = d.get(mu.group.idtag, None)
                if mu_list is not None:
                    mu_list.append(mu)

        return d

    # ------------------------------------------------------------------------------------------------------------------
    # Market units
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def market_units(self) -> List[dev.MarketUnit]:
        """
        Get the list of market units
        :return:
        """
        return self._market_units

    @market_units.setter
    def market_units(self, value: List[dev.MarketUnit]):
        self._market_units = value

    def get_market_units(self) -> List[dev.MarketUnit]:
        """
        Get list of market units
        :return: List[dev.MarketUnit]
        """
        return self._market_units

    def get_market_unit_names(self) -> StrVec:
        """
        Get array of market unit names
        :return: StrVec
        """
        return np.array([a.name for a in self._market_units])

    def get_market_unit_number(self) -> int:
        """
        Get number of market units
        :return: number of market units
        """
        return len(self._market_units)

    def add_market_unit(self, obj: dev.MarketUnit):
        """
        Add market unit
        :param obj: MarketUnit object
        """
        self._market_units.append(obj)

    def delete_market_unit(self, obj: dev.MarketUnit):
        """
        Delete market unit
        :param obj: MarketUnit
        """
        for elm in self.get_generators():
            if elm.market_unit == obj:
                elm.market_unit = None
                elm.market_unit_prof.fill(None)

        try:
            self._market_units.remove(obj)
        except ValueError:
            pass

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

        try:
            self._fuels.remove(obj)
        except ValueError:
            pass

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

        # delete_with_dialogue the gas
        try:
            self._emission_gases.remove(obj)
        except ValueError:
            pass

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
            obj.ensure_profiles_exist(self.time_profile)

    def delete_fluid_node(self, obj: dev.FluidNode):
        """
        Delete fluid node
        :param obj: FluidNode
        """
        # delete_with_dialogue dependencies
        for fluid_path in reversed(self._fluid_paths):
            if fluid_path.source == obj or fluid_path.target == obj:
                self.delete_fluid_path(fluid_path)

        try:
            self._fluid_nodes.remove(obj)
        except ValueError:
            pass

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
            obj.ensure_profiles_exist(self.time_profile)

    def delete_fluid_path(self, obj: dev.FluidPath):
        """
        Delete fuid path
        :param obj: FluidPath
        """
        try:
            self._fluid_paths.remove(obj)
        except ValueError:
            pass

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
        try:
            self._turbines.remove(obj)
        except ValueError:
            pass

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
        try:
            self._pumps.remove(obj)
        except ValueError:
            pass

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
        try:
            self._p2xs.remove(obj)
        except ValueError:
            pass

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
        Get the list/tree of diagrams
        :return:
        """
        return self._diagrams

    @diagrams.setter
    def diagrams(self, value: Union[dev.DiagramTree, List[Union[dev.MapDiagram, dev.SchematicDiagram]]]):
        if isinstance(value, dev.DiagramTree):
            self._diagrams = value
        elif isinstance(value, (list, tuple)):
            self._diagrams = dev.DiagramTree()
            for d in value:
                self._diagrams.append(d)
        else:
            self._diagrams = value

    @property
    def diagram_tree(self) -> dev.DiagramTree:
        """
        Explicit property to access the diagram tree
        :return: DiagramTree
        """
        return self._diagrams

    @diagram_tree.setter
    def diagram_tree(self, value: dev.DiagramTree):
        self.diagrams = value

    def get_diagrams(self) -> dev.DiagramTree:
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

    def add_diagram(self,
                    diagram: Union[dev.MapDiagram, dev.SchematicDiagram],
                    folder: Optional[dev.DiagramFolder] = None):
        """
        Add diagram
        :param diagram: MapDiagram, SchematicDiagram device
        :param folder: Optional DiagramFolder
        :return:
        """
        self._diagrams.add_diagram(diagram, folder=folder)

    def remove_diagram(self, diagram: Union[dev.MapDiagram, dev.SchematicDiagram]):
        """
        Remove diagrams
        :param diagram: MapDiagram, SchematicDiagram device
        """
        try:
            self._diagrams.remove_diagram(diagram)
        except ValueError as e:
            print(e)

    # ------------------------------------------------------------------------------------------------------------------
    # Manufacturer native model providers
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def manufacturer_native_models(self) -> List[dev.ManufacturerNativeModel]:
        """Return providers before their RMS/EMT Block consumers.

        :return: Ordered manufacturer native provider catalogue.
        """
        return self._manufacturer_native_models

    @manufacturer_native_models.setter
    def manufacturer_native_models(self, value: List[dev.ManufacturerNativeModel]) -> None:
        """Replace the provider catalogue.

        :param value: Complete ordered provider list.
        :return: None.
        """
        self._manufacturer_native_models = value

    def add_manufacturer_native_model(self, obj: dev.ManufacturerNativeModel) -> None:
        """Add one canonical manufacturer native provider.

        :param obj: Provider to register.
        :return: None.
        """
        if not isinstance(obj, dev.ManufacturerNativeModel):
            raise TypeError("The provider is not a ManufacturerNativeModel")
        else:
            pass
        if self.get_manufacturer_native_model_by_idtag(obj.idtag) is not None:
            raise ValueError(f"Manufacturer native provider idtag already exists: {obj.idtag}")
        else:
            self._manufacturer_native_models.append(obj)

    def get_manufacturer_native_model_by_idtag(self,
                                                idtag: str) -> dev.ManufacturerNativeModel | None:
        """Find one provider by stable identity.

        :param idtag: Provider identifier.
        :return: Matching provider or ``None``.
        """
        provider: dev.ManufacturerNativeModel
        for provider in self._manufacturer_native_models:
            if provider.idtag == idtag:
                return provider
            else:
                pass
        return None

    def get_manufacturer_native_consumers(self,
                                          provider: dev.ManufacturerNativeModel) -> List[dev.RmsModelTemplate | dev.EmtModelTemplate]:
        """Return every template whose Block hierarchy references a provider.

        :param provider: Provider whose consumers are requested.
        :return: Ordered RMS/EMT template consumers.
        """
        consumers: List[dev.RmsModelTemplate | dev.EmtModelTemplate] = list()
        template_lists: Tuple[List[dev.RmsModelTemplate] | List[dev.EmtModelTemplate], ...] = (
            self._rms_models,
            self._emt_models,
        )
        template_list: List[dev.RmsModelTemplate] | List[dev.EmtModelTemplate]
        template: dev.RmsModelTemplate | dev.EmtModelTemplate
        for template_list in template_lists:
            for template in template_list:
                found: bool = False
                for block in template.block.get_all_blocks():
                    for logic in block.procedural_logic:
                        if isinstance(logic, ManufacturerNativeControllerLogic):
                            if logic.provider_idtag == provider.idtag:
                                found = True
                            else:
                                pass
                        else:
                            pass
                if found:
                    consumers.append(template)
                else:
                    pass
        return consumers

    def get_element_deletion_blockers(self, obj: ALL_DEV_TYPES) -> List[ALL_DEV_TYPES]:
        """Return objects that prevent safe deletion of one database element.

        This general Assets query keeps reference knowledge beside the model
        ownership rules and lets database views remain independent of device
        implementations.

        :param obj: Candidate database element.
        :return: Ordered objects that still reference the candidate.
        """
        blockers: List[ALL_DEV_TYPES] = list()
        if isinstance(obj, dev.ManufacturerNativeModel):
            consumer: dev.RmsModelTemplate | dev.EmtModelTemplate
            for consumer in self.get_manufacturer_native_consumers(obj):
                blockers.append(consumer)
        else:
            pass
        return blockers

    def delete_manufacturer_native_model(self, obj: dev.ManufacturerNativeModel) -> None:
        """Delete a provider only when no template still references it.

        :param obj: Provider to remove.
        :return: None.
        """
        consumers: List[dev.RmsModelTemplate | dev.EmtModelTemplate] = (
            self.get_manufacturer_native_consumers(obj)
        )
        if len(consumers) == 0:
            if obj in self._manufacturer_native_models:
                self._manufacturer_native_models.remove(obj)
            else:
                pass
        else:
            pass


    def rebind_manufacturer_native_consumer(
            self,
            consumer: dev.RmsModelTemplate | dev.EmtModelTemplate,
            source: dev.ManufacturerNativeModel,
            destination: dev.ManufacturerNativeModel,
            plan: ManufacturerNativeRebindPlan | None = None,
    ) -> None:
        """Atomically rebind one consumer after complete compatibility proof.

        Byte-identical metadata needs no mapping. A different digest requires
        the transient plan built by the IEEE/CIGRE IO layer.

        :param consumer: RMS/EMT template to update.
        :param source: Current provider.
        :param destination: Replacement provider.
        :param plan: Complete different-digest replacement plan.
        :return: None.
        """
        if source.model_info_sha256 == destination.model_info_sha256:
            rebound: bool = False
            block: Block
            for block in consumer.block.get_all_blocks():
                logic: ProceduralLogicBase
                for logic in block.procedural_logic:
                    if isinstance(logic, ManufacturerNativeControllerLogic):
                        if logic.provider_idtag == source.idtag:
                            logic.provider_idtag = destination.idtag
                            logic.model_info_sha256 = destination.model_info_sha256
                            rebound = True
                        else:
                            pass
                    else:
                        pass
            if not rebound:
                raise ValueError("The selected template does not consume the source provider")
            else:
                return
        else:
            pass

        if plan is None:
            raise ValueError("Different ModelInfo digests require a complete rebind plan")
        else:
            pass
        if (
                plan.consumer_idtag != consumer.idtag
                or plan.source_provider_idtag != source.idtag
                or plan.destination_provider_idtag != destination.idtag
                or plan.source_model_info_sha256 != source.model_info_sha256
                or plan.destination_model_info_sha256 != destination.model_info_sha256
        ):
            raise ValueError("Manufacturer native rebind plan identities are stale")
        else:
            pass

        if isinstance(consumer, dev.RmsModelTemplate):
            occurrence_mode: IeeeCigreDllModelMode = IeeeCigreDllModelMode.RMS
        else:
            if isinstance(consumer, dev.EmtModelTemplate):
                occurrence_mode = IeeeCigreDllModelMode.EMT
            else:
                raise TypeError("Manufacturer native consumer must be an RMS or EMT template")

        occurrences: list[ManufacturerNativeControllerLogic] = list()
        source_fingerprints: list[str] = list()
        block: Block
        for block in consumer.block.get_all_blocks():
            logic: ProceduralLogicBase
            for logic in block.procedural_logic:
                if isinstance(logic, ManufacturerNativeControllerLogic):
                    if logic.provider_idtag == source.idtag:
                        fingerprint_payload: tuple[object, ...] = (
                            int(occurrence_mode.value),
                            logic.provider_idtag,
                            logic.model_info_sha256,
                            tuple(
                                (
                                    binding.is_input,
                                    binding.port_ordinal,
                                    binding.element_ordinal,
                                    binding.get_variable().name,
                                    binding.get_variable().non_mutable_uid,
                                )
                                for binding in logic.signal_bindings
                            ),
                            tuple(
                                (
                                    override.parameter_ordinal,
                                    override.data_type,
                                    override.fixed_value,
                                    override.value,
                                )
                                for override in logic.parameter_overrides
                            ),
                        )
                        fingerprint_bytes: bytes = json.dumps(
                            fingerprint_payload,
                            ensure_ascii=True,
                            allow_nan=False,
                            separators=(",", ":"),
                        ).encode("utf-8")
                        occurrences.append(logic)
                        source_fingerprints.append(
                            hashlib.sha256(fingerprint_bytes).hexdigest()
                        )
                    else:
                        pass
                else:
                    pass
        if tuple(source_fingerprints) != plan.source_occurrence_fingerprints:
            raise ValueError("Manufacturer native consumer changed after plan construction")
        else:
            pass

        replacement_bindings: list[Tuple[IeeeCigreDllSignalBinding, ...]] = list()
        replacement_overrides: list[Tuple[IeeeCigreDllParameterOverride, ...]] = list()
        occurrence_index: int
        for occurrence_index in range(len(occurrences)):
            signal_records: Tuple[Tuple[bool, int, int, str, int], ...] = (
                plan.replacement_signal_records[occurrence_index]
            )
            override_records: Tuple[Tuple[int, int, bool, int | float | str], ...] = (
                plan.replacement_override_records[occurrence_index]
            )
            binding_list: list[IeeeCigreDllSignalBinding] = list()
            signal_record: Tuple[bool, int, int, str, int]
            signal_record_index: int = 0
            for signal_record in signal_records:
                source_binding: IeeeCigreDllSignalBinding = (
                    occurrences[occurrence_index].signal_bindings[signal_record_index]
                )
                binding_variable: Var = source_binding.get_variable()
                if binding_variable.non_mutable_uid == signal_record[4]:
                    pass
                else:
                    raise ValueError("Manufacturer native rebind variable identity is stale")
                binding_list.append(IeeeCigreDllSignalBinding(
                    is_input=signal_record[0],
                    port_ordinal=signal_record[1],
                    element_ordinal=signal_record[2],
                    variable=binding_variable,
                ))
                signal_record_index += 1
            override_list: list[IeeeCigreDllParameterOverride] = list()
            override_record: Tuple[int, int, bool, int | float | str]
            for override_record in override_records:
                override_list.append(IeeeCigreDllParameterOverride(
                    parameter_ordinal=override_record[0],
                    data_type=override_record[1],
                    fixed_value=override_record[2],
                    value=override_record[3],
                ))
            replacement_bindings.append(tuple(binding_list))
            replacement_overrides.append(tuple(override_list))

        # No validation remains below this point; every occurrence changes as
        # one in-memory transaction after the complete replacement is ready.
        for occurrence_index in range(len(occurrences)):
            occurrence: ManufacturerNativeControllerLogic = occurrences[occurrence_index]
            occurrence.provider_idtag = destination.idtag
            occurrence.model_info_sha256 = destination.model_info_sha256
            occurrence.signal_bindings = replacement_bindings[occurrence_index]
            occurrence.parameter_overrides = replacement_overrides[occurrence_index]

    # DynamicModel
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def rms_models(self) -> List[dev.RmsModelTemplate]:
        """
        list of rms models
        :return:
        """
        return self._rms_models

    @rms_models.setter
    def rms_models(self, value: List[dev.RmsModelTemplate]):
        self._rms_models = value

    def get_rms_models_number(self) -> int:
        """
        Get number of RMS models
        """
        return len(self._rms_models)

    def add_rms_model(self, obj: dev.RmsModelTemplate):
        """
        Add rms model to the collection
        :param obj: DynamicModel instance
        """
        if obj is not None:
            if isinstance(obj, dev.RmsModelTemplate):
                self._rms_models.append(obj)
            else:
                print('The template is not a RmsModelTemplate!')

    def delete_rms_model(self, obj: dev.RmsModelTemplate):
        """
        Delete RMS model from the collection
        :param obj: DynamicModel object
        """

        for elm in self.get_injection_devices_iter():
            if elm.rms_template == obj:
                elm.rms_template = None

        for elm in self.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
            if elm.rms_template == obj:
                elm.rms_template = None

        try:
            self._rms_models.remove(obj)
        except ValueError:
            pass

    def get_rms_models_by_device_type(self, tpe: DeviceType) -> List[dev.RmsModelTemplate]:
        """
        Return complete RMS device templates assignable to one host type.

        Internal controls remain registered in ``rms_models`` for composition,
        but they must not appear in a physical device property selector.

        :param tpe: Physical host device type.
        :return: Matching complete RMS device templates.
        """
        result: List[dev.RmsModelTemplate] = list()
        template: dev.RmsModelTemplate
        for template in self.rms_models:
            if (
                    template.tpe == tpe
                    and classify_dynamic_template_block(template.block)
                    is DynamicTemplateCategory.DEVICE
            ):
                result.append(template)
            else:
                pass
        return result

    def get_rms_templates_for_editor(self, tpe: DeviceType) -> List[dev.RmsModelTemplate]:
        """Return RMS device, component and measurement templates for editing.

        :param tpe: Device type whose internal model is being composed.
        :return: Compatible RMS templates grouped later by their typed contract.
        """
        result: List[dev.RmsModelTemplate] = list()
        template: dev.RmsModelTemplate
        for template in self.rms_models:
            if _matches_dynamic_template_device_type(tpe, template.tpe):
                result.append(template)
            else:
                pass
        return result

    def get_loaded_rms_models_by_device_type(self, tpe: DeviceType) -> List[dev.RmsModelTemplate]:
        """
        Return already materialized RMS templates without triggering lazy loading.

        :param tpe: Supported device type.
        :return: Matching loaded RMS templates.
        """
        result: List[dev.RmsModelTemplate] = list()
        template: dev.RmsModelTemplate
        for template in self._rms_models:
            if (
                    template.tpe == tpe
                    and classify_dynamic_template_block(template.block)
                    is DynamicTemplateCategory.DEVICE
            ):
                result.append(template)
            else:
                pass
        return result

    # ------------------------------------------------------------------------------------------------------------------
    # EmtModel
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def emt_models(self) -> List[dev.EmtModelTemplate]:
        """
        list of emt models
        :return:
        """
        return self._emt_models

    @emt_models.setter
    def emt_models(self, value: List[dev.EmtModelTemplate]):
        self._emt_models = value

    def get_emt_models_number(self) -> int:
        """
        Get number of EMT models
        """
        return len(self._emt_models)

    def add_emt_model(self, obj: dev.EmtModelTemplate):
        """
        Add emt model to the collection
        :param obj: DynamicModel instance
        """
        if obj is not None:
            if isinstance(obj, dev.EmtModelTemplate):
                self._emt_models.append(obj)
            else:
                print('The template is not a EmtModelTemplate!')

    def delete_emt_model(self, obj: dev.EmtModelTemplate) -> None:
        """Remove a library template and clear matching device references.

        Injections and branches own template references through ``emt_template``.
        Buses own independently constructed Blocks and have no such reference.
        Existing setters retain materialized Blocks when the reference is cleared,
        matching RMS deletion and explicit custom-model ownership.

        :param obj: Library template whose matching references must be cleared.
        :return: None; an absent library entry is handled without an exception.
        """
        # Use the canonical reference setter rather than undeclared Block state.
        injection: INJECTION_DEVICE_TYPES
        for injection in self.get_injection_devices_iter():
            if injection.emt_template == obj:
                injection.emt_template = None
            else:
                pass

        # Apply the same ownership rule to every existing branch collection.
        branch: BRANCH_TYPES
        for branch in self.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
            if branch.emt_template == obj:
                branch.emt_template = None
            else:
                pass

        # Idempotent removal preserves the established missing-entry behavior.
        if obj in self._emt_models:
            self._emt_models.remove(obj)
        else:
            pass

    def get_emt_models_by_device_type(self, tpe: DeviceType) -> List[dev.EmtModelTemplate]:
        """
        Return complete EMT device templates assignable to one host type.

        :param tpe: Physical host device type.
        :return: Matching complete EMT device templates.
        """
        result: List[dev.EmtModelTemplate] = list()
        template: dev.EmtModelTemplate
        for template in self.emt_models:
            if (
                    template.tpe == tpe
                    and classify_dynamic_template_block(template.block)
                    is DynamicTemplateCategory.DEVICE
            ):
                result.append(template)
            else:
                pass
        return result

    def get_emt_templates_for_editor(self, tpe: DeviceType) -> List[dev.EmtModelTemplate]:  # TODO: SANPEN: WTF is this? GUI code on the engine?
        """Return EMT device, component and measurement templates for editing.

        :param tpe: Device type whose internal model is being composed.
        :return: Compatible EMT templates grouped later by their typed contract.
        """
        result: List[dev.EmtModelTemplate] = list()
        template: dev.EmtModelTemplate
        for template in self.emt_models:
            if _matches_dynamic_template_device_type(tpe, template.tpe):
                result.append(template)
            else:
                pass
        return result

    def get_loaded_emt_models_by_device_type(self, tpe: DeviceType) -> List[dev.EmtModelTemplate]:
        """
        Return already materialized EMT templates without triggering lazy loading.

        :param tpe: Supported device type.
        :return: Matching loaded EMT templates.
        """
        result: List[dev.EmtModelTemplate] = list()
        template: dev.EmtModelTemplate
        for template in self._emt_models:
            if (
                    template.tpe == tpe
                    and classify_dynamic_template_block(template.block)
                    is DynamicTemplateCategory.DEVICE
            ):
                result.append(template)
            else:
                pass
        return result

    @property
    def fmu_templates(self) -> List[dev.FmuTemplate]:
        """
        List of reusable FMU templates.

        :return: FMU templates.
        """

        return self._fmu_templates

    @fmu_templates.setter
    def fmu_templates(self, value: List[dev.FmuTemplate]) -> None:
        """
        Replace the complete FMU template catalogue.

        :param value: FMU template list.
        :return: None.
        """

        self._fmu_templates = value

    def get_fmu_templates_number(self) -> int:
        """
        Return the number of reusable FMU templates.

        :return: Number of FMU templates.
        """

        return len(self._fmu_templates)

    def add_fmu_template(self, obj: dev.FmuTemplate) -> None:
        """
        Add one reusable FMU template to the catalogue.

        :param obj: FMU template instance.
        :return: None.
        """

        if obj is not None:
            if isinstance(obj, dev.FmuTemplate):
                self._fmu_templates.append(obj)
            else:
                print('The template is not a FmuTemplate!')
        else:
            pass

    def delete_fmu_template(self, obj: dev.FmuTemplate) -> None:
        """
        Delete one reusable FMU template from the catalogue.

        :param obj: FMU template instance.
        :return: None.
        """

        for elm in self.buses:
            if elm.rms_fmu_template == obj:
                elm.rms_fmu_template = None
            else:
                pass

            if elm.emt_fmu_template == obj:
                elm.emt_fmu_template = None
            else:
                pass

        for elm in self.get_injection_devices_iter():
            if elm.rms_fmu_template == obj:
                elm.rms_fmu_template = None
            else:
                pass

            if elm.emt_fmu_template == obj:
                elm.emt_fmu_template = None
            else:
                pass

        for elm in self.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
            if elm.rms_fmu_template == obj:
                elm.rms_fmu_template = None
            else:
                pass

            if elm.emt_fmu_template == obj:
                elm.emt_fmu_template = None
            else:
                pass

        try:
            self._fmu_templates.remove(obj)
        except ValueError:
            pass

    def get_fmu_templates_by_device_type(self, tpe: DeviceType) -> List[dev.FmuTemplate]:
        """
        Get FMU templates filtered by supported device type.

        :param tpe: Supported VeraGrid device type.
        :return: Matching FMU templates.
        """

        return [elm for elm in self.fmu_templates if _matches_dynamic_template_device_type(tpe, elm.tpe)]

    def get_fmu_templates_by_device_type_and_domain(self,
                                                    tpe: DeviceType,
                                                    domain: FmuTemplateDomain) -> List[dev.FmuTemplate]:
        """
        Get FMU templates filtered by supported device type and simulation domain.

        :param tpe: Supported VeraGrid device type.
        :param domain: Supported FMU simulation domain.
        :return: Matching FMU templates.
        """

        return [elm for elm in self.fmu_templates if elm.tpe == tpe and elm.domain == domain]

    def get_dynamic_templates_by_device_type_and_domain(
            self,
            tpe: DeviceType,
            domain: FmuTemplateDomain) -> List[dev.RmsModelTemplate | dev.EmtModelTemplate | dev.FmuTemplate]:
        """
        Get all reusable templates for one device type and one simulation domain.

        Native templates and FMU templates are both returned because the block editor
        library must expose both under the same ``Templates`` category.

        :param tpe: Supported VeraGrid device type.
        :param domain: Simulation domain used by the editor.
        :return: Matching native and FMU templates.
        """

        if domain == FmuTemplateDomain.RMS:
            native_templates: List[dev.RmsModelTemplate | dev.EmtModelTemplate | dev.FmuTemplate] = list(
                self.get_rms_templates_for_editor(tpe)
            )
        else:
            if domain == FmuTemplateDomain.EMT:
                native_templates = list(self.get_emt_templates_for_editor(tpe))
            else:
                raise ValueError(f"Unsupported dynamic template domain {domain}")

        native_templates.extend(self.get_fmu_templates_by_device_type_and_domain(tpe, domain))
        return native_templates

    def get_dynamic_templates_by_domain(
            self,
            domain: FmuTemplateDomain
    ) -> List[dev.RmsModelTemplate | dev.EmtModelTemplate | dev.FmuTemplate]:
        """
        Get all reusable templates registered for one simulation domain.

        :param domain: Simulation domain used by the editor.
        :return: Matching native and FMU templates.
        """

        templates: List[dev.RmsModelTemplate | dev.EmtModelTemplate | dev.FmuTemplate] = list()
        if domain == FmuTemplateDomain.RMS:
            templates.extend(self.rms_models)
        else:
            if domain == FmuTemplateDomain.EMT:
                templates.extend(self.emt_models)
            else:
                raise ValueError(f"Unsupported dynamic template domain {domain}")

        fmu_template: dev.FmuTemplate
        for fmu_template in self.fmu_templates:
            if fmu_template.domain == domain:
                templates.append(fmu_template)
            else:
                pass

        return templates

    # ------------------------------------------------------------------------------------------------------------------
    # Control PC
    # ------------------------------------------------------------------------------------------------------------------

    @property
    def control_pcs(self) -> List[dev.ControlPc]:
        """
        List of control PCs.

        :return: Control PC devices.
        """

        return self._control_pcs

    @control_pcs.setter
    def control_pcs(self, value: List[dev.ControlPc]) -> None:
        """
        Replace the complete control PC list.

        :param value: Control PC device list.
        :return: None.
        """

        self._control_pcs = value

    def get_control_pcs_number(self) -> int:
        """
        Return the number of control PCs.

        :return: Number of control PCs.
        """

        return len(self._control_pcs)

    def add_control_pc(self, obj: dev.ControlPc) -> None:
        """
        Add one control PC.

        :param obj: Control PC instance.
        :return: None.
        """

        if obj is not None:
            if isinstance(obj, dev.ControlPc):
                self._control_pcs.append(obj)
            else:
                print('The device is not a ControlPc!')
        else:
            pass

    def delete_control_pc(self, obj: dev.ControlPc) -> None:
        """
        Delete one control PC.

        :param obj: Control PC instance.
        :return: None.
        """

        try:
            self._control_pcs.remove(obj)
        except ValueError:
            pass

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
        Add any branch object (it's type will be inferred here)
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
                self.add_transformer2w(obj.get_equivalent_transformer(index=self.time_profile))
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
        for branch_list in self.get_branch_lists(add_vsc=True, add_hvdc=True, add_switch=True):
            try:
                branch_list.remove(obj)
                self.delete_groupings_with_object(obj=obj)
            except ValueError:  # element not found ...
                pass

    def get_branch_lists(self, add_vsc: bool = True,
                         add_hvdc: bool = True,
                         add_switch: bool = False) -> List[List[BRANCH_TYPES]]:
        """
        Return all the branch objects
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: list of branch devices lists
        """
        lst: List[List[BRANCH_TYPES]] = [
            self._lines,
            self._dc_lines,
            self._transformers2w,
            self._windings,
            self._upfc_devices,
            self._series_reactances,
        ]

        if add_vsc:
            lst.append(self._vsc_devices)

        if add_hvdc:
            lst.append(self._hvdc_lines)

        if add_switch:
            lst.append(self._switch_devices)

        return lst

    def get_branches(self, add_vsc: bool = False, add_hvdc: bool = False,
                     add_switch: bool = True) -> List[BRANCH_TYPES]:
        """
        Return all the branch objects
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: list of branch devices
        """
        elms = list()
        for lst in self.get_branch_lists(add_vsc=add_vsc, add_hvdc=add_hvdc, add_switch=add_switch):
            for elm in lst:
                elms.append(elm)
        return elms

    def get_branches_iter(self, add_vsc: bool = True,
                          add_hvdc: bool = True,
                          add_switch: bool = False) -> Generator[BRANCH_TYPES, None, None]:
        """
        Return all the branch objects
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: list of branch devices
        """
        for lst in self.get_branch_lists(add_vsc=add_vsc, add_hvdc=add_hvdc, add_switch=add_switch):
            for elm in lst:
                yield elm

    def get_branch_number(self, add_vsc: bool = False,
                          add_hvdc: bool = False,
                          add_switch: bool = True) -> int:
        """
        return the number of Branches (of all types)
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: number
        """
        m = 0
        for branch_list in self.get_branch_lists(add_vsc=add_vsc,
                                                 add_hvdc=add_hvdc,
                                                 add_switch=add_switch):
            m += len(branch_list)
        return m

    def get_branch_names(self, add_vsc: bool = True,
                         add_hvdc: bool = True,
                         add_switch: bool = False) -> StrVec:
        """
        Get array of all branch names
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: StrVec
        """

        names = list()
        for lst in self.get_branch_lists(add_vsc=add_vsc,
                                         add_hvdc=add_hvdc,
                                         add_switch=add_switch):
            for elm in lst:
                names.append(elm.name)
        return np.array(names)

    def get_branch_actives(self,
                           t_idx: int | None,
                           add_vsc: bool = True,
                           add_hvdc: bool = True,
                           add_switch: bool = False) -> IntVec:
        """
        Get array of all branch active states
        :param t_idx: Index of time step
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: StrVec
        """
        n = self.get_branch_number(add_vsc=add_vsc, add_hvdc=add_hvdc, add_switch=add_switch)
        data: IntVec = np.zeros(n, dtype=int)
        i = 0
        for elm in self.get_branches_iter(add_vsc=add_vsc, add_hvdc=add_hvdc, add_switch=add_switch):
            data[i] = elm.active_prof[t_idx] if t_idx is not None else elm.active
            i += 1
        return data

    def get_branches_index_dict(self, add_vsc: bool = True,
                                add_hvdc: bool = True,
                                add_switch: bool = False) -> Dict[BRANCH_TYPES, int]:
        """
        Get the branch to index dictionary
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: Branch object to index
        """
        return {b: i for i, b in enumerate(self.get_branches_iter(add_vsc=add_vsc,
                                                                  add_hvdc=add_hvdc,
                                                                  add_switch=add_switch))}

    def get_branches_idtag_index_dict(self, add_vsc: bool = True,
                                      add_hvdc: bool = True,
                                      add_switch: bool = False) -> Dict[str, int]:
        """
        Get the branch to index dictionary
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: Branch object to index
        """
        return {b.idtag: i for i, b in enumerate(self.get_branches_iter(add_vsc=add_vsc,
                                                                        add_hvdc=add_hvdc,
                                                                        add_switch=add_switch))}

    def get_branches_index_dict2(self, add_vsc: bool = True,
                                 add_hvdc: bool = True,
                                 add_switch: bool = False) -> Dict[str, int]:
        """
        Get the branch to index dictionary
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: Branch idtag to index
        """
        return {b.idtag: i for i, b in enumerate(self.get_branches_iter(add_vsc=add_vsc,
                                                                        add_hvdc=add_hvdc,
                                                                        add_switch=add_switch))}

    def get_branches_dict(self, add_vsc: bool = True,
                          add_hvdc: bool = True,
                          add_switch: bool = False) -> Dict[str, int]:
        """
        Get dictionary of branches (excluding HVDC)
        the key is the idtag, the value is the branch position
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: Dict[str, int]
        """
        return {e.idtag: ei for ei, e in enumerate(self.get_branches_iter(add_vsc=add_vsc,
                                                                          add_hvdc=add_hvdc,
                                                                          add_switch=add_switch))}

    def get_branch_FT(self, add_vsc: bool = True,
                      add_hvdc: bool = True,
                      add_switch: bool = False) -> Tuple[IntVec, IntVec]:
        """
        get the from and to arrays of indices
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: IntVec, IntVec
        """
        m = self.get_branch_number(add_vsc=add_vsc, add_hvdc=add_hvdc, add_switch=add_switch)
        F: IntVec = np.zeros(m, dtype=int)
        T: IntVec = np.zeros(m, dtype=int)
        bus_dict = self.get_bus_index_dict()
        for i, elm in enumerate(self.get_branches_iter(add_vsc=add_vsc, add_hvdc=add_hvdc, add_switch=add_switch)):
            F[i] = bus_dict[elm.bus_from]
            T[i] = bus_dict[elm.bus_to]
        return F, T

    def get_branches_monitored_indices(self,
                                       add_vsc: bool = True,
                                       add_hvdc: bool = True,
                                       add_switch: bool = False) -> IntVec:
        """
         Get the indices of the monitored branche
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: numpy array with the indices of the branches
        """
        lst = list()
        i = 0
        for elm in self.get_branches_iter(add_vsc=add_vsc, add_hvdc=add_hvdc, add_switch=add_switch):
            if elm.monitor_loading:
                lst.append(i)
            i += 1

        return np.array(lst, dtype=int)

    def delete_groupings_with_object(self, obj: BRANCH_TYPES, delete_groups: bool = True):
        """
        Delete the dependencies that may come with a branch
        :param obj: branch object or any object
        :param delete_groups: delete_with_dialogue empty groups too?
        :return:
        """
        for elm in self.contingencies:
            if elm.device_idtag == obj.idtag:
                self.delete_contingency(elm, del_group=delete_groups)

        for elm in self.remedial_actions:
            if elm.device_idtag == obj.idtag:
                self.delete_remedial_action(elm, del_group=delete_groups)

        for elm in self.investments:
            if elm.device_idtag == obj.idtag:
                self.delete_investment(elm, del_group=delete_groups)

    def get_hvdc_FT(self) -> Tuple[IntVec, IntVec]:
        """
        get the from and to arrays of indices of HVDC lines
        :return: IntVec, IntVec
        """
        m = len(self._hvdc_lines)
        F: IntVec = np.zeros(m, dtype=int)
        T: IntVec = np.zeros(m, dtype=int)
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

    def get_injections_device_types(self) -> List[DeviceType]:
        """
        Get a list of all devices types that can inject or subtract power from a node
        :return: List of DeviceType
        """
        return [DeviceType.GeneratorDevice,
                DeviceType.BatteryDevice,
                DeviceType.LoadDevice,
                DeviceType.ExternalGridDevice,
                DeviceType.StaticGeneratorDevice,
                DeviceType.ShuntDevice,
                DeviceType.ControllableShuntDevice,
                DeviceType.CurrentInjectionDevice]

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

    def get_injection_devices_iter(self) -> Generator[INJECTION_DEVICE_TYPES, None, None]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        for lst in self.get_injection_devices_lists():
            for elm in lst:
                yield elm

    def get_injections_bus_index_dict(self, bus_index_dict: Dict[dev.Bus, int] = None):
        """
        Get a dictionary of generators related to their bus index
        :param bus_index_dict: bus object to bus index dictionary (optional)
        :return: generator object to bus index dictionary

        """
        if bus_index_dict is None:
            bus_index_dict = self.get_bus_index_dict()

        return {g.idtag: bus_index_dict[g.bus] for g in self.get_injection_devices_iter() if g.bus is not None}

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

    def get_load_like_devices_iter(self) -> Generator[INJECTION_DEVICE_TYPES, None, None]:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """

        for lst in self.get_load_like_devices_lists():
            for elm in lst:
                yield elm

    def get_load_like_device_number(self) -> int:
        """
        Get a list of all devices that can inject or subtract power from a node
        :return: List of EditableDevice
        """
        n = 0
        for lst in self.get_load_like_devices_lists():
            n += len(lst)

        return n

    def get_load_like_devices_names(self) -> StrVec:
        """
        Get a list of names of the load like devices
        :return: array of str
        """
        elms = list()
        for lst in self.get_load_like_devices_lists():
            for elm in lst:
                elms.append(elm.name)
        return np.array(elms)

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

    def get_shunt_like_devices_names(self) -> StrVec:
        """
        Get a list of all devices names that can inject or subtract power from a node
        :return: Array of Shunt devices' names
        """
        elms = list()
        for lst in self.get_shunt_like_devices_lists():
            for elm in lst:
                elms.append(elm.name)
        return np.array(elms)

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
        Get a list of devices susceptible to be included in contingencies / remedial actions
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

    def get_elements_by_type(self, device_type: DeviceType) -> pd.DatetimeIndex | List[ALL_DEV_TYPES]:
        """
        Get set of elements and their parent nodes
        :param device_type: DeviceTYpe instance
        :return: List of elements, it raises an exception if the elements are unknown
        """

        if device_type == DeviceType.LoadDevice:
            return self._loads

        elif device_type == DeviceType.StaticGeneratorDevice:
            return self._static_generators

        elif device_type == DeviceType.GeneratorDevice:
            return self._generators

        elif device_type == DeviceType.BatteryDevice:
            return self._batteries

        elif device_type == DeviceType.ShuntDevice:
            return self._shunts

        elif device_type == DeviceType.ExternalGridDevice:
            return self._external_grids

        elif device_type == DeviceType.CurrentInjectionDevice:
            return self._current_injections

        elif device_type == DeviceType.ControllableShuntDevice:
            return self._controllable_shunts

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

        elif device_type == DeviceType.TransformerNwDevice:
            return self._transformers_nw

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

        elif device_type == DeviceType.UndergroundCableTypeDevice:
            return self._underground_cable_constructions

        elif device_type == DeviceType.DcCableTypeDevice:
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

        elif device_type == DeviceType.RemedialActionDevice:
            return self._remedial_actions

        elif device_type == DeviceType.RemedialActionGroupDevice:
            return self._remedial_action_groups

        elif device_type == DeviceType.ShortCircuitEvent:
            return self._short_circuit_events

        elif device_type == DeviceType.Technology:
            return self._technologies

        elif device_type == DeviceType.Owner:
            return self._owners

        elif device_type == DeviceType.InvestmentDevice:
            return self._investments

        elif device_type == DeviceType.InvestmentsGroupDevice:
            return self._investments_groups

        elif device_type == DeviceType.FuelDevice:
            return self._fuels

        elif device_type == DeviceType.EmissionGasDevice:
            return self._emission_gases

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

        elif device_type == DeviceType.FluidInjectionDevice:
            return self.get_fluid_injections()

        elif device_type == DeviceType.PiMeasurementDevice:
            return self.get_p_measurements()

        elif device_type == DeviceType.QiMeasurementDevice:
            return self.get_q_measurements()

        elif device_type == DeviceType.PgMeasurementDevice:
            return self.get_pg_measurements()

        elif device_type == DeviceType.QgMeasurementDevice:
            return self.get_qg_measurements()

        elif device_type == DeviceType.PfMeasurementDevice:
            return self.get_pf_measurements()

        elif device_type == DeviceType.PtMeasurementDevice:
            return self.get_pt_measurements()

        elif device_type == DeviceType.QfMeasurementDevice:
            return self.get_qf_measurements()

        elif device_type == DeviceType.QtMeasurementDevice:
            return self.get_qt_measurements()

        elif device_type == DeviceType.VmMeasurementDevice:
            return self.get_vm_measurements()

        elif device_type == DeviceType.VaMeasurementDevice:
            return self.get_va_measurements()

        elif device_type == DeviceType.IfMeasurementDevice:
            return self.get_if_measurements()

        elif device_type == DeviceType.ItMeasurementDevice:
            return self.get_it_measurements()

        elif device_type == DeviceType.LoadLikeDevice:
            return self.get_load_like_devices()

        elif device_type == DeviceType.BranchDevice:
            return self.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)

        elif device_type == DeviceType.ShuntLikeDevice:
            return self.get_shunt_like_devices()

        elif device_type == DeviceType.NoDevice:
            return list()

        elif device_type == DeviceType.TimeDevice:
            return self.get_time_array()

        elif device_type == DeviceType.ModellingAuthority:
            return self.get_modelling_authorities()

        elif device_type == DeviceType.FacilityDevice:
            return self.facilities

        elif device_type == DeviceType.MarketUnitsGroupDevice:
            return self.market_unit_groups

        elif device_type == DeviceType.MarketUnitDevice:
            return self.market_units

        elif device_type == DeviceType.LambdaDevice:
            return list()

        elif device_type == DeviceType.ManufacturerNativeModelDevice:
            return self.manufacturer_native_models

        elif device_type == DeviceType.RmsModelTemplateDevice:
            return self.rms_models

        elif device_type == DeviceType.EmtModelTemplateDevice:
            return self.emt_models

        elif device_type == DeviceType.FmuTemplateDevice:
            return self.fmu_templates

        elif device_type == DeviceType.ControlPc:
            return self.control_pcs

        elif device_type == DeviceType.RmsEventDevice:
            return self.rms_events

        elif device_type == DeviceType.RmsEventsGroupDevice:
            return self.rms_events_groups

        elif device_type == DeviceType.EmtEventDevice:
            return self.emt_events

        elif device_type == DeviceType.EmtEventsGroupDevice:
            return self.emt_events_groups

        elif device_type == DeviceType.DynamicPlotGroupDevice:
            return self.dynamic_plots

        elif device_type == DeviceType.DynamicPlotEntry:
            return self.dynamic_plot_entries

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
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._loads = devices

        elif device_type == DeviceType.StaticGeneratorDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._static_generators = devices

        elif device_type == DeviceType.GeneratorDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._generators = devices

        elif device_type == DeviceType.BatteryDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._batteries = devices

        elif device_type == DeviceType.ShuntDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._shunts = devices

        elif device_type == DeviceType.ExternalGridDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._external_grids = devices

        elif device_type == DeviceType.CurrentInjectionDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._current_injections = devices

        elif device_type == DeviceType.ControllableShuntDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._controllable_shunts = devices

        elif device_type == DeviceType.LineDevice:
            for d in devices:
                # this is done to detect those lines that should be transformers
                self.add_line(d, logger=logger)

        elif device_type == DeviceType.Transformer2WDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._transformers2w = devices


        elif device_type == DeviceType.Transformer3WDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._transformers3w = devices


        elif device_type == DeviceType.TransformerNwDevice:
            # TODO: TransformerNwDevice is not a DynamicDevice (for now). We must inspect how to model it dynamically
            # for d in devices:
            #     d.set_var_factory(self._var_factory)
            self._transformers_nw = devices


        elif device_type == DeviceType.WindingDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._windings = devices

        elif device_type == DeviceType.SeriesReactanceDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._series_reactances = devices

        elif device_type == DeviceType.HVDCLineDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._hvdc_lines = devices

        elif device_type == DeviceType.UpfcDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._upfc_devices = devices

        elif device_type == DeviceType.VscDevice:
            # for elm in devices:  # TODO SANPEN: Why not?
            #     elm.correct_buses_connection()
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._vsc_devices = devices

        elif device_type == DeviceType.BranchGroupDevice:
            self._branch_groups = devices

        elif device_type == DeviceType.BusDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._buses = ListSet(devices)

        elif device_type == DeviceType.OverheadLineTypeDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._overhead_line_types = devices

        elif device_type == DeviceType.TransformerTypeDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._transformer_types = devices

        elif device_type == DeviceType.UnderGroundLineDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._underground_cable_types = devices

        elif device_type == DeviceType.UndergroundCableTypeDevice:
            self._underground_cable_constructions = devices

        elif device_type == DeviceType.DcCableTypeDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._underground_cable_types = devices

        elif device_type == DeviceType.SequenceLineDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._sequence_line_types = devices

        elif device_type == DeviceType.WireDevice:
            self._wire_types = devices

        elif device_type == DeviceType.DCLineDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._dc_lines = devices

        elif device_type == DeviceType.SwitchDevice:
            for d in devices:
                d.set_var_factory(self._var_factory)
            self._switch_devices = devices

        elif device_type == DeviceType.SubstationDevice:
            self._substations = devices

        elif device_type == DeviceType.VoltageLevelDevice:
            self._voltage_levels = devices

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

        elif device_type == DeviceType.RemedialActionDevice:
            self._remedial_actions = devices

        elif device_type == DeviceType.RemedialActionGroupDevice:
            self._remedial_action_groups = devices

        elif device_type == DeviceType.ShortCircuitEvent:
            self._short_circuit_events = devices

        elif device_type == DeviceType.Technology:
            self._technologies = devices

        elif device_type == DeviceType.Owner:
            self._owners = devices

        elif device_type == DeviceType.InvestmentDevice:
            self._investments = devices

        elif device_type == DeviceType.InvestmentsGroupDevice:
            self._investments_groups = devices

        elif device_type == DeviceType.FuelDevice:
            self._fuels = devices

        elif device_type == DeviceType.EmissionGasDevice:
            self._emission_gases = devices

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

        elif device_type == DeviceType.PgMeasurementDevice:
            self._pg_measurements = devices

        elif device_type == DeviceType.QgMeasurementDevice:
            self._qg_measurements = devices

        elif device_type == DeviceType.PfMeasurementDevice:
            self._pf_measurements = devices

        elif device_type == DeviceType.PtMeasurementDevice:
            self._pt_measurements = devices

        elif device_type == DeviceType.QfMeasurementDevice:
            self._qf_measurements = devices

        elif device_type == DeviceType.QtMeasurementDevice:
            self._qt_measurements = devices

        elif device_type == DeviceType.VmMeasurementDevice:
            self._vm_measurements = devices

        elif device_type == DeviceType.VaMeasurementDevice:
            self._va_measurements = devices

        elif device_type == DeviceType.IfMeasurementDevice:
            self._if_measurements = devices

        elif device_type == DeviceType.ItMeasurementDevice:
            self._it_measurements = devices

        elif device_type == DeviceType.ModellingAuthority:
            self._modelling_authorities = devices

        elif device_type == DeviceType.FacilityDevice:
            self._facilities = devices

        elif device_type == DeviceType.MarketUnitsGroupDevice:
            self._market_unit_groups = devices

        elif device_type == DeviceType.MarketUnitDevice:
            self._market_units = devices

        elif device_type == DeviceType.ManufacturerNativeModelDevice:
            self._manufacturer_native_models = devices

        elif device_type == DeviceType.RmsModelTemplateDevice:
            self._rms_models = devices

        elif device_type == DeviceType.EmtModelTemplateDevice:
            self._emt_models = devices

        elif device_type == DeviceType.FmuTemplateDevice:
            self._fmu_templates = devices

        elif device_type == DeviceType.ControlPc:
            self._control_pcs = devices

        elif device_type == DeviceType.RmsEventDevice:
            self._rms_events = devices

        elif device_type == DeviceType.RmsEventsGroupDevice:
            self._rms_events_groups = devices

        elif device_type == DeviceType.EmtEventDevice:
            self._emt_events = devices

        elif device_type == DeviceType.EmtEventsGroupDevice:
            self._emt_events_groups = devices

        elif device_type == DeviceType.DynamicPlotGroupDevice:
            self._dynamic_plots = devices

        elif device_type == DeviceType.DynamicPlotEntry:
            self._dynamic_plot_entries = devices

        else:
            raise Exception('Element type not understood ' + str(device_type))

    def add_element(self, obj: ALL_DEV_TYPES) -> None:
        """
        Add a device in its corresponding list
        :param obj: device object to add
        :return: Nothing
        """

        if obj.device_type == DeviceType.LoadDevice:
            self.add_load(api_obj=obj, bus=obj.bus)

        elif obj.device_type == DeviceType.StaticGeneratorDevice:
            self.add_static_generator(api_obj=obj, bus=obj.bus)

        elif obj.device_type == DeviceType.GeneratorDevice:
            self.add_generator(api_obj=obj, bus=obj.bus)

        elif obj.device_type == DeviceType.BatteryDevice:
            self.add_battery(api_obj=obj, bus=obj.bus)

        elif obj.device_type == DeviceType.ShuntDevice:
            self.add_shunt(api_obj=obj, bus=obj.bus)

        elif obj.device_type == DeviceType.ExternalGridDevice:
            self.add_external_grid(api_obj=obj, bus=obj.bus)

        elif obj.device_type == DeviceType.CurrentInjectionDevice:
            self.add_current_injection(api_obj=obj, bus=obj.bus)

        elif obj.device_type == DeviceType.ControllableShuntDevice:
            self.add_controllable_shunt(api_obj=obj, bus=obj.bus)

        elif obj.device_type == DeviceType.LineDevice:
            self.add_line(obj=obj)

        elif obj.device_type == DeviceType.Transformer2WDevice:
            self.add_transformer2w(obj=obj)

        elif obj.device_type == DeviceType.Transformer3WDevice:
            self.add_transformer3w(obj=obj)

        elif obj.device_type == DeviceType.TransformerNwDevice:
            self.add_transformer_nw(obj=obj)

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

        elif obj.device_type == DeviceType.UndergroundCableTypeDevice:
            self.add_underground_cable(obj=obj)

        elif obj.device_type == DeviceType.DcCableTypeDevice:
            self.add_dc_cable_type(obj=obj)

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

        elif obj.device_type == DeviceType.RemedialActionDevice:
            self.add_remedial_action(obj=obj)

        elif obj.device_type == DeviceType.RemedialActionGroupDevice:
            self.add_remedial_action_group(obj=obj)

        elif obj.device_type == DeviceType.Technology:
            self.add_technology(obj=obj)

        elif obj.device_type == DeviceType.Owner:
            self.add_owner(obj=obj)

        elif obj.device_type == DeviceType.InvestmentDevice:
            self.add_investment(obj=obj)

        elif obj.device_type == DeviceType.InvestmentsGroupDevice:
            self.add_investments_group(obj=obj)

        elif obj.device_type == DeviceType.FuelDevice:
            self.add_fuel(obj=obj)

        elif obj.device_type == DeviceType.EmissionGasDevice:
            self.add_emission_gas(obj=obj)

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

        elif obj.device_type == DeviceType.PgMeasurementDevice:
            self.add_pg_measurement(obj=obj)

        elif obj.device_type == DeviceType.QgMeasurementDevice:
            self.add_qg_measurement(obj=obj)

        elif obj.device_type == DeviceType.PfMeasurementDevice:
            self.add_pf_measurement(obj=obj)

        elif obj.device_type == DeviceType.PtMeasurementDevice:
            self.add_pt_measurement(obj=obj)

        elif obj.device_type == DeviceType.QfMeasurementDevice:
            self.add_qf_measurement(obj=obj)

        elif obj.device_type == DeviceType.QtMeasurementDevice:
            self.add_qt_measurement(obj=obj)

        elif obj.device_type == DeviceType.VmMeasurementDevice:
            self.add_vm_measurement(obj=obj)

        elif obj.device_type == DeviceType.VaMeasurementDevice:
            self.add_va_measurement(obj=obj)

        elif obj.device_type == DeviceType.IfMeasurementDevice:
            self.add_if_measurement(obj=obj)

        elif obj.device_type == DeviceType.ItMeasurementDevice:
            self.add_it_measurement(obj=obj)

        elif obj.device_type == DeviceType.ModellingAuthority:
            self.add_modelling_authority(obj=obj)

        elif obj.device_type == DeviceType.FacilityDevice:
            self.add_facility(obj=obj)

        elif obj.device_type == DeviceType.MarketUnitsGroupDevice:
            self.add_market_unit_group(obj=obj)

        elif obj.device_type == DeviceType.MarketUnitDevice:
            self.add_market_unit(obj=obj)

        elif obj.device_type == DeviceType.ManufacturerNativeModelDevice:
            self.add_manufacturer_native_model(obj=obj)

        elif obj.device_type == DeviceType.RmsModelTemplateDevice:
            self.add_rms_model(obj=obj)

        elif obj.device_type == DeviceType.EmtModelTemplateDevice:
            self.add_emt_model(obj=obj)

        elif obj.device_type == DeviceType.FmuTemplateDevice:
            self.add_fmu_template(obj=obj)

        elif obj.device_type == DeviceType.ControlPc:
            self.add_control_pc(obj=obj)

        elif obj.device_type == DeviceType.RmsEventDevice:
            self.add_rms_event(obj=obj)

        elif obj.device_type == DeviceType.RmsEventsGroupDevice:
            self.add_rms_events_group(obj=obj)

        elif obj.device_type == DeviceType.EmtEventDevice:
            self.add_emt_event(obj=obj)

        elif obj.device_type == DeviceType.EmtEventsGroupDevice:
            self.add_emt_events_group(obj=obj)

        elif obj.device_type == DeviceType.DynamicPlotGroupDevice:
            self.add_dynamic_plot(obj=obj)

        elif obj.device_type == DeviceType.DynamicPlotEntry:
            self.add_dynamic_plot_entry(obj=obj)

        elif obj.device_type == DeviceType.SwitchDevice:
            self.add_switch(obj=obj)

        elif obj.device_type == DeviceType.ShortCircuitEvent:
            self.add_short_circuit_event(obj=obj)
        else:
            raise Exception('Element type not understood ' + str(obj.device_type))

    def delete_element(self, obj: ALL_DEV_TYPES) -> None:
        """
        Get set of elements and their parent nodes
        :param obj: device object to delete_with_dialogue
        :return: Nothing
        """

        # Every deletion route observes the same Assets-owned reference policy,
        # including callers that bypass the database view.
        deletion_blockers: List[ALL_DEV_TYPES] = self.get_element_deletion_blockers(obj)
        if len(deletion_blockers) > 0:
            return
        else:
            pass

        if obj.device_type == DeviceType.LoadDevice:
            self.delete_load(obj)

        elif obj.device_type == DeviceType.StaticGeneratorDevice:
            self.delete_static_generator(obj)

        elif obj.device_type == DeviceType.GeneratorDevice:
            self.delete_generator(obj)

        elif obj.device_type == DeviceType.BatteryDevice:
            self.delete_battery(obj)

        elif obj.device_type == DeviceType.ShuntDevice:
            self.delete_shunt(obj)

        elif obj.device_type == DeviceType.ExternalGridDevice:
            self.delete_external_grid(obj)

        elif obj.device_type == DeviceType.CurrentInjectionDevice:
            self.delete_current_injection(obj)

        elif obj.device_type == DeviceType.ControllableShuntDevice:
            self.delete_controllable_shunt(obj)

        elif obj.device_type == DeviceType.LineDevice:
            self.delete_line(obj)

        elif obj.device_type == DeviceType.Transformer2WDevice:
            self.delete_transformer2w(obj)

        elif obj.device_type == DeviceType.Transformer3WDevice:
            self.delete_transformer3w(obj)

        elif obj.device_type == DeviceType.TransformerNwDevice:
            self.delete_transformer_nw(obj)

        elif obj.device_type == DeviceType.WindingDevice:
            self.delete_winding(obj)

        elif obj.device_type == DeviceType.SeriesReactanceDevice:
            self.delete_series_reactance(obj)

        elif obj.device_type == DeviceType.SwitchDevice:
            self.delete_switch(obj)

        elif obj.device_type == DeviceType.HVDCLineDevice:
            self.delete_hvdc_line(obj)

        elif obj.device_type == DeviceType.UpfcDevice:
            self.delete_upfc_converter(obj)

        elif obj.device_type == DeviceType.VscDevice:
            self.delete_vsc_converter(obj)

        elif obj.device_type == DeviceType.BusDevice:
            self.delete_bus(obj, delete_associated=True)

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

        elif obj.device_type == DeviceType.UndergroundCableTypeDevice:
            self.delete_underground_cable(obj)

        elif obj.device_type == DeviceType.DcCableTypeDevice:
            self.delete_dc_cable_type(obj)

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

        elif obj.device_type == DeviceType.RemedialActionDevice:
            self.delete_remedial_action(obj)

        elif obj.device_type == DeviceType.RemedialActionGroupDevice:
            self.delete_remedial_action_group(obj)

        elif obj.device_type == DeviceType.Technology:
            self.delete_technology(obj)

        elif obj.device_type == DeviceType.Owner:
            self.delete_owner(obj)

        elif obj.device_type == DeviceType.InvestmentDevice:
            self.delete_investment(obj)

        elif obj.device_type == DeviceType.InvestmentsGroupDevice:
            self.delete_investment_groups(obj)

        elif obj.device_type == DeviceType.FuelDevice:
            self.delete_fuel(obj)

        elif obj.device_type == DeviceType.EmissionGasDevice:
            self.delete_emission_gas(obj)

        elif obj.device_type == DeviceType.FluidNodeDevice:
            self.delete_fluid_node(obj)

        elif obj.device_type == DeviceType.ShortCircuitEvent:
            self.delete_short_circuit_event(obj)

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

        elif obj.device_type == DeviceType.PgMeasurementDevice:
            self.delete_pg_measurement(obj)

        elif obj.device_type == DeviceType.QgMeasurementDevice:
            self.delete_qg_measurement(obj)

        elif obj.device_type == DeviceType.PfMeasurementDevice:
            self.delete_pf_measurement(obj)

        elif obj.device_type == DeviceType.PtMeasurementDevice:
            self.delete_pt_measurement(obj)

        elif obj.device_type == DeviceType.QfMeasurementDevice:
            self.delete_qf_measurement(obj)

        elif obj.device_type == DeviceType.QtMeasurementDevice:
            self.delete_qt_measurement(obj)

        elif obj.device_type == DeviceType.VmMeasurementDevice:
            self.delete_vm_measurement(obj)

        elif obj.device_type == DeviceType.VaMeasurementDevice:
            self.delete_va_measurement(obj)

        elif obj.device_type == DeviceType.IfMeasurementDevice:
            self.delete_if_measurement(obj)

        elif obj.device_type == DeviceType.ItMeasurementDevice:
            self.delete_it_measurement(obj)

        elif obj.device_type == DeviceType.ModellingAuthority:
            self.delete_modelling_authority(obj)

        elif obj.device_type == DeviceType.FacilityDevice:
            self.delete_facility(obj)

        elif obj.device_type == DeviceType.MarketUnitsGroupDevice:
            self.delete_market_unit_group(obj)

        elif obj.device_type == DeviceType.MarketUnitDevice:
            self.delete_market_unit(obj)

        elif obj.device_type == DeviceType.LineLocation:
            pass

        elif obj.device_type == DeviceType.ManufacturerNativeModelDevice:
            self.delete_manufacturer_native_model(obj=obj)

        elif obj.device_type == DeviceType.RmsModelTemplateDevice:
            self.delete_rms_model(obj=obj)

        elif obj.device_type == DeviceType.EmtModelTemplateDevice:
            self.delete_emt_model(obj=obj)

        elif obj.device_type == DeviceType.FmuTemplateDevice:
            self.delete_fmu_template(obj=obj)

        elif obj.device_type == DeviceType.ControlPc:
            self.delete_control_pc(obj=obj)

        elif obj.device_type == DeviceType.RmsEventDevice:
            self.delete_rms_event(obj=obj)

        elif obj.device_type == DeviceType.RmsEventsGroupDevice:
            self.delete_rms_events_group(obj=obj)

        elif obj.device_type == DeviceType.EmtEventDevice:
            self.delete_emt_event(obj=obj)

        elif obj.device_type == DeviceType.EmtEventsGroupDevice:
            self.delete_emt_events_group(obj=obj)

        elif obj.device_type == DeviceType.DynamicPlotGroupDevice:
            self.delete_dynamic_plot(obj=obj)

        elif obj.device_type == DeviceType.DynamicPlotEntry:
            self.delete_dynamic_plot_entry(obj=obj)

        else:
            raise Exception('Element type not understood ' + str(obj.device_type))

    def merge_object(self,
                     api_obj: ALL_DEV_TYPES,
                     all_elms_base_dict: Dict[str, ALL_DEV_TYPES],
                     logger: Logger) -> bool:
        """
        Add, Delete or Modify an object based on the UUID
        :param api_obj: Any asset (from a diff presumably)
        :param all_elms_base_dict: All elements dict from the base circuit (idtag-> object)
        :param logger: Logger object
        :return: replaced?
        """

        if api_obj.selected_to_merge:

            if api_obj.action == ActionType.Add:
                new_obj = api_obj.copy(forced_new_idtag=False)
                new_obj.rebind_device_references(objects_by_idtag=all_elms_base_dict)
                self.add_element(obj=new_obj)
                all_elms_base_dict[new_obj.idtag] = new_obj

            elif api_obj.action == ActionType.Delete:

                elm_from_base = all_elms_base_dict.get(api_obj.idtag, None)
                if elm_from_base is not None:
                    if elm_from_base.device_type == DeviceType.BusDevice:
                        self.delete_bus(obj=elm_from_base, delete_associated=False)
                    else:
                        self.delete_element(obj=elm_from_base)
                    all_elms_base_dict.pop(api_obj.idtag, None)

            elif api_obj.action == ActionType.Modify:

                elm_from_base = all_elms_base_dict.get(api_obj.idtag, None)

                if elm_from_base is not None:
                    changed_props = list(api_obj.iter_properties_selected_to_merge())
                    api_obj.rebind_device_references(objects_by_idtag=all_elms_base_dict, props=changed_props)

                    for prop in changed_props:
                        val = api_obj.get_property_value(prop=prop, t_idx=None)
                        elm_from_base.set_property_value(prop=prop, value=val, t_idx=None)
                        if prop.has_profile():
                            elm_from_base.set_profile(prop=prop,
                                                      arr=api_obj.get_profile_by_prop(prop=prop).copy())
                else:
                    new_obj = api_obj.copy(forced_new_idtag=False)
                    new_obj.rebind_device_references(objects_by_idtag=all_elms_base_dict)
                    self.add_element(obj=new_obj)
                    all_elms_base_dict[new_obj.idtag] = new_obj

            elif api_obj.action == ActionType.NoAction:
                pass

            return True

        else:
            return False

    def get_all_elements_iter(self) -> Generator[ALL_DEV_TYPES, None, None]:
        """
        Get all elements
        :return: ALL_DEV_TYPES
        """

        for key, tpe in self.device_type_name_dict.items():
            elements = self.get_elements_by_type(device_type=tpe)

            for elm in elements:
                yield elm

    def get_all_elements_number(self) -> int:
        """
        Get all elements number
        :return: int
        """
        a = 0
        for key, tpe in self.device_type_name_dict.items():
            a += len(self.get_elements_by_type(device_type=tpe))

        return a

    def get_all_elements_dict(self,
                              use_secondary_key: bool = False,
                              use_rdfid: bool = False,
                              logger=Logger()) -> Tuple[Dict[str, ALL_DEV_TYPES], bool]:
        """
        Get a dictionary of all elements
        :param use_secondary_key: if true the code i˘s used as key
        :param use_rdfid: if true the rdfid is used as key
        :param logger: Logger
        :return: Dict[idtag] -> object, ok
        """
        data = dict()
        ok = True
        for key, tpe in self.device_type_name_dict.items():

            elements = self.get_elements_by_type(device_type=tpe)

            for elm in elements:

                e = data.get(elm.idtag, None)

                if e is None:

                    if use_secondary_key:
                        data[elm.code] = elm
                    elif use_rdfid:
                        data[elm.rdfid] = elm
                    else:
                        data[elm.idtag] = elm

                else:
                    logger.add_error(
                        msg="Duplicated idtag!",
                        device=elm.name,
                        device_class=elm.device_type.value,
                        device_property="idtag",
                        expected_value=f"{e.device_type.value}:{e.idtag}:{e.name}"
                    )
                    ok = False

        return data, ok

    def get_all_elements_dict_by_type(
            self,
            add_locations: bool = False,
            string_keys: bool = True
    ) -> Dict[Union[str, DeviceType], Union[Dict[str, ALL_DEV_TYPES], Any]]:
        """
        Get a dictionary of all elements by type
        :param add_locations: Add locations to dict
        :param string_keys: make the keys string otherwise use DeviceType
        :return:
        """

        data = dict()
        for key, tpe in self.device_type_name_dict.items():
            key = tpe.value if string_keys else tpe
            data[key] = self.get_elements_dict_by_type(element_type=tpe,
                                                       use_secondary_key=False)

        # add locations
        if add_locations:
            key = DeviceType.LineLocation.value if string_keys else DeviceType.LineLocation
            data[key] = self.get_elements_dict_by_type(element_type=DeviceType.LineLocation,
                                                       use_secondary_key=False)

        return data

    def get_elements_dict_by_type(self,
                                  element_type: DeviceType,
                                  use_secondary_key: bool = False,
                                  use_rdfid: bool = False) -> Dict[str, ALL_DEV_TYPES]:
        """
        Get dictionary of elements
        :param element_type: element type (Bus, Line, etc...)
        :param use_secondary_key: use the code as dictionary key? otherwise the idtag is used
        :param use_rdfid: if true the rdfid is used as key
        :return: Dict[str, dev.EditableDevice]
        """

        if use_secondary_key:
            return {elm.code: elm for elm in self.get_elements_by_type(element_type)}
        elif use_rdfid:
            return {elm.rdfid: elm for elm in self.get_elements_by_type(element_type)}
        else:
            return {elm.idtag: elm for elm in self.get_elements_by_type(element_type)}

    def clear(self) -> None:
        """
        Clear the multi-circuit (delete the bus and branch objects)
        """

        for key, elm_list in self.template_objects_dict.items():
            for elm in elm_list:
                self.get_elements_by_type(device_type=elm.device_type).clear()

    def get_dictionary_of_lists(
            self,
            elm_type: DeviceType
    ) -> Tuple[ALL_DEV_TYPES, Dict[DeviceType, List[ALL_DEV_TYPES]]]:
        """
        Function that returns the template of an elements and a dictionary
        of the lists of elements that contain it's dependencies
        :param elm_type: DeviceType
        :return: Template, dictionary of dependencies
        """
        dictionary_of_lists = dict()

        if elm_type == DeviceType.BusDevice:
            elm = dev.Bus()
            dictionary_of_lists = {
                DeviceType.AreaDevice: self.areas,
                DeviceType.ZoneDevice: self.zones,
                DeviceType.SubstationDevice: self.substations,
                DeviceType.VoltageLevelDevice: self.voltage_levels,
                DeviceType.BusBarDevice: self.bus_bars,
                DeviceType.CountryDevice: self.countries,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.Owner: self.owners,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.LoadDevice:
            elm = dev.Load()
            dictionary_of_lists = {
                DeviceType.Technology: self.technologies,
                DeviceType.Owner: self.owners,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.FacilityDevice: self.facilities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.StaticGeneratorDevice:
            elm = dev.StaticGenerator()
            dictionary_of_lists = {
                DeviceType.Technology: self.technologies,
                DeviceType.Owner: self.owners,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.FacilityDevice: self.facilities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.ControllableShuntDevice:
            elm = dev.ControllableShunt()
            dictionary_of_lists = {
                DeviceType.Technology: self.technologies,
                DeviceType.Owner: self.owners,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.FacilityDevice: self.facilities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.CurrentInjectionDevice:
            elm = dev.CurrentInjection()
            dictionary_of_lists = {
                DeviceType.Technology: self.technologies,
                DeviceType.Owner: self.owners,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.FacilityDevice: self.facilities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.GeneratorDevice:
            elm = dev.Generator()
            dictionary_of_lists = {
                DeviceType.Technology: self.technologies,
                DeviceType.Owner: self.owners,
                DeviceType.FuelDevice: self.fuels,
                DeviceType.EmissionGasDevice: self.emission_gases,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.MarketUnitDevice: self.market_units,
                DeviceType.FacilityDevice: self.facilities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.BatteryDevice:
            elm = dev.Battery()
            dictionary_of_lists = {
                DeviceType.Technology: self.technologies,
                DeviceType.Owner: self.owners,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.MarketUnitDevice: self.market_units,
                DeviceType.FacilityDevice: self.facilities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.ShuntDevice:
            elm = dev.Shunt()
            dictionary_of_lists = {
                DeviceType.Technology: self.technologies,
                DeviceType.Owner: self.owners,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.FacilityDevice: self.facilities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.ExternalGridDevice:
            elm = dev.ExternalGrid()
            dictionary_of_lists = {
                DeviceType.Technology: self.technologies,
                DeviceType.Owner: self.owners,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.FacilityDevice: self.facilities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.LineDevice:
            elm = dev.Line()
            any_line_templates: List[ALL_DEV_TYPES] = list()
            for line_template_list in (
                    self.overhead_line_types,
                    self.underground_cable_types,
                    self.sequence_line_types):
                for line_template in line_template_list:
                    any_line_templates.append(line_template)

            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.BranchGroupDevice: self.branch_groups,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
                DeviceType.AnyLineTemplateDevice: any_line_templates,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.SwitchDevice:
            elm = dev.Switch()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.BranchGroupDevice: self.branch_groups,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.Transformer2WDevice:
            elm = dev.Transformer2W()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.BranchGroupDevice: self.branch_groups,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.WindingDevice:
            elm = dev.Winding()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.BranchGroupDevice: self.branch_groups,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.Transformer3WDevice:
            elm = dev.Transformer3W()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.TransformerNwDevice:
            elm = dev.TransformerNW()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
            }

        elif elm_type == DeviceType.HVDCLineDevice:
            elm = dev.HvdcLine()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.BranchGroupDevice: self.branch_groups,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.VscDevice:
            elm = dev.VSC()
            bus_or_branch_devices: List[ALL_DEV_TYPES] = list()
            for bus in self.buses:
                bus_or_branch_devices.append(bus)
            for branch in self.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
                bus_or_branch_devices.append(branch)

            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.BranchGroupDevice: self.branch_groups,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
                DeviceType.BusOrBranch: bus_or_branch_devices,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.UpfcDevice:
            elm = dev.UPFC()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.BranchGroupDevice: self.branch_groups,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.SeriesReactanceDevice:
            elm = dev.SeriesReactance()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.BranchGroupDevice: self.branch_groups,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.DCLineDevice:
            elm = dev.DcLine()
            any_line_templates: List[ALL_DEV_TYPES] = list()
            for line_template_list in (
                    self.overhead_line_types,
                    self.underground_cable_types,
                    self.sequence_line_types):
                for line_template in line_template_list:
                    any_line_templates.append(line_template)

            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.BranchGroupDevice: self.branch_groups,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
                DeviceType.AnyLineTemplateDevice: any_line_templates,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.SubstationDevice:
            elm = dev.Substation()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.CountryDevice: self.get_countries(),
                DeviceType.CommunityDevice: self.get_communities(),
                DeviceType.RegionDevice: self.get_regions(),
                DeviceType.MunicipalityDevice: self.get_municipalities(),
                DeviceType.AreaDevice: self.get_areas(),
                DeviceType.ZoneDevice: self.get_zones(),
            }

        elif elm_type == DeviceType.BusBarDevice:
            elm = dev.BusBar()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.VoltageLevelDevice: self.voltage_levels,
                DeviceType.ModellingAuthority: self.modelling_authorities,
            }

        elif elm_type == DeviceType.VoltageLevelDevice:
            elm = dev.VoltageLevel()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.SubstationDevice: self.get_substations(),
            }

        elif elm_type == DeviceType.AreaDevice:
            elm = dev.Area()

        elif elm_type == DeviceType.ZoneDevice:
            elm = dev.Zone()
            dictionary_of_lists = {DeviceType.AreaDevice: self.get_areas(), }

        elif elm_type == DeviceType.CountryDevice:
            elm = dev.Country()

        elif elm_type == DeviceType.CommunityDevice:
            elm = dev.Community()
            dictionary_of_lists = {DeviceType.CountryDevice: self.get_countries(), }

        elif elm_type == DeviceType.RegionDevice:
            elm = dev.Region()
            dictionary_of_lists = {DeviceType.CommunityDevice: self.get_communities(), }

        elif elm_type == DeviceType.MunicipalityDevice:
            elm = dev.Municipality()
            dictionary_of_lists = {DeviceType.RegionDevice: self.get_regions(), }

        elif elm_type == DeviceType.ContingencyDevice:
            elm = dev.Contingency()
            dictionary_of_lists = {DeviceType.ContingencyGroupDevice: self.get_contingency_groups(), }

        elif elm_type == DeviceType.ContingencyGroupDevice:
            elm = dev.ContingencyGroup()

        elif elm_type == DeviceType.ShortCircuitEvent:
            elm = dev.ShortCircuitEvent()

        elif elm_type == DeviceType.ManufacturerNativeModelDevice:
            elm = dev.ManufacturerNativeModel()

        elif elm_type == DeviceType.RemedialActionDevice:
            elm = dev.RemedialAction()
            dictionary_of_lists = {DeviceType.RemedialActionGroupDevice: self.remedial_action_groups, }

        elif elm_type == DeviceType.RemedialActionGroupDevice:
            elm = dev.RemedialActionGroup()
            dictionary_of_lists = {DeviceType.ContingencyGroupDevice: self.get_contingency_groups(), }

        elif elm_type == DeviceType.InvestmentDevice:
            elm = dev.Investment()
            dictionary_of_lists = {DeviceType.InvestmentsGroupDevice: self.investments_groups, }

        elif elm_type == DeviceType.InvestmentsGroupDevice:
            elm = dev.InvestmentsGroup()

        elif elm_type == DeviceType.BranchGroupDevice:
            elm = dev.BranchGroup()

        elif elm_type == DeviceType.Technology:
            elm = dev.Technology()

        elif elm_type == DeviceType.Owner:
            elm = dev.Owner()

        elif elm_type == DeviceType.FuelDevice:
            elm = dev.Fuel()

        elif elm_type == DeviceType.EmissionGasDevice:
            elm = dev.EmissionGas()

        elif elm_type == DeviceType.WireDevice:
            elm = dev.Wire()

        elif elm_type == DeviceType.UndergroundCableTypeDevice:
            elm = dev.UndergroundCableType()

        elif elm_type == DeviceType.OverheadLineTypeDevice:
            elm = dev.OverheadLineType()
            dictionary_of_lists = {
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(DeviceType.LineDevice),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(DeviceType.LineDevice),
            }

        elif elm_type == DeviceType.SequenceLineDevice:
            elm = dev.SequenceLineType()
            dictionary_of_lists = {
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(DeviceType.LineDevice),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(DeviceType.LineDevice),
            }

        elif elm_type == DeviceType.UnderGroundLineDevice:
            elm = dev.UndergroundLineType()
            dictionary_of_lists = {
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.RmsModelTemplateDevice: (
                    self.get_rms_models_by_device_type(DeviceType.LineDevice)
                    + self.get_rms_models_by_device_type(DeviceType.DCLineDevice)),
                DeviceType.EmtModelTemplateDevice: (
                    self.get_emt_models_by_device_type(DeviceType.LineDevice)
                    + self.get_emt_models_by_device_type(DeviceType.DCLineDevice)),
            }

        elif elm_type == DeviceType.DcCableTypeDevice:
            elm = dev.UndergroundLineType()
            dictionary_of_lists = {
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(DeviceType.DCLineDevice),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(DeviceType.DCLineDevice),
            }

        elif elm_type == DeviceType.TransformerTypeDevice:
            elm = dev.TransformerType()
            dictionary_of_lists = {
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.RmsModelTemplateDevice: self.get_loaded_rms_models_by_device_type(
                    DeviceType.Transformer2WDevice),
                DeviceType.EmtModelTemplateDevice: self.get_loaded_emt_models_by_device_type(
                    DeviceType.Transformer2WDevice),
            }

        elif elm_type == DeviceType.FluidNodeDevice:
            elm = dev.FluidNode()
            dictionary_of_lists = {
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.BusDevice: self.buses,
            }

        elif elm_type == DeviceType.FluidPathDevice:
            elm = dev.FluidPath()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.FluidNodeDevice: self.get_fluid_nodes(),
                DeviceType.ModellingAuthority: self.modelling_authorities,
            }

        elif elm_type == DeviceType.FluidTurbineDevice:
            elm = dev.FluidTurbine()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.FluidNodeDevice: self.get_fluid_nodes(),
                DeviceType.GeneratorDevice: self.get_generators(),
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.FacilityDevice: self.facilities,
            }

        elif elm_type == DeviceType.FluidPumpDevice:
            elm = dev.FluidPump()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.FluidNodeDevice: self.get_fluid_nodes(),
                DeviceType.GeneratorDevice: self.get_generators(),
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.FacilityDevice: self.facilities,
            }

        elif elm_type == DeviceType.FluidP2XDevice:
            elm = dev.FluidP2x()
            dictionary_of_lists = {
                DeviceType.Owner: self.owners,
                DeviceType.FluidNodeDevice: self.get_fluid_nodes(),
                DeviceType.GeneratorDevice: self.get_generators(),
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.FacilityDevice: self.facilities,
            }

        elif elm_type == DeviceType.ModellingAuthority:
            elm = dev.ModellingAuthority()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.FacilityDevice:
            elm = dev.Facility()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.MarketUnitsGroupDevice:
            elm = dev.MarketUnitsGroup()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.MarketUnitDevice:
            elm = dev.MarketUnit()
            dictionary_of_lists = {
                DeviceType.FacilityDevice: self.facilities,
                DeviceType.MarketUnitsGroupDevice: self.market_unit_groups,
            }

        elif elm_type == DeviceType.RmsModelTemplateDevice:
            elm = dev.RmsModelTemplate()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.EmtModelTemplateDevice:
            elm = dev.EmtModelTemplate()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.FmuTemplateDevice:
            elm = dev.FmuTemplate()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.ControlPc:
            elm = dev.ControlPc()
            dictionary_of_lists = {
                DeviceType.ModellingAuthority: self.modelling_authorities,
                DeviceType.RmsModelTemplateDevice: self.get_rms_models_by_device_type(elm_type),
                DeviceType.EmtModelTemplateDevice: self.get_emt_models_by_device_type(elm_type),
            }

        elif elm_type == DeviceType.RmsEventDevice:
            elm = dev.RmsEvent()
            dictionary_of_lists = {DeviceType.RmsEventsGroupDevice: self.rms_events_groups}

        elif elm_type == DeviceType.RmsEventsGroupDevice:
            elm = dev.RmsEventsGroup()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.EmtEventDevice:
            elm = dev.EmtEvent()
            dictionary_of_lists = {DeviceType.EmtEventsGroupDevice: self.emt_events_groups}

        elif elm_type == DeviceType.EmtEventsGroupDevice:
            elm = dev.EmtEventsGroup()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.DynamicPlotGroupDevice:
            elm = dev.DynamicPlot()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.DynamicPlotEntry:
            elm = dev.DynamicPlotEntry()
            dictionary_of_lists = {
                DeviceType.DynamicPlotGroupDevice: self.dynamic_plots,
                DeviceType.RmsEventsGroupDevice: self.rms_events_groups,
            }

        elif elm_type == DeviceType.PiMeasurementDevice:
            elm = dev.PiMeasurement()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.QiMeasurementDevice:
            elm = dev.QiMeasurement()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.PgMeasurementDevice:
            elm = dev.PgMeasurement()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.QgMeasurementDevice:
            elm = dev.QgMeasurement()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.PfMeasurementDevice:
            elm = dev.PfMeasurement()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.QfMeasurementDevice:
            elm = dev.QfMeasurement()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.PtMeasurementDevice:
            elm = dev.PtMeasurement()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.QtMeasurementDevice:
            elm = dev.QtMeasurement()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.IfMeasurementDevice:
            elm = dev.IfMeasurement()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.ItMeasurementDevice:
            elm = dev.ItMeasurement()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.VmMeasurementDevice:
            elm = dev.VmMeasurement()
            dictionary_of_lists = dict()

        elif elm_type == DeviceType.VaMeasurementDevice:
            elm = dev.VaMeasurement()
            dictionary_of_lists = dict()

        else:
            raise Exception(f'elm_type not understood: {elm_type.value}')

        # Collect dependency types from the property declarations and explicit
        # pointer targets so new device relationships need no branch here.
        dependency_types: List[DeviceType] = list()
        for property_definition in elm.registered_properties.values():
            if isinstance(property_definition.tpe, DeviceType):
                dependency_types.append(property_definition.tpe)
            else:
                pass

        if isinstance(elm, PointerDeviceParent):
            for pointer_device_type in elm.pointer_dev_tpes:
                dependency_types.append(pointer_device_type)
        else:
            pass

        # Resolve every dependency to the corresponding circuit list while
        # retaining specialized lists assembled above for aggregate types.
        for dependency_type in dependency_types:
            if dependency_type == DeviceType.PhysicalDeviceType:
                # A generic pointer targets network objects, not catalogue,
                # event, grouping, or other metadata objects.
                if DeviceType.BusDevice not in dictionary_of_lists:
                    dictionary_of_lists[DeviceType.BusDevice] = self.buses
                else:
                    pass

                for injection_device_type in self.get_injections_device_types():
                    if injection_device_type not in dictionary_of_lists:
                        dictionary_of_lists[injection_device_type] = self.get_elements_by_type(
                            injection_device_type)
                    else:
                        pass

                branch_device_types: List[DeviceType] = [
                    DeviceType.LineDevice,
                    DeviceType.DCLineDevice,
                    DeviceType.Transformer2WDevice,
                    DeviceType.Transformer3WDevice,
                    DeviceType.TransformerNwDevice,
                    DeviceType.WindingDevice,
                    DeviceType.HVDCLineDevice,
                    DeviceType.VscDevice,
                    DeviceType.UpfcDevice,
                    DeviceType.SeriesReactanceDevice,
                    DeviceType.SwitchDevice,
                ]
                for branch_device_type in branch_device_types:
                    if branch_device_type not in dictionary_of_lists:
                        dictionary_of_lists[branch_device_type] = self.get_elements_by_type(
                            branch_device_type)
                    else:
                        pass
            else:
                if dependency_type not in dictionary_of_lists:
                    dictionary_of_lists[dependency_type] = self.get_elements_by_type(dependency_type)
                else:
                    pass

        if (DeviceType.RmsModelTemplateDevice in dictionary_of_lists) or (
                DeviceType.EmtModelTemplateDevice in dictionary_of_lists):
            dictionary_of_lists[DeviceType.FmuTemplateDevice] = self.get_fmu_templates_by_device_type(elm_type)
            dictionary_of_lists[
                ("rms_fmu_template", DeviceType.FmuTemplateDevice)] = self.get_fmu_templates_by_device_type_and_domain(
                elm_type,
                FmuTemplateDomain.RMS,
            )
            dictionary_of_lists[
                ("emt_fmu_template", DeviceType.FmuTemplateDevice)] = self.get_fmu_templates_by_device_type_and_domain(
                elm_type,
                FmuTemplateDomain.EMT,
            )
        else:
            pass

        return elm, dictionary_of_lists

    def new_idtags(self) -> None:
        """
        Generates new idtags for every object in this assets class
        """
        for elm in self.get_all_elements_iter():
            elm.new_idtag()

    def replace_objects(self, old_object: Any, new_obj: Any, logger: Logger) -> None:
        """
        Replace object for every object in this assets class
        :param old_object: object to replace
        :param new_obj: object used to replace the old one
        :param logger: Logger to record what happened
        """
        for elm in self.get_all_elements_iter():
            elm.replace_objects(old_object=old_object, new_obj=new_obj, logger=logger)

    def refine_pointer_objects(self,
                               logger: Logger,
                               all_elements_dict: Dict[str, ALL_DEV_TYPES] | None = None) -> None:
        """
        Find the device types of pointer objects
        :param logger:
        :param all_elements_dict:
        :return:
        """
        if all_elements_dict is None:
            d, ok = self.get_all_elements_dict(logger=logger)
        else:
            d = all_elements_dict

        objects_to_remove = list()

        for lst in [self.investments, self.remedial_actions, self.contingencies]:
            for elm in lst:
                pointed = d.get(elm.device_idtag, None)
                if pointed is None:
                    logger.add_error("Reference not found, element deleted",
                                     device_class=elm.device_type.value,
                                     value=elm.device_idtag)
                    objects_to_remove.append(elm)
                else:
                    elm.set_device(pointed)

        # Delete the elements that don't point to the right element
        for elm in objects_to_remove:
            self.delete_element(obj=elm)

    def get_devices_static_params_mapping(self) -> Dict[DeviceType, List[ParamPowerFlowReferenceType]]:
        """
        Generate the dictionary of static references for the dynamic data mapping
        :return: Dict[DeviceType, List[ParamPowerFlowReferenceType]]
        """
        data: Dict[DeviceType, List[ParamPowerFlowReferenceType]] = dict()

        for cat, elms in self.template_objects_dict.items():

            for elm in elms:  # for each device type
                lst: List[ParamPowerFlowReferenceType] = list()
                # The dynamic mapping contract must include inherited schema
                # declarations because many static-to-dynamic references live in
                # shared parent classes such as InjectionParent, LoadParent,
                # BranchParent and ShuntParent.
                for prop in elm.CLASS_PROPERTY_DECLARATIONS:
                    if prop.dyn_ref is not None:
                        lst.append(prop.dyn_ref)
                    else:
                        pass
                data[elm.device_type] = lst

        return data
