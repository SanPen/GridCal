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


def parse_json_data_v3(data: dict, logger: Logger):
    """
    New Json parser
    :param data:
    :param logger:
    :return:
    """
    devices = data['devices']
    profiles = data['profiles']

    if DeviceType.CircuitDevice.value in devices.keys():

        dta = devices[DeviceType.CircuitDevice.value]

        circuit = MultiCircuit(name=str(dta['name']),
                               Sbase=float(dta['sbase']),
                               fbase=float(dta['fbase']),
                               idtag=str(dta['id']))

        jcircuit = devices["Circuit"]
        circuit.Sbase = jcircuit["sbase"]

        # Countries
        country_dict = dict()
        if 'Country' in devices.keys():
            elms = devices["Country"]
            for jentry in elms:
                elm = Country(idtag=str(jentry['id']),
                              code=str(jentry['code']),
                              name=str(jentry['name']))
                circuit.countries.append(elm)
                country_dict[elm.idtag] = elm
        else:
            elm = Country(idtag=None, code='Default', name='Default')
            circuit.countries.append(elm)

        # Areas
        areas_dict = dict()
        if 'Area' in devices.keys():
            elms = devices["Area"]
            for jentry in elms:
                elm = Area(idtag=str(jentry['id']),
                           code=str(jentry['code']),
                           name=str(jentry['name']))
                circuit.areas.append(elm)
                areas_dict[elm.idtag] = elm
        else:
            elm = Area(idtag=None, code='Default', name='Default')
            circuit.areas.append(elm)

        # Zones
        zones_dict = dict()
        if 'Zone' in devices.keys():
            elms = devices["Zone"]
            for jentry in elms:
                elm = Zone(idtag=str(jentry['id']),
                           code=str(jentry['code']),
                           name=str(jentry['name']))
                circuit.zones.append(elm)
                zones_dict[elm.idtag] = elm
        else:
            elm = Zone(idtag=None, code='Default', name='Default')
            circuit.zones.append(elm)

        # Substations
        substations_dict = dict()
        if 'Substation' in devices.keys():
            elms = devices["Substation"]
            for jentry in elms:
                elm = Substation(idtag=str(jentry['id']),
                                 code=str(jentry['code']),
                                 name=str(jentry['name']))
                circuit.substations.append(elm)
                substations_dict[elm.idtag] = elm
        else:
            elm = Substation(idtag=None, code='Default', name='Default')
            circuit.substations.append(elm)

        # buses
        bus_dict = dict()
        if 'Bus' in devices.keys():
            buses = devices["Bus"]
            for jentry in buses:

                area_id = str(jentry['area']) if 'area' in jentry.keys() else ''
                zone_id = str(jentry['zone']) if 'zone' in jentry.keys() else ''
                substation_id = str(jentry['substation']) if 'substation' in jentry.keys() else ''
                country_id = str(jentry['country']) if 'country' in jentry.keys() else ''

                if area_id in areas_dict.keys():
                    area = areas_dict[area_id]
                else:
                    area = circuit.areas[0]

                if zone_id in zones_dict.keys():
                    zone = zones_dict[zone_id]
                else:
                    zone = circuit.zones[0]

                if substation_id in substations_dict.keys():
                    substation = substations_dict[substation_id]
                else:
                    substation = circuit.substations[0]

                if country_id in country_dict.keys():
                    country = country_dict[country_id]
                else:
                    country = circuit.countries[0]

                bus = Bus(name=str(jentry['name']),
                          idtag=str(jentry['id']),
                          code=str(jentry['name_code']),
                          vnom=float(jentry['vnom']),
                          vmin=float(jentry['vmin']),
                          vmax=float(jentry['vmax']),
                          r_fault=float(jentry['rf']),
                          x_fault=float(jentry['xf']),
                          xpos=float(jentry['x']),
                          ypos=float(jentry['y']),
                          height=float(jentry['h']),
                          width=float(jentry['w']),
                          active=bool(jentry['active']),
                          is_slack=bool(jentry['is_slack']),
                          area=area,
                          zone=zone,
                          substation=substation,
                          country=country,
                          longitude=float(jentry['lon']),
                          latitude=float(jentry['lat']))

                bus_dict[jentry['id']] = bus
                circuit.add_bus(bus)

        if 'Generator' in devices.keys():
            generators = devices["Generator"]
            for jentry in generators:
                gen = Generator(name=str(jentry['name']),
                                idtag=str(jentry['id']),
                                active_power=float(jentry['p']),
                                power_factor=float(jentry['pf']),
                                voltage_module=float(jentry['vset']),
                                is_controlled=bool(jentry['is_controlled']),
                                Qmin=float(jentry['qmin']),
                                Qmax=float(jentry['qmax']),
                                Snom=float(jentry['snom']),
                                active=bool(jentry['active']),
                                p_min=float(jentry['pmin']),
                                p_max=float(jentry['pmax']),
                                op_cost=float(jentry['cost']),
                                )
                gen.bus = bus_dict[jentry['bus']]
                circuit.add_generator(gen.bus, gen)

        if 'Battery' in devices.keys():
            batteries = devices["Battery"]
            for jentry in batteries:
                gen = Battery(name=str(jentry['name']),
                              idtag=str(jentry['id']),
                              active_power=float(jentry['p']),
                              power_factor=float(jentry['pf']),
                              voltage_module=float(jentry['vset']),
                              is_controlled=bool(jentry['is_controlled']),
                              Qmin=float(jentry['qmin']),
                              Qmax=float(jentry['qmax']),
                              Snom=float(jentry['snom']),
                              active=bool(jentry['active']),
                              p_min=float(jentry['pmin']),
                              p_max=float(jentry['pmax']),
                              op_cost=float(jentry['cost']),
                              )
                gen.bus = bus_dict[jentry['bus']]
                circuit.add_battery(gen.bus, gen)

        if 'Load' in devices.keys():
            loads = devices["Load"]
            for jentry in loads:
                elm = Load(name=str(jentry['name']),
                           idtag=str(jentry['id']),
                           P=float(jentry['p']),
                           Q=float(jentry['q']),
                           active=bool(jentry['active']))
                elm.bus = bus_dict[jentry['bus']]
                circuit.add_load(elm.bus, elm)

        if "Shunt" in devices.keys():
            shunts = devices["Shunt"]
            for jentry in shunts:
                elm = Shunt(name=str(jentry['name']),
                            idtag=str(jentry['id']),
                            G=float(jentry['g']),
                            B=float(jentry['b']),
                            Bmax=float(jentry['b_max']),
                            Bmin=float(jentry['b_min']),
                            active=bool(jentry['active']),
                            controlled=bool(jentry['controlled'])
                            )
                elm.bus = bus_dict[jentry['bus']]
                circuit.add_shunt(elm.bus, elm)

        if "Line" in devices.keys():
            lines = devices["Line"]
            for entry in lines:
                elm = Line(bus_from=bus_dict[entry['bus_from']],
                           bus_to=bus_dict[entry['bus_to']],
                           name=str(entry['name']),
                           idtag=str(entry['id']),
                           code=str(entry['name_code']),
                           r=float(entry['r']),
                           x=float(entry['x']),
                           b=float(entry['b']),
                           rate=float(entry['rate']),
                           active=entry['active'],
                           length=float(entry['length']),
                           temp_base=float(entry['base_temperature']),
                           temp_oper=float(entry['operational_temperature']),
                           alpha=float(entry['alpha'])
                           )
                circuit.add_line(elm)

        if "Transformer2w" in devices.keys():
            transformers = devices["Transformer2w"]

            for entry in transformers:

                v1 = float(entry['Vnomf'])
                v2 = float(entry['Vnomt'])

                bus_from = bus_dict[entry['bus_from']]
                bus_to = bus_dict[entry['bus_to']]

                if v1 == 0.0:
                    v1 = bus_from.Vnom

                if v2 == 0.0:
                    v2 = bus_to.Vnom

                if v1 > v2:
                    HV = v1
                    LV = v2
                else:
                    HV = v2
                    LV = v1

                elm = Transformer2W(bus_from=bus_from,
                                    bus_to=bus_to,
                                    name=str(entry['name']),
                                    idtag=str(entry['id']),
                                    code=str(entry['name_code']),
                                    r=float(entry['r']),
                                    x=float(entry['x']),
                                    g=float(entry['g']),
                                    b=float(entry['b']),
                                    rate=float(entry['rate']),
                                    HV=HV,
                                    LV=LV,
                                    active=bool(entry['active']),
                                    tap=float(entry['tap_module']),
                                    shift_angle=float(entry['tap_angle']),
                                    bus_to_regulated=bool(entry['bus_to_regulated']),
                                    vset=float(entry['vset']),
                                    temp_base=float(entry['base_temperature']),
                                    temp_oper=float(entry['operational_temperature']),
                                    alpha=float(entry['alpha'])
                                    )
                circuit.add_transformer2w(elm)

        if "TransformerNw" in devices.keys():
            transformers = devices["TransformerNw"]

            for tentry in transformers:
                for entry in tentry['windings']:
                    v1 = float(entry['Vnomf'])
                    v2 = float(entry['Vnomt'])

                    if v1 > v2:
                        HV = v1
                        LV = v2
                    else:
                        HV = v2
                        LV = v1

                    elm = Transformer2W(bus_from=bus_dict[entry['bus_from']],
                                        bus_to=bus_dict[entry['bus_to']],
                                        name=str(tentry['name']),
                                        idtag=str(entry['id']),
                                        code=str(entry['name_code']),
                                        active=bool(tentry['active']),
                                        r=float(entry['r']),
                                        x=float(entry['x']),
                                        g=float(entry['g']),
                                        b=float(entry['b']),
                                        rate=float(entry['rate']),
                                        HV=HV,
                                        LV=LV
                                        )
                    circuit.add_transformer2w(elm)

        if "VSC" in devices.keys():
            vsc = devices["VSC"]

            # TODO: call correct_buses_connection()

        if "HVDC Line" in devices.keys():
            hvdc = devices["HVDC Line"]

        # fill x, y
        circuit.fill_xy_from_lat_lon()

        return circuit

    else:
        logger.add('The Json structure does not have a Circuit inside the devices!')
        return MultiCircuit()


