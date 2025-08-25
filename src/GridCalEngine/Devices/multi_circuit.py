# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import os
import cmath
import copy
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Union, Set, Sequence, TYPE_CHECKING
from uuid import getnode as get_mac, uuid4
import networkx as nx
from matplotlib import pyplot as plt
from scipy.sparse import csc_matrix, lil_matrix, coo_matrix

from GridCalEngine.Devices.assets import Assets
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.basic_structures import IntVec, Vec, Mat, CxVec, IntMat, CxMat

import GridCalEngine.Devices as dev
from GridCalEngine.Devices.types import ALL_DEV_TYPES, INJECTION_DEVICE_TYPES, FLUID_TYPES, AREA_TYPES
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Topology.topology import find_different_states
from GridCalEngine.enumerations import DeviceType, ActionType, SubObjectType

if TYPE_CHECKING:
    from GridCalEngine.Simulations.OPF.opf_ts_results import OptimalPowerFlowTimeSeriesResults
    from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults


def get_system_user() -> str:
    """
    Get the system mac + user name
    :return: string with the system mac address and the current user
    """

    # get the proper function to find the user depending on the platform
    if 'USERNAME' in os.environ:
        user = os.environ["USERNAME"]
    elif 'USER' in os.environ:
        user = os.environ["USER"]
    else:
        user = ''

    try:
        mac = get_mac()
    except:
        mac = ''

    return str(mac) + ':' + user


def get_fused_device_lst(elm_list: List[INJECTION_DEVICE_TYPES], property_names: list):
    """
    Fuse all the devices of a list by adding their selected properties
    :param elm_list: list of devices
    :param property_names: properties to fuse
    :return: list of one element
    """
    if len(elm_list) > 1:
        # more than a single element, fuse the list

        elm1 = elm_list[0]  # select the main device
        deletable_elms = [elm_list[i] for i in range(1, len(elm_list))]
        act_final = elm1.active
        act_prof_final = elm1.active_prof.toarray()

        # set the final active value
        for i in range(1, len(elm_list)):  # for each of the other generators
            elm2 = elm_list[i]

            # modify the final status
            act_final = bool(act_final + elm2.active)  # equivalent to OR

            if act_prof_final is not None:
                act_prof_final = (act_prof_final.toarray() + elm2.active_prof.toarray()).astype(bool)

        for prop in property_names:  # sum the properties

            # initialize the value with whatever it is inside elm1
            if 'prof' not in prop:
                # is a regular property
                val = getattr(elm1, prop) * elm1.active
            else:
                if act_prof_final is not None:
                    # it is a profile property
                    val = getattr(elm1, prop).toarray() * elm1.active_prof.toarray()
                else:
                    val = None

            for i in range(1, len(elm_list)):  # for each of the other generators
                elm2 = elm_list[i]

                if 'prof' not in prop:
                    # is a regular property
                    val += getattr(elm2, prop) * elm2.active
                else:
                    if act_prof_final is not None:
                        # it is a profile property
                        val += elm2.get_profile(prop).toarray() * elm2.active_prof.toarray()

            # set the final property value
            if 'prof' not in prop:
                elm1.set_snapshot_value(prop, val)
            else:
                elm1.set_profile(prop, val)

        # set the final active status
        elm1.active = act_final
        elm1.active_prof.set(act_prof_final)

        return [elm1], deletable_elms

    elif len(elm_list) == 1:
        # single element list, return it as it comes
        return elm_list, list()

    else:
        # the list is empty
        return list(), list()


