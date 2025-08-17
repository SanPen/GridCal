# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

import math
from typing import Dict, Optional
import sqlite3
import json

import pandapower
import pandas as pd
from power_grid_model_io.functions.phase_to_phase import reactive_power

import GridCalEngine.Devices as dev
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
            self._has_measurements = False
            # Initialize measurements with zero-copy optimization
            if "measurement" in self.panda_net and not self.panda_net["measurement"].empty:
                self._meas_groups = self.panda_net["measurement"].groupby(
                    ['element_type', 'element'], sort=False
                )


        else:
            self.panda_net = None
            self.fBase = 50.0
            self.Sbase = 100.0
            self.load_scale = 1.0
            self.logger.add_info("Pandapower not available :/, try pip install pandapower")

    def _get_measurements(self, elm_type: str, elm_idx: int) -> Optional[pd.DataFrame]:
        """Get measurements with O(1) lookup and zero allocations"""
        if self._meas_groups is None:
            return None
        try:
            return self._meas_groups.get_group((elm_type, elm_idx))
        except KeyError:
            return None

    def parse_buses(self, grid: dev.MultiCircuit) -> Dict[int, dev.Bus]:
        bus_dict = {}
        for idx, row in self.panda_net.bus.iterrows():
            bus = dev.Bus(
                name=row['name'],
                Vnom=row['vn_kv'],
                vmin=row.get('min_vm_pu', 0.9),
                vmax=row.get('max_vm_pu', 1.1),
                active=bool(row['in_service'])
            )
            grid.add_bus(bus)
            bus_dict[idx] = bus

            # Measurement handling - zero allocations
            if (meas := self._get_measurements('bus', idx)) is not None:
                for _, m in meas.iterrows():
                    if m['measurement_type'] == 'v':
                        grid.add_vm_measurement(
                            dev.VmMeasurement(
                                value=m['value'],
                                uncertainty=m['std_dev'],
                                api_obj=bus,
                                name=m['name']
                            )
                        )
        return bus_dict
    def parse_external_grids(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add external grid (slack bus) generators to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        :return:
        """
        # pandapower measurement table element_type(str) - Clarifies
        # which
        # element is measured. “bus”, “line”, “trafo”, “trafo3w”, “load”, “gen”, “sgen”, “shunt”, “ward”, “xward”
        # and “ext_grid” are possible
        # meas_type(str) - Type
        # of
        # measurement. “v”, “p”, “q”, “i”, “va” and “ia” are
        # possible
        for idx, row in self.panda_net.ext_grid.iterrows():
            bus = bus_dictionary[row['bus']]
            elm = dev.ExternalGrid(name=row['name'], Vm=row['vm_pu'])
            grid.add_external_grid(bus, elm)
            if (meas := self._get_measurements('ext_grid', idx)) is not None:
                self.assign_v_p_q_i_measurement_to_connected_bus_and_switches(bus, grid, meas, row)

    def assign_v_p_q_i_measurement_to_connected_bus_and_switches(self, bus, grid, meas_df, row):
        """Process measurements with proper DataFrame handling"""
        if meas_df is None or meas_df.empty:
            return

        for _, meas_row in meas_df.iterrows():
            m_type = meas_row['measurement_type']
            m_value = float(meas_row['value'])
            m_std = float(meas_row['std_dev'])
            m_name = str(meas_row['name'])
            # voltage meas still added to the connected bus
            if m_type== 'v':
                grid.add_vm_measurement(
                    dev.VmMeasurement(
                        value=m_value,
                        uncertainty=m_std,
                        api_obj=bus,
                        name=m_name
                    )
                )
            if  m_type in ('p', 'q', 'i'):
                # GridCal does not support P,Q measurement on single pole element
                # we need to find connected switch directly to this element
                sw_set = pandapower.get_connected_switches(self.panda_net, row["bus"])
                if not sw_set.empty:
                    api_obj = sw_set.iloc[0]
                    if m_type == 'p':
                        grid.add_pf_measurement(
                            dev.PfMeasurement(
                                value=m_value * self.load_scale,
                                uncertainty=m_std,
                                api_obj=api_obj,
                                name=m_name
                            )
                        )
                    if m_type== 'q':
                        grid.add_qf_measurement(
                            dev.QfMeasurement(
                                value=m_value * self.load_scale,
                                uncertainty=m_std,
                                api_obj=api_obj,
                                name=m_name
                            )
                        )
                    if m_type== 'i':
                        vnom = bus.Vnom if hasattr(bus, 'Vnom') else 1.0
                        ibase = self.Sbase / (vnom * math.sqrt(3))
                        value = m_value / ibase  # Convert kA to pu
                        grid.add_if_measurement(
                            dev.IfMeasurement(
                                value=value,
                                uncertainty=m_std,
                                api_obj=api_obj,
                                name=m_name
                            )
                        )
                else:
                    self.logger.add_warning(f"Connecting switch was not found for this measurement {meas_row}")
    def parse_loads(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add loads to the GridCal grid based on Pandapower data
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        """

        for idx, row in self.panda_net.load.iterrows():
            bus = bus_dictionary[row['bus']]
            elm = dev.Load(
                name=row['name'],
                P=row['p_mw'] * self.load_scale,
                Q=row['q_mvar'] * self.load_scale
            )
            grid.add_load(bus=bus, api_obj=elm)
            if (meas := self._get_measurements('load', idx)) is not None:
                self.assign_v_p_q_i_measurement_to_connected_bus_and_switches(bus, grid, meas, row)
    def parse_shunts(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add shunts to the GridCal grid based on Pandapower data
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        """
        for idx, row in self.panda_net.shunt.iterrows():
            bus = bus_dictionary[row['bus']]
            elm = dev.Shunt(
                name=row['name'],
                G=row["p_mw"] * self.load_scale,
                B=row["q_mvar"] * self.load_scale
            )
            grid.add_shunt(bus=bus, api_obj=elm)
            if (meas := self._get_measurements('shunt', idx)) is not None:
                self.assign_v_p_q_i_measurement_to_connected_bus_and_switches(bus, grid, meas, row)
    def parse_lines(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add lines (conductors) to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        """

        for idx, row in self.panda_net.line.iterrows():
            bus1 = bus_dictionary[row['from_bus']]
            bus2 = bus_dictionary[row['to_bus']]

            elm = dev.Line(
                bus_from=bus1,
                bus_to=bus2,
                name=row['name'],
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
            if (meas := self._get_measurements('line', idx)) is not None:
                for _, m_row in meas.iterrows():
                    m_type = m_row['measurement_type']
                    m_value = float(m_row['value']) * self.load_scale
                    m_std = float(m_row['std_dev'])
                    m_name = str(m_row['name'])
                    if m_type == 'p':
                        if m_row["side"] == "from": # from bus is supported
                            grid.add_pf_measurement(
                                dev.PfMeasurement(
                                    value=m_value,
                                    uncertainty=m_std,
                                    api_obj=elm,
                                    name=m_name,
                                )
                            )
                        else:
                            # again look for connecting switch to provide this meas there
                            sw_set = pandapower.get_connected_switches(self.panda_net, bus2)
                            if not sw_set.empty:
                                api_obj = sw_set.iloc[0]
                                grid.add_pf_measurement(
                                    dev.PfMeasurement(
                                        value=m_value,
                                        uncertainty=m_std,
                                        api_obj=api_obj,
                                        name=m_name
                                    )
                                )
                    elif m_row['measurement_type'] == 'q':
                        if m_row["side"] == "from":
                            grid.add_qf_measurement(
                                dev.QfMeasurement(
                                    value=m_value,
                                    uncertainty=m_std,
                                    api_obj=elm,
                                    name=m_name,
                                )
                            )
                        else:
                            # again look for connecting switch to provide this meas there
                            sw_set = pandapower.get_connected_switches(self.panda_net, bus2)
                            if not sw_set.empty:
                                api_obj = sw_set.iloc[0]
                                grid.add_qf_measurement(
                                    dev.QfMeasurement(
                                        value=m_value,
                                        uncertainty=m_std,
                                        api_obj=api_obj,
                                        name=m_name
                                    )
                                )
                    else:
                        self.logger.add_warning(f"PandaPower {m_row['type']} measurement not implemented")
    def parse_impedances(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add impedances to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        :return:
        """
        mult = 1.6  # Multiplicative factor for impedance

        # Add impedance elements to the GridCal grid
        for idx, row in self.panda_net.impedance.iterrows():
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
                r=ru,
                x=xu
            )

            grid.add_series_reactance(elm)
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

    def parse_generators(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add synchronous generators (row) to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        :return:
        """

        for idx, row in self.panda_net.gen.iterrows():
            bus = bus_dictionary[row['bus']]
            elm = dev.Generator(
                name=row['name'],
                P=row['p_mw'] * self.load_scale,
                active=row['in_service'],
                is_controlled=True
            )

            grid.add_generator(bus=bus, api_obj=elm)  # Add generator to the grid
            if (meas := self._get_measurements('gen', idx)) is not None:
                self.assign_v_p_q_i_measurement_to_connected_bus_and_switches(bus, grid, meas, row)

        for idx, row in self.panda_net.sgen.iterrows():
            bus = bus_dictionary[row['bus']]
            elm = dev.Generator(
                name=row['name'],
                P=row['p_mw'] * self.load_scale,
                power_factor =  row['p_mw'] / math.sqrt(row['q_mvar']**2 + row['p_mw']**2),
                active=row['in_service'],
                is_controlled=False,
            )

            grid.add_generator(bus=bus, api_obj=elm)  # Add generator to the grid
            if (meas := self._get_measurements('sgen', idx)) is not None:
                self.assign_v_p_q_i_measurement_to_connected_bus_and_switches(bus, grid, meas, row)

    def parse_transformers(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """
        Add transformers to the GridCal grid
        :param grid: MultiCircuit grid
        :param bus_dictionary:
        """

        self.create_trafo2w_assign_measurements(bus_dictionary, grid)
        # 3W trafo has to be parsed as well

    def process_each_transformer_measurements(self, bus2, elm, grid, meas_row):
        """Handle individual transformer measurements"""
        m_type = meas_row['measurement_type']
        m_value = float(meas_row['value']) * self.load_scale
        m_std = float(meas_row['std_dev'])
        m_name = str(meas_row['name'])
        if m_type == 'p':
            if meas_row["side"] == "hv_bus":  # hv bus is supported
                grid.add_pf_measurement(
                    dev.PfMeasurement(
                        value=m_value,
                        uncertainty=m_std,
                        api_obj=elm,
                        name=m_name,
                    )
                )
            else:
                # For LV side or unspecified, use switch if available
                # again look for connecting switch to provide this meas there
                sw_set = pandapower.get_connected_switches(self.panda_net, bus2)
                if not sw_set.empty:
                    api_obj = sw_set.iloc[0]
                    grid.add_pf_measurement(
                        dev.PfMeasurement(
                            value=m_value,
                            uncertainty=m_std,
                            api_obj=api_obj,
                            name=m_name
                        )
                    )
        elif m_type == 'q':
            if meas_row["side"] == "hv_bus":
                grid.add_qf_measurement(
                    dev.QfMeasurement(
                        value=m_value,
                        uncertainty=m_std,
                        api_obj=elm,
                        name=m_name,
                    )
                )
            else:
                # again look for connecting switch to provide this meas there
                sw_set = pandapower.get_connected_switches(self.panda_net, bus2)
                if not sw_set.empty:
                    api_obj = sw_set.iloc[0]
                    grid.add_pf_measurement(
                        dev.PfMeasurement(
                            value=m_value,
                            uncertainty=m_std,
                            api_obj=api_obj,
                            name=m_name,
                        )
                    )
        else:
            self.logger.add_warning(f"PandaPower {meas_row} measurement not implemented")

    def create_trafo2w_assign_measurements(self, bus_dictionary, grid):
        for idx, row in self.panda_net.trafo.iterrows():
            bus1 = bus_dictionary[row['hv_bus']]
            bus2 = bus_dictionary[row['lv_bus']]

            elm = dev.Transformer2W(
                bus_from=bus1,
                bus_to=bus2,
                name=row.get('name', f"Transformer {idx}"),
                HV=row['vn_hv_kv'],
                LV=row['vn_lv_kv'],
                nominal_power=row['sn_mva'],
                active=bool(row['in_service'])
            )

            elm.fill_design_properties(
                Pcu=0.0,  # pandapower has no pcu apparently
                Pfe=row['pfe_kw'],
                I0=row['i0_percent'],
                Vsc=row['vk_percent'],
                Sbase=self.Sbase
            )

            grid.add_transformer2w(elm)
            if (meas := self._get_measurements('trafo', idx)) is not None:
                for _, m_row in meas.iterrows():
                    self.process_each_transformer_measurements(bus2, elm, grid, m_row)

    def parse_switches(self, grid: dev.MultiCircuit, bus_dictionary: Dict[str, dev.Bus]):
        """

        :param grid: MultiCircuit grid
        :param bus_dictionary:
        :return:
        """

        # Add switches to the GridCal grid
        for idx, switch_row in self.panda_net.switch.iterrows():

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
                        if line.bus_from == bus_dictionary[line_data['from_bus']] and line.bus_to == bus_dictionary[
                            line_data['to_bus']]:
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
                active=switch_row['closed']
            )
            grid.add_switch(switch_branch)
    # def parse_measurements(self, grid: dev.MultiCircuit):
    #     """
    #
    #     :param grid:
    #     :return:
    #     """
    #     df: pd.DataFrame | None = self.panda_net.get("measurement", None)
    #
    #     if df is not None:
    #         for i, row in df.iterrows():
    #             name = row['name']
    #             m_tpe = row['measurement_type']  # v, p, q
    #             elm_tpe = row['element_type']  # bus, line
    #             idx = row['element']  # index
    #             val = row['value']
    #             std = row['std_dev']
    #             side = row['side']
    #
    #             if elm_tpe == 'bus':
    #
    #                 if m_tpe == 'v':
    #                     try:
    #                         grid.add_vm_measurement(
    #                             dev.VmMeasurement(value=val, uncertainty=std, api_obj=grid.buses[idx], name=name)
    #                         )
    #                     except Exception as ex:
    #                         breakpoint()
    #                         print(f"{val},{idx}")
    #                 else:
    #                     self.logger.add_warning(f"PandaPower {m_tpe} measurement not implemented")
    #
    #             elif elm_tpe == 'line':
    #                 if m_tpe == 'p':
    #                     if side == 1:
    #                         grid.add_pf_measurement(
    #                             dev.PfMeasurement(
    #                                 value=val * self.load_scale,
    #                                 uncertainty=std,
    #                                 api_obj=grid.lines[idx],
    #                                 name=name
    #                             )
    #                         )
    #                     else:
    #                         self.logger.add_warning("To side not implemented for P measurements")
    #                 elif m_tpe == 'q':
    #                     if side == 1:
    #                         grid.add_qf_measurement(
    #                             dev.QfMeasurement(
    #                                 value=val * self.load_scale,
    #                                 uncertainty=std,
    #                                 api_obj=grid.lines[idx],
    #                                 name=name
    #                             )
    #                         )
    #                     else:
    #                         self.logger.add_warning("To side not implemented for Q measurements")
    #                 else:
    #                     self.logger.add_warning(f"PandaPower {m_tpe} measurement not implemented")
    #             else:
    #                 self.logger.add_warning(f"PandaPower {elm_tpe} measurement not implemented")

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
            self.parse_transformers(grid=grid, bus_dictionary=bus_dict)
            self.parse_switches(grid=grid, bus_dictionary=bus_dict)
            self.parse_measurements(grid=grid)

        return grid
