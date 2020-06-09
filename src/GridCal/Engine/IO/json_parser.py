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

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Devices import *


def parse_json_data(data) -> MultiCircuit:
    """
    Parse JSON structure into GridCal MultiCircuit
    :param data: JSON structure (list of dictionaries)
    :return: GridCal MultiCircuit
    """

    circuit = MultiCircuit()

    bus_id = dict()

    for element in data:

        if element["phases"] == 'ps':

            if element["type"] == "circuit":

                circuit = MultiCircuit()
                circuit.name = element["name"]
                circuit.Sbase = element["Sbase"]
                circuit.comments = element['comments']

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
                    elm.type = BusMode.Slack
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
                           G=element["G"],
                           B=element["B"],
                           Ir=element["Ir"],
                           Ii=element["Ii"],
                           P=element["P"],
                           Q=element["Q"],
                           active=element['active'])
                bus.loads.append(elm)

            elif element["type"] == "controlled_gen":

                # get the matching bus object pointer
                bus = bus_id[element["bus"]]

                # create a load in the bus
                elm = Generator(name=element['name'],
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
                                      P=element['P'], Q=element['Q'],
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
                            G=element["g"], B=element["b"],
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
                             branch_type=element["branch_type"])
                circuit.add_branch(elm)

        else:
            warn('ID: ' + element["id"] + ' error: GridCal only takes positive sequence elements.')

    return circuit


def parse_json_data_v2(data: dict, logger: Logger):

    devices = data['devices']
    profiles = data['profiles']

    if DeviceType.CircuitDevice.value in devices.keys():

        dta = devices[DeviceType.CircuitDevice.value]
        circuit = MultiCircuit(name=dta['name'],
                               Sbase=dta['sbase'],
                               fbase=dta['fbase'],
                               idtag=dta['id'])

        return circuit

    else:
        logger.add('The Json structure does not have a Circuit inside the devices!')
        return MultiCircuit()


def parse_json(file_name) -> MultiCircuit:
    """
    Parse JSON file into Circuit
    :param file_name: 
    :return: GridCal MultiCircuit
    """
    data = json.load(open(file_name))

    return parse_json_data(data)


def save_json_file(file_path, circuit: MultiCircuit):
    """
    Save JSON file
    :param file_path: file path 
    :param circuit: GridCal MultiCircuit element
    """
    elements = dict()
    element_profiles = dict()
    key = 0
    units_dict = dict()
    logger = Logger()

    def add_to_dict(d, d2, key):
        if key in d.keys():
            d[key].append(d2)
        else:
            d[key] = [d2]

    def add_to_dict2(d, d2, key):
        if key not in d.keys():
            d[key] = d2

    # add the circuit
    elements[DeviceType.CircuitDevice.value] = circuit.get_properties_dict()
    units_dict[DeviceType.CircuitDevice.value] = circuit.get_units_dict()
    element_profiles[DeviceType.CircuitDevice.value] = circuit.get_profiles_dict()

    # add the buses
    for elm in circuit.buses:

        # pack the bus data into a dictionary
        add_to_dict(d=elements, d2=elm.get_properties_dict(), key=elm.device_type.value)
        add_to_dict(d=element_profiles, d2=elm.get_profiles_dict(), key=elm.device_type.value)
        add_to_dict2(d=units_dict, d2=elm.get_units_dict(), key=elm.device_type.value)

        # pack all the elements within the bus
        devices = elm.loads + elm.controlled_generators + elm.static_generators + elm.batteries + elm.shunts
        for device in devices:
            add_to_dict(d=elements, d2=device.get_properties_dict(), key=device.device_type.value)
            add_to_dict(d=element_profiles, d2=device.get_profiles_dict(), key=device.device_type.value)
            add_to_dict2(d=units_dict, d2=device.get_units_dict(), key=device.device_type.value)

    # branches
    for branch_list in circuit.get_branch_lists():
        for elm in branch_list:
            # pack the branch data into a dictionary
            add_to_dict(d=elements, d2=elm.get_properties_dict(), key=elm.device_type.value)
            add_to_dict(d=element_profiles, d2=elm.get_profiles_dict(), key=elm.device_type.value)
            add_to_dict2(d=units_dict, d2=elm.get_units_dict(), key=elm.device_type.value)

    data = {'version': '2.0',
            'software': 'GridCal',
            'units': units_dict,
            'devices': elements,
            'profiles': element_profiles}

    data_str = json.dumps(data, indent=True)

    # Save json to a text file file
    text_file = open(file_path, "w")
    text_file.write(data_str)
    text_file.close()

    return logger
