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

import os
import cmath
import copy
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Union, Set
from uuid import getnode as get_mac, uuid4
import networkx as nx
from matplotlib import pyplot as plt
from scipy.sparse import csc_matrix, lil_matrix

from GridCalEngine.Devices.assets import Assets
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.basic_structures import IntVec, Vec, Mat, CxVec, IntMat, CxMat

import GridCalEngine.Devices as dev
from GridCalEngine.Devices.types import ALL_DEV_TYPES, INJECTION_DEVICE_TYPES, FLUID_TYPES
from GridCalEngine.basic_structures import Logger
import GridCalEngine.Topology.topology as tp
from GridCalEngine.Topology.topology_processor import TopologyProcessorInfo, process_grid_topology_at
from GridCalEngine.enumerations import DeviceType, ActionType


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

    def __str__(self):
        return str(self.name)

    def valid_for_simulation(self) -> bool:
        """
        Checks if the data could be simulated
        :return: true / false
        """
        return (self.get_bus_number() + self.get_connectivity_nodes_number()) > 0

    def get_objects_with_profiles_list(self) -> List[ALL_DEV_TYPES]:
        """
        get objects_with_profiles in the form of list
        :return: List[dev.EditableDevice]
        """
        lst = list()
        for key, elm_list in self.objects_with_profiles.items():
            for elm in elm_list:
                lst.append(elm)
        return lst

    def get_objects_with_profiles_str_dict(self) -> Dict[str, List[str]]:
        """
        get objects_with_profiles as a strings dictionary
        :return:
        """
        d = dict()
        for key, elm_list in self.objects_with_profiles.items():
            d[key] = [o.device_type.value for o in elm_list]
        return d

    def get_bus_default_types(self) -> IntVec:
        """
        Return an array of bus types
        :return: number
        """
        return np.ones(len(self._buses), dtype=int)

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
        active = np.empty((self.get_time_number(), self.get_branch_number_wo_hvdc()), dtype=int)
        for i, b in enumerate(self.get_branches_wo_hvdc()):
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

        return tp.find_different_states(states_array=self.get_branch_active_time_array())

    def copy(self) -> "MultiCircuit":
        """
        Returns a deep (true) copy of this circuit.
        """
        cpy = MultiCircuit(name=self.name, Sbase=self.Sbase, fbase=self.fBase, idtag=self.idtag)

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

                'connectivity_nodes',
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

    def build_graph(self):
        """
        Returns a networkx DiGraph object of the grid.
        """
        graph = nx.DiGraph()

        bus_dictionary = dict()

        for i, bus in enumerate(self._buses):
            graph.add_node(i)
            bus_dictionary[bus.idtag] = i

        tuples = list()
        for branch_list in self.get_branch_lists():
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

        for branch_list in self.get_branch_lists():
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
                branch.apply_template(branch.template, self.Sbase, logger=logger)

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
                            cn_from=line.cn_from,
                            cn_to=line.cn_to,
                            name='HVDC Line',
                            active=line.active,
                            rate=line.rate,
                            )

        hvdc.active_prof = line.active_prof
        hvdc.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_hvdc(hvdc)

        # delete the line from the circuit
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
                                        cn_from=line.cn_from,
                                        cn_to=line.cn_to,
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

        # delete the line from the circuit
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
        self.add_battery(bus=gen.bus, api_obj=batt, cn=gen.cn)

        # delete the line from the circuit
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
                      cn_from=line.cn_from,
                      cn_to=line.cn_to,
                      name='VSC',
                      active=line.active,
                      rate=line.rate,
                      r=line.R,
                      x=line.X,
                      Beq=line.B,
                      tap_module=1.0,
                      )

        vsc.active_prof = line.active_prof
        vsc.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_vsc(vsc)

        # delete the line from the circuit
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
                        cn_from=line.cn_from,
                        cn_to=line.cn_to,
                        name='UPFC',
                        active=line.active,
                        rate=line.rate,
                        rs=line.R,
                        xs=line.X)

        upfc.active_prof = line.active_prof
        upfc.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_upfc(upfc)

        # delete the line from the circuit
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
                                               cn_from=line.cn_from,
                                               cn_to=line.cn_to,
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

        # delete the line from the circuit
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
                                      cn_from=line.cn_from,
                                      cn_to=line.cn_to,
                                      name='Switch',
                                      active=line.active,
                                      rate=line.rate,
                                      r=line.R,
                                      x=line.X)

        series_reactance.active_prof = line.active_prof
        series_reactance.rate_prof = line.rate_prof

        # add device to the circuit
        self.add_switch(series_reactance)

        # delete the line from the circuit
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

        # delete the line from the circuit
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
            df_branch.index = self.get_branch_names_wo_hvdc()

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
            E_batt = list()

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
                E_batt.append(elm.energy_array)

            # form DataFrames
            P = pd.DataFrame(data=np.array(P).transpose(), index=self.time_profile, columns=load_names)
            Q = pd.DataFrame(data=np.array(Q).transpose(), index=self.time_profile, columns=load_names)
            Ir = pd.DataFrame(data=np.array(Ir).transpose(), index=self.time_profile, columns=load_names)
            Ii = pd.DataFrame(data=np.array(Ii).transpose(), index=self.time_profile, columns=load_names)
            G = pd.DataFrame(data=np.array(G).transpose(), index=self.time_profile, columns=load_names)
            B = pd.DataFrame(data=np.array(B).transpose(), index=self.time_profile, columns=load_names)
            P_gen = pd.DataFrame(data=np.array(P_gen).transpose(), index=self.time_profile, columns=gen_names)
            V_gen = pd.DataFrame(data=np.array(V_gen).transpose(), index=self.time_profile, columns=gen_names)
            E_batt = pd.DataFrame(data=np.array(E_batt).transpose(), index=self.time_profile, columns=bat_names)

            with pd.ExcelWriter(file_name) as writer:  # pylint: disable=abstract-class-instantiated
                P.to_excel(writer, 'P loads')
                Q.to_excel(writer, 'Q loads')

                Ir.to_excel(writer, 'Ir loads')
                Ii.to_excel(writer, 'Ii loads')

                G.to_excel(writer, 'G loads')
                B.to_excel(writer, 'B loads')

                P_gen.to_excel(writer, 'P generators')
                V_gen.to_excel(writer, 'V generators')

                E_batt.to_excel(writer, 'Energy batteries')

        else:
            raise Exception('There are no time series!')

    def set_state(self, t: int):
        """
        Set the profiles state at the index t as the default values.
        """
        for device in self.items_declared():
            device.set_profile_values(t)

        self.snapshot_time = self.time_profile[t]

    def get_bus_branch_connectivity_matrix(self) -> Tuple[csc_matrix, csc_matrix, csc_matrix]:
        """
        Get the branch-bus connectivity
        :return: Cf, Ct, C
        """
        n = self.get_bus_number()
        m = self.get_branch_number()
        Cf = lil_matrix((m, n))
        Ct = lil_matrix((m, n))

        bus_dict = {bus: i for i, bus in enumerate(self._buses)}

        k = 0
        for branch_list in self.get_branch_lists():
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
        A = C.T * C
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
        coord = np.array([b.get_coordinates() for b in self._buses])

        return coord.mean(axis=0).tolist()

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

    def get_used_templates(self):
        """
        Get a list of the used templates in the objects
        :return: list
        """
        val = set()

        branches = self.get_branches()

        for branch in branches:
            if hasattr(branch, 'template'):
                obj = getattr(branch, 'template')
                val.add(obj)

                # if it is a tower, add the wire templates too
                if obj.device_type == DeviceType.OverheadLineTypeDevice:
                    for wire in obj.wires_in_tower:
                        val.add(wire)

        return list(val)

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
        :param remove_offset: remove the sometimes huge offset coming from pyproj
        :return Logger object
        """

        n = len(self._buses)
        lon = np.zeros(n)
        lat = np.zeros(n)
        for i, bus in enumerate(self._buses):
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

        # remove the offset
        if remove_offset:
            x_min = np.min(x)
            y_max = np.max(y)
            x -= x_min + 100  # 100 is a healthy offset
            y -= y_max - 100  # 100 is a healthy offset

        # assign the values
        for i, bus in enumerate(self._buses):
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
        n = len(self._buses)
        x = np.zeros(n)
        y = np.zeros(n)
        for i, bus in enumerate(self._buses):
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
        for i, bus in enumerate(self._buses):
            if destructive or (bus.x == 0.0 and bus.y == 0.0):
                bus.latitude = lat[i]
                bus.longitude = lon[i]

        return logger

    def import_bus_lat_lon(self, df: pd.DataFrame, bus_col, lat_col, lon_col) -> Logger:
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
        for i, bus in enumerate(self._buses):
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

        lst = np.zeros(len(self._buses), dtype=int)
        for k, bus in enumerate(self._buses):
            if bus.area is not None:
                lst[k] = areas_dict.get(bus.area, 0)
            else:
                lst[k] = 0
        return lst

    def get_area_buses(self, area: dev.Area) -> List[Tuple[int, dev.Bus]]:
        """
        Get the selected buses
        :return:
        """
        lst: List[Tuple[int, dev.Bus]] = list()
        for k, bus in enumerate(self._buses):
            if bus.area == area:
                lst.append((k, bus))
        return lst

    def get_areas_buses(self, areas: List[dev.Area]) -> List[Tuple[int, dev.Bus]]:
        """
        Get the selected buses
        :return:
        """
        lst: List[Tuple[int, dev.Bus]] = list()
        for k, bus in enumerate(self._buses):
            if bus.area in areas:
                lst.append((k, bus))
        return lst

    def get_zone_buses(self, zone: dev.Zone) -> List[Tuple[int, dev.Bus]]:
        """
        Get the selected buses
        :return:
        """
        lst: List[Tuple[int, dev.Bus]] = list()
        for k, bus in enumerate(self._buses):
            if bus.zone == zone:
                lst.append((k, bus))
        return lst

    def get_inter_area_branches(self, a1: dev.Area, a2: dev.Area):
        """
        Get the inter-area Branches
        :param a1: Area from
        :param a2: Area to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.get_branches()):
            if branch.bus_from.area == a1 and branch.bus_to.area == a2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from.area == a2 and branch.bus_to.area == a1:
                lst.append((k, branch, -1.0))
        return lst

    def get_inter_areas_branches(self, a1: List[dev.Area], a2: List[dev.Area]) -> List[Tuple[int, object, float]]:
        """
        Get the inter-area Branches. HVDC Branches are not considered
        :param a1: Area from
        :param a2: Area to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.get_branches_wo_hvdc()):
            if branch.bus_from.area in a1 and branch.bus_to.area in a2:
                lst.append((k, branch, 1.0))
            elif branch.bus_from.area in a2 and branch.bus_to.area in a1:
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
        return lst

    def get_inter_zone_branches(self, z1: dev.Zone, z2: dev.Zone) -> List[Tuple[int, object, float]]:
        """
        Get the inter-area Branches
        :param z1: Zone from
        :param z2: Zone to
        :return: List of (branch index, branch object, flow sense w.r.t the area exchange)
        """
        lst: List[Tuple[int, object, float]] = list()
        for k, branch in enumerate(self.get_branches()):
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

        branches = self.get_branches_wo_hvdc()
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

    def change_base(self, Sbase_new: float):
        """
        Change the elements base impedance
        :param Sbase_new: new base impedance in MVA
        """
        Sbase_old = self.Sbase

        # get all the Branches with impedance
        elms = self.get_branches_wo_hvdc()

        # change the base at each element
        for elm in elms:
            elm.change_base(Sbase_old, Sbase_new)

        # assign the new base
        self.Sbase = Sbase_new

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

    def get_injection_devices_grouped_by_cn(self) -> Dict[dev.ConnectivityNode,
    Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]]:
        """
        Get the injection devices grouped by bus and by device type
        :return: Dict[ConnectivityNode, Dict[DeviceType, List[Injection devs]]
        """
        groups: Dict[dev.ConnectivityNode, Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]] = dict()

        for lst in self.get_injection_devices_lists():

            for elm in lst:

                devices_by_type = groups.get(elm.cn, None)

                if devices_by_type is None:
                    groups[elm.cn] = {elm.device_type: [elm]}
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
        :return: Dict[bus, Dict[DeviceType, List[Injection devs]]
        """
        result: List[Dict[DeviceType, List[INJECTION_DEVICE_TYPES]]] = list()

        group_devices = self.get_elements_by_type(device_type=group_type)

        for group_device in group_devices:

            devices_by_type = dict()

            for lst in self.get_injection_devices_lists():

                for elm in lst:

                    if group_type == DeviceType.AreaDevice:
                        matches = elm.bus.area == group_device

                    elif group_type == DeviceType.ZoneDevice:
                        matches = elm.bus.zone == group_device

                    elif group_type == DeviceType.SubstationDevice:
                        matches = elm.bus.substation == group_device

                    elif group_type == DeviceType.CountryDevice:
                        matches = ((elm.bus.country == group_device) or
                                   (elm.bus.substation.country == group_device))

                    elif group_type == DeviceType.CommunityDevice:
                        matches = (elm.bus.substation.community == group_device)

                    elif group_type == DeviceType.RegionDevice:
                        matches = elm.bus.substation.region == group_device

                    elif group_type == DeviceType.MunicipalityDevice:
                        matches = elm.bus.substation.municipality == group_device

                    else:
                        matches = False

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
                    # we keep the first, we delete the others
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

                    # delete elements
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
        v = np.zeros(len(self._buses), dtype=complex)

        for i, bus in enumerate(self._buses):
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

        for elm in self.get_injection_devices():
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

        for elm in self.get_injection_devices():
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

    def get_branch_rates_prof_wo_hvdc(self) -> Mat:
        """
        Get the complex bus power Injections
        :return: (ntime, nbr) [MVA]
        """
        val = np.zeros((self.get_time_number(), self.get_branch_number_wo_hvdc()))

        for i, branch in enumerate(self.get_branches_wo_hvdc()):
            val[:, i] = branch.rate_prof.toarray()

        return val

    def get_branch_rates_wo_hvdc(self) -> Vec:
        """
        Get the complex bus power Injections
        :return: (nbr) [MVA]
        """
        val = np.zeros(self.get_branch_number_wo_hvdc())

        for i, branch in enumerate(self.get_branches_wo_hvdc()):
            val[i] = branch.rate

        return val

    def get_branch_contingency_rates_prof_wo_hvdc(self) -> Mat:
        """
        Get the complex bus power Injections
        :return: (ntime, nbr) [MVA]
        """
        val = np.zeros((self.get_time_number(), self.get_branch_number_wo_hvdc()))

        for i, branch in enumerate(self.get_branches_wo_hvdc()):
            val[:, i] = branch.rate_prof.toarray() * branch.contingency_factor_prof.toarray()

        return val

    def get_branch_contingency_rates_wo_hvdc(self) -> Vec:
        """
        Get the complex bus power Injections
        :return: (nbr) [MVA]
        """
        val = np.zeros(self.get_branch_number_wo_hvdc())

        for i, branch in enumerate(self.get_branches_wo_hvdc()):
            val[i] = branch.rate_prof.toarray() * branch.contingency_factor.toarray()

        return val

    def get_fuel_rates_sparse_matrix(self) -> csc_matrix:
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

    def get_emission_rates_sparse_matrix(self) -> csc_matrix:
        """
        Get the emission rates matrix with relation to the generators
        should be used to get the fuel amounts by: Rates_mat x Pgen
        :return: CSC sparse matrix (n_emissions, n_gen)
        """
        nemissions = len(self._emission_gases)
        gen_index_dict = self.get_generator_indexing_dict()
        em_index_dict = self.get_emissions_indexing_dict()
        nelm = len(gen_index_dict)

        gen_emissions_rates_matrix: lil_matrix = lil_matrix((nemissions, nelm), dtype=float)

        # create associations between generators and emissions
        for generator in self.generators:
            for assoc in generator.emissions:
                gen_idx = gen_index_dict[generator.idtag]
                em_idx = em_index_dict[assoc.api_object.idtag]
                gen_emissions_rates_matrix[em_idx, gen_idx] = assoc.value

        return gen_emissions_rates_matrix.tocsc()

    def get_technology_connectivity_matrix(self) -> csc_matrix:
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
            for assoc in generator.fuels:
                gen_idx = gen_index_dict[generator.idtag]
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
            all_elements_dict = self.get_all_elements_dict()

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
                         skip_internals: bool = False) -> Tuple[bool, Logger]:
        """
        Compare this circuit with another circuits for equality
        :param grid2: MultiCircuit
        :param detailed_profile_comparison: if true, profiles are compared element-wise with the getters
        :param skip_internals: skip non visible properties
        :return: equal?, Logger with the comparison information
        """
        logger = Logger()

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
        for key, template_elms_list in self.objects_with_profiles.items():

            # for each object type
            for template_elm in template_elms_list:

                # get all objects of the type
                elms1 = self.get_elements_by_type(device_type=template_elm.device_type)
                elms2 = grid2.get_elements_by_type(device_type=template_elm.device_type)

                if len(elms1) != len(elms2):
                    logger.add_error(msg="Different number of elements",
                                     device_class=template_elm.device_type.value,
                                     value=len(elms2),
                                     expected_value=len(elms1))

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

                            if v1 != v2:
                                logger.add_error(msg="Different snapshot values",
                                                 device_class=template_elm.device_type.value,
                                                 device_property=prop.name,
                                                 value=v2,
                                                 expected_value=v1)

                            if prop.has_profile():
                                p1 = elm1.get_profile_by_prop(prop=prop)
                                p2 = elm1.get_profile_by_prop(prop=prop)

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
                               detailed_profile_comparison: bool = True) -> Tuple[bool, Logger, "MultiCircuit"]:
        """
        Compare this circuit with another circuits for equality
        :param base_grid: MultiCircuit used as comparison base
        :param detailed_profile_comparison: if true, profiles are compared element-wise with the getters
        :return: equal?, Logger with the comparison information, Multicircuit with the elements that have changed
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

        if self.snapshot_time != base_grid.snapshot_time:
            logger.add_error(msg="Different snapshot times",
                             device_class="snapshot time",
                             value=str(base_grid.get_snapshot_time_unix),
                             expected_value=self.get_snapshot_time_unix)

        # get a dictionary of all the elements of the other circuit
        base_elements_dict = base_grid.get_all_elements_dict()

        for elm_from_here in self.items():  # for every device...
            action = ActionType.NoAction

            # try to search for the counterpart in the base circuit
            elm_from_base = base_elements_dict.get(elm_from_here.idtag, None)

            if elm_from_base is None:
                # not found in the base, add it
                action = ActionType.Add

            else:
                # check differences
                for prop_name, prop in elm_from_here.registered_properties.items():

                    # compare the snapshot values
                    v1 = elm_from_here.get_property_value(prop=prop, t_idx=None)
                    v2 = elm_from_base.get_property_value(prop=prop, t_idx=None)

                    if v1 != v2:
                        logger.add_info(msg="Different snapshot values",
                                        device_class=elm_from_here.device_type.value,
                                        device_property=prop.name,
                                        value=v2,
                                        expected_value=v1)
                        action = ActionType.Modify

                    if prop.has_profile():
                        p1 = elm_from_here.get_profile_by_prop(prop=prop)
                        p2 = elm_from_here.get_profile_by_prop(prop=prop)

                        if p1 != p2:
                            logger.add_info(msg="Different profile values",
                                            device_class=elm_from_here.device_type.value,
                                            device_property=prop.name,
                                            object_value=p2,
                                            expected_object_value=p1)
                            action = ActionType.Modify

                        if detailed_profile_comparison:
                            for t_idx in range(nt):

                                v1 = p1[t_idx]
                                v2 = p2[t_idx]

                                if v1 != v2:
                                    logger.add_info(msg="Different time series values",
                                                    device_class=elm_from_here.device_type.value,
                                                    device_property=prop.name,
                                                    device=str(elm_from_here),
                                                    value=v2,
                                                    expected_value=v1)
                                    action = ActionType.Modify

                                v1b = elm_from_here.get_property_value(prop=prop, t_idx=t_idx)
                                v2b = elm_from_base.get_property_value(prop=prop, t_idx=t_idx)

                                if v1 != v1b:
                                    logger.add_info(
                                        msg="Profile values differ with different getter methods!",
                                        device_class=elm_from_here.device_type.value,
                                        device_property=prop.name,
                                        device=str(elm_from_here),
                                        value=v1b,
                                        expected_value=v1)
                                    action = ActionType.Modify

                                if v2 != v2b:
                                    logger.add_info(
                                        msg="Profile getting values differ with different getter methods!",
                                        device_class=elm_from_here.device_type.value,
                                        device_property=prop.name,
                                        device=str(elm_from_here),
                                        value=v1b,
                                        expected_value=v1)
                                    action = ActionType.Modify

            if action != ActionType.NoAction:
                new_element = elm_from_here.copy(forced_new_idtag=False)
                new_element.action = action
                dgrid.add_element(obj=new_element)
                logger.add_info(msg="Device added in the diff circuit",
                                device_class=new_element.device_type.value,
                                device_property=new_element.name, )

        # if any error in the logger, bad
        return logger.error_count() == 0, logger, dgrid

    def add_circuit(self, circuit: "MultiCircuit") -> Logger:
        """
        Add a circuit to this circuit
        :param circuit: Circuit to insert
        :return: Logger
        """

        logger = Logger()

        # add profiles if required
        if self.time_profile is not None:

            for bus in circuit._buses:
                bus.create_profiles(index=self.time_profile)

            for lst in [circuit._lines, circuit._transformers2w, circuit._hvdc_lines]:
                for branch in lst:
                    branch.create_profiles(index=self.time_profile)

        for api_object in circuit.items():
            self.add_or_replace_object(api_obj=api_object, logger=logger)

        return logger

    def clean_branches(self,
                       nt: int,
                       bus_set: Set[dev.Bus],
                       cn_set: Set[dev.ConnectivityNode],
                       logger: Logger) -> None:
        """
        Clean the branch refferences
        :param nt: number of time steps
        :param bus_set: Set of Buses
        :param cn_set: Set of connectivity nodes
        :param logger: Logger
        """
        elements_to_delete = list()
        for lst in self.get_branch_lists():
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

                if elm.cn_from is not None:
                    if elm.cn_from not in cn_set:
                        elm.cn_from = None
                        logger.add_info("Cn from set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="cn_from")

                if elm.cn_to is not None:
                    if elm.cn_to not in cn_set:
                        elm.cn_to = None
                        logger.add_info("Cn to set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="cn_to")

                all_bus_from_prof_none = True
                all_bus_to_prof_none = True
                for t_idx in range(nt):
                    if elm.bus_from_prof[t_idx] is not None:
                        if elm.bus_from_prof[t_idx] not in bus_set:
                            elm.bus_from_prof[t_idx] = None
                        else:
                            all_bus_from_prof_none = False

                    if elm.bus_to_prof[t_idx] is not None:
                        if elm.bus_to_prof[t_idx] not in bus_set:
                            elm.bus_to_prof[t_idx] = None
                        else:
                            all_bus_to_prof_none = False

                # if the element is topologically isolated, delete it
                if (all_bus_from_prof_none and all_bus_to_prof_none
                        and elm.bus_from is None and elm.bus_to is None
                        and elm.cn_from is None and elm.cn_to is None):
                    elements_to_delete.append(elm)

        for elm in elements_to_delete:
            self.delete_element(obj=elm)
            logger.add_info("Deleted isolated branch",
                            device=elm.idtag,
                            device_class=elm.device_type.value)

    def clean_injections(self,
                         nt: int,
                         bus_set: Set[dev.Bus],
                         cn_set: Set[dev.ConnectivityNode],
                         logger: Logger) -> None:
        """
        Clean the branch refferences
        :param nt: number of time steps
        :param bus_set: Set of Buses
        :param cn_set: Set of connectivity nodes
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

                if elm.cn is not None:
                    if elm.cn not in cn_set:
                        elm.cn = None
                        logger.add_info("Cn set to None",
                                        device=elm.idtag,
                                        device_class=elm.device_type.value,
                                        device_property="cn")

                all_bus_prof_none = True
                for t_idx in range(nt):
                    if elm.bus_prof[t_idx] is not None:
                        if elm.bus_prof[t_idx] not in bus_set:
                            elm.bus_prof[t_idx] = None
                        else:
                            all_bus_prof_none = False

                # if the element is topologically isolated, delete it
                if all_bus_prof_none and elm.bus is None and elm.cn is None:
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

        # pass 2: delete the "null" contingencies
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

        # pass 4: delete unrefferenced groups
        groups_to_delete = [elm for i, elm in enumerate(self._contingency_groups) if group_counter[i] == 0]
        for elm in groups_to_delete:
            self.delete_contingency_group(obj=elm)
            logger.add_info("Deleted isolated contingency group",
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

        # pass 2: delete the "null" contingencies
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

        # pass 4: delete unreferenced groups
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
        bus_set = set(self._buses)
        cn_set = set(self._connectivity_nodes)
        all_dev = self.get_all_elements_dict()
        nt = self.get_time_number()

        self.clean_branches(nt=nt, bus_set=bus_set, cn_set=cn_set, logger=logger)
        self.clean_injections(nt=nt, bus_set=bus_set, cn_set=cn_set, logger=logger)
        self.clean_contingencies(all_dev=all_dev, logger=logger)
        self.clean_investments(all_dev=all_dev, logger=logger)
        self.clean_technologies()

        return logger

    def convert_to_node_breaker(self) -> None:
        """
        Convert this MultiCircuit in-place from bus/branch to node/breaker network model
        """

        bus_to_busbar_cn = dict()  # relate a bus to its equivalent busbar's cn
        for bus in self._buses:
            bus_bar = dev.BusBar(name='Artificial_BusBar_{}'.format(bus.name))
            self.add_bus_bar(bus_bar)
            bus_to_busbar_cn[bus.idtag] = bus_bar.cn
            bus_bar.cn.code = bus.code  # for soft checking later
            if bus_bar.cn.default_bus:
                bus_bar.cn.default_bus.code = bus.code  # for soft checking later

        # add the cn's at the branches
        for lst in [self.get_branches(), self.get_switches()]:
            for elm in lst:
                if elm.bus_from:
                    elm.cn_from = bus_to_busbar_cn.get(elm.bus_from.idtag, None)
                if elm.bus_to:
                    elm.cn_to = bus_to_busbar_cn.get(elm.bus_to.idtag, None)

        # add the cn's at the branches
        for lst in self.get_injection_devices_lists():
            for elm in lst:
                if elm.bus:
                    elm.cn = bus_to_busbar_cn.get(elm.bus.idtag, None)

    def convert_to_node_breaker_adding_switches(self) -> None:
        """
        Convert this MultiCircuit in-place from bus/branch to node/breaker network model,
        adding switches at the extremes of every branch
        """

        bus_to_busbar_cn = dict()  # relate a bus to its equivalent busbar's cn
        for bus in self._buses:
            bus_bar = dev.BusBar(name='Artificial_BusBar_{}'.format(bus.name))
            self.add_bus_bar(bus_bar)
            bus_to_busbar_cn[bus.idtag] = bus_bar.cn
            bus_bar.cn.code = bus.code  # for soft checking later
            if bus_bar.cn.default_bus:
                bus_bar.cn.default_bus.code = bus.code  # for soft checking later

        # branches
        for elm in self.get_branches():
            # Create two new connectivity nodes
            cnfrom = dev.ConnectivityNode(name='Artificial_CN_from_L{}'.format(elm.name))
            cnto = dev.ConnectivityNode(name='Artificial_CN_to_L{}'.format(elm.name))
            self.add_connectivity_node(cnfrom)
            self.add_connectivity_node(cnto)
            elm.cn_to = cnto
            elm.cn_from = cnfrom

            # Create two new switches
            sw1 = dev.Switch(name='Artificial_SW_from_L{}'.format(elm.name),
                             cn_from=bus_to_busbar_cn[elm.bus_from.idtag],
                             cn_to=cnfrom,
                             active=True)
            sw2 = dev.Switch(name='Artificial_SW_to_L{}'.format(elm.name),
                             cn_from=cnto,
                             cn_to=bus_to_busbar_cn[elm.bus_to.idtag],
                             active=True)
            self.add_switch(sw1)
            self.add_switch(sw2)

        # injections
        for elm in self.get_injection_devices():
            # TODO: Add the posibbility to add a switch here too
            elm.cn = bus_to_busbar_cn[elm.bus.idtag]

        # Removing original buses
        bidx = [b for b in self.get_buses()]
        for b in bidx:
            self.delete_bus(b)

    def process_topology_at(self,
                            t_idx: Union[int, None] = None,
                            logger: Union[Logger, None] = None,
                            debug: int = 0) -> TopologyProcessorInfo:
        """
        Topology processor finding the Buses that calculate a certain node-breaker topology
        This function fill the bus pointers into the grid object, and adds any new bus required for simulation
        :param t_idx: Time index, None for the Snapshot
        :param logger: Logger object
        :param debug: Debug level
        :return: TopologyProcessorInfo
        """

        return process_grid_topology_at(grid=self,
                                        t_idx=t_idx,
                                        logger=logger,
                                        debug=debug)

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
        self.add_investment(dev.Investment(name=mid_bus.name, device_idtag=mid_bus.idtag, group=inv_group))
        self.add_investment(dev.Investment(name=br1.name, device_idtag=br1.idtag, group=inv_group))
        self.add_investment(dev.Investment(name=br2.name, device_idtag=br2.idtag, group=inv_group))

        # include the deactivation of the original line
        self.add_investment(dev.Investment(name=original_line.name,
                                           device_idtag=original_line.idtag,
                                           status=False, group=inv_group))

        return mid_sub, mid_vl, mid_bus, br1, br2

    def split_line_int_out(self,
                           original_line: Union[dev.Line],
                           position: float,
                           km_io: float):
        """

        :param original_line:
        :param position:
        :param km_io:
        :return:
        """

        # Each of the Branches will have the proportional impedance
        # Bus_from           Middle_bus            Bus_To
        # o----------------------o--------------------o
        #   >-------- x -------->|
        #   (x: distance measured in per unit (0~1)

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

        # kilometers of the in/out appart from the original line
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
        self.add_investment(
            dev.Investment(name=B1.name, device_idtag=B1.idtag, status=True, group=inv_group))
        self.add_investment(
            dev.Investment(name=B2.name, device_idtag=B2.idtag, status=True, group=inv_group))
        self.add_investment(
            dev.Investment(name=B3.name, device_idtag=B3.idtag, status=True, group=inv_group))
        self.add_investment(
            dev.Investment(name=br1.name, device_idtag=br1.idtag, status=True, group=inv_group))
        self.add_investment(
            dev.Investment(name=br2.name, device_idtag=br2.idtag, status=True, group=inv_group))
        self.add_investment(
            dev.Investment(name=br3.name, device_idtag=br3.idtag, status=True, group=inv_group))
        self.add_investment(
            dev.Investment(name=br4.name, device_idtag=br4.idtag, status=True, group=inv_group))

        # include the deactivation of the original line
        self.add_investment(dev.Investment(name=original_line.name,
                                           device_idtag=original_line.idtag,
                                           status=False, group=inv_group))

        return mid_sub, mid_vl, B1, B2, B3, br1, br2, br3, br4
