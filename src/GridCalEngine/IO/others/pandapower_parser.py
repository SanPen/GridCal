# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Dict
import sqlite3
import json

import pandas as pd

import GridCalEngine.Devices as dev
from GridCalEngine.Devices.types import ALL_DEV_TYPES
from GridCalEngine.basic_structures import Logger

try:
    from pandapower import from_pickle, from_sqlite, from_json, from_excel
    from pandapower.auxiliary import pandapowerNet

    PANDAPOWER_AVAILABLE = True

except ImportError:
    PANDAPOWER_AVAILABLE = False


def is_pandapower_pickle(file_path):
    """
    Check if a file is pandapower Pickle
    :param file_path:
    :return:
    """
    if PANDAPOWER_AVAILABLE:
        try:
            net = from_pickle(file_path)
            return isinstance(net, dict) and all(key in net for key in ["bus", "line", "load", "ext_grid"])
        except Exception:
            return False
    else:
        return False


def is_pandapower_json(file_path):
    """
    Check if a file is pandapower JSON
    :param file_path:
    :return:
    """
    if PANDAPOWER_AVAILABLE:
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            return isinstance(data, dict) and all(key in data for key in ["bus", "line", "load", "ext_grid"])
        except Exception:
            return False
    else:
        return False


def is_pandapower_sqlite(file_path):
    """
    Check if a file is pandapower SQLite
    :param file_path:
    :return:
    """
    if PANDAPOWER_AVAILABLE:
        try:
            with sqlite3.connect(file_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = {row[0] for row in cursor.fetchall()}
            return {"bus", "line", "load", "ext_grid"}.issubset(tables)
        except Exception:
            return False
    else:
        return False


def is_pandapower_file(file_path: str):
    """
    Check if this is a pandapower file
    :param file_path:
    :return:
    """
    if file_path.endswith(".p"):
        return is_pandapower_pickle(file_path)
    elif file_path.endswith(".json"):
        return is_pandapower_json(file_path)
    elif file_path.endswith(".sqlite"):
        return is_pandapower_sqlite(file_path)
    else:
        return False


class Panda2GridCal:

    def __init__(self, file_or_net: str | "pandapowerNet", logger: Logger | None = None):
        """
        Initialize
        :param file_or_net: PandaPower file name or pandapowerNet
        """
        self.logger = logger if logger is not None else Logger()

        self.panda_dict: Dict[str, Dict[int, ALL_DEV_TYPES]] = dict()

        if PANDAPOWER_AVAILABLE:
            if isinstance(file_or_net, str):
                if file_or_net.endswith(".p"):
                    self.panda_net: pandapowerNet = from_pickle(file_or_net)
                elif file_or_net.endswith(".sqlite"):
                    self.panda_net: pandapowerNet = from_sqlite(file_or_net)
                elif file_or_net.endswith(".json"):
                    self.panda_net: pandapowerNet = from_json(file_or_net)
                elif file_or_net.endswith(".xlsx"):
                    self.panda_net: pandapowerNet = from_excel(file_or_net)
                else:
                    raise Exception("Don't know what to do with this PandaPower file :/")

            elif isinstance(file_or_net, pandapowerNet):
                self.panda_net: pandapowerNet = file_or_net
            else:
                raise Exception(f"The argument is not recognized as a Pandapower net or file :/ {file_or_net}")

            self.logger.add_info("This seems to be a pandapower file")
            self.fBase = self.panda_net.f_hz
            self.Sbase = self.panda_net.sn_mva if self.panda_net.sn_mva > 0.0 else 100.0
            self.load_scale = 100.0 / self.Sbase
        else:
            self.panda_net = None
            self.fBase = 50.0
            self.Sbase = 100.0
            self.load_scale = 1.0
            self.logger.add_info("Pandapower not available :/, try pip install pandapower")

    def register(self, panda_type: str, panda_code: int, api_obj: ALL_DEV_TYPES):
        """
        Register a panda object and it's associated GridCal object
        :param panda_type: table name
        :param panda_code: index key
        :param api_obj: GridCal object
        """
        d = self.panda_dict.get(panda_type, None)

        if d is None:
            self.panda_dict[panda_type] = {panda_code: api_obj}
        else:
            p = d.get(panda_code, None)
            if p is None:
                d[panda_code] = api_obj
            else:
                self.logger.add_error("Panda index repeated", device_class=panda_type, value=panda_code)

    def get_api_object_by_registry(self, panda_type: str, panda_code: int) -> ALL_DEV_TYPES | None:
        """
        Get a previously registered gridcal object from a pandapower table-key
        :param panda_type: table name
        :param panda_code: index key
        :return: GridCal object
        """
        d = self.panda_dict.get(panda_type, None)

        if d is None:
            return None
        else:
            return d.get(panda_code, None)

    def parse_buses(self, grid: dev.MultiCircuit) -> Dict[str, dev.Bus]:
        """
        Add buses to the GridCal grid based on Pandapower data
        :param grid: MultiCircuit grid
        :return: PP row name to GridCal row object
        """

        bus_dictionary = dict()
        for _, row in self.panda_net.bus.iterrows():
            elm = dev.Bus(
                name=row['name'],
                Vnom=row['vn_kv'],
                code=row['index'],
                vmin=row['min_vm_pu'] if 'min_vm_pu' in row else 0.9,
                vmax=row['max_vm_pu'] if 'max_vm_pu' in row else 1.1,
                active=bool(row['in_service'])
            )
            grid.add_bus(elm)  # Add the row to the GridCal grid
            bus_dictionary[row.name] = elm

            self.register(panda_type="bus", panda_code=row['index'], api_obj=elm)

        return bus_dictionary

    def parse_external_grids(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add external grid (slack bus) generators to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        :return:
        """

        for _, row in self.panda_net.ext_grid.iterrows():
            bus = bus_dictionary[row['bus']]
            elm = dev.ExternalGrid(
                name=row['name'],
                code=row['index'],
                Vm=row['vm_pu']
            )
            grid.add_external_grid(bus, elm)

            self.register(panda_type="ext_grid", panda_code=row['index'], api_obj=elm)

    def parse_loads(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add loads to the GridCal grid based on Pandapower data
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        """

        for _, row in self.panda_net.load.iterrows():
            bus = bus_dictionary[row['bus']]
            elm = dev.Load(
                name=row['name'],
                code=row['index'],
                P=row['p_mw'] * self.load_scale,
                Q=row['q_mvar'] * self.load_scale
            )
            grid.add_load(bus=bus, api_obj=elm)

            self.register(panda_type="load", panda_code=row['index'], api_obj=elm)

    def parse_shunts(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add shunts to the GridCal grid based on Pandapower data
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        """
        for _, row in self.panda_net.shunt.iterrows():
            bus = bus_dictionary[row['bus']]
            elm = dev.Shunt(
                name=row['name'],
                code=row['index'],
                G=row["p_mw"] * self.load_scale,
                B=row["q_mvar"] * self.load_scale
            )
            grid.add_shunt(bus=bus, api_obj=elm)

            self.register(panda_type="shunt", panda_code=row['index'], api_obj=elm)

    def parse_lines(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add lines (conductors) to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        """

        for _, row in self.panda_net.line.iterrows():
            bus1 = bus_dictionary[row['from_bus']]
            bus2 = bus_dictionary[row['to_bus']]

            elm = dev.Line(
                bus_from=bus1,
                bus_to=bus2,
                name=row['name'],
                code=row['index'],
                active=bool(row['in_service'])
            )

            elm.fill_design_properties(
                r_ohm=row['r_ohm_per_km'],
                x_ohm=row['x_ohm_per_km'],
                c_nf=row['c_nf_per_km'],
                length=row['length_km'],
                Imax=row['max_i_ka'],
                freq=self.fBase,
                Sbase=self.Sbase,
            )

            # Uncomment the following lines if line activation status is needed
            #            if (self.lines[self.lines['id'] == idx]['Enabled'].values[0] == False):
            #                line.active = False
            grid.add_line(elm)

            self.register(panda_type="line", panda_code=row['index'], api_obj=elm)

    def parse_impedances(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add impedances to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        :return:
        """
        mult = 1.6  # Multiplicative factor for impedance

        # Add impedance elements to the GridCal grid
        for _, row in self.panda_net.impedance.iterrows():
            bus1 = bus_dictionary[row['from_bus']]
            bus2 = bus_dictionary[row['to_bus']]

            # Calculate base impedance
            zbase = (self.panda_net.bus.loc[row['from_bus'], 'vn_kv']) ** 2 / self.Sbase
            ru = row.rft_pu * row.sn_mva / zbase * mult
            xu = row.xft_pu * row.sn_mva / zbase * mult

            elm = dev.SeriesReactance(
                bus_from=bus1,
                bus_to=bus2,
                name=row['name'],
                code=row['index'],
                r=ru,
                x=xu
            )

            grid.add_series_reactance(elm)

            self.register(panda_type="impedance", panda_code=row['index'], api_obj=elm)

    def parse_storage(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add storages to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        :return:
        """

        for _, row in self.panda_net.storage.iterrows():
            bus = bus_dictionary[row['bus']]
            elm = dev.Battery(
                code=row['index'],
                Pmin=row['min_p_mw'],
                Pmax=row['max_p_mw'],
                Qmin=row['min_q_mvar'],
                Qmax=row['max_q_mvar'],
                Sbase=row['sn_mva'],
                Enom=row['max_e_mwh'],
                active=row['in_service'],
                soc=row['soc_percent']
            )

            grid.add_battery(bus=bus, api_obj=elm)  # Add battery to the grid

            self.register(panda_type="storage", panda_code=row['index'], api_obj=elm)

    def parse_generators(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add synchronous generators (row) to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        :return:
        """

        for _, row in self.panda_net.gen.iterrows():
            bus = bus_dictionary[row['bus']]
            elm = dev.Generator(
                name=row['name'],
                code=row['index'],
                P=row['p_mw'] * self.load_scale,
                active=row['in_service'],
                is_controlled=True
            )

            grid.add_generator(bus=bus, api_obj=elm)  # Add generator to the grid

            self.register(panda_type="gen", panda_code=row['index'], api_obj=elm)

    def parse_static_generators(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add synchronous generators (row) to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        :return:
        """

        for _, row in self.panda_net.sgen.iterrows():
            bus = bus_dictionary[row['bus']]
            elm = dev.StaticGenerator(
                name=row['name'],
                code=row['index'],
                P=row['p_mw'] * self.load_scale,
                active=row['in_service'],
            )

            grid.add_generator(bus=bus, api_obj=elm)  # Add generator to the grid

            self.register(panda_type="sgen", panda_code=row['index'], api_obj=elm)

    def parse_transformers(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add transformers to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        """

        for _, row in self.panda_net.trafo.iterrows():
            bus1 = bus_dictionary[row['hv_bus']]
            bus2 = bus_dictionary[row['lv_bus']]

            elm = dev.Transformer2W(
                bus_from=bus1,
                bus_to=bus2,
                name='Transformer 1',
                code=row['index'],
                HV=row['vn_hv_kv'],
                LV=row['vn_lv_kv'],
                nominal_power=row['sn_mva']
            )

            elm.fill_design_properties(
                Pcu=0.0,  # pandapower has no pcu apparently
                Pfe=row['pfe_kw'],
                I0=row['i0_percent'],
                Vsc=row['vk_percent'],
                Sbase=self.Sbase
            )

            grid.add_transformer2w(elm)

            self.register(panda_type="trafo", panda_code=row['index'], api_obj=elm)

    def parse_switches(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """

        :param grid: MultiCircuit grid
        :param bus_dictionary:
        :return:
        """

        # Add switches to the GridCal grid
        for _, switch_row in self.panda_net.switch.iterrows():

            # Identify the first bus in the switch
            bus_from = bus_dictionary[switch_row['bus']]

            if switch_row['et'] == 'b':  # Bus-to-bus switch
                # Get the second bus directly
                bus_to = bus_dictionary[switch_row['element']]
            else:  # Bus-to-element switch
                # Create or reuse an auxiliary bus for the element
                aux_bus_name = f"Aux_Bus_{switch_row['et']}_{switch_row['element']}"
                aux_bus_voltage = self.panda_net.bus.loc[switch_row['bus'], 'vn_kv']

                # Check if an auxiliary bus with this name exists
                bus_to = None
                for bus in grid.buses:
                    if bus.name == aux_bus_name:
                        bus_to = bus
                        break

                if not bus_to:
                    # Create the auxiliary bus if it doesn't exist
                    bus_to = dev.Bus(name=aux_bus_name, Vnom=aux_bus_voltage)
                    grid.add_bus(bus_to)

                # Link the auxiliary bus to the corresponding element
                if switch_row['et'] == 'l':  # Line element
                    line_data = self.panda_net.line.loc[switch_row['element']]
                    # Update the line's connections to include the auxiliary bus
                    for line in grid.lines:
                        if (line.bus_from == bus_dictionary[line_data['from_bus']]
                                and line.bus_to == bus_dictionary[line_data['to_bus']]):
                            if line_data['from_bus'] == switch_row['bus']:
                                line.bus_from = bus_to
                            else:
                                line.bus_to = bus_to
                            break

                elif switch_row['et'] == 't':  # Transformer element
                    trafo_data = self.panda_net.trafo.loc[switch_row['element']]

                    # Update the transformer's connections to include the auxiliary bus
                    for transformer in grid.transformers2w:
                        if (transformer.bus_from == bus_dictionary[trafo_data['hv_bus']]
                                and transformer.bus_to == bus_dictionary[trafo_data['lv_bus']]):

                            if trafo_data['hv_bus'] == switch_row['bus']:
                                transformer.bus_from = bus_to
                            else:
                                transformer.bus_to = bus_to
                            break

            # Create the switch as a normal branch in GridCal
            switch_branch = dev.Switch(
                bus_from=bus_from,
                bus_to=bus_to,
                name=f"Switch_{switch_row['et']}_{switch_row['element']}",
                code=switch_row['index'],
                active=switch_row['closed']
            )
            grid.add_switch(switch_branch)

            self.register(panda_type="switch", panda_code=switch_row['index'], api_obj=switch_branch)

    def parse_measurements(self, grid: dev.MultiCircuit):
        """

        :param grid:
        :return:
        """
        df: pd.DataFrame | None = self.panda_net.get("measurement", None)

        if df is not None:
            for i, row in df.iterrows():
                name = row['name']
                m_tpe = row['measurement_type']  # v, p, q

                # bus, line, transformer, transformer3w, load, sgen, static_generator, ward, xward, external_grid
                elm_tpe = row['element_type']
                idx = row['element']  # index
                val = row['value']
                std = row['std_dev']
                side = row['side']

                api_object = self.get_api_object_by_registry(panda_type=elm_tpe, panda_code=idx)

                if api_object is not None:

                    if elm_tpe == 'bus':

                        if m_tpe == 'v':
                            grid.add_vm_measurement(dev.VmMeasurement(
                                value=val,
                                uncertainty=std,
                                api_obj=api_object,
                                name=name)
                            )
                        elif m_tpe == 'p':
                            grid.add_pi_measurement(dev.PiMeasurement(
                                value=val,
                                uncertainty=std,
                                api_obj=api_object,
                                name=name)
                            )
                        elif m_tpe == 'q':
                            grid.add_qi_measurement(dev.QiMeasurement(
                                value=val,
                                uncertainty=std,
                                api_obj=api_object,
                                name=name)
                            )
                        else:
                            self.logger.add_warning(f"PandaPower {m_tpe} measurement not implemented")

                    if elm_tpe in ['load', 'gen', 'sgen', 'shunt']:

                        if m_tpe == 'v':
                            grid.add_vm_measurement(dev.VmMeasurement(
                                value=val,
                                uncertainty=std,
                                api_obj=api_object.bus,
                                name=name)
                            )
                        elif m_tpe == 'p':
                            grid.add_pi_measurement(dev.PiMeasurement(
                                value=val,
                                uncertainty=std,
                                api_obj=api_object.bus,
                                name=name)
                            )
                        elif m_tpe == 'q':
                            grid.add_qi_measurement(dev.QiMeasurement(
                                value=val,
                                uncertainty=std,
                                api_obj=api_object.bus,
                                name=name)
                            )
                        else:
                            self.logger.add_warning(f"PandaPower {m_tpe} measurement not implemented")

                    elif elm_tpe in ['line', 'impedance', 'transformer']:
                        if m_tpe == 'p':
                            if side == 1 or side == 'from':
                                grid.add_pf_measurement(dev.PfMeasurement(
                                    value=val * self.load_scale,
                                    uncertainty=std,
                                    api_obj=api_object,
                                    name=name
                                ))
                            elif side == 2 or side == 'to':
                                grid.add_pt_measurement(dev.PtMeasurement(
                                    value=val * self.load_scale,
                                    uncertainty=std,
                                    api_obj=api_object,
                                    name=name
                                ))
                        elif m_tpe == 'q':
                            if side == 1 or side == 'from':
                                grid.add_qf_measurement(dev.QfMeasurement(
                                    value=val * self.load_scale,
                                    uncertainty=std,
                                    api_obj=api_object,
                                    name=name
                                ))
                            elif side == 2 or side == 'to':
                                grid.add_qt_measurement(dev.QtMeasurement(
                                    value=val * self.load_scale,
                                    uncertainty=std,
                                    api_obj=api_object,
                                    name=name
                                ))
                        else:
                            self.logger.add_warning(f"PandaPower {m_tpe} measurement not implemented")
                    else:
                        self.logger.add_warning(f"PandaPower {elm_tpe} measurement not implemented")

    def get_multicircuit(self) -> dev.MultiCircuit:
        """
        Get a GridCal Multi-circuit from a PandaPower grid
        :return: MultiCircuit
        """
        grid = dev.MultiCircuit()

        if self.panda_net is not None:
            grid.Sbase = 100.0  # always, the pandapower scaling is handled in the conversions
            grid.fBase = self.panda_net.f_hz

            bus_dict = self.parse_buses(grid=grid)
            self.parse_lines(grid=grid, bus_dictionary=bus_dict)
            self.parse_impedances(grid=grid, bus_dictionary=bus_dict)
            self.parse_loads(grid=grid, bus_dictionary=bus_dict)
            self.parse_shunts(grid=grid, bus_dictionary=bus_dict)
            self.parse_external_grids(grid=grid, bus_dictionary=bus_dict)
            self.parse_storage(grid=grid, bus_dictionary=bus_dict)
            self.parse_generators(grid=grid, bus_dictionary=bus_dict)
            self.parse_static_generators(grid=grid, bus_dictionary=bus_dict)
            self.parse_transformers(grid=grid, bus_dictionary=bus_dict)
            self.parse_switches(grid=grid, bus_dictionary=bus_dict)
            self.parse_measurements(grid=grid)

        return grid