def parse_json_data_v2(data: dict, logger: Logger):
    """
    New Json parser
    :param data:
    :param logger:
    :return:
    """
    devices = data['devices']
    profiles = data['profiles']

    if DeviceType.CircuitDevice.value in devices.keys():

        dta = devices[DeviceType.CircuitDevice.value]
        circuit = MultiCircuit(name=str(dta['name']),
                               Sbase=float(dta['sbase']),
                               fbase=float(dta['fbase']),
                               idtag=str(dta['id']))

        jcircuit = devices["Circuit"]
        circuit.Sbase = jcircuit["sbase"]

        # Countries
        country_dict = dict()
        if 'Country' in devices.keys():
            elms = devices["Country"]
            for jentry in elms:
                elm = Country(idtag=str(jentry['id']),
                              code=str(jentry['code']),
                              name=str(jentry['name']))
                circuit.countries.append(elm)
                country_dict[elm.idtag] = elm
        else:
            elm = Country(idtag=None, code='Default', name='Default')
            circuit.countries.append(elm)

        # Areas
        areas_dict = dict()
        if 'Area' in devices.keys():
            elms = devices["Area"]
            for jentry in elms:
                elm = Area(idtag=str(jentry['id']),
                           code=str(jentry['code']),
                           name=str(jentry['name']))
                circuit.areas.append(elm)
                areas_dict[elm.idtag] = elm
        else:
            elm = Area(idtag=None, code='Default', name='Default')
            circuit.areas.append(elm)

        # Zones
        zones_dict = dict()
        if 'Zone' in devices.keys():
            elms = devices["Zone"]
            for jentry in elms:
                elm = Zone(idtag=str(jentry['id']),
                           code=str(jentry['code']),
                           name=str(jentry['name']))
                circuit.zones.append(elm)
                zones_dict[elm.idtag] = elm
        else:
            elm = Zone(idtag=None, code='Default', name='Default')
            circuit.zones.append(elm)

        # Substations
        substations_dict = dict()
        if 'Substation' in devices.keys():
            elms = devices["Substation"]
            for jentry in elms:
                elm = Substation(idtag=str(jentry['id']),
                                 code=str(jentry['code']),
                                 name=str(jentry['name']))
                circuit.substations.append(elm)
                substations_dict[elm.idtag] = elm
        else:
            elm = Substation(idtag=None, code='Default', name='Default')
            circuit.substations.append(elm)

        # buses
        bus_dict = dict()
        if 'Bus' in devices.keys():
            buses = devices["Bus"]
            for jentry in buses:

                area_id = str(jentry['area']) if 'area' in jentry.keys() else ''
                zone_id = str(jentry['zone']) if 'zone' in jentry.keys() else ''
                substation_id = str(jentry['substation']) if 'substation' in jentry.keys() else ''
                country_id = str(jentry['country']) if 'country' in jentry.keys() else ''

                if area_id in areas_dict.keys():
                    area = areas_dict[area_id]
                else:
                    area = circuit.areas[0]

                if zone_id in zones_dict.keys():
                    zone = zones_dict[zone_id]
                else:
                    zone = circuit.zones[0]

                if substation_id in substations_dict.keys():
                    substation = substations_dict[substation_id]
                else:
                    substation = circuit.substations[0]

                if country_id in country_dict.keys():
                    country = country_dict[country_id]
                else:
                    country = circuit.countries[0]

                bus = Bus(name=str(jentry['name']),
                          idtag=str(jentry['id']),
                          vnom=float(jentry['vnom']),
                          vmin=float(jentry['vmin']),
                          vmax=float(jentry['vmax']),
                          r_fault=float(jentry['rf']),
                          x_fault=float(jentry['xf']),
                          xpos=float(jentry['x']),
                          ypos=float(jentry['y']),
                          height=float(jentry['h']),
                          width=float(jentry['w']),
                          active=bool(jentry['active']),
                          is_slack=bool(jentry['is_slack']),
                          area=area,
                          zone=zone,
                          substation=substation,
                          country=country,
                          longitude=float(jentry['lon']),
                          latitude=float(jentry['lat']))

                bus_dict[jentry['id']] = bus
                circuit.add_bus(bus)

        if 'Generator' in devices.keys():
            generators = devices["Generator"]
            for jentry in generators:
                gen = Generator(name=str(jentry['name']),
                                idtag=str(jentry['id']),
                                active_power=float(jentry['p']),
                                power_factor=float(jentry['pf']),
                                voltage_module=float(jentry['vset']),
                                is_controlled=bool(jentry['is_controlled']),
                                Qmin=float(jentry['qmin']),
                                Qmax=float(jentry['qmax']),
                                Snom=float(jentry['snom']),
                                active=bool(jentry['active']),
                                p_min=float(jentry['pmin']),
                                p_max=float(jentry['pmax']),
                                op_cost=float(jentry['cost']),
                                )
                gen.bus = bus_dict[jentry['bus']]
                circuit.add_generator(gen.bus, gen)

        if 'Battery' in devices.keys():
            batteries = devices["Battery"]
            for jentry in batteries:
                gen = Battery(name=str(jentry['name']),
                              idtag=str(jentry['id']),
                              active_power=float(jentry['p']),
                              power_factor=float(jentry['pf']),
                              voltage_module=float(jentry['vset']),
                              is_controlled=bool(jentry['is_controlled']),
                              Qmin=float(jentry['qmin']),
                              Qmax=float(jentry['qmax']),
                              Snom=float(jentry['snom']),
                              active=bool(jentry['active']),
                              p_min=float(jentry['pmin']),
                              p_max=float(jentry['pmax']),
                              op_cost=float(jentry['cost']),
                              )
                gen.bus = bus_dict[jentry['bus']]
                circuit.add_battery(gen.bus, gen)

        if 'Load' in devices.keys():
            loads = devices["Load"]
            for jentry in loads:
                elm = Load(name=str(jentry['name']),
                           idtag=str(jentry['id']),
                           P=float(jentry['p']),
                           Q=float(jentry['q']),
                           active=bool(jentry['active']))
                elm.bus = bus_dict[jentry['bus']]
                circuit.add_load(elm.bus, elm)

        if "Shunt" in devices.keys():
            shunts = devices["Shunt"]
            for jentry in shunts:
                elm = Shunt(name=str(jentry['name']),
                            idtag=str(jentry['id']),
                            G=float(jentry['g']),
                            B=float(jentry['b']),
                            active=bool(jentry['active']))
                elm.bus = bus_dict[jentry['bus']]
                circuit.add_shunt(elm.bus, elm)

        if "Line" in devices.keys():
            lines = devices["Line"]
            for entry in lines:
                elm = Line(bus_from=bus_dict[entry['bus_from']],
                           bus_to=bus_dict[entry['bus_to']],
                           name=str(entry['name']),
                           idtag=str(entry['id']),
                           r=float(entry['r']),
                           x=float(entry['x']),
                           b=float(entry['b']),
                           rate=float(entry['rate']),
                           active=entry['active'],
                           length=float(entry['length']),
                           )
                circuit.add_line(elm)

        if "Transformer" in devices.keys() or "Transformer2w" in devices.keys():

            if "Transformer" in devices.keys():
                transformers = devices["Transformer"]
            elif "Transformer2w" in devices.keys():
                transformers = devices["Transformer2w"]
            else:
                raise Exception('Transformer key not found')

            for entry in transformers:
                elm = Transformer2W(bus_from=bus_dict[entry['bus_from']],
                                    bus_to=bus_dict[entry['bus_to']],
                                    name=str(entry['name']),
                                    idtag=str(entry['id']),
                                    r=float(entry['r']),
                                    x=float(entry['x']),
                                    g=float(entry['g']),
                                    b=float(entry['b']),
                                    rate=float(entry['rate']),
                                    active=bool(entry['active']),
                                    tap=float(entry['tap_module']),
                                    shift_angle=float(entry['tap_angle']),
                                    )
                circuit.add_transformer2w(elm)

        if "VSC" in devices.keys():
            vsc = devices["VSC"]

            # TODO: call correct_buses_connection()

        if "HVDC Line" in devices.keys():
            hvdc = devices["HVDC Line"]

        # fill x, y
        circuit.fill_xy_from_lat_lon()

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