class MultiCircuit(Assets):
    """
    The concept of circuit should be easy enough to understand. It represents a set of
    nodes (:ref:`buses<Bus>`) and :ref:`Branches<Branch>` (lines, transformers or other
    impedances).

    The :ref:`MultiCircuit<multicircuit>` class is the main object in **GridCal**. It
    represents a circuit that may contain islands. It is important to understand that a
    circuit split in two or more islands cannot be simulated as is, because the
    admittance matrix would be singular. The solution to this is to split the circuit
    in island-circuits. Therefore :ref:`MultiCircuit<multicircuit>` identifies the
    islands and creates individual **Circuit** objects for each of them.

    **GridCal** uses an object oriented approach for the data management. This allows
    to group the data in a smart way. In **GridCal** there are only two types of object
    directly declared in a **Circuit** or :ref:`MultiCircuit<multicircuit>` object.
    These are the :ref:`Bus<bus>` and the :ref:`Branch<branch>`. The Branches connect
    the buses and the buses contain all the other possible devices like loads,
    generators, batteries, etc. This simplifies enormously the management of element
    when adding, associating and deleting.

    .. code:: ipython3

        from GridCalEngine.multi_circuit import MultiCircuit
        grid = MultiCircuit(name="My grid")

    """
    __slots__ = (
        'name',
        'idtag',
        'comments',
        'model_version',
        'user_name',
        'Sbase',
        'fBase',
        'logger',
    )

    def __init__(self,
                 name: str = '',
                 Sbase: float = 100,
                 fbase: float = 50.0,
                 idtag: Union[str, None] = None):
        """
        class constructor
        :param name: name of the circuit
        :param Sbase: base power in MVA
        :param fbase: base frequency in Hz
        :param idtag: unique identifier
        """
        Assets.__init__(self)

        self.name: str = name

        if idtag is None:
            self.idtag: str = uuid4().hex
        else:
            self.idtag: str = idtag

        self.comments: str = ''

        # this is a number that serves
        self.model_version: int = 2

        # user mane
        self.user_name: str = get_system_user()

        # Base power (MVA)
        self.Sbase: float = Sbase

        # Base frequency in Hz
        self.fBase: float = fbase

        # logger of events
        self.logger: Logger = Logger()

    def to_dict(self):
        """
        Create grid configuration data
        :return:
        """
        return {
            'name': self.name,
            'comments': self.comments,
            'model_version': self.model_version,
            'user_name': self.user_name,
            'Sbase': self.Sbase,
            'fBase': self.fBase,
            'idtag': self.idtag,
        }

    def parse(self, data: Dict[str, str | int | float]):
        """
        Parse grid configuration data
        :param data:
        :return:
        """
        self.name = data.get("name", self.name)
        self.comments = data.get("comments", self.comments)
        self.model_version = data.get("model_version", self.model_version)
        self.user_name = data.get("user_name", self.user_name)
        self.Sbase = data.get("Sbase", self.Sbase)
        self.fBase = data.get("fBase", self.fBase)
        self.idtag = data.get("idtag", self.idtag)

    def __str__(self):
        return str(self.name)

    def valid_for_simulation(self) -> bool:
        """
        Checks if the data could be simulated
        :return: true / false
        """
        return self.get_bus_number() > 0

    def get_template_objects_list(self) -> List[ALL_DEV_TYPES]:
        """
        get objects_with_profiles in the form of list
        :return: List[dev.EditableDevice]
        """
        lst = list()
        for key, elm_list in self.template_objects_dict.items():
            for elm in elm_list:
                lst.append(elm)
        return lst

    def get_template_objects_str_dict(self) -> Dict[str, List[str]]:
        """
        get objects_with_profiles as a strings dictionary
        :return:
        """
        d = dict()
        for key, elm_list in self.template_objects_dict.items():
            d[key] = [o.device_type.value for o in elm_list]
        return d

    def get_bus_default_types(self) -> IntVec:
        """
        Return an array of bus types
        :return: number
        """
        return np.ones(len(self.buses), dtype=int)

    def get_dimensions(self):
        """
        Get the three dimensions of the circuit: number of buses, number of Branches, number of time steps
        :return: (nbus, nbranch, ntime)
        """
        return self.get_bus_number(), self.get_branch_number(), self.get_time_number()

    def get_branch_active_time_array(self) -> IntMat:
        """
        Get branch active matrix
        :return: array with branch active status
        """
        active = np.empty((self.get_time_number(),
                           self.get_branch_number(add_hvdc=False, add_vsc=False, add_switch=True)), dtype=int)
        for i, b in enumerate(self.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)):
            active[:, i] = b.active_prof.toarray()
        return active

    def get_topologic_group_dict(self) -> Dict[int, List[int]]:
        """
        Get numerical circuit time groups
        :return: Dictionary with the time: [array of times] represented by the index, for instance
                 {0: [0, 1, 2, 3, 4], 5: [5, 6, 7, 8]}
                 This means that [0, 1, 2, 3, 4] are represented by the topology of 0
                 and that [5, 6, 7, 8] are represented by the topology of 5
        """

        return find_different_states(states_array=self.get_branch_active_time_array())

    def copy(self) -> "MultiCircuit":
        """
        Returns a deep (true) copy of this circuit.
        """
        cpy = MultiCircuit(name=self.name, Sbase=self.Sbase, fbase=self.fBase, idtag=self.idtag)

        # TODO: make this list automatic
        ppts = ['branch_groups',
                'lines',
                'dc_lines',
                'transformers2w',
                'hvdc_lines',
                'vsc_devices',
                'upfc_devices',
                'switch_devices',
                'transformers3w',
                'windings',
                'series_reactances',
                'buses',
                'loads',
                'generators',
                'external_grids',
                'shunts',
                'batteries',
                'static_generators',
                'current_injections',
                'controllable_shunts',
                # 'connectivity_nodes',
                'bus_bars',
                'overhead_line_types',
                'wire_types',
                'underground_cable_types',
                'sequence_line_types',
                'transformer_types',
                'substations',
                'voltage_levels',
                'areas',
                'zones',
                'countries',
                'communities',
                'regions',
                'municipalities',
                'time_profile',
                'contingencies',
                'contingency_groups',
                'investments',
                'investments_groups',
                'technologies',
                'fuels',
                'emission_gases',
                # 'generators_technologies',
                # 'generators_fuels',
                # 'generators_emissions',
                'fluid_nodes',
                'fluid_paths',
                'pi_measurements',
                'qi_measurements',
                'vm_measurements',
                'pf_measurements',
                'qf_measurements',
                'if_measurements',
                'modelling_authorities'
                ]

        for pr in ppts:
            setattr(cpy, pr, copy.deepcopy(getattr(self, pr)))

        return cpy

    def build_graph(self) -> nx.MultiDiGraph:
        """
        Returns a networkx DiGraph object of the grid.
        """
        graph = nx.MultiDiGraph()

        bus_dictionary = dict()

        for i, bus in enumerate(self.buses):
            graph.add_node(i)
            bus_dictionary[bus.idtag] = i

        tuples = list()
        for branch_list in self.get_branch_lists(add_vsc=True, add_hvdc=True, add_switch=True):
            for branch in branch_list:
                f = bus_dictionary[branch.bus_from.idtag]
                t = bus_dictionary[branch.bus_to.idtag]
                if branch.device_type in [DeviceType.LineDevice,
                                          DeviceType.DCLineDevice,
                                          DeviceType.HVDCLineDevice]:
                    if hasattr(branch, 'X'):
                        w = branch.X
                    else:
                        w = 1e-3
                else:
                    if hasattr(branch, 'X'):
                        w = branch.X
                    else:
                        w = 1e-6

                # self.graph.add_edge(f, t)
                tuples.append((f, t, w))

        graph.add_weighted_edges_from(tuples)

        return graph

    def build_graph_real_power_flow(self, current_flow):
        """
        Returns a networkx DiGraph object of the grid.

        Arguments:

            **current_flow** (list): power_flow.results.If object
        """
        graph_real_power_flow = nx.DiGraph()

        current_flow_direction = np.real(current_flow) > 0
        bus_dictionary = self.get_elements_dict_by_type(element_type=DeviceType.BusDevice,
                                                        use_secondary_key=False)

        for branch_list in self.get_branch_lists(add_vsc=True, add_hvdc=True, add_switch=True):
            for direction, branch in zip(current_flow_direction, branch_list):
                f = bus_dictionary[branch.bus_from.idtag]
                t = bus_dictionary[branch.bus_to.idtag]
                if direction:
                    graph_real_power_flow.add_edge(f, t)
                else:
                    graph_real_power_flow.add_edge(t, f)

        return graph_real_power_flow

    def apply_all_branch_types(self) -> Logger:
        """
        Apply all the branch types
        """
        logger = Logger()
        for branch in self._lines:
            if branch.template is not None:
                branch.apply_template(branch.template, self.Sbase, freq=self.fBase, logger=logger)

        for branch in self._transformers2w:
            if branch.template is not None:
                branch.apply_template(branch.template, self.Sbase, logger=logger)

        return logger

    def convert_line_to_hvdc(self, line: dev.Line) -> dev.HvdcLine:
        """
        Convert a line to HVDC, this is the GUI way to create HVDC objects
        :param line: Line instance
        :return: HvdcLine
        """
        hvdc = dev.HvdcLine(bus_from=line.bus_from,
                            bus_to=line.bus_to,
                            name='HVDC Line',
                            active=line.active,
                            rate=line.rate,
                            )

        hvdc.active_prof = line.active_prof
        hvdc.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_hvdc(hvdc)

        # delete_with_dialogue the line from the circuit
        self.delete_line(line)

        return hvdc

    def convert_line_to_transformer(self, line: dev.Line) -> dev.Transformer2W:
        """
        Convert a line to Transformer
        :param line: Line instance
        :return: Transformer2W
        """
        transformer = dev.Transformer2W(bus_from=line.bus_from,
                                        bus_to=line.bus_to,
                                        name='Transformer',
                                        active=line.active,
                                        rate=line.rate,
                                        r=line.R,
                                        x=line.X,
                                        b=line.B,
                                        )

        transformer.active_prof = line.active_prof
        transformer.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_transformer2w(transformer)

        # delete_with_dialogue the line from the circuit
        self.delete_line(line)

        return transformer

    def convert_generator_to_battery(self, gen: dev.Generator) -> dev.Battery:
        """
        Convert a generator to battery
        :param gen: Generator instance
        :return: Transformer2W
        """
        batt = dev.Battery(name=gen.name,
                           idtag=gen.idtag,
                           P=gen.P,
                           power_factor=gen.Pf,
                           vset=gen.Vset,
                           is_controlled=gen.is_controlled,
                           Qmin=gen.Qmin,
                           Qmax=gen.Qmax,
                           Snom=gen.Snom,
                           active=gen.active,
                           Pmin=gen.Pmin,
                           Pmax=gen.Pmax,
                           Cost=gen.Cost,
                           Sbase=gen.Sbase,
                           enabled_dispatch=gen.enabled_dispatch,
                           mttf=gen.mttf,
                           mttr=gen.mttr,
                           r1=gen.R1, x1=gen.X1,
                           r0=gen.R0, x0=gen.X0,
                           r2=gen.R2, x2=gen.X2,
                           capex=gen.capex,
                           opex=gen.opex,
                           build_status=gen.build_status)

        batt.active_prof = gen.active_prof
        batt.P_prof = gen.P_prof
        batt.power_factor_prof = gen.Pf_prof
        batt.vset_prof = gen.Vset_prof

        # add device to the circuit
        self.add_battery(bus=gen.bus, api_obj=batt)

        # delete_with_dialogue the line from the circuit
        self.delete_injection_device(gen)

        return batt

    def convert_line_to_vsc(self, line: dev.Line) -> dev.VSC:
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :return: Nothing
        """
        vsc = dev.VSC(bus_from=line.bus_from,
                      bus_to=line.bus_to,
                      name='VSC',
                      active=line.active,
                      rate=line.rate)

        vsc.active_prof = line.active_prof
        vsc.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_vsc(vsc)

        # delete_with_dialogue the line from the circuit
        self.delete_line(line)

        return vsc

    def convert_line_to_upfc(self, line: dev.Line) -> dev.UPFC:
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :return: UPFC
        """
        upfc = dev.UPFC(bus_from=line.bus_from,
                        bus_to=line.bus_to,
                        name='UPFC',
                        active=line.active,
                        rate=line.rate,
                        rs=line.R,
                        xs=line.X)

        upfc.active_prof = line.active_prof
        upfc.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_upfc(upfc)

        # delete_with_dialogue the line from the circuit
        self.delete_line(line)

        return upfc

    def convert_line_to_series_reactance(self, line: dev.Line) -> dev.SeriesReactance:
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :return: SeriesReactance
        """
        series_reactance = dev.SeriesReactance(bus_from=line.bus_from,
                                               bus_to=line.bus_to,
                                               name='Series reactance',
                                               active=line.active,
                                               rate=line.rate,
                                               r=line.R,
                                               x=line.X,
                                               )

        series_reactance.active_prof = line.active_prof
        series_reactance.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_series_reactance(series_reactance)

        # delete_with_dialogue the line from the circuit
        self.delete_line(line)

        return series_reactance

    def convert_line_to_switch(self, line: dev.Line) -> dev.Switch:
        """
        Convert a line to voltage source converter
        :param line: Line instance
        :return: SeriesReactance
        """
        series_reactance = dev.Switch(bus_from=line.bus_from,
                                      bus_to=line.bus_to,
                                      name='Switch',
                                      active=line.active,
                                      rate=line.rate,
                                      r=line.R,
                                      x=line.X)

        series_reactance.active_prof = line.active_prof
        series_reactance.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_switch(series_reactance)

        # delete_with_dialogue the line from the circuit
        self.delete_line(line)

        return series_reactance

    def convert_fluid_path_to_line(self, fluid_path: dev.FluidPath) -> dev.Line:
        """
        Convert a line to voltage source converter
        :param fluid_path: FluidPath
        :return: Line
        """
        line = dev.Line(bus_from=fluid_path.source.bus,
                        bus_to=fluid_path.target.bus,
                        name='line',
                        active=True,
                        rate=9999,
                        r=0.001,
                        x=0.01)

        # add device to the circuit
        self.add_line(line)

        # delete_with_dialogue the line from the circuit
        self.delete_fluid_path(fluid_path)

        return line

    def plot_graph(self, ax=None):
        """
        Plot the grid.
        :param ax: Matplotlib axis object
        :return:
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111)

        graph = self.build_graph()
        nx.draw_spring(graph, ax=ax)

    def export_pf(self, file_name, power_flow_results):
        """
        Export power flow results to file.

        Arguments:

            **file_name** (str): Excel file name
        """

        if power_flow_results is not None:
            df_bus, df_branch = power_flow_results.export_all()

            df_bus.index = self.get_bus_names()
            df_branch.index = self.get_branch_names(add_hvdc=False, add_vsc=False, add_switch=True)

            with pd.ExcelWriter(file_name) as writer:  # pylint: disable=abstract-class-instantiated
                df_bus.to_excel(writer, 'Bus results')
                df_branch.to_excel(writer, 'Branch results')

        else:
            raise Exception('There are no power flow results!')

    def export_profiles(self, file_name):
        """
        Export object profiles to file.

        Arguments:

            **file_name** (str): Excel file name
        """

        if self.time_profile is not None:

            # collect data
            P = list()
            Q = list()
            Ir = list()
            Ii = list()
            G = list()
            B = list()
            P_gen = list()
            V_gen = list()

            load_names = list()
            gen_names = list()
            bat_names = list()

            for elm in self._loads:
                load_names.append(elm.name)
                P.append(elm.P_prof)
                Q.append(elm.Q_prof)

                Ir.append(elm.Ir_prof)
                Ii.append(elm.Ii_prof)

                G.append(elm.G_prof)
                B.append(elm.B_prof)

            for elm in self._generators:
                gen_names.append(elm.name)

                P_gen.append(elm.P_prof)
                V_gen.append(elm.Vset_prof)

            for elm in self._batteries:
                bat_names.append(elm.name)
                gen_names.append(elm.name)
                P_gen.append(elm.P_prof)
                V_gen.append(elm.Vset_prof)

            # form DataFrames
            P = pd.DataFrame(data=np.array(P).transpose(), index=self.time_profile, columns=load_names)
            Q = pd.DataFrame(data=np.array(Q).transpose(), index=self.time_profile, columns=load_names)
            Ir = pd.DataFrame(data=np.array(Ir).transpose(), index=self.time_profile, columns=load_names)
            Ii = pd.DataFrame(data=np.array(Ii).transpose(), index=self.time_profile, columns=load_names)
            G = pd.DataFrame(data=np.array(G).transpose(), index=self.time_profile, columns=load_names)
            B = pd.DataFrame(data=np.array(B).transpose(), index=self.time_profile, columns=load_names)
            P_gen = pd.DataFrame(data=np.array(P_gen).transpose(), index=self.time_profile, columns=gen_names)
            V_gen = pd.DataFrame(data=np.array(V_gen).transpose(), index=self.time_profile, columns=gen_names)

            with pd.ExcelWriter(file_name) as writer:  # pylint: disable=abstract-class-instantiated
                P.to_excel(writer, 'P loads')
                Q.to_excel(writer, 'Q loads')

                Ir.to_excel(writer, 'Ir loads')
                Ii.to_excel(writer, 'Ii loads')

                G.to_excel(writer, 'G loads')
                B.to_excel(writer, 'B loads')

                P_gen.to_excel(writer, 'P generators')
                V_gen.to_excel(writer, 'V generators')

        else:
            raise Exception('There are no time series!')

    def set_state(self, t: int):
        """
        Set the profiles state at the index t as the default values.
        """
        self.ensure_profiles_exist()

        for device in self.items():
            device.set_profile_values(t)

        self.snapshot_time = self.time_profile[t]

    def get_snapshot_time_str(self) -> str:
        """
        Get the snapshot datetime as a string
        :return: snapshot datetime string
        """
        return self.snapshot_time.strftime("%Y-%m-%d %H:%M:%S")

    def get_bus_branch_connectivity_matrix(self) -> Tuple[csc_matrix, csc_matrix, csc_matrix]:
        """
        Get the branch-bus connectivity
        :return: Cf, Ct, C
        """
        n = self.get_bus_number()
        m = self.get_branch_number()
        Cf = lil_matrix((m, n))
        Ct = lil_matrix((m, n))

        bus_dict = {bus: i for i, bus in enumerate(self.buses)}

        k = 0
        for branch_list in self.get_branch_lists(add_vsc=True, add_hvdc=True, add_switch=True):
            for br in branch_list:
                i = bus_dict[br.bus_from]  # store the row indices
                j = bus_dict[br.bus_to]  # store the row indices
                Cf[k, i] = 1
                Ct[k, j] = 1
                k += 1

        C = csc_matrix(Cf + Ct)
        Cf = csc_matrix(Cf)
        Ct = csc_matrix(Ct)

        return Cf, Ct, C

    def get_adjacent_matrix(self) -> csc_matrix:
        """
        Get the bus adjacent matrix
        :return: Adjacent matrix
        """
        Cf, Ct, C = self.get_bus_branch_connectivity_matrix()
        A = C.T @ C
        return A.tocsc()

    @staticmethod
    def get_adjacent_buses(A: csc_matrix, bus_idx):
        """
        Return array of indices of the buses adjacent to the bus given by it's index
        :param A: Adjacent matrix
        :param bus_idx: bus index
        :return: array of adjacent bus indices
        """
        return A.indices[A.indptr[bus_idx]:A.indptr[bus_idx + 1]]

    def get_center_location(self):
        """
        Get the mean coordinates of the system (lat, lon)
        """
        coord = np.array([b.get_coordinates() for b in self.buses])

        return np.mean(coord, axis=0).tolist()

    def snapshot_balance(self):
        """
        Creates a report DataFrame with the snapshot active power balance
        :return: DataFrame
        """

        data = {'Generators': 0.0,
                'Static generators': 0.0,
                'Batteries': 0.0,
                'Loads': 0.0,
                'Balance': 0.0}

        for gen in self._generators:
            if gen.active:
                data['Generators'] = data['Generators'] + gen.P

        for gen in self._static_generators:
            if gen.active:
                data['Static generators'] = data['Static generators'] + gen.P

        for gen in self._batteries:
            if gen.active:
                data['Batteries'] = data['Batteries'] + gen.P

        for load in self._loads:
            if load.active:
                data['Loads'] = data['Loads'] + load.P

        generation = data['Generators'] + data['Static generators'] + data['Batteries']
        load = data['Loads']
        data['Generation - Load'] = generation - data['Loads']
        data['Imbalance (%)'] = abs(load - generation) / max(load, generation) * 100.0

        return pd.DataFrame(data, index=['Power (MW)']).transpose()

    def scale_power(self, factor):
        """
        Modify the loads and generators
        :param factor: multiplier
        :return: Nothing
        """
        for elm in self.get_loads():
            elm.P *= factor
            elm.Q *= factor

        for elm in self.get_generators():
            elm.P *= factor

        for elm in self.get_static_generators():
            elm.P *= factor
            elm.Q *= factor

    def get_automatic_precision(self):
        """
        Get the precision that simulates correctly the power flow
        :return: tolerance parameter for the power flow options, exponent
        """
        injections = np.array([g.P for g in self.get_generators()])
        P = np.abs(injections) / self.Sbase
        P = P[P > 0]
        if np.sum(P) > 0:
            lg = np.log10(P)
            lg[lg == -np.inf] = 1e20
            exponent = int(np.min(np.abs(lg))) * 3
            tolerance = 1.0 / (10.0 ** exponent)
        else:
            exponent = 3
            tolerance = 1e-3

        return tolerance, exponent

    def fill_xy_from_lat_lon(self,
                             destructive: bool = True,
                             factor: float = 0.01,
                             remove_offset: bool = True) -> Logger:
        """
        fill the x and y value from the latitude and longitude values
        :param destructive: if true, the values are overwritten regardless, otherwise only if x and y are 0
        :param factor: Explosion factor
        :param remove_offset: delete the sometimes huge offset coming from pyproj
        :return Logger object
        """

        n = len(self.buses)
        lon = np.zeros(n)
        lat = np.zeros(n)
        for i, bus in enumerate(self.buses):
            lon[i] = bus.longitude
            lat[i] = bus.latitude

        # perform the coordinate transformation
        logger = Logger()
        try:
            import pyproj
        except ImportError:
            logger.add_error("pyproj is not installed")
            return logger

        transformer = pyproj.Transformer.from_crs(4326, 25830, always_xy=True)

        # the longitude is more reated to x, the latitude is more related to y
        x, y = transformer.transform(xx=lon, yy=lat)
        x *= factor
        y *= factor

        # delete the offset
        if remove_offset:
            x_min = np.min(x)
            y_max = np.max(y)
            x -= x_min + 100  # 100 is a healthy offset
            y -= y_max - 100  # 100 is a healthy offset

        # assign the values
        for i, bus in enumerate(self.buses):
            if destructive or (bus.x == 0.0 and bus.y == 0.0):
                bus.x = x[i]
                bus.y = y[i]

        return logger

    def fill_lat_lon_from_xy(self, destructive=True, factor=1.0, offset_x=0, offset_y=0):
        """
        Convert the coordinates to some random lat lon
        :param destructive:
        :param factor:
        :param offset_x:
        :param offset_y:
        :return:
        """
        n = len(self.buses)
        x = np.zeros(n)
        y = np.zeros(n)
        for i, bus in enumerate(self.buses):
            x[i] = bus.x * factor + offset_x
            y[i] = bus.y * factor + offset_y

        logger = Logger()
        try:
            import pyproj
        except ImportError:
            logger.add_error("pyproj is not installed")
            return logger

        proj_latlon = pyproj.Proj(proj='latlong', datum='WGS84')
        proj_xy = pyproj.Proj(proj="utm", zone=33, datum='WGS84')
        lonlat = pyproj.transform(proj_xy, proj_latlon, x, y)

        lon = lonlat[0]
        lat = lonlat[1]

        # assign the values
        for i, bus in enumerate(self.buses):
            if destructive or (bus.x == 0.0 and bus.y == 0.0):
                bus.latitude = lat[i]
                bus.longitude = lon[i]

        return logger

    def import_bus_lat_lon(self, df: pd.DataFrame, bus_col: str, lat_col: str, lon_col: str) -> Logger:
        """
        Import the buses' latitude and longitude
        :param df: Pandas DataFrame with the information
        :param bus_col: bus column name
        :param lat_col: latitude column name
        :param lon_col: longitude column name
        :return: Logger
        """
        logger = Logger()
        lats = df[lat_col].values
        lons = df[lon_col].values
        names = df[bus_col].values

        d = dict()
        for lat, lon, name in zip(lats, lons, names):
            d[str(name)] = (lat, lon)

        # assign the values
        for i, bus in enumerate(self.buses):
            if bus.name in d.keys():
                lat, lon = d[bus.name]
                bus.latitude = lat
                bus.longitude = lon
            elif bus.code in d.keys():
                lat, lon = d[bus.code]
                bus.latitude = lat
                bus.longitude = lon
            else:
                logger.add_error("No coordinates for bus", bus.name)

        return logger

    def get_bus_area_indices(self) -> IntVec:
        """
        Get array of area indices for each bus
        :return:
        """
        areas_dict = {elm: k for k, elm in enumerate(self.get_areas())}

        lst = np.zeros(len(self.buses), dtype=int)
        for k, bus in enumerate(self.buses):
            if bus.area is not None:
                lst[k] = areas_dict.get(bus.area, 0)
            else:
                lst[k] = 0
        return lst

    def get_areas_buses(self, areas: List[dev.Area]) -> List[Tuple[int, dev.Bus]]:
        """
        Get the selected buses
        :return: list of bus indices and bus ptr
        """
        lst: List[Tuple[int, dev.Bus]] = list()
        for k, bus in enumerate(self.buses):
            if bus.area in areas:
                lst.append((k, bus))
        return lst

    def get_zone_buses(self, zones: List[dev.Zone]) -> List[Tuple[int, dev.Bus]]:
        """
        Get the selected buses
        :return: list of bus indices and bus ptr
        """
        lst: List[Tuple[int, dev.Bus]] = list()
        for k, bus in enumerate(self.buses):
            if bus.zone in zones:
                lst.append((k, bus))
        return lst

    def get_country_buses(self, countries: List[dev.Country]) -> List[Tuple[int, dev.Bus]]:
        """
        Get the selected buses
        :return: list of bus indices and bus ptr
        """
        lst: List[Tuple[int, dev.Bus]] = list()
        for k, bus in enumerate(self.buses):
            if bus.country in countries:
                lst.append((k, bus))
        return lst

    def get_aggregation_buses(self, aggregations: List[AREA_TYPES]) -> List[Tuple[int, dev.Bus]]:
        """
        Get the selected buses
        :param aggregations:
        :return: list of bus indices and bus ptr
        """
        if len(aggregations) == 0:
            return list()

        if isinstance(aggregations[0], dev.Area):
            return self.get_areas_buses(aggregations)

        if isinstance(aggregations[0], dev.Zone):
            return self.get_zone_buses(aggregations)

        if isinstance(aggregations[0], dev.Country):
            return self.get_country_buses(aggregations)

        raise TypeError("Aggregation type not supported")

    def get_inter_areas_branches(self, a1: List[dev.Area], a2: List[dev.Area]) -> List[Tuple[int, object, float]]:
        """
        Get the inter-area Branches. HVDC Branches are not considered
        :param a1: Area from
        :param a2: Area to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)):
            if branch.bus_from.area in a1 and branch.bus_to.area in a2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from.area in a2 and branch.bus_to.area in a1:
                lst.append((k, branch, -1.0))
            else:
                pass
        return lst

    def get_inter_buses_branches(self, a1: Set[dev.Bus], a2: Set[dev.Bus]) -> List[Tuple[int, object, float]]:
        """
        Get the inter-buses Branches. HVDC Branches are not considered
        :param a1: Group of Buses 1
        :param a2: Group of Buses 1
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)):
            if branch.bus_from in a1 and branch.bus_to in a2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from in a2 and branch.bus_to in a1:
                lst.append((k, branch, -1.0))
        return lst

    def get_inter_areas_hvdc_branches(self, a1: List[dev.Area], a2: List[dev.Area]) -> List[Tuple[int, object, float]]:
        """
        Get the inter-area Branches
        :param a1: Area from
        :param a2: Area to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self._hvdc_lines):
            if branch.bus_from.area in a1 and branch.bus_to.area in a2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from.area in a2 and branch.bus_to.area in a1:
                lst.append((k, branch, -1.0))
            else:
                pass
        return lst

    def get_inter_buses_hvdc_branches(self, a1: Set[dev.Bus], a2: Set[dev.Bus]) -> List[Tuple[int, object, float]]:
        """
        Get the inter-area Branches
        :param a1: Group of Buses 1
        :param a2: Group of Buses 1
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self._hvdc_lines):
            if branch.bus_from in a1 and branch.bus_to in a2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from in a2 and branch.bus_to in a1:
                lst.append((k, branch, -1.0))
        return lst

    def get_inter_areas_vsc_branches(self, a1: List[dev.Area], a2: List[dev.Area]) -> List[Tuple[int, object, float]]:
        """
        Get the inter-area VSC
        :param a1: Area from
        :param a2: Area to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.vsc_devices):
            if branch.bus_from.area in a1 and branch.bus_to.area in a2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from.area in a2 and branch.bus_to.area in a1:
                lst.append((k, branch, -1.0))
            else:
                pass
        return lst

    def get_inter_buses_vsc_branches(self, a1: Set[dev.Bus], a2: Set[dev.Bus]) -> List[Tuple[int, object, float]]:
        """
        Get the inter-area VSC
        :param a1: Group of Buses 1
        :param a2: Group of Buses 1
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.vsc_devices):
            if branch.bus_from in a1 and branch.bus_to in a2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from in a2 and branch.bus_to in a1:
                lst.append((k, branch, -1.0))
        return lst

    def get_inter_zone_branches(self, z1: dev.Zone, z2: dev.Zone) -> List[Tuple[int, object, float]]:
        """
        Get the inter-area Branches
        :param z1: Zone from
        :param z2: Zone to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.get_branches(add_vsc=False, add_hvdc=False, add_switch=True)):
            if branch.bus_from.zone == z1 and branch.bus_to.zone == z2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from.zone == z2 and branch.bus_to.zone == z1:
                lst.append((k, branch, -1.0))
        return lst

    def get_branch_area_connectivity_matrix(self, a1: List[dev.Area], a2: List[dev.Area]) -> csc_matrix:
        """
        Get the inter area connectivity matrix
        :param a1: list of sending areas
        :param a2: list of receiving areas
        :return: Connectivity of the Branches to each sending or receiving area groups (Branches, 2)
        """
        area_dict = {a: i for i, a in enumerate(self._areas)}

        area1_list = [area_dict[a] for a in a1]
        area2_list = [area_dict[a] for a in a2]

        branches = self.get_branches()  # all including HVDC

        conn = lil_matrix((len(branches), 2), dtype=int)

        for k, elm in enumerate(branches):
            i = area_dict[elm.bus_from.area]
            j = area_dict[elm.bus_to.area]
            if i != j:
                if (i in area1_list) and (j in area2_list):
                    # from->to matches the areas
                    conn[k, 0] = 1
                    conn[k, 1] = -1
                elif (i in area2_list) and (j in area1_list):
                    # reverse the sign
                    conn[k, 0] = -1
                    conn[k, 1] = 1

        return conn.tocsc()

    def get_branch_areas_info(self) -> Tuple[List[str], IntVec, IntVec, IntVec, IntVec, IntVec]:
        """
        Get the area-branches information
        :return: area_names, bus_area_indices, F, T, hvdc_F, hvdc_T
        """
        area_dict: Dict[dev.Area, int] = {elm: i for i, elm in enumerate(self.get_areas())}
        bus_dict: Dict[dev.Bus, int] = self.get_bus_index_dict()

        area_names = [a.name for a in self.get_areas()]
        bus_area_indices = np.array([area_dict.get(b.area, 0) for b in self.get_buses()])

        branches = self.get_branches(add_vsc=False, add_hvdc=False, add_switch=True)
        F = np.zeros(len(branches), dtype=int)
        T = np.zeros(len(branches), dtype=int)
        for k, elm in enumerate(branches):
            F[k] = bus_dict[elm.bus_from]
            T[k] = bus_dict[elm.bus_to]

        hvdc = self.get_hvdc()
        hvdc_F = np.zeros(len(hvdc), dtype=int)
        hvdc_T = np.zeros(len(hvdc), dtype=int)
        for k, elm in enumerate(hvdc):
            hvdc_F[k] = bus_dict[elm.bus_from]
            hvdc_T[k] = bus_dict[elm.bus_to]

        return area_names, bus_area_indices, F, T, hvdc_F, hvdc_T

    def get_inter_aggregation_info(self,
                                   objects_from: List[AREA_TYPES],
                                   objects_to: List[AREA_TYPES]) -> dev.InterAggregationInfo:
        """
        Get the lists that help defining the inter area objects
        :param objects_from: list of objects from
        :param objects_to: list of objects to
        :return: InterAggregationInfo
        """
        logger = Logger()

        if len(objects_from) == 0 or len(objects_to) == 0:
            logger.add_error(msg=f'One of the lists has no elements')
            return dev.InterAggregationInfo(valid=False, lst_from=[], lst_to=[], lst_br=[], lst_br_hvdc=[],
                                            objects_from=[], objects_to=[], logger=logger)

        # find the buses in the aggregation from
        lst_from = self.get_aggregation_buses(objects_from)
        buses_from_set = {x[1] for x in lst_from}

        # find the buses in the aggregation to
        lst_to = self.get_aggregation_buses(objects_to)
        buses_to_set = {x[1] for x in lst_to}

        buses_intersection = buses_from_set & buses_to_set

        if len(buses_intersection) > 0:
            dev_tpe_from = objects_from[0].device_type
            dev_tpe_to = objects_to[0].device_type

            for bus in buses_intersection:
                logger.add_error(msg=f'Bus in both selected {dev_tpe_from.value} to {dev_tpe_to.value}',
                                 device_class=bus.device_type.value,
                                 device=bus.name)

            return dev.InterAggregationInfo(valid=False, lst_from=[], lst_to=[], lst_br=[], lst_br_hvdc=[],
                                            objects_from=[], objects_to=[], logger=logger)

        # find the tie branches
        lst_br = self.get_inter_buses_branches(buses_from_set, buses_to_set)
        lst_br_hvdc = self.get_inter_buses_hvdc_branches(buses_from_set, buses_to_set)

        return dev.InterAggregationInfo(valid=True,
                                        lst_from=lst_from,
                                        lst_to=lst_to,
                                        lst_br=lst_br,
                                        lst_br_hvdc=lst_br_hvdc,
                                        objects_from=objects_from,
                                        objects_to=objects_to,
                                        logger=logger)

    def change_base(self, Sbase_new: float):
        """
        Change the elements base impedance
        :param Sbase_new: new base impedance in MVA
        """
        Sbase_old = self.Sbase

        # get all the Branches with impedance
        elms = self.get_branches(add_vsc=False, add_hvdc=False, add_switch=True)

        # change the base at each element
        for elm in elms:
            elm.change_base(Sbase_old, Sbase_new)

        # assign the new base
        self.Sbase = Sbase_new

    def get_injection_devices_grouped_by_substation(self) -> Dict[
        dev.Substation, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]]:
        """
        Get the injection devices grouped by bus and by device type
        :return: Dict[bus, Dict[DeviceType, List[Injection devs]]
        """
        groups: Dict[dev.Substation, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]] = dict()

        for lst in self.get_injection_devices_lists():

            for elm in lst:

                if elm.bus.substation is not None:

                    devices_by_type = groups.get(elm.bus.substation, None)

                    if devices_by_type is None:
                        groups[elm.bus.substation] = {elm.device_type: [elm]}
                    else:
                        lst = devices_by_type.get(elm.device_type, None)
                        if lst is None:
                            devices_by_type[elm.device_type] = [elm]
                        else:
                            devices_by_type[elm.device_type].append(elm)

        return groups

    def get_injection_devices_grouped_by_bus(self) -> Dict[dev.Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]]:
        """
        Get the injection devices grouped by bus and by device type
        :return: Dict[bus, Dict[DeviceType, List[Injection devs]]
        """
        groups: Dict[dev.Bus, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]] = dict()

        for lst in self.get_injection_devices_lists():

            for elm in lst:

                devices_by_type = groups.get(elm.bus, None)

                if devices_by_type is None:
                    groups[elm.bus] = {elm.device_type: [elm]}
                else:
                    lst = devices_by_type.get(elm.device_type, None)
                    if lst is None:
                        devices_by_type[elm.device_type] = [elm]
                    else:
                        devices_by_type[elm.device_type].append(elm)

        return groups

    def get_injection_devices_grouped_by_fluid_node(self) -> Dict[dev.FluidNode, Dict[DeviceType, List[FLUID_TYPES]]]:
        """
        Get the injection devices grouped by bus and by device type
        :return: Dict[bus, Dict[DeviceType, List[Injection devs]]
        """
        groups: Dict[dev.FluidNode, Dict[DeviceType, List[FLUID_TYPES]]] = dict()

        for elm in self.get_fluid_injections():

            devices_by_type = groups.get(elm.plant, None)

            if devices_by_type is None:
                groups[elm.plant] = {elm.device_type: [elm]}
            else:
                lst = devices_by_type.get(elm.device_type, None)
                if lst is None:
                    devices_by_type[elm.device_type] = [elm]
                else:
                    devices_by_type[elm.device_type].append(elm)

        return groups

    def get_injection_devices_grouped_by_group_type(
            self,
            group_type: DeviceType) -> List[Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]]:
        """
        Get the injection devices grouped by bus and by device type
        :param group_type: some grouping Device Type (Region, Substation, Area, Country, etc...)
        :return: Dict[bus, Dict[DeviceType, List[Injection devs]]
        """
        result: List[Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]] = list()

        group_devices = self.get_elements_by_type(device_type=group_type)

        for group_device in group_devices:

            devices_by_type = dict()

            for elm in self.get_injection_devices_iter():

                if elm.bus is not None:
                    if group_type == DeviceType.AreaDevice:
                        if elm.bus.area is not None:
                            matches = elm.bus.area == group_device
                        else:
                            matches = False

                    elif group_type == DeviceType.ZoneDevice:
                        if elm.bus.zone is not None:
                            matches = elm.bus.zone == group_device
                        else:
                            matches = False

                    elif group_type == DeviceType.SubstationDevice:
                        if elm.bus.substation is not None:
                            matches = elm.bus.substation == group_device
                        else:
                            matches = False

                    elif group_type == DeviceType.CountryDevice:
                        if elm.bus.substation is not None:
                            matches = elm.bus.substation.country == group_device

                            if elm.bus.country is not None:
                                if elm.bus.substation.country != elm.bus.country:
                                    print(f"Bus <{elm.bus.name}> country is different from its substation country :/")
                        else:
                            if elm.bus.country is not None:
                                matches = elm.bus.country == group_device
                            else:
                                matches = False

                    elif group_type == DeviceType.CommunityDevice:
                        if elm.bus.substation is not None:
                            if elm.bus.substation.community is not None:
                                matches = elm.bus.substation.community == group_device
                            else:
                                matches = False
                        else:
                            matches = False

                    elif group_type == DeviceType.RegionDevice:
                        if elm.bus.substation is not None:
                            if elm.bus.substation.region is not None:
                                matches = elm.bus.substation.region == group_device
                            else:
                                matches = False
                        else:
                            matches = False

                    elif group_type == DeviceType.MunicipalityDevice:
                        if elm.bus.substation is not None:
                            if elm.bus.substation.municipality is not None:
                                matches = elm.bus.substation.municipality == group_device
                            else:
                                matches = False
                        else:
                            matches = False

                    else:
                        matches = False
                else:
                    matches = False

                # if we found a match ...
                if matches:
                    lst = devices_by_type.get(elm.device_type, None)
                    if lst is None:
                        devices_by_type[elm.device_type] = [elm]
                    else:
                        devices_by_type[elm.device_type].append(elm)

            result.append(devices_by_type)

        return result

    def get_batteries_by_bus(self) -> Dict[dev.Bus, List[dev.Battery]]:
        """
        Get the injection devices grouped by bus and by device type
        :return: Dict[bus, Dict[DeviceType, List[Injection devs]]
        """
        groups: Dict[dev.Bus, List[dev.Battery]] = dict()

        for elm in self.get_batteries():

            lst = groups.get(elm.bus, None)
            if lst is None:
                groups[elm.bus] = [elm]
            else:
                lst.append(elm)

        return groups

    def get_substation_buses(self, substation: dev.Substation) -> List[dev.Bus]:
        """
        Get the list of buses of this substation
        :param substation:
        :return:
        """
        lst: List[dev.Bus] = list()

        for bus in self.buses:
            if bus.substation == substation:
                lst.append(bus)

        return lst

    def fuse_devices(self) -> List[INJECTION_DEVICE_TYPES]:
        """
        Fuse all the different devices in a node to a single device per node
        :return:
        """
        list_of_deleted = list()
        for bus, devices_by_type in self.get_injection_devices_grouped_by_bus().items():

            for dev_tpe, injection_devs_list in devices_by_type.items():

                if len(injection_devs_list) > 1:
                    # there are more than one device of this type in the bus
                    # we keep the first, we delete_with_dialogue the others
                    if dev_tpe == DeviceType.GeneratorDevice:
                        _, to_delete = get_fused_device_lst(injection_devs_list,
                                                            ['P', 'Pmin', 'Pmax',
                                                             'Qmin', 'Qmax', 'Snom', 'P_prof'])
                    elif dev_tpe == DeviceType.BatteryDevice:
                        _, to_delete = get_fused_device_lst(injection_devs_list,
                                                            ['P', 'Pmin', 'Pmax',
                                                             'Qmin', 'Qmax', 'Snom', 'Enom', 'P_prof'])
                    elif dev_tpe == DeviceType.LoadDevice:
                        _, to_delete = get_fused_device_lst(injection_devs_list,
                                                            ['P', 'Q', 'Ir', 'Ii', 'G', 'B',
                                                             'P_prof', 'Q_prof'])
                    elif dev_tpe == DeviceType.StaticGeneratorDevice:
                        _, to_delete = get_fused_device_lst(injection_devs_list, ['P', 'Q', 'P_prof', 'Q_prof'])

                    elif dev_tpe == DeviceType.ShuntDevice:
                        _, to_delete = get_fused_device_lst(injection_devs_list, ['G', 'B', 'G_prof', 'B_prof'])

                    else:
                        to_delete = list()

                    # delete_with_dialogue elements
                    for elm in to_delete:
                        self.delete_injection_device(obj=elm)
                        list_of_deleted.append(elm)

        return list_of_deleted

    def set_generators_active_profile_from_their_active_power(self):
        """
        Modify the generators active profile to match the active power profile
        if P=0, active = False else active=True
        """
        for g in self.get_generators():
            g.active_prof.set(g.P_prof.toarray().astype(bool))

    def set_batteries_active_profile_from_their_active_power(self):
        """
        Modify the batteries active profile to match the active power profile
        if P=0, active = False else active=True
        """
        for g in self.get_batteries():
            g.active_prof.set(g.P_prof.toarray().astype(bool))

    def set_loads_active_profile_from_their_active_power(self):
        """
        Modify the loads active profile to match the active power profile
        if P=0, active = False else active=True
        """
        for ld in self.get_loads():
            ld.active_prof.set(ld.P_prof.toarray().astype(bool))

    def get_voltage_guess(self) -> CxVec:
        """
        Get the buses stored voltage guess
        :return: array of complex voltages per bus
        """
        v = np.zeros(len(self.buses), dtype=complex)

        for i, bus in enumerate(self.buses):
            if bus.active:
                v[i] = cmath.rect(bus.Vm0, bus.Va0)

        return v

    def get_Sbus(self) -> CxVec:
        """
        Get the complex bus power Injections
        :return: (nbus) [MW + j MVAr]
        """
        val = np.zeros(self.get_bus_number(), dtype=complex)
        bus_dict = self.get_bus_index_dict()

        for elm in self.get_injection_devices_iter():
            k = bus_dict[elm.bus]
            val[k] = elm.get_S()

        return val

    def get_Sbus_prof(self) -> CxMat:
        """
        Get the complex bus power Injections
        :return: (ntime, nbus) [MW + j MVAr]
        """
        val = np.zeros((self.get_time_number(), self.get_bus_number()), dtype=complex)

        bus_dict = self.get_bus_index_dict()

        for elm in self.get_injection_devices_iter():
            k = bus_dict[elm.bus]
            val[:, k] = elm.get_Sprof()

        return val

    def get_Sbus_prof_fixed(self) -> CxMat:
        """
        Get the complex bus power Injections considering those devices that cannot be dispatched
        This is, all devices except generators and batteries with enabled_dispatch=True
        :return: (ntime, nbus) [MW + j MVAr]
        """
        val = np.zeros((self.get_time_number(), self.get_bus_number()), dtype=complex)
        bus_dict = self.get_bus_index_dict()

        for elm in self.get_load_like_devices():
            k = bus_dict[elm.bus]
            val[:, k] = elm.get_Sprof()

        for elm in self.get_generation_like_devices():
            if not elm.enabled_dispatch:
                k = bus_dict[elm.bus]
                val[:, k] = elm.get_Sprof()

        return val

    def get_Sbus_prof_dispatchable(self) -> CxMat:
        """
        Get the complex bus power Injections only considering those devices that can be dispatched
        This is, generators and batteries with enabled_dispatch=True
        :return: (ntime, nbus) [MW + j MVAr]
        """
        val = np.zeros((self.get_time_number(), self.get_bus_number()), dtype=complex)
        bus_dict = self.get_bus_index_dict()

        for elm in self.get_generation_like_devices():
            if elm.enabled_dispatch:
                k = bus_dict[elm.bus]
                val[:, k] = elm.get_Sprof()

        return val

    def get_Pbus(self) -> Vec:
        """
        Get snapshot active power array per bus
        :return: Vec
        """
        return self.get_Sbus().real

    def get_Pbus_prof(self) -> Mat:
        """
        Get profiles active power per bus
        :return: Mat
        """
        return self.get_Sbus_prof().real

    def get_imbalance(self) -> float:
        """
        Get the system imbalance in per unit
        :return:
        """
        P = self.get_Pbus()
        Pg = P[P > 0].sum()
        Pl = -P[P < 0].sum()
        if Pl > 0:
            ratio = (Pg - Pl) / Pl
        else:
            ratio = 1.0

        return ratio

    def get_branch_rates_prof(self, add_hvdc=False, add_vsc=False, add_switch=True) -> Mat:
        """
        Get the complex bus power Injections
        :return: (ntime, nbr) [MVA]
        """
        val = np.zeros((self.get_time_number(),
                        self.get_branch_number(add_hvdc=add_hvdc, add_vsc=add_vsc, add_switch=add_switch)))

        for i, branch in enumerate(self.get_branches(add_hvdc=add_hvdc, add_vsc=add_vsc, add_switch=add_switch)):
            val[:, i] = branch.rate_prof.toarray()

        return val

    def get_branch_rates(self, add_hvdc=False, add_vsc=False, add_switch=True) -> Vec:
        """
        Get the complex bus power Injections
        :return: (nbr) [MVA]
        """
        val = np.zeros(self.get_branch_number(add_hvdc=add_hvdc, add_vsc=add_vsc, add_switch=add_switch))

        for i, branch in enumerate(self.get_branches(add_hvdc=add_hvdc, add_vsc=add_vsc, add_switch=add_switch)):
            val[i] = branch.rate

        return val

    def get_branch_contingency_rates_prof(self, add_hvdc=False, add_vsc=False, add_switch=True) -> Mat:
        """
        Get the complex bus power Injections
        :return: (ntime, nbr) [MVA]
        """
        val = np.zeros((self.get_time_number(),
                        self.get_branch_number(add_hvdc=add_hvdc, add_vsc=add_vsc, add_switch=add_switch)))

        for i, branch in enumerate(self.get_branches(add_hvdc=add_hvdc, add_vsc=add_vsc, add_switch=add_switch)):
            val[:, i] = branch.rate_prof.toarray() * branch.contingency_factor_prof.toarray()

        return val

    def get_branch_contingency_rates(self, add_hvdc=False, add_vsc=False, add_switch=True) -> Vec:
        """
        Get the complex bus power Injections
        :return: (nbr) [MVA]
        """
        val = np.zeros(self.get_branch_number(add_hvdc=add_hvdc, add_vsc=add_vsc, add_switch=add_switch))

        for i, branch in enumerate(self.get_branches(add_hvdc=add_hvdc, add_vsc=add_vsc, add_switch=add_switch)):
            val[i] = branch.rate_prof.toarray() * branch.contingency_factor.toarray()

        return val

    def get_gen_fuel_rates_sparse_matrix(self) -> csc_matrix:
        """
        Get the fuel rates matrix with relation to the generators
        should be used to get the fuel amounts by: Rates_mat x Pgen
        :return: CSC sparse matrix (n_fuel, n_gen)
        """
        nfuel = len(self._fuels)
        gen_index_dict = self.get_generator_indexing_dict()
        fuel_index_dict = self.get_fuel_indexing_dict()
        nelm = len(gen_index_dict)

        gen_fuel_rates_matrix: lil_matrix = lil_matrix((nfuel, nelm), dtype=float)

        # create associations between generators and fuels
        for generator in self.generators:
            for assoc in generator.fuels:
                gen_idx = gen_index_dict[generator.idtag]
                fuel_idx = fuel_index_dict[assoc.api_object.idtag]
                gen_fuel_rates_matrix[fuel_idx, gen_idx] = assoc.value

        return gen_fuel_rates_matrix.tocsc()

    def get_gen_emission_rates_sparse_matrix(self) -> csc_matrix:
        """
        Get the emission rates matrix with relation to the generators
        should be used to get the fuel amounts by: Rates_mat x Pgen
        :return: CSC sparse matrix (n_emissions, n_gen)
        """
        n_emissions = len(self._emission_gases)
        gen_index_dict = self.get_generator_indexing_dict()
        em_index_dict = self.get_emissions_indexing_dict()
        n_elm = len(gen_index_dict)

        gen_emissions_rates_matrix: lil_matrix = lil_matrix((n_emissions, n_elm), dtype=float)

        # create associations between generators and emissions
        for generator in self.generators:
            for assoc in generator.emissions:
                gen_idx = gen_index_dict[generator.idtag]
                em_idx = em_index_dict[assoc.api_object.idtag]
                gen_emissions_rates_matrix[em_idx, gen_idx] = assoc.value

        return gen_emissions_rates_matrix.tocsc()

    def get_gen_technology_connectivity_matrix(self) -> csc_matrix:
        """
        Get the technology connectivity matrix with relation to the generators
        should be used to get the generation per technology by: Tech_mat x Pgen
        :return: CSC sparse matrix (n_tech, n_gen)
        """
        ntech = len(self._technologies)
        gen_index_dict = self.get_generator_indexing_dict()
        tech_index_dict = self.get_technology_indexing_dict()
        nelm = len(gen_index_dict)

        gen_tech_proportions_matrix: lil_matrix = lil_matrix((ntech, nelm), dtype=int)

        # create associations between generators and technologies
        for generator in self.generators:
            for assoc in generator.technologies:
                gen_idx = gen_index_dict[generator.idtag]
                tech_idx = tech_index_dict[assoc.api_object.idtag]
                gen_tech_proportions_matrix[tech_idx, gen_idx] = assoc.value

        return gen_tech_proportions_matrix.tocsc()

    def get_batt_technology_connectivity_matrix(self) -> csc_matrix:
        """
        Get the technology connectivity matrix with relation to the generators
        should be used to get the generation per technology by: Tech_mat x Pgen
        :return: CSC sparse matrix (n_tech, n_gen)
        """
        ntech = len(self._technologies)
        gen_index_dict = self.get_batteries_indexing_dict()
        tech_index_dict = self.get_technology_indexing_dict()
        nelm = len(gen_index_dict)

        gen_tech_proportions_matrix: lil_matrix = lil_matrix((ntech, nelm), dtype=int)

        # create associations between generators and technologies
        for elm in self.batteries:
            for assoc in elm.technologies:
                gen_idx = gen_index_dict[elm.idtag]
                tech_idx = tech_index_dict[assoc.api_object.idtag]
                gen_tech_proportions_matrix[tech_idx, gen_idx] = assoc.value

        return gen_tech_proportions_matrix.tocsc()

    def set_investments_status(self,
                               investments_list: List[dev.Investment],
                               status: bool,
                               all_elements_dict: Union[None, dict[str, EditableDevice]] = None) -> None:
        """
        Set the active (and active profile) status of a list of investments' objects
        :param investments_list: list of investments
        :param status: status to set in the internal structures
        :param all_elements_dict: Dictionary of all elements (idtag -> object), if None if is computed
        """

        if all_elements_dict is None:
            all_elements_dict, dict_ok = self.get_all_elements_dict()

        for inv in investments_list:
            device_idtag = inv.device_idtag
            device = all_elements_dict[device_idtag]

            if hasattr(device, 'active'):
                device.active = status
                profile = device.get_profile('active')
                if profile is not None:
                    profile.fill(status)

    def merge_buses(self, bus1: dev.Bus, bus2: dev.Bus):
        """
        Transfer the injection elements' associations from bus2 to bus 1
        :param bus1: Bus that will receive the devices
        :param bus2: Bus that "donates" the devices
        """
        for elm in self.get_injection_devices():

            if elm.bus == bus2:
                elm.bus = bus1

    def compare_circuits(self, grid2: "MultiCircuit",
                         detailed_profile_comparison: bool = True,
                         skip_internals: bool = False,
                         tolerance: float = 1e-06) -> Tuple[bool, Logger]:
        """
        Compare this circuit with another circuits for equality
        :param grid2: MultiCircuit
        :param detailed_profile_comparison: if true, profiles are compared element-wise with the getters
        :param skip_internals: skip non visible properties
        :param tolerance
        :return: equal?, Logger with the comparison information
        """
        logger = Logger()

        if self.Sbase != grid2.Sbase:
            logger.add_error(msg="Different Sbase",
                             device_class="time",
                             value=grid2.Sbase,
                             expected_value=self.Sbase)

        if self.fBase != grid2.fBase:
            logger.add_error(msg="Different fBase",
                             device_class="time",
                             value=grid2.fBase,
                             expected_value=self.fBase)

        if self.get_time_number() != grid2.get_time_number():
            nt = 0
            logger.add_error(msg="Different number of time steps",
                             device_class="time",
                             value=grid2.get_time_number(),
                             expected_value=self.get_time_number())
        else:
            nt = self.get_time_number()

        if (self.snapshot_time != grid2.snapshot_time) and not skip_internals:
            logger.add_error(msg="Different snapshot times",
                             device_class="snapshot time",
                             value=str(grid2.get_snapshot_time_unix()),
                             expected_value=self.get_snapshot_time_unix())

        # for each category
        # for key, template_elms_list in self.categorized_template_objects_dict.items():

        # for each object type
        for template_elm in self.template_items():

            # get all objects of the type
            elms1 = self.get_elements_by_type(device_type=template_elm.device_type)
            elms2 = grid2.get_elements_by_type(device_type=template_elm.device_type)

            if len(elms1) != len(elms2):
                logger.add_error(msg="Different number of elements",
                                 device_class=template_elm.device_type.value,
                                 value=len(elms2),
                                 expected_value=len(elms1))
            else:
                # for every property
                for prop_name, prop in template_elm.registered_properties.items():

                    if skip_internals:
                        analyze = prop.display
                    else:
                        analyze = True

                    if analyze:
                        # for every pair of elements:
                        for elm1, elm2 in zip(elms1, elms2):

                            # compare the snapshot values
                            v1 = elm1.get_property_value(prop=prop, t_idx=None)
                            v2 = elm2.get_property_value(prop=prop, t_idx=None)

                            if prop.tpe == float:
                                if not np.isclose(v1, v2, atol=tolerance):
                                    logger.add_error(
                                        msg="Different snapshot values",
                                        device_class=template_elm.device_type.value,
                                        device_property=prop.name,
                                        value=v2,
                                        expected_value=v1)
                            elif prop.tpe == SubObjectType.Array:
                                if len(v1) != len(v2):
                                    logger.add_error(
                                        msg="Different array length",
                                        device_class=template_elm.device_type.value,
                                        device_property=prop.name,
                                        value=v2,
                                        expected_value=v1)
                                else:
                                    if not np.all(np.isclose(v1, v2, atol=tolerance)):
                                        logger.add_error(
                                            msg="Different array values",
                                            device_class=template_elm.device_type.value,
                                            device_property=prop.name,
                                            value=v2,
                                            expected_value=v1)
                            else:
                                if v1 != v2:
                                    logger.add_error(msg="Different snapshot values",
                                                     device_class=template_elm.device_type.value,
                                                     device_property=prop.name,
                                                     value=v2,
                                                     expected_value=v1)
                            if prop.has_profile():
                                p1 = elm1.get_profile_by_prop(prop=prop)
                                p2 = elm2.get_profile_by_prop(prop=prop)

                                if p1 != p2:
                                    logger.add_error(msg="Different profile values",
                                                     device_class=template_elm.device_type.value,
                                                     device_property=prop.name,
                                                     object_value=p2,
                                                     expected_object_value=p1)

                                if detailed_profile_comparison:
                                    for t_idx in range(nt):

                                        v1 = p1[t_idx]
                                        v2 = p2[t_idx]

                                        if v1 != v2:
                                            logger.add_error(msg="Different time series values",
                                                             device_class=template_elm.device_type.value,
                                                             device_property=prop.name,
                                                             device=str(elm1),
                                                             value=v2,
                                                             expected_value=v1)

                                        v1b = elm1.get_property_value(prop=prop, t_idx=t_idx)
                                        v2b = elm2.get_property_value(prop=prop, t_idx=t_idx)

                                        if v1 != v1b:
                                            logger.add_error(
                                                msg="Profile getting values differ with different getter methods!",
                                                device_class=template_elm.device_type.value,
                                                device_property=prop.name,
                                                device=str(elm1),
                                                value=v1b,
                                                expected_value=v1)

                                        if v2 != v2b:
                                            logger.add_error(
                                                msg="Profile getting values differ with different getter methods!",
                                                device_class=template_elm.device_type.value,
                                                device_property=prop.name,
                                                device=str(elm1),
                                                value=v1b,
                                                expected_value=v1)

        # if any error in the logger, bad
        return logger.error_count() == 0, logger

    def differentiate_circuits(self, base_grid: "MultiCircuit",
                               detailed_profile_comparison: bool = True,
                               force_second_pass: bool = False) -> Tuple[bool, Logger, "MultiCircuit"]:
        """
        Compare this circuit with another circuits for equality
        :param base_grid: MultiCircuit used as comparison base
        :param detailed_profile_comparison: if true, profiles are compared element-wise with the getters
        :param force_second_pass: if true, the base grid is inspected for elements that it contains that
                                  this grid doesn't (deletions)
        :return: equal?, Logger with the comparison information, MultiCircuit with the elements that have changed
        """
        logger = Logger()

        dgrid = MultiCircuit(name=self.name + " increment")
        dgrid.comments = f"Incremental grid created from {self.name} using {base_grid.name} as base."

        if self.get_time_number() != base_grid.get_time_number():
            nt = 0
            logger.add_error(msg="Different number of time steps",
                             device_class="time",
                             value=base_grid.get_time_number(),
                             expected_value=self.get_time_number())
        else:
            nt = self.get_time_number()

        if (self.snapshot_time.second != base_grid.snapshot_time.second or
                self.snapshot_time.minute != base_grid.snapshot_time.minute or
                self.snapshot_time.hour != base_grid.snapshot_time.hour or
                self.snapshot_time.day != base_grid.snapshot_time.day or
                self.snapshot_time.month != base_grid.snapshot_time.month or
                self.snapshot_time.year != base_grid.snapshot_time.year):
            logger.add_error(msg="Different snapshot times",
                             device_class="snapshot time",
                             value=str(base_grid.get_snapshot_time_unix),
                             expected_value=self.get_snapshot_time_unix)
        # if self.snapshot_time != base_grid.snapshot_time:
        #     logger.add_error(msg="Different snapshot times",
        #                      device_class="snapshot time",
        #                      value=str(base_grid.get_snapshot_time_unix),
        #                      expected_value=self.get_snapshot_time_unix)

        # --------------------------------------------------------------------------------------------------------------
        # Pass 1: compare this grid with the base to discover added and modified elements
        # --------------------------------------------------------------------------------------------------------------

        # get a dictionary of all the elements of the other circuit
        base_elements_dict, dict_ok = base_grid.get_all_elements_dict(logger=logger)

        if not dict_ok:
            return True, logger, dgrid

        for new_elm in self.items():  # for every device...
            action = ActionType.NoAction

            # try to search for the counterpart in the base circuit
            elm_from_base = base_elements_dict.get(new_elm.idtag, None)

            if elm_from_base is None:
                # not found in the base, add it
                action = ActionType.Add

            else:
                # check differences
                action, changed_props = elm_from_base.compare(
                    other=new_elm,
                    logger=logger,
                    detailed_profile_comparison=detailed_profile_comparison,
                    nt=nt
                )

            if action != ActionType.NoAction:
                new_element = new_elm.copy(forced_new_idtag=False)
                new_element.action = action
                dgrid.add_element(obj=new_element)
                logger.add_info(msg="Device added in the diff circuit",
                                device_class=new_element.device_type.value,
                                device_property=new_element.name, )

        # --------------------------------------------------------------------------------------------------------------
        # Pass 2: compare base with this grid to discover deleted elements
        # only relevant if both grids have the same idtag
        # --------------------------------------------------------------------------------------------------------------
        if self.idtag == base_grid.idtag or force_second_pass:

            # get a dictionary of all the elements of the other circuit
            here_elements_dict, dict_ok = self.get_all_elements_dict(logger=logger)

            if not dict_ok:
                return True, logger, dgrid

            for base_elm in base_grid.items():

                # try to search for the counterpart in the base circuit
                elm_from_here = here_elements_dict.get(base_elm.idtag, None)

                if elm_from_here is None:
                    # not found in here, it was deleted

                    new_element = base_elm.copy(forced_new_idtag=False)
                    new_element.action = ActionType.Delete
                    dgrid.add_element(obj=new_element)
                    logger.add_info(msg="Device deleted in the diff circuit",
                                    device_class=new_element.device_type.value,
                                    device_property=new_element.name, )

                else:
                    # the element exists here, we already checked that
                    pass

        # if any error in the logger, bad
        return logger.error_count() == 0, logger, dgrid

    def add_circuit(self, new_grid: "MultiCircuit") -> Logger:
        """
        Add a circuit to this circuit, keeping all elements (this is not equal to a circuit merge)
        :param new_grid: Circuit to insert
        :return: Logger
        """

        # re-id all elements
        new_grid.new_idtags()

        # add is the same as merge but the idtags are renewed so that there are no conflicts
        logger = self.merge_circuit(new_grid)

        return logger

    def merge_circuit(self, new_grid: "MultiCircuit") -> Logger:
        """
        Add a circuit to this circuit, keeping all elements (this is not equal to a circuit merge)
        :param new_grid: Circuit to insert
        :return: Logger
        """

        logger = Logger()

        all_elms_base_dict, ok = self.get_all_elements_dict(logger=logger)
        if not ok:
            return logger

        # add profiles if required
        if self.time_profile is not None:
            new_grid.time_profile = self.time_profile
            new_grid.ensure_profiles_exist()

        for new_elm in new_grid.items():
            self.merge_object(api_obj=new_elm,
                              all_elms_base_dict=all_elms_base_dict,
                              logger=logger)

        return logger

    def clean_branches(self,
                       bus_set: Set[dev.Bus],
                       logger: Logger) -> None:
        """
        Clean the branch references
        :param bus_set: Set of Buses
        :param logger: Logger
        """
        elements_to_delete = list()
        for lst in self.get_branch_lists(add_vsc=True, add_hvdc=True, add_switch=True):
            for elm in lst:
                if elm.bus_from is not None:
                    if elm.bus_from not in bus_set:
                        elm.bus_from = None
                        logger.add_info("Bus from set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="bus_from")

                if elm.bus_to is not None:
                    if elm.bus_to not in bus_set:
                        elm.bus_to = None
                        logger.add_info("Bus to set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="bus_to")

                # if the element is topologically isolated, delete_with_dialogue it
                if (elm.bus_from is None and elm.bus_to is None):
                    elements_to_delete.append(elm)

        for elm in elements_to_delete:
            self.delete_element(obj=elm)
            logger.add_info("Deleted isolated branch",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

    def clean_injections(self,
                         bus_set: Set[dev.Bus],
                         logger: Logger) -> None:
        """
        Clean the branch references
        :param bus_set: Set of Buses
        :param logger: Logger
        """
        elements_to_delete = list()
        for lst in self.get_injection_devices_lists():
            for elm in lst:
                if elm.bus is not None:
                    if elm.bus not in bus_set:
                        elm.bus = None
                        logger.add_info("Bus set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="bus")

                # if the element is topologically isolated, delete_with_dialogue it
                if elm.bus is None:
                    elements_to_delete.append(elm)

        for elm in elements_to_delete:
            self.delete_element(obj=elm)
            logger.add_info("Deleted isolated injection",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

    def clean_contingencies(self, all_dev: Dict[str, ALL_DEV_TYPES], logger: Logger) -> None:
        """
        Clean the contingencies and contingency groups
        :param all_dev:
        :param logger: Logger
        """
        contingencies_to_delete = list()

        # pass 1: detect the "null" contingencies
        for elm in self._contingencies:
            if elm.device_idtag not in all_dev.keys():
                contingencies_to_delete.append(elm)

        # pass 2: delete_with_dialogue the "null" contingencies
        for elm in contingencies_to_delete:
            self.delete_contingency(obj=elm)
            logger.add_info("Deleted isolated contingency",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

        # pass 3: count how many times a group is refferenced
        group_counter = np.zeros(len(self._contingency_groups), dtype=int)
        group_dict = {elm: i for i, elm in enumerate(self._contingency_groups)}
        for elm in self._contingencies:
            group_idx = group_dict[elm.group]
            group_counter[group_idx] += 1

        # pass 4: delete_with_dialogue unrefferenced groups
        groups_to_delete = [elm for i, elm in enumerate(self._contingency_groups) if group_counter[i] == 0]
        for elm in groups_to_delete:
            self.delete_contingency_group(obj=elm)
            logger.add_info("Deleted isolated contingency group",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

    def clean_remedial_actions(self, all_dev: Dict[str, ALL_DEV_TYPES], logger: Logger) -> None:
        """
        Clean the remedial actons and remedial actons groups
        :param all_dev:
        :param logger: Logger
        """
        ra_to_delete = list()

        # pass 1: detect the "null" contingencies
        for elm in self._remedial_actions:
            if elm.device_idtag not in all_dev.keys():
                ra_to_delete.append(elm)

        # pass 2: delete_with_dialogue the "null" contingencies
        for elm in ra_to_delete:
            self.delete_remedial_action(obj=elm)
            logger.add_info("Deleted isolated remedial action",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

        # pass 3: count how many times a group is refferenced
        group_counter = np.zeros(len(self._remedial_action_groups), dtype=int)
        group_dict = {elm: i for i, elm in enumerate(self._remedial_action_groups)}
        for elm in self._remedial_actions:
            group_idx = group_dict[elm.group]
            group_counter[group_idx] += 1

        # pass 4: delete_with_dialogue unrefferenced groups
        groups_to_delete = [elm for i, elm in enumerate(self._remedial_action_groups) if group_counter[i] == 0]
        for elm in groups_to_delete:
            self.delete_remedial_action_group(obj=elm)
            logger.add_info("Deleted isolated remedial action group",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

    def clean_investments(self, all_dev: Dict[str, ALL_DEV_TYPES], logger: Logger) -> None:
        """
        Clean the investments and investment groups
        :param all_dev:
        :param logger: Logger
        """
        contingencies_to_delete = list()

        # pass 1: detect the "null" contingencies
        for elm in self._investments:
            if elm.device_idtag not in all_dev.keys():
                contingencies_to_delete.append(elm)

        # pass 2: delete_with_dialogue the "null" contingencies
        for elm in contingencies_to_delete:
            self.delete_investment(obj=elm)
            logger.add_info("Deleted isolated investment",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

        # pass 3: count how many times a group is referenced
        group_counter = np.zeros(len(self._investments_groups), dtype=int)
        group_dict = {elm: i for i, elm in enumerate(self._investments_groups)}
        for elm in self._investments:
            group_idx = group_dict[elm.group]
            group_counter[group_idx] += 1

        # pass 4: delete_with_dialogue unreferenced groups
        groups_to_delete = [elm for i, elm in enumerate(self._investments_groups) if group_counter[i] == 0]
        for elm in groups_to_delete:
            self.delete_investment_groups(obj=elm)
            logger.add_info("Deleted isolated investment group",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

    def clean_technologies(self) -> None:
        """
        Clean the technology associations to deleted technologies
        """

        for elm_list in self.get_injection_devices_lists():
            for elm in elm_list:
                to_del = list()
                for assoc in elm.technologies:
                    if assoc.api_object not in self.technologies:
                        to_del.append(assoc)

                for assoc in to_del:
                    elm.technologies.remove(assoc)

    def clean(self) -> Logger:
        """
        Clean dead references
        """
        logger = Logger()
        bus_set = set(self.buses)
        all_dev, dict_ok = self.get_all_elements_dict()
        nt = self.get_time_number()

        self.clean_branches(bus_set=bus_set, logger=logger)
        self.clean_injections(bus_set=bus_set, logger=logger)
        self.clean_contingencies(all_dev=all_dev, logger=logger)
        self.clean_investments(all_dev=all_dev, logger=logger)
        self.clean_technologies()

        return logger

    def split_line(self,
                   original_line: Union[dev.Line],
                   position: float,
                   extra_km: float):
        """

        :param original_line:
        :param position:
        :param extra_km:
        :return:
        """

        # Each of the Branches will have the proportional impedance
        # Bus_from           Middle_bus            Bus_To
        # o----------------------o--------------------o
        #   >-------- x -------->|
        #   (x: distance measured in per unit (0~1)

        name = original_line.name + ' split'
        mid_sub = dev.Substation(name=name,
                                 area=original_line.bus_from.area,
                                 zone=original_line.bus_from.zone,
                                 country=original_line.bus_from.country)

        mid_vl = dev.VoltageLevel(name=name, substation=mid_sub)

        mid_bus = dev.Bus(name=name,
                          Vnom=original_line.bus_from.Vnom,
                          vmin=original_line.bus_from.Vmin,
                          vmax=original_line.bus_from.Vmax,
                          voltage_level=mid_vl,
                          substation=mid_sub,
                          area=original_line.bus_from.area,
                          zone=original_line.bus_from.zone,
                          country=original_line.bus_from.country)

        position_a = position + (extra_km / original_line.length) if original_line.length > 0.0 else position

        # create first split
        br1 = dev.Line(name=original_line.name + ' split 1',
                       bus_from=original_line.bus_from,
                       bus_to=mid_bus,
                       r=original_line.R * position_a,
                       x=original_line.X * position_a,
                       b=original_line.B * position_a,
                       r0=original_line.R0 * position_a,
                       x0=original_line.X0 * position_a,
                       b0=original_line.B0 * position_a,
                       r2=original_line.R2 * position_a,
                       x2=original_line.X2 * position_a,
                       b2=original_line.B2 * position_a,
                       length=original_line.length * position_a,
                       rate=original_line.rate,
                       contingency_factor=original_line.contingency_factor,
                       protection_rating_factor=original_line.protection_rating_factor)

        position_c = ((1.0 - position) + (extra_km / original_line.length)
                      if original_line.length > 0.0 else (1.0 - position))

        br2 = dev.Line(name=original_line.name + ' split 2',
                       bus_from=mid_bus,
                       bus_to=original_line.bus_to,
                       r=original_line.R * position_c,
                       x=original_line.X * position_c,
                       b=original_line.B * position_c,
                       r0=original_line.R0 * position_c,
                       x0=original_line.X0 * position_c,
                       b0=original_line.B0 * position_c,
                       r2=original_line.R2 * position_c,
                       x2=original_line.X2 * position_c,
                       b2=original_line.B2 * position_c,
                       length=original_line.length * position_c,
                       rate=original_line.rate,
                       contingency_factor=original_line.contingency_factor,
                       protection_rating_factor=original_line.protection_rating_factor)

        # deactivate the original line
        original_line.active = False
        original_line.active_prof.fill(False)

        # add to gridcal the new 2 lines and the bus
        self.add_substation(obj=mid_sub)
        self.add_voltage_level(obj=mid_vl)
        self.add_bus(mid_bus)
        self.add_line(br1)
        self.add_line(br2)

        # add new stuff as new investment
        inv_group = dev.InvestmentsGroup(name=original_line.name + ' split', category='Line split')
        self.add_investments_group(inv_group)
        self.add_investment(dev.Investment(name=mid_bus.name, device=mid_bus, group=inv_group))
        self.add_investment(dev.Investment(name=br1.name, device=br1, group=inv_group))
        self.add_investment(dev.Investment(name=br2.name, device=br2, group=inv_group))

        # include the deactivation of the original line
        self.add_investment(dev.Investment(name=original_line.name,
                                           device=original_line,
                                           status=False,
                                           group=inv_group))

        return mid_sub, mid_vl, mid_bus, br1, br2

    def split_line_int_out(self,
                           original_line: Union[dev.Line],
                           position: float,
                           km_io: float):
        """
        Split line with in/out
        :param original_line: Line device to split
        :param position: Position in per-unit (0, 1) measured from the "from" side where the splits happens
        :param km_io: Amount of kilometers to the Substation to connect with the in/out
        :return: mid_sub, mid_vl, B1, B2, B3, br1, br2, br3, br4
        """

        # Each of the Branches will have the proportional impedance
        # Bus_from              B1  B2                Bus_To
        # o----------------------o o--------------------o
        #                        | |   ^
        #                        | |   | km_io: Distance of the in/out in km
        #                        | |   ^
        #                         o  B3 (substation bus)
        #  >--------- x -------->|
        #  x: distance measured in per unit (0~1) from the "from" node

        # C(x, y) = (x1 + t * (x2 - x1), y1 + t * (y2 - y1))

        B1 = dev.Bus(name=original_line.name + ' split bus 1',
                     Vnom=original_line.bus_from.Vnom,
                     vmin=original_line.bus_from.Vmin,
                     vmax=original_line.bus_from.Vmax,
                     area=original_line.bus_from.area,
                     zone=original_line.bus_from.zone,
                     country=original_line.bus_from.country)

        B2 = dev.Bus(name=original_line.name + ' split bus 2',
                     Vnom=original_line.bus_from.Vnom,
                     vmin=original_line.bus_from.Vmin,
                     vmax=original_line.bus_from.Vmax,
                     area=original_line.bus_from.area,
                     zone=original_line.bus_from.zone,
                     country=original_line.bus_from.country)

        mid_sub = dev.Substation(name=original_line.name + ' new bus',
                                 area=original_line.bus_from.area,
                                 zone=original_line.bus_from.zone,
                                 country=original_line.bus_from.country)
        mid_vl = dev.VoltageLevel(name=original_line.name + ' new bus',
                                  substation=mid_sub)
        B3 = dev.Bus(name=original_line.name + ' new bus',
                     Vnom=original_line.bus_from.Vnom,
                     vmin=original_line.bus_from.Vmin,
                     vmax=original_line.bus_from.Vmax,
                     voltage_level=mid_vl,
                     substation=mid_sub,
                     area=original_line.bus_from.area,
                     zone=original_line.bus_from.zone,
                     country=original_line.bus_from.country)

        # create first split
        br1 = dev.Line(name=original_line.name + ' split 1',
                       bus_from=original_line.bus_from,
                       bus_to=B1,
                       r=original_line.R * position,
                       x=original_line.X * position,
                       b=original_line.B * position,
                       r0=original_line.R0 * position,
                       x0=original_line.X0 * position,
                       b0=original_line.B0 * position,
                       r2=original_line.R2 * position,
                       x2=original_line.X2 * position,
                       b2=original_line.B2 * position,
                       length=original_line.length * position,
                       rate=original_line.rate,
                       contingency_factor=original_line.contingency_factor,
                       protection_rating_factor=original_line.protection_rating_factor)

        position_c = 1.0 - position
        br2 = dev.Line(name=original_line.name + ' split 2',
                       bus_from=B2,
                       bus_to=original_line.bus_to,
                       r=original_line.R * position_c,
                       x=original_line.X * position_c,
                       b=original_line.B * position_c,
                       r0=original_line.R0 * position_c,
                       x0=original_line.X0 * position_c,
                       b0=original_line.B0 * position_c,
                       r2=original_line.R2 * position_c,
                       x2=original_line.X2 * position_c,
                       b2=original_line.B2 * position_c,
                       length=original_line.length * position_c,
                       rate=original_line.rate,
                       contingency_factor=original_line.contingency_factor,
                       protection_rating_factor=original_line.protection_rating_factor)

        # kilometers of the in/out apart from the original line
        proportion_io = km_io / original_line.length

        br3 = dev.Line(name=original_line.name + ' in',
                       bus_from=B1,
                       bus_to=B3,
                       r=original_line.R * proportion_io,
                       x=original_line.X * proportion_io,
                       b=original_line.B * proportion_io,
                       r0=original_line.R0 * proportion_io,
                       x0=original_line.X0 * proportion_io,
                       b0=original_line.B0 * proportion_io,
                       r2=original_line.R2 * proportion_io,
                       x2=original_line.X2 * proportion_io,
                       b2=original_line.B2 * proportion_io,
                       length=original_line.length * proportion_io,
                       rate=original_line.rate,
                       contingency_factor=original_line.contingency_factor,
                       protection_rating_factor=original_line.protection_rating_factor)

        br4 = dev.Line(name=original_line.name + ' out',
                       bus_from=B3,
                       bus_to=B2,
                       r=original_line.R * proportion_io,
                       x=original_line.X * proportion_io,
                       b=original_line.B * proportion_io,
                       r0=original_line.R0 * proportion_io,
                       x0=original_line.X0 * proportion_io,
                       b0=original_line.B0 * proportion_io,
                       r2=original_line.R2 * proportion_io,
                       x2=original_line.X2 * proportion_io,
                       b2=original_line.B2 * proportion_io,
                       length=original_line.length * proportion_io,
                       rate=original_line.rate,
                       contingency_factor=original_line.contingency_factor,
                       protection_rating_factor=original_line.protection_rating_factor)

        # deactivate the original line
        original_line.active = False
        original_line.active_prof.fill(False)

        # add to gridcal the new 2 lines and the bus
        self.add_substation(obj=mid_sub)
        self.add_voltage_level(obj=mid_vl)
        self.add_bus(B1)
        self.add_bus(B2)
        self.add_bus(B3)
        self.add_line(br1)
        self.add_line(br2)
        self.add_line(br3)
        self.add_line(br4)

        # add new stuff as new investment
        inv_group = dev.InvestmentsGroup(name=original_line.name + ' in/out', category='Line in/out')
        self.add_investments_group(inv_group)
        self.add_investment(dev.Investment(name=B1.name, device=B1, status=True, group=inv_group))
        self.add_investment(dev.Investment(name=B2.name, device=B2, status=True, group=inv_group))
        self.add_investment(dev.Investment(name=B3.name, device=B3, status=True, group=inv_group))
        self.add_investment(dev.Investment(name=br1.name, device=br1, status=True, group=inv_group))
        self.add_investment(dev.Investment(name=br2.name, device=br2, status=True, group=inv_group))
        self.add_investment(dev.Investment(name=br3.name, device=br3, status=True, group=inv_group))
        self.add_investment(dev.Investment(name=br4.name, device=br4, status=True, group=inv_group))

        # include the deactivation of the original line
        self.add_investment(dev.Investment(name=original_line.name,
                                           device=original_line,
                                           status=False, group=inv_group))

        return mid_sub, mid_vl, B1, B2, B3, br1, br2, br3, br4

    def add_catalogue(self, data: Assets):
        """
        Add the catalogue from another circuit
        :param data:
        :return:
        """
        self.transformer_types += data.transformer_types
        self.underground_cable_types += data.underground_cable_types
        self.wire_types += data.wire_types
        self.sequence_line_types += data.sequence_line_types

    def set_opf_ts_results(self, results: OptimalPowerFlowTimeSeriesResults):
        """
        Assign OptimalPowerFlowTimeSeriesResults to the objects
        :param results: OptimalPowerFlowTimeSeriesResults
        :return:
        """
        for i, elm in enumerate(self.get_generators()):
            elm.P_prof.set(results.generator_power[:, i])

        for i, elm in enumerate(self.get_batteries()):
            elm.P_prof.set(results.battery_power[:, i])

        for i, elm in enumerate(self.get_loads()):
            elm.P_prof.set(results.load_power[:, i])

    def set_opf_snapshot_results(self, results: OptimalPowerFlowResults):
        """
        Assign OptimalPowerFlowResults to the objects
        :param results:OptimalPowerFlowResults
        :return:
        """
        for i, elm in enumerate(self.get_generators()):
            elm.P = results.generator_power[i]

        for i, elm in enumerate(self.get_batteries()):
            elm.P = results.battery_power[i]

        # for i, elm in enumerate(self.get_loads()):
        #     elm.P = results.load_power[i]

    def get_reduction_sets(self, reduction_bus_indices: Sequence[int],
                           add_vsc=False, add_hvdc=False, add_switch=True) -> Tuple[IntVec, IntVec, IntVec, IntVec]:
        """
        Generate the set of bus indices for grid reduction
        :param reduction_bus_indices: array of bus indices to reduce (external set)
        :param add_vsc: Include the list of VSC?
        :param add_hvdc: Include the list of HvdcLine?
        :param add_switch: Include the list of Switch?
        :return: external, boundary, internal, boundary_branches
        """
        bus_idx_dict = self.get_bus_index_dict()
        external_set = set(reduction_bus_indices)
        boundary_set = set()
        internal_set = set()
        boundary_branches = list()

        for k, branch in enumerate(self.get_branches(add_vsc=add_vsc, add_hvdc=add_hvdc, add_switch=add_switch)):
            f = bus_idx_dict[branch.bus_from]
            t = bus_idx_dict[branch.bus_to]
            if f in external_set:
                if t in external_set:
                    # the branch belongs to the external set
                    pass
                else:
                    # the branch is a boundary link and t is a frontier bus
                    boundary_set.add(t)
                    boundary_branches.append(k)
            else:
                # we know f is not external...

                if t in external_set:
                    # f is not in the external set, but t is: the branch is a boundary link and f is a frontier bus
                    boundary_set.add(f)
                    boundary_branches.append(k)
                else:
                    # f nor t are in the external set: both belong to the internal set
                    internal_set.add(f)
                    internal_set.add(t)

        # buses cannot be in both the internal and boundary set
        elms_to_remove = list()
        for i in internal_set:
            if i in boundary_set:
                elms_to_remove.append(i)

        for i in elms_to_remove:
            internal_set.remove(i)

        # convert to arrays and sort
        external = np.sort(np.array(list(external_set)))
        boundary = np.sort(np.array(list(boundary_set)))
        internal = np.sort(np.array(list(internal_set)))
        boundary_branches = np.array(boundary_branches)

        return external, boundary, internal, boundary_branches

    def get_buses_from_objects(self, elements: List[ALL_DEV_TYPES]) -> Set[dev.Bus]:
        """
        Returns set of buses belonging to the list elements

        :param elements: list of objects
        :return: set of buses
        """

        buses = set()

        for sel_obj in elements:

            if isinstance(sel_obj, dev.Bus):
                root_bus = sel_obj

            elif isinstance(sel_obj, dev.Generator):
                root_bus = sel_obj.bus

            elif isinstance(sel_obj, dev.Battery):
                root_bus = sel_obj.bus

            elif isinstance(sel_obj, dev.Load):
                root_bus = sel_obj.bus

            elif isinstance(sel_obj, dev.Shunt):
                root_bus = sel_obj.bus

            elif isinstance(sel_obj, dev.Line):
                root_bus = sel_obj.bus_from

            elif isinstance(sel_obj, dev.Transformer2W):
                root_bus = sel_obj.bus_from

            elif isinstance(sel_obj, dev.DcLine):
                root_bus = sel_obj.bus_from

            elif isinstance(sel_obj, dev.HvdcLine):
                root_bus = sel_obj.bus_from

            elif isinstance(sel_obj, dev.VSC):
                root_bus = sel_obj.bus_from

            elif isinstance(sel_obj, dev.UPFC):
                root_bus = sel_obj.bus_from

            elif isinstance(sel_obj, dev.Switch):
                root_bus = sel_obj.bus_from

            elif isinstance(sel_obj, dev.VoltageLevel):
                root_bus = None
                sel = self.get_voltage_level_buses(vl=sel_obj)
                for bus in sel:
                    buses.add(bus)

            elif isinstance(sel_obj, dev.Substation):
                root_bus = None
                sel = self.get_substation_buses(substation=sel_obj)
                for bus in sel:
                    buses.add(bus)

            else:
                root_bus = None

            if root_bus is not None:
                buses.add(root_bus)

        return buses

    def get_topology_data(self, t_idx: int | None = None):
        """
        Get the topology data
        :param t_idx: time_index (None for the snapshot)
        :return:
        """
        nbus = self.get_bus_number()
        nbr = self.get_branch_number(add_vsc=False, add_hvdc=False, add_switch=True)
        nhvdc = self.get_hvdc_number()
        nvsc = self.get_vsc_number()

        bus_active = np.zeros(nbus, dtype=int)
        bus_dict: Dict[dev.Bus, int] = dict()
        for i, elm in enumerate(self.buses):
            bus_active[i] = elm.active if t_idx is None else elm.active_prof[t_idx]
            bus_dict[elm] = i

        branch_active = np.zeros(nbr, dtype=int)
        branch_F = np.zeros(nbr, dtype=int)
        branch_T = np.zeros(nbr, dtype=int)
        for i, elm in enumerate(self.get_branches(add_vsc=False, add_hvdc=False, add_switch=True)):
            branch_active[i] = elm.active if t_idx is None else elm.active_prof[t_idx]
            branch_F[i] = bus_dict[elm.bus_from]
            branch_T[i] = bus_dict[elm.bus_to]

        hvdc_active = np.zeros(nhvdc, dtype=int)
        hvdc_F = np.zeros(nhvdc, dtype=int)
        hvdc_T = np.zeros(nhvdc, dtype=int)
        for i, elm in enumerate(self.hvdc_lines):
            hvdc_active[i] = elm.active if t_idx is None else elm.active_prof[t_idx]
            hvdc_F[i] = bus_dict[elm.bus_from]
            hvdc_T[i] = bus_dict[elm.bus_to]

        vsc_active = np.zeros(nvsc, dtype=int)
        vsc_F = np.zeros(nvsc, dtype=int)
        vsc_T = np.zeros(nvsc, dtype=int)
        for i, elm in enumerate(self.vsc_devices):
            vsc_active[i] = elm.active if t_idx is None else elm.active_prof[t_idx]
            vsc_F[i] = bus_dict[elm.bus_from]
            vsc_T[i] = bus_dict[elm.bus_to]

        return (bus_active,
                branch_active, branch_F, branch_T,
                hvdc_active, hvdc_F, hvdc_T,
                vsc_active, vsc_F, vsc_T)
