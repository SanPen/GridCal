# Copyright (c) 2020-2025, RTE (http://www.rte-france.com)
# See AUTHORS.md
# All rights reserved.
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of the deeac project.
import os
from typing import Dict
import numpy as np
import VeraGridEngine.Devices as dev
from VeraGridEngine.enumerations import ShuntControlMode, GeneratorControlMode
from VeraGridEngine.basic_structures import Logger

from VeraGridEngine.Utils.optional_dependencies import optional_dependency_failure

# Its native runtime or API can be incompatible even when pypowsybl is installed.
# Validate the reader exports before making this optional importer available.
try:
    import pypowsybl as pp
    from pypowsybl import PyPowsyblError
    from pypowsybl.network import load

    PYPOWSYBL_AVAILABLE = True
    PYPOWSYBL_UNAVAILABLE_REASON: str = ""

except (ImportError, AttributeError, OSError, RuntimeError, ValueError, TypeError) as error:
    pp = None
    PYPOWSYBL_AVAILABLE = False
    PYPOWSYBL_UNAVAILABLE_REASON = optional_dependency_failure("pypowsybl", error)


class IidmParser:
    """
    Xiidm file parser
    """
    __slots__ = (
        "logger",
        "ps_grid",
    )

    def __init__(self, fname: str, logger: Logger | None = None):
        """

        :param fname: xiidm file
        """
        self.logger = Logger() if logger is None else logger

        if os.path.exists(fname):
            if PYPOWSYBL_AVAILABLE:
                self.ps_grid = load(fname)
            else:
                self.ps_grid = None
                self.logger.add_error(f"pypowsybl unavailable: {PYPOWSYBL_UNAVAILABLE_REASON}")
        else:
            self.ps_grid = None

    def parse(self) -> dev.MultiCircuit:
        """
        Convert the PowSybl structures to  deeac
        :return: Network
        """

        grid = dev.MultiCircuit()

        if self.ps_grid is None:
            return grid
        else:

            """
            - Expected objects:   
            - areas    
            - buses (from bus view)    
            - buses from bus/breaker view    
            - lines    
            - 2 windings transformers    
            - 3 windings transformers    
            - generators    
            - loads    
            - shunt compensators    
            - dangling lines    
            - LCC and VSC converters stations    
            - static var compensators    
            - switches    
            - voltage levels    
            - substations    
            - busbar sections    
            - HVDC lines    
            - ratio and phase tap changer steps associated to a 2 windings transformers    
            - identifiables that are all the equipment on the network    
            - injections    
            - branches (lines and two windings transformers)    
            - terminals are a practical view of those objects 
              which are very important in the java implementation    
            - DC nodes    
            - DC lines    
            - voltage source converters    
            - DC grounds
            """

            substations = self.ps_grid.get_substations(all_attributes=True)
            voltage_levels = self.ps_grid.get_voltage_levels(all_attributes=True)
            buses = self.ps_grid.get_buses(all_attributes=True)

            lines = self.ps_grid.get_lines(all_attributes=True)
            # branches = self.ps_grid.get_branches(all_attributes=True)
            switches = self.ps_grid.get_switches(all_attributes=True)
            transformers2w = self.ps_grid.get_2_windings_transformers(all_attributes=True)
            transformers3w = self.ps_grid.get_3_windings_transformers(all_attributes=True)

            self.ps_grid.get_phase_tap_changers(all_attributes=True)
            self.ps_grid.get_phase_tap_changer_steps(all_attributes=True)

            hvdc = self.ps_grid.get_hvdc_lines(all_attributes=True)

            loads = self.ps_grid.get_loads(all_attributes=True)
            gens = self.ps_grid.get_generators(all_attributes=True)
            capacitor_banks = self.ps_grid.get_shunt_compensators(all_attributes=True)
            svc = self.ps_grid.get_static_var_compensators(all_attributes=True)

            grid.name = self.ps_grid.name
            grid.Sbase = self.ps_grid.nominal_apparent_power
            is_in_pu = self.ps_grid.per_unit

            """
            Substation
            0 = {str} 'name'
            1 = {str} 'TSO': To track to which Transmission System Operator the substation belongs
            2 = {str} 'geo_tags': They make it possible to accurately locate the substation
            3 = {str} 'country': To specify in which country the substation is located
            4 = {str} 'fictitious'
            """
            country_dict: Dict[str, dev.Country] = dict()
            se_dict: Dict[str, dev.Substation] = dict()
            for i, row in substations.iterrows():

                country = country_dict.get(row["country"], None)
                if country is None:
                    country = dev.Country(name=row["country"])
                    grid.add_country(obj=country)
                    country_dict[country.name] = country

                name = row["name"]
                if name == "":
                    name = i

                elm = dev.Substation(
                    name=name,
                    code=i,
                    country=country
                )
                grid.add_substation(obj=elm)
                se_dict[i] = elm

            """
            Voltage Level
            0 = {str} 'name'
            1 = {str} 'substation_id'
            2 = {str} 'nominal_v': kV, Nominal base voltage
            3 = {str} 'high_voltage_limit' kV, Low voltage limit magnitude
            4 = {str} 'low_voltage_limit' kV, High voltage limit magnitude
            
            In the docs 
            (https://powsybl.readthedocs.io/projects/powsybl-core/en/stable/grid_model/network_subnetwork.html)
            it says that topology_kind is required, but doesn't seem to be present
            """
            vl_dict: Dict[str, dev.VoltageLevel] = dict()
            for i, row in voltage_levels.iterrows():
                se = se_dict.get(row["substation_id"], None)

                if se is None:
                    self.logger.add_error("Substation not found",
                                          value=row["substation_id"])

                name = row["name"]
                if name == "":
                    name = i

                elm = dev.VoltageLevel(
                    name=name,
                    code=i,
                    Vnom=float(row["nominal_v"]),
                    substation=se
                )
                grid.add_voltage_level(obj=elm)
                vl_dict[i] = elm

                try:
                    topology = self.ps_grid.get_node_breaker_topology(voltage_level_id=i)
                except pp.PyPowsyblError:
                    pass

            """
            Bus
            0 = {str} 'name'
            1 = {str} 'v_mag'
            2 = {str} 'v_angle'
            3 = {str} 'connected_component'
            4 = {str} 'synchronous_component'
            5 = {str} 'voltage_level_id'
            6 = {str} 'fictitious'
            """
            bus_dict: Dict[str, dev.Bus] = dict()
            for idx, row in buses.iterrows():
                vl = vl_dict.get(row["voltage_level_id"], None)

                if vl is None:
                    self.logger.add_error("Voltage level not found",
                                          value=row["voltage_level_id"])

                bus = dev.Bus(
                    name=row["name"] if row["name"] != "" else idx,
                    code=idx,
                    Vnom=10 if vl is None else vl.Vnom,
                    Vm0=float(row["v_mag"]),
                    Va0=float(row["v_angle"]),
                    voltage_level=vl
                )
                grid.add_bus(obj=bus)
                bus_dict[idx] = bus

            """
            Line
            00 = {str} 'name'
            01 = {str} 'r'
            02 = {str} 'x'
            03 = {str} 'g1'
            04 = {str} 'b1'
            05 = {str} 'g2'
            06 = {str} 'b2'
            07 = {str} 'p1'
            08 = {str} 'q1'
            09 = {str} 'i1'
            10 = {str} 'p2'
            11 = {str} 'q2'
            12 = {str} 'i2'
            13 = {str} 'voltage_level1_id'
            14 = {str} 'voltage_level2_id'
            15 = {str} 'bus1_id'
            16 = {str} 'bus_breaker_bus1_id'
            17 = {str} 'node1'
            18 = {str} 'bus2_id'
            19 = {str} 'bus_breaker_bus2_id'
            20 = {str} 'node2'
            21 = {str} 'connected1'
            22 = {str} 'connected2'
            23 = {str} 'fictitious'
            24 = {str} 'selected_limits_group_1'
            25 = {str} 'selected_limits_group_2'
            """
            for i, row in lines.iterrows():
                bus1: dev.Bus | None = bus_dict.get(row["bus1_id"], None)
                bus2: dev.Bus | None = bus_dict.get(row["bus2_id"], None)

                if bus1 is None:
                    self.logger.add_error("Bus from not found",
                                          device_class="Line",
                                          device=i)

                if bus2 is None:
                    self.logger.add_error("Bus to not found",
                                          device_class="Line",
                                          device=i)

                if bus1 is not None and bus2 is not None:

                    Vn = max(bus1.Vnom, bus2.Vnom)
                    Zbase = Vn * Vn / grid.Sbase
                    Ybase = 1.0 / Zbase
                    elm = dev.Line(
                        name=row["name"] if row["name"] != "" else i,
                        code=i,
                        bus_from=bus1,
                        bus_to=bus2,
                        r=row["r"] / Zbase,
                        x=row["x"] / Zbase,
                        b=row["b1"] / Ybase,
                    )

                    grid.add_line(obj=elm, logger=self.logger)
                else:
                    pass

            """
            Switch
            00 = {str} 'name'
            01 = {str} 'kind' {'DISCONNECTOR', 'BREAKER'}
            02 = {str} 'open'
            03 = {str} 'retained'
            04 = {str} 'voltage_level_id'
            05 = {str} 'bus_breaker_bus1_id'
            06 = {str} 'bus_breaker_bus2_id'
            07 = {str} 'node1'
            08 = {str} 'node2'
            09 = {str} 'fictitious'
            """
            # TODO: Unclear when these are available or how they're connected
            # for i, row in switches.iterrows():
            #     bus1: dev.Bus = bus_dict[row["bus_breaker_bus1_id"]]
            #     bus2: dev.Bus = bus_dict[row["bus_breaker_bus2_id"]]
            #
            #     elm = dev.Switch(
            #         name=row["name"],
            #         code = i,
            #         bus_from=bus1,
            #         bus_to=bus2,
            #         retained=bool(row["retained"]),
            #         active=not bool(row["open"])
            #     )
            #
            #     grid.add_switch(obj=elm)

            """
            Transformer
            https://powsybl.readthedocs.io/projects/pypowsybl/en/stable/reference/api/pypowsybl.network.Network.get_2_windings_transformers.html#pypowsybl.network.Network.get_2_windings_transformers
            00 = {str} 'name'
            01 = {str} 'r': the resistance of the transformer at its “2” side (in Ohm)
            02 = {str} 'x': x: the reactance of the transformer at its “2” side (in Ohm)
            03 = {str} 'g': b: the susceptance of transformer at its “2” side (in Siemens)
            04 = {str} 'b': the conductance of transformer at its “2” side (in Siemens)
            05 = {str} 'rated_u1': the rated voltage of the transformer at side 1 (in kV)
            06 = {str} 'rated_u2': the rated voltage of the transformer at side 2 (in kV)
            07 = {str} 'rated_s': the rated apparent power of the transformer (in MVA)
            08 = {str} 'p1': the active flow on the transformer at its “1” side, NaN if no loadflow has been computed (in MW)
            09 = {str} 'q1': the reactive flow on the transformer at its “1” side, NaN if no loadflow has been computed (in MVAr)
            10 = {str} 'i1': the current on the transformer at its “1” side, NaN if no loadflow has been computed (in A)
            11 = {str} 'p2'
            12 = {str} 'q2'
            13 = {str} 'i2'
            14 = {str} 'voltage_level1_id': voltage level where the transformer is connected, on side 1
            15 = {str} 'voltage_level2_id': voltage level where the transformer is connected, on side 2
            16 = {str} 'bus1_id': bus where this transformer is connected, on side 1
            17 = {str} 'bus_breaker_bus1_id' (optional): bus of the bus-breaker view where this transformer is connected, on side 1
            18 = {str} 'node1': (optional): node where this transformer is connected on side 1, in node-breaker voltage levels
            19 = {str} 'bus2_id': bus where this transformer is connected, on side 2
            20 = {str} 'bus_breaker_bus2_id'
            21 = {str} 'node2'
            22 = {str} 'connected1': the side “1” of the transformer is connected to a bus
            23 = {str} 'connected2': the side “2” of the transformer is connected to a bus
            24 = {str} 'fictitious': the transformer is part of the model and not of the actual network
            25 = {str} 'selected_limits_group_1': (optional): Name of the selected operational limits group selected for side 1
            26 = {str} 'selected_limits_group_2': (optional): Name of the selected operational limits group selected for side 2
            27 = {str} 'rho'(optional): the voltage ratio of the transformer at current tap position
            28 = {str} 'alpha'(optional): the phase shift of the transformer at current tap position (in degree)
            29 = {str} 'r_at_current_tap'(optional): the resistance of the transformer at current tap position (in Ohm)
            30 = {str} 'x_at_current_tap'(optional): the reactance of the transformer at current tap position (in Ohm)
            31 = {str} 'g_at_current_tap'(optional): the susceptance of the transformer at current tap position (in Ohm)
            32 = {str} 'b_at_current_tap'(optional): the conductance of the transformer at current tap position (in Ohm)
            """
            for i, row in transformers2w.iterrows():
                bus1: dev.Bus | None = bus_dict.get(row["bus1_id"], None)
                bus2: dev.Bus | None = bus_dict.get(row["bus2_id"], None)

                if bus1 is None:
                    self.logger.add_error("Bus from not found",
                                          device_class="Line",
                                          device=i)

                if bus2 is None:
                    self.logger.add_error("Bus to not found",
                                          device_class="Line",
                                          device=i)

                if bus1 is not None and bus2 is not None:

                    rated_u1 = float(row["rated_u1"])
                    rated_u2 = float(row["rated_u2"])
                    if rated_u1 > rated_u2:
                        HV = rated_u1
                        LV = rated_u2
                    else:
                        HV = rated_u2
                        LV = rated_u1

                    Sn = float(row["rated_s"])
                    if np.isnan(Sn):
                        Sn = 9999.0

                    # The per unit is referred to the bus 2
                    Zbase = bus2.Vnom * bus2.Vnom / grid.Sbase
                    Ybase = 1.0 / Zbase
                    r = float(row["r"]) / Zbase
                    x = float(row["x"]) / Zbase
                    g = float(row["g"]) / Ybase
                    b = float(row["b"]) / Ybase

                    elm = dev.Transformer2W(
                        name=row["name"] if row["name"] != "" else i,
                        code=i,
                        bus_from=bus1,
                        bus_to=bus2,
                        r=r,
                        x=x,
                        g=g,
                        b=b,
                        HV=HV,
                        LV=LV,
                        rate=Sn,
                        tap_module=float(row["rho"]),
                        tap_phase=float(row["alpha"]),  # TODO in deg or rad? we need rad
                    )

                    grid.add_transformer2w(obj=elm)
                else:
                    pass

            """
            rated_u0: the rated voltage of the transformer at middle point od the star model (in kV)
            fictitious (optional): True if the transformer is part of the model and not of the actual network
            r1: the leg 1 resistance of the transformer (in Ohm)
            x1: the leg 1 reactance of the transformer (in Ohm)
            b1: the leg 1 susceptance of transformer (in Siemens)
            g1: the leg 1 conductance of transformer (in Siemens)
            rated_u1: the leg 1 rated voltage of the transformer (in kV)
            rated_s1: the leg 1 rated apparent power of the transformer (in MVA)
            ratio_tap_position1: the leg 1 ratio tap changer current position
            phase_tap_position1: the leg 1 phase tap changer current position
            p1: the leg 1 active power flow on the transformer, NaN if no loadflow has been computed (in MW)
            q1: the leg 1 reactive power flow on the transformer, NaN if no loadflow has been computed (in MVAr)
            i1: the leg 1 current on the transformer, NaN if no loadflow has been computed (in A)
            voltage_level1_id: the voltage level where the leg 1 of the transformer is connected
            bus1_id: the bus where the leg 1 of the transformer is connected
            bus_breaker_bus1_id (optional): the bus of the bus-breaker view where leg 1 of the transformer is connected
            node1 (optional): the node where the leg 1 transformer is connected (only in node-breaker voltage levels)
            connected1: True if the leg 1 of the transformer is connected to a bus
            selected_limits_group_1 (optional): the name of the selected operational limits group selected for the leg 1 of the transformer
            rho1 (optional): the leg 1 voltage ratio of the transformer at current tap position
            alpha1 (optional): the leg 1 phase shift of the transformer at current tap position (in degree)
            r1_at_current_tap (optional): the leg 1 resistance of the transformer at current tap position (in Ohm)
            x1_at_current_tap (optional): the leg 1 reactance of the transformer at current tap position (in Ohm)
            g1_at_current_tap (optional): the leg 1 susceptance of the transformer at current tap position (in Ohm)
            b1_at_current_tap (optional): the leg 1 conductance of the transformer at current tap position (in Ohm)
            r2: the leg 2 resistance of the transformer (in Ohm)
            x2: the leg 2 reactance of the transformer (in Ohm)
            b2: the leg 2 susceptance of transformer (in Siemens)
            g2: the leg 2 conductance of transformer (in Siemens)
            rated_u2: the leg 2 rated voltage of the transformer (in kV)
            rated_s2: the leg 2 rated apparent power of the transformer (in MVA)
            ratio_tap_position2: the leg 2 ratio tap changer current position
            phase_tap_position2: the leg 2 phase tap changer current position
            p2: the leg 2 active power flow on the transformer, NaN if no loadflow has been computed (in MW)
            q2: the leg 2 reactive power flow on the transformer, NaN if no loadflow has been computed (in MVAr)
            i2: the leg 2 current on the transformer, NaN if no loadflow has been computed (in A)
            voltage_level2_id: the voltage level where the leg 2 of the transformer is connected
            bus2_id: the bus where the leg 2 of the transformer is connected
            bus_breaker_bus2_id (optional): the bus of the bus-breaker view where leg 2 of the transformer is connected
            node2 (optional): the node where the leg 2 transformer is connected (only in node-breaker voltage levels)
            connected2: True if the leg 2 of the transformer is connected to a bus
            selected_limits_group_2 (optional): the name of the selected operational limits group selected for the leg 2 of the transformer
            rho2 (optional): the leg 2 voltage ratio of the transformer at current tap position
            alpha2 (optional): the leg 2 phase shift of the transformer at current tap position (in degree)
            r2_at_current_tap (optional): the leg 2 resistance of the transformer at current tap position (in Ohm)
            x2_at_current_tap (optional): the leg 2 reactance of the transformer at current tap position (in Ohm)
            g2_at_current_tap (optional): the leg 2 susceptance of the transformer at current tap position (in Ohm)
            b2_at_current_tap (optional): the leg 2 conductance of the transformer at current tap position (in Ohm)
            r3: the leg 3 resistance of the transformer (in Ohm)
            x3: the leg 3 reactance of the transformer (in Ohm)
            b3: the leg 3 susceptance of transformer (in Siemens)
            g3: the leg 3 conductance of transformer (in Siemens)
            rated_u3: the leg 3 rated voltage of the transformer (in kV)
            rated_s3: the leg 3 rated apparent power of the transformer (in MVA)
            ratio_tap_position3: the leg 3 ratio tap changer current position
            phase_tap_position3: the leg 3 phase tap changer current position
            p3: the leg 3 active power flow on the transformer, NaN if no loadflow has been computed (in MW)
            q3: the leg 3 reactive power flow on the transformer, NaN if no loadflow has been computed (in MVAr)
            i3: the leg 3 current on the transformer, NaN if no loadflow has been computed (in A)
            voltage_level3_id: the voltage level where the leg 3 of the transformer is connected
            bus3_id: the bus where the leg 3 of the transformer is connected
            bus_breaker_bus3_id (optional): the bus of the bus-breaker view where leg 3 of the transformer is connected
            node3 (optional): the node where the leg 3 transformer is connected (only in node-breaker voltage levels)
            connected3: True if the leg 3 of the transformer is connected to a bus
            selected_limits_group_3 (optional): the name of the selected operational limits group selected for the leg 3 of the transformer
            rho3 (optional): the leg 3 voltage ratio of the transformer at current tap position
            alpha3 (optional): the leg 3 phase shift of the transformer at current tap position (in degree)
            r3_at_current_tap (optional): the leg 3 resistance of the transformer at current tap position (in Ohm)
            x3_at_current_tap (optional): the leg 3 reactance of the transformer at current tap position (in Ohm)
            g3_at_current_tap (optional): the leg 3 susceptance of the transformer at current tap position (in Ohm)
            b3_at_current_tap (optional): the leg 3 conductance of the transformer at current tap position (in Ohm)
            """
            for i, row in transformers3w.iterrows():
                pass

            """
            HVDC
            00 = {str} 'name'
            01 = {str} 'converters_mode'
            02 = {str} 'target_p'
            03 = {str} 'max_p'
            04 = {str} 'nominal_v'
            05 = {str} 'r'
            06 = {str} 'converter_station1_id'
            07 = {str} 'converter_station2_id'
            08 = {str} 'connected1'
            09 = {str} 'connected2'
            10 = {str} 'fictitious'
            """
            for i, row in hvdc.iterrows():

                bus1: dev.Bus | None = bus_dict.get(row["converter_station1_id"], None)
                bus2: dev.Bus | None = bus_dict.get(row["converter_station2_id"], None)

                if bus1 is None:
                    self.logger.add_error("Bus from not found",
                                          device_class="Line",
                                          device=i)

                if bus2 is None:
                    self.logger.add_error("Bus to not found",
                                          device_class="Line",
                                          device=i)

                if bus1 is not None and bus2 is not None:
                    connected1 = bool(row["connected1"])
                    connected2 = bool(row["connected2"])

                    # TODO, what is the content of converters_mode? PMODE1, PMODE3 stuff probably but investigate

                    elm = dev.HvdcLine(
                        name=row["name"] if row["name"] != "" else i,
                        bus_from=bus1,
                        bus_to=bus2,
                        dc_link_voltage=float(row["nominal_v"]),
                        Pset=float(row["target_p"]),
                        rate=float(row["max_p"]),
                        r=float(row["r"]),  # TODO: Ohm?, we need Ohm
                        active=connected1 and connected2
                    )

                    grid.add_hvdc(obj=elm)

            """
            Load
            00 = {str} 'name'
            01 = {str} 'type'
            02 = {str} 'p0'
            03 = {str} 'q0'
            04 = {str} 'p'
            05 = {str} 'q'
            06 = {str} 'i'
            07 = {str} 'voltage_level_id'
            08 = {str} 'bus_id'
            09 = {str} 'bus_breaker_bus_id'
            10 = {str} 'node'
            11 = {str} 'connected'
            12 = {str} 'fictitious'
            """
            for i, row in loads.iterrows():
                bus1: dev.Bus | None = bus_dict.get(row["bus_id"], None)

                if bus1 is None:
                    self.logger.add_error("Bus not found",
                                          device_class="Load",
                                          device=i)
                else:
                    elm = dev.Load(
                        name=row["name"] if row["name"] != "" else i,
                        code=i,
                        P1=float(row["p"]),
                        Q1=float(row["q"]),
                        active=bool(row["connected"])
                    )
                    grid.add_load(bus=bus1, api_obj=elm)

            """
            Generator
            00 = {str} 'name'
            01 = {str} 'energy_source'
            02 = {str} 'target_p' MW, The active power target
            03 = {str} 'min_p' MW, Minimum generator active power output
            04 = {str} 'max_p' MW, Maximum generator active power output
            05 = {str} 'min_q' MVAr
            06 = {str} 'max_q' MVAr
            07 = {str} 'min_q_at_target_p' 
            08 = {str} 'max_q_at_target_p'
            09 = {str} 'min_q_at_p'
            10 = {str} 'max_q_at_p'
            11 = {str} 'rated_s' MVA, The rated nominal power
            12 = {str} 'reactive_limits_kind'
            13 = {str} 'target_v' kV, The voltage target at regulating terminal which can be remote or local
            14 = {str} 'target_q' MVAr, The reactive power target at local terminal
            15 = {str} 'voltage_regulator_on'
            16 = {str} 'regulated_element_id'
            17 = {str} 'regulated_bus_id'
            18 = {str} 'regulated_bus_breaker_bus_id'
            19 = {str} 'p'
            20 = {str} 'q'
            21 = {str} 'i'
            22 = {str} 'voltage_level_id'
            23 = {str} 'bus_id'
            24 = {str} 'bus_breaker_bus_id'
            25 = {str} 'node'
            26 = {str} 'condenser'
            27 = {str} 'connected'
            28 = {str} 'fictitious'
            """
            for i, row in gens.iterrows():
                bus1: dev.Bus | None = bus_dict.get(row["bus_id"], None)

                if bus1 is None:
                    self.logger.add_error("Bus not found",
                                          device_class="Generator",
                                          device=i)
                else:

                    p = float(row["p"])
                    q = float(row["q"])
                    S = p + 1j * q
                    Sabs = abs(S)
                    if bool(row["voltage_regulator_on"]):
                        control_mode = GeneratorControlMode.V
                    else:
                        control_mode = GeneratorControlMode.Q

                    elm = dev.Generator(
                        name=row["name"] if row["name"] != "" else i,
                        code=i,
                        P=p,
                        Q=q,
                        vset=float(row["target_v"]),
                        Pmin=float(row["min_p"]),
                        Pmax=float(row["max_p"]),
                        Qmin=float(row["min_q"]),
                        Qmax=float(row["max_q"]),
                        Snom=float(row["rated_s"]),
                        active=bool(row["connected"]),
                        control_mode=control_mode,
                    )
                    elm.control_bus = bus_dict.get(row["regulated_bus_id"], None)
                    grid.add_generator(bus=bus1, api_obj=elm)

            """
            Capacitor bank
            00 = {str} 'name'
            01 = {str} 'g'
            02 = {str} 'b'
            03 = {str} 'model_type'
            04 = {str} 'max_section_count'
            05 = {str} 'section_count'
            06 = {str} 'solved_section_count'
            07 = {str} 'voltage_regulation_on'
            08 = {str} 'target_v'
            09 = {str} 'target_deadband'
            10 = {str} 'regulating_bus_id'
            11 = {str} 'p'
            12 = {str} 'q'
            13 = {str} 'i'
            14 = {str} 'voltage_level_id'
            15 = {str} 'bus_id'
            16 = {str} 'bus_breaker_bus_id'
            17 = {str} 'node'
            18 = {str} 'connected'
            19 = {str} 'fictitious'
            """
            for i, row in capacitor_banks.iterrows():
                bus1: dev.Bus | None = bus_dict.get(row["bus_id"], None)

                if bus1 is None:
                    self.logger.add_error("Bus not found",
                                          device_class="Capacitor Bank",
                                          device=i)
                else:
                    elm = dev.Shunt(
                        name=row["name"] if row["name"] != "" else i,
                        code=i,
                        G1=float(row["g"]),
                        B1=float(row["b"]),
                        active=bool(row["connected"])
                    )
                    grid.add_shunt(bus=bus1, api_obj=elm)

            """
            SVC
            00 = {str} 'name'
            01 = {str} 'b_min'
            02 = {str} 'b_max'
            03 = {str} 'target_v'
            04 = {str} 'target_q'
            05 = {str} 'regulation_mode'
            06 = {str} 'regulating'
            07 = {str} 'regulated_element_id'
            08 = {str} 'regulated_bus_id'
            09 = {str} 'regulated_bus_breaker_bus_id'
            10 = {str} 'p'
            11 = {str} 'q'
            12 = {str} 'i'
            13 = {str} 'voltage_level_id'
            14 = {str} 'bus_id'
            15 = {str} 'bus_breaker_bus_id'
            16 = {str} 'node'
            17 = {str} 'connected'
            18 = {str} 'fictitious'
            """
            for i, row in svc.iterrows():
                bus1: dev.Bus | None = bus_dict.get(row["bus_id"], None)

                if bus1 is None:
                    self.logger.add_error("Bus not found",
                                          device_class="SVC",
                                          device=i)
                else:
                    elm = dev.ControllableShunt(
                        name=row["name"] if row["name"] != "" else i,
                        code=i,
                        G1=float(row["p"]),  # TODO: Make sure about the units
                        B1=float(row["q"]),
                        active=bool(row["connected"]),
                        Bmin=float(row["b_min"]),
                        Bmax=float(row["b_max"]),
                        vset=float(row["target_v"]),
                        control_mode=ShuntControlMode.Continuous if bool(row["regulating"]) else ShuntControlMode.Locked
                    )
                    elm.control_bus = bus_dict.get(row["regulated_bus_id"], None)
                    grid.add_controllable_shunt(bus=bus1, api_obj=elm)

            return grid
