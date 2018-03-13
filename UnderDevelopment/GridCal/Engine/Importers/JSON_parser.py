# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import json

from GridCal.Engine.CalculationEngine import *


def parse_json_data(data):
    """
    Parse JSON structure into GridCal MultiCircuit
    :param data: JSON structure (list of dictionaries)
    :return: GridCal MultiCircuit
    """

    circuit = MultiCircuit()

    bus_id = dict()

    for element in data:

        if element["type"] == 'ps':

            if element["type"] == "circuit":

                circuit = MultiCircuit()
                circuit.name = element["name"]
                circuit.Sbase = element["Sbase"]

            elif element["type"] == "bus":

                # create the bus and add some properties
                elm = Bus(name=element["name"],
                          vnom=element["Vnom"],
                          vmin=0.9,
                          vmax=1.1,
                          xpos=element['x'],
                          ypos=element['y'],
                          height=element['h'],
                          width=element['w'],
                          active=True)

                if element["is_slack"]:
                    elm.type = NodeType.REF
                if element["vmax"] > 0:
                    elm.Vmax = element["vmax"]
                if element["vmin"] > 0:
                    elm.Vmin = element["vmin"]

                elm.Zf = complex(element['rf'], element['xf'])

                circuit.add_bus(elm)

                # add the bus to the dictionary
                bus_id[element["id"]] = elm

            elif element["type"] == "load":

                # get the matching bus object pointer
                bus = bus_id[element["bus"]]

                # create a load in the bus
                elm = Load(name=element['name'],
                           impedance=complex(element["Zr"], element["Zi"]),
                           current=complex(element["Ir"], element["Ii"]),
                           power=complex(element["P"], element["Q"]),
                           impedance_prof=None,
                           current_prof=None,
                           power_prof=None,
                           active=element['active'])
                bus.loads.append(elm)

            elif element["type"] == "controlled_gen":

                # get the matching bus object pointer
                bus = bus_id[element["bus"]]

                # create a load in the bus
                elm = ControlledGenerator(name=element['name'],
                                          active_power=element["P"],
                                          voltage_module=element["vset"],
                                          Qmin=element['qmin'],
                                          Qmax=element['qmax'],
                                          Snom=element['Snom'],
                                          power_prof=None,
                                          vset_prof=None,
                                          active=element['active'],
                                          p_min=0.0,
                                          p_max=element['Snom'],
                                          op_cost=1.0)
                bus.controlled_generators.append(elm)

            elif element["type"] == "static_gen":

                # get the matching bus object pointer
                bus = bus_id[element["bus"]]

                # create a load in the bus
                elm = StaticGenerator(name=element['name'],
                                      power=complex(element['P'], element['Q']),
                                      power_prof=None,
                                      active=element['active'])
                bus.static_generators.append(elm)

            elif element["type"] == "battery":

                # get the matching bus object pointer
                bus = bus_id[element["bus"]]

                # create a load in the bus
                elm = Battery(name=element['name'],
                              active_power=element["P"],
                              voltage_module=element["vset"],
                              Qmin=element['qmin'],
                              Qmax=element['qmax'],
                              Snom=element['Snom'],
                              Enom=element['Enom'],
                              power_prof=None,
                              vset_prof=None,
                              active=element['active'])
                bus.batteries.append(elm)

            elif element["type"] == "shunt":

                # get the matching bus object pointer
                bus = bus_id[element["bus"]]

                # create a load in the bus
                elm = Shunt(name=element['name'],
                            admittance=complex(element["g"], element["b"]),
                            admittance_prof=None,
                            active=element['active'])
                bus.shunts.append(elm)

            elif element["type"] == "branch":

                # get the matching bus object pointer
                bus1 = bus_id[element["from"]]
                bus2 = bus_id[element["to"]]

                # create a load in the  bus
                elm = Branch(bus_from=bus1,
                             bus_to=bus2,
                             name=element["name"],
                             r=element["r"],
                             x=element["x"],
                             g=element["g"],
                             b=element["b"],
                             rate=element["rate"],
                             tap=element["tap_module"],
                             shift_angle=element["tap_angle"],
                             active=element["active"],
                             mttf=0,
                             mttr=0,
                             is_transformer=element["is_transformer"])
                circuit.add_branch(elm)

        else:
            warn('ID: ' + element["id"] + ' error: GridCal only takes positive sequence elements.')

    return circuit


def parse_json(file_name):
    """
    Parse JSON file into Circuit
    :param file_name: 
    :return: GridCal MultiCircuit
    """
    data = json.load(open(file_name))

    return parse_json_data(data)