def save_json_file(file_path, circuit: MultiCircuit, simulation_drivers=list()):
    """
    Save JSON file
    :param file_path: file path 
    :param circuit: GridCal MultiCircuit element
    :param simulation_drivers: List of Simulation Drivers
    """
    elements = dict()
    element_profiles = dict()
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

    # add the areas
    for cls in [circuit.substations, circuit.zones, circuit.areas, circuit.countries]:
        for elm in cls:
            # pack the bus data into a dictionary
            add_to_dict(d=elements, d2=elm.get_properties_dict(), key=elm.device_type.value)
            add_to_dict(d=element_profiles, d2=elm.get_profiles_dict(), key=elm.device_type.value)
            add_to_dict2(d=units_dict, d2=elm.get_units_dict(), key=elm.device_type.value)

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

    # results
    results = dict()
    for driver in simulation_drivers:
        if driver is not None:

            if driver.name == 'Power Flow':

                bus_data = dict()
                for i, elm in enumerate(circuit.buses):
                    bus_data[elm.idtag] = {'vm': np.abs(driver.results.voltage[i]),
                                           'va': np.angle(driver.results.voltage[i])}

                branch_data = dict()
                for i, elm in enumerate(circuit.get_branches_wo_hvdc()):
                    branch_data[elm.idtag] = {'p': driver.results.Sf[i].real,
                                              'q': driver.results.Sf[i].imag,
                                              'losses': driver.results.losses[i].real}

                for i, elm in enumerate(circuit.hvdc_lines):
                    branch_data[elm.idtag] = {'p': driver.results.hvdc_Pf[i].real,
                                              'q': 0,
                                              'losses': driver.results.hvdc_losses[i].real}

                results["power_flow"] = {'bus': bus_data,
                                         'branch': branch_data}

            elif driver.name == 'Time Series':

                bus_data = dict()
                for i, elm in enumerate(circuit.buses):
                    bus_data[elm.idtag] = {'vm': np.abs(driver.results.voltage[:, i]).tolist(),
                                           'va': np.angle(driver.results.voltage[:, i]).tolist()}

                branch_data = dict()
                for i, elm in enumerate(circuit.get_branches_wo_hvdc()):
                    branch_data[elm.idtag] = {'p': driver.results.Sf[:, i].real.tolist(),
                                              'q': driver.results.Sf[:, i].imag.tolist(),
                                              'losses': driver.results.losses[:, i].real.tolist()}

                for i, elm in enumerate(circuit.hvdc_lines):
                    branch_data[elm.idtag] = {'p': driver.results.hvdc_Pf[:, i].real,
                                              'q': 0,
                                              'losses': driver.results.hvdc_losses[:, i].real}

                results["time_series"] = {'bus': bus_data,
                                          'branch': branch_data}

    data = {'version': '3',
            'review': '1',
            'software': 'GridCal',
            'units': units_dict,
            'devices': elements,
            'profiles': element_profiles,
            'results': results}

    data_str = json.dumps(data, indent=True)

    # Save json to a text file file
    text_file = open(file_path, "w")
    text_file.write(data_str)
    text_file.close()

    return logger
