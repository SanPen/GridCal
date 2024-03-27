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

import json
from typing import List, Union, Any, Dict
from warnings import warn
import numpy as np
from GridCalEngine.basic_structures import Logger
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.IO.gridcal.contingency_parser import get_contingencies_dict, parse_contingencies
from GridCalEngine.IO.gridcal.generic_io_functions import CustomJSONizer
import GridCalEngine.Devices as dev
from GridCalEngine.Devices.profile import Profile
from GridCalEngine.Devices.Parents.editable_device import EditableDevice
from GridCalEngine.enumerations import (DeviceType, ConverterControlType, HvdcControlType, BuildStatus,
                                        TransformerControlType)


def add_to_dict(main_dict: Dict[str, List[Any]], data_to_append: Dict[Any, Any], key: str):
    """
    Append d2 into a list of d at the key
    :param main_dict: Dictionary to append to
    :param data_to_append: Secondary dictionary to append
    :param key: key where to append the dictionary
    """
    lst = main_dict.get(key, None)
    if lst is None:
        main_dict[key] = [data_to_append]  # create list at the entry
    else:
        lst.append(data_to_append)  # increase list


def add_to_dict2(main_dict: Dict[str, Any], data: Dict[Any, Any], key: str):
    """
    Add data to the main dictionary at the given key if it does not exists already
    :param main_dict:Dictionary to append to
    :param data: Some dictionary
    :param key: key to store
    """
    if key not in main_dict.keys():
        main_dict[key] = data


def profile_to_json(profile: Profile) -> Dict[str, Any]:
    """
    Convert a Profile to a json dictionary
    :param profile:
    :return:
    """
    if profile.is_sparse:
        indptr, data = profile.get_sparse_representation()
        return {'type': 'sparse',
                'base': profile.default_value,
                'size': profile.size(),
                'data': data,
                'indptr': indptr}
    else:
        arr = profile.tolist()
        return {'type': 'dense',
                'data': arr}


def json_to_profile(d: Dict[str, Any]) -> Profile:
    """
    Convert a json
    :param d:
    :return:
    """
    if isinstance(d, dict):
        if 'type' in d.keys():
            if d['type'] == 'sparse':
                profile = Profile(default_value=d['base'], is_sparse=True)
                profile.create_sparse(size=d['size'], default_value=d['base'])
                profile.set_sparse_representation(indptr=d['indptr'], data=d['data'])
                return profile

            elif d['type'] == 'dense':
                val = np.array(d['data'])
                if len(val):
                    profile = Profile(default_value=val[0])
                    profile.set(arr=val)
                else:
                    profile = Profile(default_value=0)
                return profile
            else:
                raise Exception('Unknown profile type' + str(d['type']))

        else:
            raise Exception("The passed dictionary is not a profile definition")
    elif isinstance(d, list):
        if len(d) > 0:
            profile = Profile(default_value=d[0])
            profile.set(arr=np.array(d))
            return profile
    else:
        raise Exception("The passed value is not a list or dictionary definition")


def get_profiles_dict(elm: EditableDevice) -> Dict[str, Any]:
    """

    :return:
    """

    """
    Example:
    {'id': self.idtag,
    'active': active_prof,
    'rate': rate_prof}
    """
    data = {'id': elm.idtag}
    for property_name, profile_name in elm.properties_with_profile.items():
        data[property_name] = profile_to_json(elm.get_profile(magnitude=property_name))

    return data


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
                elm = dev.Bus(name=element["name"],
                              vnom=element["Vnom"],
                              vmin=0.9,
                              vmax=1.1,
                              xpos=element['x'],
                              ypos=element['y'],
                              height=element['h'],
                              width=element['w'],
                              active=True)

                if element["is_slack"]:
                    elm.type = dev.BusMode.Slack
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
                elm = dev.Load(name=element['name'],
                               G=element["G"],
                               B=element["B"],
                               Ir=element["Ir"],
                               Ii=element["Ii"],
                               P=element["P"],
                               Q=element["Q"],
                               active=element['active'])
                circuit.add_load(bus=bus, api_obj=elm)

            elif element["type"] == "controlled_gen":

                # get the matching bus object pointer
                bus = bus_id[element["bus"]]

                # create a load in the bus
                elm = dev.Generator(name=element['name'],
                                    P=element["P"],
                                    vset=element["vset"],
                                    Qmin=element['qmin'],
                                    Qmax=element['qmax'],
                                    Snom=element['Snom'],
                                    active=element['active'],
                                    Pmin=0.0,
                                    Pmax=element['Snom'],
                                    Cost=1.0)
                circuit.add_generator(bus=bus, api_obj=elm)

            elif element["type"] == "static_gen":

                # get the matching bus object pointer
                bus = bus_id[element["bus"]]

                # create a load in the bus
                elm = dev.StaticGenerator(name=element['name'],
                                          P=element['P'], Q=element['Q'],
                                          active=element['active'])
                circuit.add_generator(bus=bus, api_obj=elm)

            elif element["type"] == "battery":

                # get the matching bus object pointer
                bus = bus_id[element["bus"]]

                # create a load in the bus
                elm = dev.Battery(name=element['name'],
                                  P=element["P"],
                                  vset=element["vset"],
                                  Qmin=element['qmin'],
                                  Qmax=element['qmax'],
                                  Snom=element['Snom'],
                                  Enom=element['Enom'],
                                  active=element['active'])
                circuit.add_battery(bus=bus, api_obj=elm)

            elif element["type"] == "shunt":

                # get the matching bus object pointer
                bus = bus_id[element["bus"]]

                # create a load in the bus
                elm = dev.Shunt(name=element['name'],
                                G=element["g"], B=element["b"],
                                active=element['active'])
                circuit.add_shunt(bus=bus, api_obj=elm)

            elif element["type"] == "branch":

                # get the matching bus object pointer
                bus1 = bus_id[element["from"]]
                bus2 = bus_id[element["to"]]

                # create a load in the  bus
                elm = dev.Branch(bus_from=bus1,
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


def set_object_properties(elm, prop: List[str], entry: Dict[str, Any]):
    """
    Set the properties of an object
    :param elm: object to be set
    :param prop: list of properties
    :param entry:
    :return:
    """
    for jprop, gcprop in prop:
        if jprop in entry.keys():
            setattr(elm, gcprop, entry[jprop])


def parse_json_data_v3(data: dict, logger: Logger):
    """
    Json parser for V3
    :param data:
    :param logger:
    :return:
    """
    devices = data['devices']
    profiles = data['profiles']

    # parse devices
    if DeviceType.CircuitDevice.value in devices.keys():

        dta = devices[DeviceType.CircuitDevice.value]

        circuit = MultiCircuit(name=str(dta['name']),
                               Sbase=float(dta['sbase']),
                               fbase=float(dta['fbase']),
                               idtag=str(dta['id']))

        jcircuit = devices["Circuit"]
        circuit.Sbase = jcircuit["sbase"]

        # parse time series
        if DeviceType.CircuitDevice.value in profiles.keys():
            circuit.set_time_profile(profiles[DeviceType.CircuitDevice.value]['time'])

        # Countries
        country_dict = dict()
        if 'Country' in devices.keys():
            elms = devices["Country"]
            for jentry in elms:
                elm = dev.Country(idtag=str(jentry['id']),
                                  code=str(jentry['code']),
                                  name=str(jentry['name']))

                circuit.add_country(elm)
                country_dict[elm.idtag] = elm

        else:
            elm = dev.Country(idtag=None, code='Default', name='Default')
            circuit.add_country(elm)

        # Areas
        areas_dict = dict()
        if 'Area' in devices.keys():
            elms = devices["Area"]
            for jentry in elms:
                elm = dev.Area(idtag=str(jentry['id']),
                               code=str(jentry['code']),
                               name=str(jentry['name']))
                circuit.add_area(elm)
                areas_dict[elm.idtag] = elm
        else:
            elm = dev.Area(idtag=None, code='Default', name='Default')
            circuit.add_area(elm)

        # Zones
        zones_dict = dict()
        if 'Zone' in devices.keys():
            elms = devices["Zone"]
            for jentry in elms:
                elm = dev.Zone(idtag=str(jentry['id']),
                               code=str(jentry['code']),
                               name=str(jentry['name']))
                circuit.add_zone(elm)
                zones_dict[elm.idtag] = elm
        else:
            elm = dev.Zone(idtag=None, code='Default', name='Default')
            circuit.add_zone(elm)

        # Substations
        substations_dict = dict()
        if 'Substation' in devices.keys():
            elms = devices["Substation"]
            for jentry in elms:
                elm = dev.Substation(idtag=str(jentry['id']),
                                     code=str(jentry['code']),
                                     name=str(jentry['name']))
                circuit.add_substation(elm)
                substations_dict[elm.idtag] = elm
        else:
            elm = dev.Substation(idtag=None, code='Default', name='Default')
            circuit.add_substation(elm)

        # buses
        bus_dict = dict()
        if 'Bus' in devices.keys():
            buses = devices["Bus"]

            if 'Bus' in profiles.keys():
                device_profiles_dict = {e['id']: e for e in profiles["Bus"]}
                has_profiles = True
            else:
                device_profiles_dict = dict()
                has_profiles = False

            for jentry in buses:

                area_id = str(jentry['area']) if 'area' in jentry.keys() else ''
                zone_id = str(jentry['zone']) if 'zone' in jentry.keys() else ''
                substation_id = str(jentry['Substation']) if 'Substation' in jentry.keys() else ''
                country_id = str(jentry['country']) if 'country' in jentry.keys() else ''
                area = areas_dict.get(area_id, None)
                zone = zones_dict.get(zone_id, None)
                substation = substations_dict.get(substation_id, None)
                country = country_dict.get(country_id, None)

                bus = dev.Bus(name=str(jentry['name']),
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
                              is_internal=bool(jentry.get('is_internal', False)),
                              is_dc=bool(jentry.get('is_dc', False)),
                              area=area,
                              zone=zone,
                              substation=substation,
                              country=country,
                              longitude=float(jentry['lon']),
                              latitude=float(jentry['lat']))

                bus_dict[jentry['id']] = bus

                if has_profiles:
                    bus.active_prof = json_to_profile(device_profiles_dict[bus.idtag]['active'])

                circuit.add_bus(bus)

        if 'Generator' in devices.keys():
            generators = devices["Generator"]

            if 'Generator' in profiles.keys():
                device_profiles_dict = {e['id']: e for e in profiles["Generator"]}
                has_profiles = True
            else:
                device_profiles_dict = dict()
                has_profiles = False

            for jentry in generators:
                elm = dev.Generator(name=str(jentry['name']),
                                    idtag=str(jentry['id']),
                                    P=float(jentry['p']),
                                    power_factor=float(jentry['pf']),
                                    vset=float(jentry['vset']),
                                    is_controlled=bool(jentry['is_controlled']),
                                    Qmin=float(jentry['qmin']),
                                    Qmax=float(jentry['qmax']),
                                    Snom=float(jentry['snom']),
                                    active=bool(jentry['active']),
                                    Pmin=float(jentry['pmin']),
                                    Pmax=float(jentry['pmax']),
                                    Cost=float(jentry['cost'] if "cost" in jentry else 1.0),
                                    )

                if has_profiles:
                    profile_entry = device_profiles_dict[elm.idtag]
                    elm.active_prof = json_to_profile(profile_entry['active'])
                    elm.P_prof = json_to_profile(profile_entry['p'])
                    elm.Vset_prof = json_to_profile(profile_entry['v'])
                    elm.Pf_prof = json_to_profile(profile_entry['pf'])

                elm.bus = bus_dict[jentry['bus']]
                circuit.add_generator(elm.bus, elm)

        if 'Battery' in devices.keys():
            batteries = devices["Battery"]

            if 'Battery' in profiles.keys():
                device_profiles_dict = {e['id']: e for e in profiles["Battery"]}
                has_profiles = True
            else:
                device_profiles_dict = dict()
                has_profiles = False

            for jentry in batteries:
                elm = dev.Battery(name=str(jentry['name']),
                                  idtag=str(jentry['id']),
                                  P=float(jentry['p']),
                                  power_factor=float(jentry['pf']),
                                  vset=float(jentry['vset']),
                                  is_controlled=bool(jentry['is_controlled']),
                                  Qmin=float(jentry['qmin']),
                                  Qmax=float(jentry['qmax']),
                                  Snom=float(jentry['snom']),
                                  active=bool(jentry['active']),
                                  Pmin=float(jentry['pmin']),
                                  Pmax=float(jentry['pmax']),
                                  Cost=float(jentry['cost']),
                                  )

                if has_profiles:
                    profile_entry = device_profiles_dict[elm.idtag]
                    elm.active_prof = json_to_profile(profile_entry['active'])
                    elm.P_prof = json_to_profile(profile_entry['p'])
                    elm.Vset_prof = json_to_profile(profile_entry['v'])
                    elm.Pf_prof = json_to_profile(profile_entry['pf'])

                elm.bus = bus_dict[jentry['bus']]
                circuit.add_battery(elm.bus, elm)

        if 'Load' in devices.keys():
            loads = devices["Load"]

            if 'Load' in profiles.keys():
                device_profiles_dict = {e['id']: e for e in profiles["Load"]}
                has_profiles = True
            else:
                device_profiles_dict = dict()
                has_profiles = False

            for jentry in loads:
                elm = dev.Load(name=str(jentry['name']),
                               idtag=str(jentry['id']),
                               P=float(jentry['p']),
                               Q=float(jentry['q']),
                               Ir=float(jentry['ir']),
                               Ii=float(jentry['ii']),
                               G=float(jentry['g']),
                               B=float(jentry['b']),
                               active=bool(jentry['active']))

                if has_profiles:
                    profile_entry = device_profiles_dict[elm.idtag]
                    elm.active_prof = json_to_profile(profile_entry['active'])
                    elm.P_prof = json_to_profile(profile_entry['p'])
                    elm.Q_prof = json_to_profile(profile_entry['q'])
                    elm.Ir_prof = json_to_profile(profile_entry['ir'])
                    elm.Ii_prof = json_to_profile(profile_entry['ii'])
                    elm.G_prof = json_to_profile(profile_entry['g'])
                    elm.B_prof = json_to_profile(profile_entry['b'])

                elm.bus = bus_dict[jentry['bus']]
                circuit.add_load(elm.bus, elm)

        if "Shunt" in devices.keys():
            shunts = devices["Shunt"]

            if 'Shunt' in profiles.keys():
                device_profiles_dict = {e['id']: e for e in profiles["Shunt"]}
                has_profiles = True
            else:
                device_profiles_dict = dict()
                has_profiles = False

            for jentry in shunts:
                if 'b_max' in jentry:
                    Bmax = float(jentry['b_max'])
                elif 'bmax' in jentry:
                    Bmax = float(jentry['bmax'])
                else:
                    Bmax = 9999.0

                if 'b_min' in jentry:
                    Bmin = float(jentry['b_min'])
                elif 'bmax' in jentry:
                    Bmin = float(jentry['bmin'])
                else:
                    Bmin = 9999.0

                elm = dev.Shunt(name=str(jentry['name']),
                                idtag=str(jentry['id']),
                                G=float(jentry['g']),
                                B=float(jentry['b']),
                                active=bool(jentry['active'])
                                )

                if has_profiles:
                    profile_entry = device_profiles_dict[elm.idtag]
                    elm.active_prof = json_to_profile(profile_entry['active'])
                    elm.G_prof = json_to_profile(profile_entry['g'])
                    elm.B_prof = json_to_profile(profile_entry['b'])

                elm.bus = bus_dict[jentry['bus']]
                circuit.add_shunt(elm.bus, elm)

        if "Line" in devices.keys():

            if 'Line' in profiles.keys():
                device_profiles_dict = {e['id']: e for e in profiles["Line"]}
                has_profiles = True
            else:
                device_profiles_dict = dict()
                has_profiles = False

            for entry in devices["Line"]:
                build_status = BuildStatus.Commissioned
                build_status_str = entry.get("build_status", None)
                if build_status_str is not None:
                    if build_status_str == "candidate":
                        build_status = BuildStatus.Candidate
                    elif build_status_str == "commissioned":
                        build_status = BuildStatus.Commissioned
                    elif build_status_str == "decommissioned":
                        build_status = BuildStatus.Decommissioned
                    elif build_status_str == "planned":
                        build_status = BuildStatus.Planned
                    elif build_status_str == "planned_decommission":
                        build_status = BuildStatus.PlannedDecommission

                elm = dev.Line(bus_from=bus_dict[entry['bus_from']],
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
                               alpha=float(entry['alpha']),
                               build_status=build_status,
                               opex=entry.get('opex', 0.0),
                               capex=entry.get('capex', 0.0)
                               )

                if build_status == BuildStatus.Candidate:
                    inv_group = dev.InvestmentsGroup(idtag='',
                                                     name=f'inv{elm.name}',
                                                     category='single')
                    invst = dev.Investment(idtag='',
                                           device_idtag=elm.idtag,
                                           name=f'inv{elm.name}',
                                           code=elm.code,
                                           CAPEX=elm.capex,
                                           OPEX=elm.opex,
                                           group=inv_group)

                    circuit.add_investments_group(inv_group)
                    circuit.add_investment(invst)

                if has_profiles:
                    profile_entry = device_profiles_dict[elm.idtag]
                    elm.active_prof = json_to_profile(profile_entry['active'])
                    elm.rate_prof = json_to_profile(profile_entry['rate'])

                circuit.add_line(elm, logger=logger)

        if "DC line" in devices.keys():

            if 'DC line' in profiles.keys():
                device_profiles_dict = {e['id']: e for e in profiles["DC line"]}
                has_profiles = True
            else:
                device_profiles_dict = dict()
                has_profiles = False

            for entry in devices["DC line"]:
                elm = dev.DcLine(bus_from=bus_dict[entry['bus_from']],
                                 bus_to=bus_dict[entry['bus_to']],
                                 name=str(entry['name']),
                                 idtag=str(entry['id']),
                                 code=str(entry['name_code']),
                                 r=float(entry['r']),
                                 rate=float(entry['rate']),
                                 active=entry['active'],
                                 length=float(entry['length']),
                                 temp_base=float(entry['base_temperature']),
                                 temp_oper=float(entry['operational_temperature']),
                                 alpha=float(entry['alpha']))

                if has_profiles:
                    profile_entry = device_profiles_dict[elm.idtag]
                    elm.active_prof = json_to_profile(profile_entry['active'])
                    elm.rate_prof = json_to_profile(profile_entry['rate'])

                circuit.add_dc_line(elm)

        if "Transformer2w" in devices.keys() or "Transformer" in devices.keys():

            if "Transformer2w" in devices.keys():
                transformers = devices["Transformer2w"]
                if 'Transformer2w' in profiles.keys():
                    device_profiles_dict = {e['id']: e for e in profiles["Transformer2w"]}
                    has_profiles = True
                else:
                    device_profiles_dict = dict()
                    has_profiles = False
            else:
                transformers = devices["Transformer"]
                if 'Transformer' in profiles.keys():
                    device_profiles_dict = {e['id']: e for e in profiles["Transformer"]}
                    has_profiles = True
                else:
                    device_profiles_dict = dict()
                    has_profiles = False

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

                elm = dev.Transformer2W(bus_from=bus_from,
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
                                        tap_module=float(entry['tap_module']),
                                        tap_phase=float(entry['tap_angle']),
                                        vset=float(entry['vset']),
                                        temp_base=float(entry['base_temperature']),
                                        temp_oper=float(entry['operational_temperature']),
                                        alpha=float(entry['alpha'])
                                        )

                if has_profiles:
                    profile_entry = device_profiles_dict[elm.idtag]
                    elm.active_prof = json_to_profile(profile_entry['active'])
                    elm.rate_prof = json_to_profile(profile_entry['rate'])

                circuit.add_transformer2w(elm)

        windings_dict = dict()
        if "Windings" in devices.keys():

            transformers = devices["Windings"]
            if 'Windings' in profiles.keys():
                device_profiles_dict = {e['id']: e for e in profiles["Windings"]}
                has_profiles = True
            else:
                device_profiles_dict = dict()
                has_profiles = False

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

                elm = dev.Winding(bus_from=bus_from,
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
                                  tap_module=float(entry['tap_module']),
                                  tap_phase=float(entry['tap_angle']),
                                  vset=float(entry['vset']),
                                  temp_base=float(entry['base_temperature']),
                                  temp_oper=float(entry['operational_temperature']),
                                  alpha=float(entry['alpha'])
                                  )

                if has_profiles:
                    profile_entry = device_profiles_dict[elm.idtag]
                    elm.active_prof = json_to_profile(profile_entry['active'])
                    elm.rate_prof = json_to_profile(profile_entry['rate'])

                circuit.add_winding(elm)
                windings_dict[elm.idtag] = elm


        if "Transformer3w" in devices.keys():

            transformers = devices["Transformer3w"]

            for entry in transformers:

                elm = dev.Transformer3W(idtag=entry['id'],
                                        code=entry['code'],
                                        name=entry['name'],
                                        bus1=bus_dict[entry['bus_1']],
                                        bus2=bus_dict[entry['bus_2']],
                                        bus3=bus_dict[entry['bus_3']])

                elm.bus0 = bus_dict[entry['bus_0']]
                elm.winding1 = windings_dict[entry['winding1']]
                elm.winding2 = windings_dict[entry['winding2']]
                elm.winding3 = windings_dict[entry['winding3']]

                circuit.add_transformer3w(elm)

        if "TransformerNw" in devices.keys():

            for tr_entry in devices["TransformerNw"]:
                for entry in tr_entry['windings']:
                    v1 = float(entry['Vnomf'])
                    v2 = float(entry['Vnomt'])

                    if v1 > v2:
                        HV = v1
                        LV = v2
                    else:
                        HV = v2
                        LV = v1

                    elm = dev.Transformer2W(bus_from=bus_dict[entry['bus_from']],
                                            bus_to=bus_dict[entry['bus_to']],
                                            name=str(tr_entry['name']),
                                            idtag=str(entry['id']),
                                            code=str(entry['name_code']),
                                            active=bool(tr_entry['active']),
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

            if 'VSC' in profiles.keys():
                device_profiles_dict = {e['id']: e for e in profiles["VSC"]}
                has_profiles = True
            else:
                device_profiles_dict = dict()
                has_profiles = False

            # json property -> gc property name
            prop = [('id', 'idtag'),
                    ('name', 'name'),
                    ('name_code', 'code'),
                    ('active', 'active'),
                    ('rate', 'rate'),
                    ('contingency_factor1', 'contingency_factor'),
                    ('r', 'R1'),
                    ('x', 'X1'),
                    ('G0sw', 'G0sw'),
                    ('m', 'm'),
                    ('m_min', 'm_min'),
                    ('m_max', 'm_max'),
                    ('theta', 'theta'),
                    ('theta_min', 'theta_min'),
                    ('theta_max', 'theta_max'),
                    ('Beq', 'Beq'),
                    ('Beq_min', 'Beq_min'),
                    ('Beq_max', 'Beq_max'),
                    ('alpha1', 'alpha1'),
                    ('alpha2', 'alpha2'),
                    ('alpha3', 'alpha3'),
                    ('k', 'k'),
                    ('kdp', 'kdp'),
                    ('Pfset', 'Pdc_set'),
                    ('Qfset', 'Qac_set'),
                    ('vac_set', 'Vac_set'),
                    ('vdc_set', 'Vdc_set'),
                    ]

            modes = {0: ConverterControlType.type_0_free,
                     1: ConverterControlType.type_I_1,
                     2: ConverterControlType.type_I_2,
                     3: ConverterControlType.type_I_3,
                     4: ConverterControlType.type_II_4,
                     5: ConverterControlType.type_II_5,
                     6: ConverterControlType.type_III_6,
                     7: ConverterControlType.type_III_7,
                     8: ConverterControlType.type_IV_I,
                     9: ConverterControlType.type_IV_II}

            for entry in devices["VSC"]:

                elm = dev.VSC()
                elm.bus_from = bus_dict[entry['bus_from']]
                elm.bus_to = bus_dict[entry['bus_to']]
                set_object_properties(elm, prop, entry)

                if "control_mode" in entry.keys():
                    elm.control_mode = modes[entry["control_mode"]]
                elif "mode" in entry.keys():
                    elm.control_mode = modes[entry["mode"]]

                if has_profiles:
                    profile_entry = device_profiles_dict[elm.idtag]
                    elm.active_prof = json_to_profile(profile_entry['active'])
                    elm.rate_prof = json_to_profile(profile_entry['rate'])

                circuit.add_vsc(elm)

        if "HVDC Line" in devices.keys():

            if 'HVDC Line' in profiles.keys():
                device_profiles_dict = {e['id']: e for e in profiles["HVDC Line"]}
                has_profiles = True
            else:
                device_profiles_dict = dict()
                has_profiles = False

            hvdc_ctrl_dict = dict()
            hvdc_ctrl_dict[HvdcControlType.type_1_Pset.value] = HvdcControlType.type_1_Pset
            hvdc_ctrl_dict[HvdcControlType.type_0_free.value] = HvdcControlType.type_0_free

            prop = [('id', 'idtag'),
                    ('name', 'name'),
                    ('name_code', 'code'),
                    ('active', 'active'),
                    ('rate', 'rate'),
                    ('Pset', 'Pset'),
                    ('vset_from', 'Vset_f'),
                    ('vset_to', 'Vset_t'),
                    ('contingency_factor1', 'contingency_factor'),
                    ('length', 'length'),
                    ('r', 'r'),
                    ('angle_droop', 'angle_droop'),
                    ('min_firing_angle_f', 'min_firing_angle_f'),
                    ('max_firing_angle_f', 'max_firing_angle_f'),
                    ('min_firing_angle_t', 'min_firing_angle_t'),
                    ('max_firing_angle_t', 'max_firing_angle_t'),
                    ('overload_cost', 'overload_cost'), ]

            for entry in devices["HVDC Line"]:

                elm = dev.HvdcLine()
                elm.bus_from = bus_dict[entry['bus_from']]
                elm.bus_to = bus_dict[entry['bus_to']]
                set_object_properties(elm, prop, entry)

                if "control_mode" in entry.keys():
                    elm.control_mode = hvdc_ctrl_dict[entry["control_mode"]]

                if has_profiles:
                    profile_entry = device_profiles_dict[elm.idtag]
                    elm.active_prof = json_to_profile(profile_entry['active'])
                    elm.rate_prof = json_to_profile(profile_entry['rate'])
                    elm.Pset_prof = json_to_profile(profile_entry['Pset'])
                    elm.Vset_f_prof = json_to_profile(profile_entry['vset_from'])
                    elm.Vset_t_prof = json_to_profile(profile_entry['vset_to'])
                    elm.overload_cost_prof = json_to_profile(profile_entry['overload_cost'])

                circuit.add_hvdc(elm)

    else:
        logger.add('The Json structure does not have a Circuit inside the devices!')
        return MultiCircuit()

    if 'contingencies' in data.keys():
        circuit.set_contingencies(
            contingencies=parse_contingencies(data['contingencies'])
        )

    # fill x, y
    logger += circuit.fill_xy_from_lat_lon()
    return circuit


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
                elm = dev.Country(idtag=str(jentry['id']),
                                  code=str(jentry['code']),
                                  name=str(jentry['name']))
                circuit.add_country(elm)
                country_dict[elm.idtag] = elm
        else:
            elm = dev.Country(idtag=None, code='Default', name='Default')
            circuit.add_country(elm)

        # Areas
        areas_dict = dict()
        if 'Area' in devices.keys():
            elms = devices["Area"]
            for jentry in elms:
                elm = dev.Area(idtag=str(jentry['id']),
                               code=str(jentry['code']),
                               name=str(jentry['name']))
                circuit.add_area(elm)
                areas_dict[elm.idtag] = elm
        else:
            elm = dev.Area(idtag=None, code='Default', name='Default')
            circuit.add_area(elm)

        # Zones
        zones_dict = dict()
        if 'Zone' in devices.keys():
            elms = devices["Zone"]
            for jentry in elms:
                elm = dev.Zone(idtag=str(jentry['id']),
                               code=str(jentry['code']),
                               name=str(jentry['name']))
                circuit.add_zone(elm)
                zones_dict[elm.idtag] = elm
        else:
            elm = dev.Zone(idtag=None, code='Default', name='Default')
            circuit.add_zone(elm)

        # Substations
        substations_dict = dict()
        if 'Substation' in devices.keys():
            elms = devices["Substation"]
            for jentry in elms:
                elm = dev.Substation(idtag=str(jentry['id']),
                                     code=str(jentry['code']),
                                     name=str(jentry['name']))
                circuit.add_substation(elm)
                substations_dict[elm.idtag] = elm
        else:
            elm = dev.Substation(idtag=None, code='Default', name='Default')
            circuit.add_substation(elm)

        # buses
        bus_dict = dict()
        if 'Bus' in devices.keys():
            buses = devices["Bus"]
            for jentry in buses:
                area_id = str(jentry['area']) if 'area' in jentry.keys() else ''
                zone_id = str(jentry['zone']) if 'zone' in jentry.keys() else ''
                substation_id = str(jentry['Substation']) if 'Substation' in jentry.keys() else ''
                country_id = str(jentry['country']) if 'country' in jentry.keys() else ''
                area = areas_dict.get(area_id, None)
                zone = zones_dict.get(zone_id, None)
                substation = substations_dict.get(substation_id, None)
                country = country_dict.get(country_id, None)

                bus = dev.Bus(name=str(jentry['name']),
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
                gen = dev.Generator(name=str(jentry['name']),
                                    idtag=str(jentry['id']),
                                    P=float(jentry['p']),
                                    power_factor=float(jentry['pf']),
                                    vset=float(jentry['vset']),
                                    is_controlled=bool(jentry['is_controlled']),
                                    Qmin=float(jentry['qmin']),
                                    Qmax=float(jentry['qmax']),
                                    Snom=float(jentry['snom']),
                                    active=bool(jentry['active']),
                                    Pmin=float(jentry['pmin']),
                                    Pmax=float(jentry['pmax']),
                                    Cost=float(jentry['cost']),
                                    )
                gen.bus = bus_dict[jentry['bus']]
                circuit.add_generator(gen.bus, gen)

        if 'Battery' in devices.keys():
            batteries = devices["Battery"]
            for jentry in batteries:
                gen = dev.Battery(name=str(jentry['name']),
                                  idtag=str(jentry['id']),
                                  P=float(jentry['p']),
                                  power_factor=float(jentry['pf']),
                                  vset=float(jentry['vset']),
                                  is_controlled=bool(jentry['is_controlled']),
                                  Qmin=float(jentry['qmin']),
                                  Qmax=float(jentry['qmax']),
                                  Snom=float(jentry['snom']),
                                  active=bool(jentry['active']),
                                  Pmin=float(jentry['pmin']),
                                  Pmax=float(jentry['pmax']),
                                  Cost=float(jentry['cost']),
                                  )
                gen.bus = bus_dict[jentry['bus']]
                circuit.add_battery(gen.bus, gen)

        if 'Load' in devices.keys():
            loads = devices["Load"]
            for jentry in loads:
                elm = dev.Load(name=str(jentry['name']),
                               idtag=str(jentry['id']),
                               P=float(jentry['p']),
                               Q=float(jentry['q']),
                               active=bool(jentry['active']))
                elm.bus = bus_dict[jentry['bus']]
                circuit.add_load(elm.bus, elm)

        if "Shunt" in devices.keys():
            shunts = devices["Shunt"]
            for jentry in shunts:
                elm = dev.Shunt(name=str(jentry['name']),
                                idtag=str(jentry['id']),
                                G=float(jentry['g']),
                                B=float(jentry['b']),
                                active=bool(jentry['active']))
                elm.bus = bus_dict[jentry['bus']]
                circuit.add_shunt(elm.bus, elm)

        if "Line" in devices.keys():
            lines = devices["Line"]
            for entry in lines:
                elm = dev.Line(bus_from=bus_dict[entry['bus_from']],
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
                circuit.add_line(elm, logger=logger)

        if "Transformer" in devices.keys() or "Transformer2w" in devices.keys():

            if "Transformer" in devices.keys():
                transformers = devices["Transformer"]
            elif "Transformer2w" in devices.keys():
                transformers = devices["Transformer2w"]
            else:
                raise Exception('Transformer key not found')

            for entry in transformers:
                elm = dev.Transformer2W(bus_from=bus_dict[entry['bus_from']],
                                        bus_to=bus_dict[entry['bus_to']],
                                        name=str(entry['name']),
                                        idtag=str(entry['id']),
                                        r=float(entry['r']),
                                        x=float(entry['x']),
                                        g=float(entry['g']),
                                        b=float(entry['b']),
                                        rate=float(entry['rate']),
                                        active=bool(entry['active']),
                                        tap_module=float(entry['tap_module']),
                                        tap_phase=float(entry['tap_angle']),
                                        )
                circuit.add_transformer2w(elm)

        if "VSC" in devices.keys():
            vsc = devices["VSC"]

            # TODO: call correct_buses_connection()

        if "HVDC Line" in devices.keys():
            hvdc = devices["HVDC Line"]

        # fill x, y
        logger += circuit.fill_xy_from_lat_lon()

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


# def save_json_file_v3_old(file_path: str, circuit: MultiCircuit, simulation_drivers: Union[None, List[Any]] = None):
#     """
#     Save JSON file
#     :param file_path: file path
#     :param circuit: GridCal MultiCircuit element
#     :param simulation_drivers: List of Simulation Drivers (optional)
#     """
#     elements = dict()
#     element_profiles = dict()
#     units_dict = dict()
#     logger = Logger()
#
#     # add the circuit
#     elements[DeviceType.CircuitDevice.value] = circuit.get_properties_dict()
#     units_dict[DeviceType.CircuitDevice.value] = circuit.get_units_dict()
#     element_profiles[DeviceType.CircuitDevice.value] = circuit.get_profiles_dict()
#
#     # idelly, these list go in dependency order
#     all_lists = [circuit.substations,
#                  circuit.zones,
#                  circuit.areas,
#                  circuit.countries,
#                  circuit.technologies,
#                  circuit.contingency_groups,
#                  circuit.contingencies,
#                  circuit.investments_groups,
#                  circuit.investments,
#                  circuit.buses,
#                  circuit.connectivity_nodes]
#     all_lists += circuit.get_injection_devices_lists()
#     all_lists += circuit.get_branch_lists()
#
#     # add the devices
#     for device_list in all_lists:
#         for elm in device_list:
#             # pack the bus data into a dictionary
#             key = elm.device_type.value
#             add_to_dict(main_dict=elements,
#                         data_to_append=elm.get_properties_dict(),
#                         key=key)
#             add_to_dict(main_dict=element_profiles,
#                         data_to_append=get_profiles_dict(elm),
#                         key=key)
#
#     # results
#     results = dict()
#     if simulation_drivers is not None:
#         for driver in simulation_drivers:
#             if driver is not None:
#
#                 if driver.name == 'Power Flow':
#
#                     bus_data = dict()
#                     for i, elm in enumerate(circuit.buses):
#                         bus_data[elm.idtag] = {'vm': np.abs(driver.results.voltage[i]),
#                                                'va': np.angle(driver.results.voltage[i])}
#
#                     branch_data = dict()
#                     for i, elm in enumerate(circuit.get_branches_wo_hvdc()):
#                         branch_data[elm.idtag] = {'p': driver.results.Sf[i].real,
#                                                   'q': driver.results.Sf[i].imag,
#                                                   'losses': driver.results.losses[i].real}
#
#                     for i, elm in enumerate(circuit.hvdc_lines):
#                         branch_data[elm.idtag] = {'p': driver.results.hvdc_Pf[i].real,
#                                                   'q': 0,
#                                                   'losses': driver.results.hvdc_losses[i].real}
#
#                     results["power_flow"] = {'bus': bus_data,
#                                              'branch': branch_data}
#
#                 elif driver.name == 'Time Series':
#
#                     bus_data = dict()
#                     for i, elm in enumerate(circuit.buses):
#                         bus_data[elm.idtag] = {'vm': np.abs(driver.results.voltage[:, i]).tolist(),
#                                                'va': np.angle(driver.results.voltage[:, i]).tolist()}
#
#                     branch_data = dict()
#                     for i, elm in enumerate(circuit.get_branches_wo_hvdc()):
#                         branch_data[elm.idtag] = {'p': driver.results.Sf[:, i].real.tolist(),
#                                                   'q': driver.results.Sf[:, i].imag.tolist(),
#                                                   'losses': driver.results.losses[:, i].real.tolist()}
#
#                     for i, elm in enumerate(circuit.hvdc_lines):
#                         branch_data[elm.idtag] = {'p': driver.results.hvdc_Pf[:, i].real,
#                                                   'q': 0,
#                                                   'losses': driver.results.hvdc_losses[:, i].real}
#
#                     results["time_series"] = {'bus': bus_data,
#                                               'branch': branch_data}
#
#     data = {'version': '3',
#             'review': '3',
#             'software': 'GridCal',
#             'units': units_dict,
#             'devices': elements,
#             'profiles': element_profiles,
#             'contingencies': get_contingencies_dict(circuit=circuit),
#             'results': results,
#             }
#
#     data_str = json.dumps(data, indent=True, cls=CustomJSONizer)
#
#     # Save json to a text file
#     text_file = open(file_path, "w")
#     text_file.write(data_str)
#     text_file.close()
#
#     return logger


def get_obj_ref(elm):
    return elm.idtag if elm is not None else ''


def save_json_file_v3(file_path: str, circuit: MultiCircuit, simulation_drivers: Union[None, List[Any]] = None):
    """
    Save JSON file
    :param file_path: file path
    :param circuit: GridCal MultiCircuit element
    :param simulation_drivers: List of Simulation Drivers (optional)
    """
    logger = Logger()
    units_dict = dict()
    elements = dict()
    element_profiles = dict()

    # add the circuit
    elements["Circuit"] = {'id': circuit.idtag,
                           'phases': 'ps',
                           'name': circuit.name,
                           'sbase': circuit.Sbase,
                           'fbase': circuit.fBase,
                           'model_version': circuit.model_version,
                           'user_name': circuit.user_name,
                           'comments': circuit.comments}
    element_profiles["Circuit"] = {'time': circuit.get_time_profile_as_list()}

    # Add area-like devices
    elements['Country'] = [{'id': elm.idtag,
                            'name': elm.name,
                            'code': elm.code} for elm in circuit.get_countries()]

    elements["Community"] = [{'id': elm.idtag,
                              'name': elm.name,
                              'code': elm.code} for elm in circuit.get_communities()]

    elements["Region"] = [{'id': elm.idtag,
                           'name': elm.name,
                           'code': elm.code} for elm in circuit.get_regions()]

    elements["Municipality"] = [{'id': elm.idtag,
                                 'name': elm.name,
                                 'code': elm.code} for elm in circuit.get_municipalities()]

    elements['Area'] = [{'id': elm.idtag,
                         'name': elm.name,
                         'code': elm.code} for elm in circuit.get_areas()]

    elements['Zone'] = [{'id': elm.idtag,
                         'name': elm.name,
                         'code': elm.code} for elm in circuit.get_zones()]

    elements['Substation'] = [{'id': elm.idtag,
                               'name': elm.name,
                               'code': elm.code,
                               'area': get_obj_ref(elm.area),
                               'zone': get_obj_ref(elm.zone),
                               'country': get_obj_ref(elm.country),
                               'community': get_obj_ref(elm.community),
                               'region': get_obj_ref(elm.region),
                               'municipality': get_obj_ref(elm.municipality),
                               'address': elm.address} for elm in circuit.get_substations()]

    elements['Voltage level'] = [{'id': elm.idtag,
                                  'name': elm.name,
                                  'code': elm.code,
                                  'v_nom': elm.Vnom,
                                  'substation': get_obj_ref(elm.substation)} for elm in
                                 circuit.get_voltage_levels()]

    # Add buses
    elements['Bus'] = [{'id': elm.idtag,
                        'type': elm.determine_bus_type().value,
                        'phases': 'ps',
                        'name': elm.name,
                        'name_code': elm.code,
                        'active': elm.active,
                        'is_slack': bool(elm.is_slack),
                        'is_internal': bool(elm.is_internal),
                        'is_dc': bool(elm.is_dc),
                        'vnom': elm.Vnom,
                        'vmin': elm.Vmin,
                        'vmax': elm.Vmax,
                        'rf': elm.r_fault,
                        'xf': elm.x_fault,
                        'x': elm.x,
                        'y': elm.y,
                        'h': elm.h,
                        'w': elm.w,
                        'lat': elm.latitude,
                        'lon': elm.longitude,
                        'alt': 0.0,
                        'country': get_obj_ref(elm.country),
                        'area': get_obj_ref(elm.area),
                        'zone': get_obj_ref(elm.zone),
                        'Substation': get_obj_ref(elm.substation),

                        } for elm in circuit.get_buses()]
    element_profiles['Bus'] = [{'id': elm.idtag,
                                'active': profile_to_json(elm.active_prof)} for elm in
                               circuit.get_buses()]

    # connectivity nodes
    elements['Connectivity Node'] = [{'id': elm.idtag,
                                      'phases': 'ps',
                                      'name': elm.name,
                                      'name_code': elm.code,
                                      'dc': elm.dc,
                                      'default_bus': get_obj_ref(elm.default_bus)} for elm in
                                     circuit.get_connectivity_nodes()]

    # bus bars
    elements["BusBar"] = [{'id': elm.idtag,
                           'name': elm.name,
                           'code': elm.code,
                           'voltage_level': get_obj_ref(elm.voltage_level),
                           'cn': get_obj_ref(elm.cn)} for elm in circuit.get_bus_bars()]

    # load
    elements['Load'] = [{'id': elm.idtag,
                         'type': 'load',
                         'phases': 'ps',
                         'name': elm.name,
                         'name_code': elm.code,
                         'bus': get_obj_ref(elm.bus),
                         'cn': get_obj_ref(elm.cn),
                         'active': bool(elm.active),
                         'g': elm.G,
                         'b': elm.B,
                         'ir': elm.Ir,
                         'ii': elm.Ii,
                         'p': elm.P,
                         'q': elm.Q,
                         'shedding_cost': elm.Cost
                         } for elm in circuit.get_loads()]
    element_profiles['Load'] = [{'id': elm.idtag,
                                 'active': profile_to_json(elm.active_prof),
                                 'p': profile_to_json(elm.P_prof),
                                 'q': profile_to_json(elm.Q_prof),
                                 'ir': profile_to_json(elm.Ir_prof),
                                 'ii': profile_to_json(elm.Ii_prof),
                                 'g': profile_to_json(elm.G_prof),
                                 'b': profile_to_json(elm.B_prof)} for elm in circuit.get_loads()]

    # static generator
    elements['Static Generator'] = [{'id': elm.idtag,
                                     'type': 'load',
                                     'phases': 'ps',
                                     'name': elm.name,
                                     'name_code': elm.code,
                                     'bus': get_obj_ref(elm.bus),
                                     'cn': get_obj_ref(elm.cn),
                                     'active': bool(elm.active),
                                     'p': elm.P,
                                     'q': elm.Q,
                                     'shedding_cost': elm.Cost
                                     } for elm in circuit.get_static_generators()]
    element_profiles['Static Generator'] = [{'id': elm.idtag,
                                             'active': profile_to_json(elm.active_prof),
                                             'p': profile_to_json(elm.P_prof),
                                             'q': profile_to_json(elm.Q_prof)} for elm in
                                            circuit.get_static_generators()]

    # controllable shunt
    elements['Controllable shunt'] = [{'id': elm.idtag,
                                       'type': 'load',
                                       'phases': 'ps',
                                       'name': elm.name,
                                       'name_code': elm.code,
                                       'bus': get_obj_ref(elm.bus),
                                       'cn': get_obj_ref(elm.cn),
                                       'active': bool(elm.active),
                                       'g_steps': elm.g_steps.tolist(),
                                       'b_steps': elm.b_steps.tolist(),
                                       'step': elm.step,
                                       'shedding_cost': elm.Cost
                                       } for elm in circuit.get_controllable_shunts()]
    element_profiles['Controllable shunt'] = [{'id': elm.idtag,
                                               'active': profile_to_json(elm.active_prof),
                                               'step': profile_to_json(elm.steps_prof), } for elm in
                                              circuit.get_controllable_shunts()]

    # current injection
    elements['Current injection'] = [{'id': elm.idtag,
                                      'type': 'load',
                                      'phases': 'ps',
                                      'name': elm.name,
                                      'name_code': elm.code,
                                      'bus': get_obj_ref(elm.bus),
                                      'cn': get_obj_ref(elm.cn),
                                      'active': bool(elm.active),
                                      'ir': elm.Ir,
                                      'ii': elm.Ii,
                                      'shedding_cost': elm.Cost
                                      } for elm in circuit.get_loads()]
    element_profiles['Current injection'] = [{'id': elm.idtag,
                                              'active': profile_to_json(elm.active_prof),
                                              'ir': profile_to_json(elm.Ir_prof),
                                              'ii': profile_to_json(elm.Ii_prof)} for elm in
                                             circuit.get_loads()]

    # External grid
    elements["External grid"] = [{'id': elm.idtag,
                                  'type': 'external_grid',
                                  'phases': 'ps',
                                  'name': elm.name,
                                  'name_code': elm.code,
                                  'bus': get_obj_ref(elm.bus),
                                  'cn': get_obj_ref(elm.cn),
                                  'active': bool(elm.active),
                                  'Vm': elm.Vm,
                                  'Va': elm.Va,
                                  'P': elm.P,
                                  'Q': elm.Q,
                                  'Cost': elm.Cost
                                  } for elm in circuit.get_external_grids()]
    element_profiles["External grid"] = [{'id': elm.idtag,
                                          'active': profile_to_json(elm.active_prof),
                                          'Vm_prof': profile_to_json(elm.Vm_prof),
                                          'Va_prof': profile_to_json(elm.Va_prof),
                                          'P_prof': profile_to_json(elm.P_prof),
                                          'Q_prof': profile_to_json(elm.Q_prof),
                                          'Cost_prof': profile_to_json(elm.Cost_prof)
                                          } for elm in
                                         circuit.get_external_grids()]

    # generators
    elements['Generator'] = [{'id': elm.idtag,
                              'type': 'generator',
                              'phases': 'ps',
                              'name': elm.name,
                              'name_code': elm.code,
                              'bus': get_obj_ref(elm.bus),
                              'cn': get_obj_ref(elm.cn),
                              'active': elm.active,
                              'is_controlled': elm.is_controlled,
                              'p': elm.P,
                              'pf': elm.Pf,
                              'vset': elm.Vset,
                              'snom': elm.Snom,
                              'qmin': elm.Qmin,
                              'qmax': elm.Qmax,
                              'q_curve': elm.q_curve.str(),

                              'pmin': elm.Pmin,
                              'pmax': elm.Pmax,
                              'cost2': elm.Cost2,
                              'cost1': elm.Cost,
                              'cost0': elm.Cost0,

                              'startup_cost': elm.StartupCost,
                              'shutdown_cost': elm.ShutdownCost,
                              'min_time_up': elm.MinTimeUp,
                              'min_time_down': elm.MinTimeDown,
                              'ramp_up': elm.RampUp,
                              'ramp_down': elm.RampDown,

                              'capex': elm.capex,
                              'opex': elm.opex,
                              'build_status': str(elm.build_status.value).lower(),
                              'technology': "",
                              } for elm in circuit.get_generators()]
    element_profiles['Generator'] = [{'id': elm.idtag,
                                      'active': profile_to_json(elm.active_prof),
                                      'p': profile_to_json(elm.P_prof),
                                      'v': profile_to_json(elm.Vset_prof),
                                      'pf': profile_to_json(elm.Pf_prof)} for elm in
                                     circuit.get_generators()]

    # batteries
    elements['Battery'] = [{'id': elm.idtag,
                            'type': 'battery',
                            'phases': 'ps',
                            'name': elm.name,
                            'name_code': elm.code,
                            'bus': get_obj_ref(elm.bus),
                            'cn': get_obj_ref(elm.cn),
                            'active': elm.active,
                            'is_controlled': elm.is_controlled,
                            'p': elm.P,
                            'vset': elm.Vset,
                            'pf': elm.Pf,
                            'snom': elm.Snom,
                            'enom': elm.Enom,
                            'qmin': elm.Qmin,
                            'qmax': elm.Qmax,
                            'pmin': elm.Pmin,
                            'pmax': elm.Pmax,
                            'cost': elm.Cost,

                            'cost2': elm.Cost2,
                            'cost1': elm.Cost,
                            'cost0': elm.Cost0,

                            'startup_cost': elm.StartupCost,
                            'shutdown_cost': elm.ShutdownCost,
                            'min_time_up': elm.MinTimeUp,
                            'min_time_down': elm.MinTimeDown,
                            'ramp_up': elm.RampUp,
                            'ramp_down': elm.RampDown,

                            'capex': elm.capex,
                            'opex': elm.opex,
                            'build_status': str(elm.build_status.value).lower(),
                            'charge_efficiency': elm.charge_efficiency,
                            'discharge_efficiency': elm.discharge_efficiency,
                            'min_soc': elm.min_soc,
                            'max_soc': elm.max_soc,
                            'soc_0': elm.soc_0,
                            'min_soc_charge': elm.min_soc_charge,
                            'charge_per_cycle': elm.charge_per_cycle,
                            'discharge_per_cycle': elm.discharge_per_cycle,
                            'technology': ""
                            } for elm in circuit.get_batteries()]
    element_profiles['Battery'] = [{'id': elm.idtag,
                                    'active': profile_to_json(elm.active_prof),
                                    'p': profile_to_json(elm.P_prof),
                                    'v': profile_to_json(elm.Vset_prof),
                                    'pf': profile_to_json(elm.Pf_prof)} for elm in
                                   circuit.get_batteries()]

    # shunt
    elements["Shunt"] = [{'id': elm.idtag,
                          'type': 'load',
                          'phases': 'ps',
                          'name': elm.name,
                          'name_code': elm.code,
                          'bus': get_obj_ref(elm.bus),
                          'cn': get_obj_ref(elm.cn),
                          'active': bool(elm.active),
                          'g': elm.G,
                          'b': elm.B,
                          'g0': elm.G0,
                          'b0': elm.B0,
                          'capex': elm.capex,
                          'opex': elm.opex,
                          'build_status': str(elm.build_status.value).lower(),
                          } for elm in circuit.get_shunts()]
    element_profiles["Shunt"] = [{'id': elm.idtag,
                                  'active': profile_to_json(elm.active_prof),
                                  'g': profile_to_json(elm.G_prof),
                                  'b': profile_to_json(elm.B_prof)} for elm in
                                 circuit.get_shunts()]

    # Line
    elements["Line"] = [{'id': elm.idtag,
                         'type': 'line',
                         'phases': 'ps',
                         'name': elm.name,
                         'name_code': elm.code,
                         'bus_from': get_obj_ref(elm.bus_from),
                         'bus_to': get_obj_ref(elm.bus_to),
                         'cn_from': get_obj_ref(elm.cn_from),
                         'cn_to': get_obj_ref(elm.cn_to),
                         'active': elm.active,

                         'rate': elm.rate,
                         'contingency_factor1': elm.contingency_factor,
                         'contingency_factor2': elm.contingency_factor,
                         'contingency_factor3': elm.contingency_factor,
                         'r': elm.R,
                         'x': elm.X,
                         'b': elm.B,

                         'length': elm.length,
                         'base_temperature': elm.temp_base,
                         'operational_temperature': elm.temp_oper,
                         'alpha': elm.alpha,

                         'overload_cost': elm.Cost,
                         'capex': elm.capex,
                         'opex': elm.opex,
                         'build_status': str(elm.build_status.value).lower(),

                         'locations': []
                         } for elm in circuit.get_lines()]
    element_profiles["Line"] = [{'id': elm.idtag,
                                 'active': profile_to_json(elm.active_prof),
                                 'rate': profile_to_json(elm.rate_prof),
                                 'contingency_factor1': profile_to_json(
                                     elm.contingency_factor_prof)} for elm in
                                circuit.get_lines()]

    # DC Line
    elements["DC line"] = [{'id': elm.idtag,
                            'type': 'line',
                            'phases': 'ps',
                            'name': elm.name,
                            'name_code': elm.code,
                            'bus_from': get_obj_ref(elm.bus_from),
                            'bus_to': get_obj_ref(elm.bus_to),
                            'cn_from': get_obj_ref(elm.cn_from),
                            'cn_to': get_obj_ref(elm.cn_to),
                            'active': elm.active,

                            'rate': elm.rate,
                            'contingency_factor1': elm.contingency_factor,
                            'contingency_factor2': elm.contingency_factor,
                            'contingency_factor3': elm.contingency_factor,
                            'r': elm.R,

                            'length': elm.length,
                            'base_temperature': elm.temp_base,
                            'operational_temperature': elm.temp_oper,
                            'alpha': elm.alpha,

                            'overload_cost': elm.Cost,
                            'capex': elm.capex,
                            'opex': elm.opex,
                            'build_status': str(elm.build_status.value).lower(),

                            'locations': []
                            } for elm in circuit.get_dc_lines()]
    element_profiles["DC line"] = [{'id': elm.idtag,
                                    'active': profile_to_json(elm.active_prof),
                                    'rate': profile_to_json(elm.rate_prof),
                                    'contingency_factor1': profile_to_json(
                                        elm.contingency_factor_prof)} for elm in
                                   circuit.get_dc_lines()]

    # Transformer 2W
    control_modes = {TransformerControlType.fixed: 0,
                     TransformerControlType.V: 1,
                     TransformerControlType.Pf: 2,
                     TransformerControlType.PtV: 3,
                     TransformerControlType.Qt: 4,
                     TransformerControlType.PtQt: 5}
    elements["Transformer2w"] = [{'id': elm.idtag,
                                  'type': 'transformer',
                                  'phases': 'ps',
                                  'name': elm.name,
                                  'name_code': elm.code,
                                  'bus_from': get_obj_ref(elm.bus_from),
                                  'bus_to': get_obj_ref(elm.bus_to),
                                  'cn_from': get_obj_ref(elm.cn_from),
                                  'cn_to': get_obj_ref(elm.cn_to),
                                  'active': elm.active,
                                  'rate': elm.rate,
                                  'contingency_factor1': elm.contingency_factor,
                                  'contingency_factor2': elm.contingency_factor,
                                  'contingency_factor3': elm.contingency_factor,

                                  'Vnomf': elm.get_from_to_nominal_voltages()[0],
                                  'Vnomt': elm.get_from_to_nominal_voltages()[1],
                                  'hv': elm.HV,
                                  'lv': elm.LV,
                                  'r': elm.R,
                                  'x': elm.X,
                                  'g': elm.G,
                                  'b': elm.B,
                                  'tap_module': elm.tap_module,
                                  'min_tap_module': elm.tap_module_min,
                                  'max_tap_module': elm.tap_module_max,
                                  'id_tap_module_table': "",

                                  'tap_angle': elm.tap_phase,
                                  'min_tap_angle': elm.tap_phase_min,
                                  'max_tap_angle': elm.tap_phase_max,
                                  'id_tap_angle_table': "",

                                  'control_mode': control_modes[elm.control_mode],

                                  # 'min_tap_position': self.tap_changer.min_tap,
                                  # 'max_tap_position': self.tap_changer.max_tap,
                                  # 'tap_inc_reg_down': self.tap_changer.inc_reg_down,
                                  # 'tap_inc_reg_up': self.tap_changer.inc_reg_up,
                                  # 'virtual_tap_from': tap_f,
                                  # 'virtual_tap_to': tap_t,
                                  # 'bus_to_regulated': self.bus_to_regulated,

                                  'vset': elm.vset,
                                  'pset': elm.Pset,

                                  'base_temperature': elm.temp_base,
                                  'operational_temperature': elm.temp_oper,
                                  'alpha': elm.alpha,

                                  'overload_cost': elm.Cost,
                                  'capex': elm.capex,
                                  'opex': elm.opex,
                                  'build_status': str(elm.build_status.value).lower(),
                                  } for elm in circuit.get_transformers2w()]
    element_profiles["Transformer2w"] = [{'id': elm.idtag,
                                          'active': profile_to_json(elm.active_prof),
                                          'rate': profile_to_json(elm.rate_prof),
                                          'contingency_factor1': profile_to_json(
                                              elm.contingency_factor_prof)} for elm in
                                         circuit.get_transformers2w()]

    # Windings
    elements["Windings"] = [{'id': elm.idtag,
                             'type': 'transformer',
                             'phases': 'ps',
                             'name': elm.name,
                             'name_code': elm.code,
                             'bus_from': get_obj_ref(elm.bus_from),
                             'bus_to': get_obj_ref(elm.bus_to),
                             'cn_from': get_obj_ref(elm.cn_from),
                             'cn_to': get_obj_ref(elm.cn_to),
                             'active': elm.active,
                             'rate': elm.rate,
                             'contingency_factor1': elm.contingency_factor,
                             'contingency_factor2': elm.contingency_factor,
                             'contingency_factor3': elm.contingency_factor,

                             'Vnomf': elm.get_from_to_nominal_voltages()[0],
                             'Vnomt': elm.get_from_to_nominal_voltages()[1],
                             'hv': elm.HV,
                             'lv': elm.LV,
                             'r': elm.R,
                             'x': elm.X,
                             'g': elm.G,
                             'b': elm.B,
                             'tap_module': elm.tap_module,
                             'min_tap_module': elm.tap_module_min,
                             'max_tap_module': elm.tap_module_max,
                             'id_tap_module_table': "",

                             'tap_angle': elm.tap_phase,
                             'min_tap_angle': elm.tap_phase_min,
                             'max_tap_angle': elm.tap_phase_max,
                             'id_tap_angle_table': "",

                             'control_mode': control_modes[elm.control_mode],

                             # 'min_tap_position': self.tap_changer.min_tap,
                             # 'max_tap_position': self.tap_changer.max_tap,
                             # 'tap_inc_reg_down': self.tap_changer.inc_reg_down,
                             # 'tap_inc_reg_up': self.tap_changer.inc_reg_up,
                             # 'virtual_tap_from': tap_f,
                             # 'virtual_tap_to': tap_t,
                             # 'bus_to_regulated': self.bus_to_regulated,

                             'vset': elm.vset,
                             'pset': elm.Pset,

                             'base_temperature': elm.temp_base,
                             'operational_temperature': elm.temp_oper,
                             'alpha': elm.alpha,

                             'overload_cost': elm.Cost,
                             'capex': elm.capex,
                             'opex': elm.opex,
                             'build_status': str(elm.build_status.value).lower(),
                             } for elm in circuit.get_windings()]
    element_profiles["Windings"] = [{'id': elm.idtag,
                                     'active': profile_to_json(elm.active_prof),
                                     'rate': profile_to_json(elm.rate_prof),
                                     'contingency_factor1': profile_to_json(
                                         elm.contingency_factor_prof)} for elm in
                                    circuit.get_windings()]

    # Transformer3w
    elements["Transformer3w"] = [{'id': elm.idtag,
                                  'type': 'transformer',
                                  'phases': 'ps',
                                  'name': elm.name,
                                  'name_code': elm.code,
                                  'bus_0': get_obj_ref(elm.bus0),
                                  'bus_1': get_obj_ref(elm.bus1),
                                  'bus_2': get_obj_ref(elm.bus2),
                                  'bus_3': get_obj_ref(elm.bus3),
                                  'active': elm.active,
                                  'winding1': get_obj_ref(elm.winding1),
                                  'winding2': get_obj_ref(elm.winding2),
                                  'winding3': get_obj_ref(elm.winding3),
                                  } for elm in circuit.get_transformers3w()]

    # Series reactances
    elements["Series reactance"] = [{'id': elm.idtag,
                                     'type': 'series_reactance',
                                     'phases': 'ps',
                                     'name': elm.name,
                                     'name_code': elm.code,
                                     'bus_from': get_obj_ref(elm.bus_from),
                                     'bus_to': get_obj_ref(elm.bus_to),
                                     'cn_from': get_obj_ref(elm.cn_from),
                                     'cn_to': get_obj_ref(elm.cn_to),
                                     'active': elm.active,

                                     'rate': elm.rate,
                                     'contingency_factor1': elm.contingency_factor,
                                     'contingency_factor2': elm.contingency_factor,
                                     'contingency_factor3': elm.contingency_factor,
                                     'r': elm.R,
                                     'x': elm.X,

                                     'base_temperature': elm.temp_base,
                                     'operational_temperature': elm.temp_oper,
                                     'alpha': elm.alpha,

                                     'overload_cost': elm.Cost,
                                     'capex': elm.capex,
                                     'opex': elm.opex,
                                     'build_status': str(elm.build_status.value).lower(),

                                     } for elm in circuit.get_series_reactances()]
    element_profiles["Series reactance"] = [{'id': elm.idtag,
                                             'active': profile_to_json(elm.active_prof),
                                             'rate': profile_to_json(elm.rate_prof),
                                             'contingency_factor1': profile_to_json(
                                                 elm.contingency_factor_prof)} for elm in
                                            circuit.get_series_reactances()]

    # UPFC
    elements["UPFC"] = [{'id': elm.idtag,
                         'type': 'upfc',
                         'phases': 'ps',
                         'name': elm.name,
                         'name_code': elm.code,
                         'bus_from': get_obj_ref(elm.bus_from),
                         'bus_to': get_obj_ref(elm.bus_to),
                         'cn_from': get_obj_ref(elm.cn_from),
                         'cn_to': get_obj_ref(elm.cn_to),
                         'active': elm.active,
                         'rate': elm.rate,
                         'contingency_factor1': elm.contingency_factor,
                         'contingency_factor2': elm.contingency_factor,
                         'contingency_factor3': elm.contingency_factor,
                         'rl': 0.0,
                         'xl': 0.0,
                         'bl': 0.0,
                         'rs': elm.Rs,
                         'xs': elm.Xs,
                         'rsh': elm.Rsh,
                         'xsh': elm.Xsh,
                         'vsh': elm.Vsh,
                         'Pfset': elm.Pfset,
                         'Qfset': elm.Qfset,

                         'overload_cost': elm.Cost,
                         'capex': elm.capex,
                         'opex': elm.opex,
                         'build_status': str(elm.build_status.value).lower(),
                         } for elm in circuit.get_upfc()]
    element_profiles["UPFC"] = [{'id': elm.idtag,
                                 'active': profile_to_json(elm.active_prof),
                                 'rate': profile_to_json(elm.rate_prof),
                                 'contingency_factor1': profile_to_json(
                                     elm.contingency_factor_prof)} for elm in
                                circuit.get_upfc()]

    # VSC
    modes = {ConverterControlType.type_0_free: 0,
             ConverterControlType.type_I_1: 1,
             ConverterControlType.type_I_2: 2,
             ConverterControlType.type_I_3: 3,
             ConverterControlType.type_II_4: 4,
             ConverterControlType.type_II_5: 5,
             ConverterControlType.type_III_6: 6,
             ConverterControlType.type_III_7: 7,
             ConverterControlType.type_IV_I: 8,
             ConverterControlType.type_IV_II: 9}
    elements["VSC"] = [{'id': elm.idtag,
                        'type': 'vsc',
                        'phases': 'ps',
                        'name': elm.name,
                        'name_code': elm.code,
                        'bus_from': get_obj_ref(elm.bus_from),
                        'bus_to': get_obj_ref(elm.bus_to),
                        'cn_from': get_obj_ref(elm.cn_from),
                        'cn_to': get_obj_ref(elm.cn_to),
                        'active': elm.active,

                        'rate': elm.rate,
                        'contingency_factor1': elm.contingency_factor,
                        'contingency_factor2': elm.contingency_factor,
                        'contingency_factor3': elm.contingency_factor,

                        'r': elm.R,
                        'x': elm.X,
                        'g': elm.G0sw,

                        'm': elm.tap_module,
                        'm_min': elm.tap_module_min,
                        'm_max': elm.tap_module_max,

                        'theta': elm.tap_phase,
                        'theta_min': elm.tap_phase_min,
                        'theta_max': elm.tap_phase_max,

                        'Beq': elm.Beq,
                        'Beq_min': elm.Beq_min,
                        'Beq_max': elm.Beq_max,

                        'alpha1': elm.alpha1,
                        'alpha2': elm.alpha2,
                        'alpha3': elm.alpha3,

                        'k': elm.k,
                        'kdp': elm.kdp,
                        'Pfset': elm.Pdc_set,
                        'Qfset': elm.Qac_set,
                        'vac_set': elm.Vac_set,
                        'vdc_set': elm.Vdc_set,

                        'control_mode': modes[elm.control_mode],

                        'overload_cost': elm.Cost,
                        'capex': elm.capex,
                        'opex': elm.opex,
                        'build_status': str(elm.build_status.value).lower(),
                        } for elm in circuit.get_vsc()]
    element_profiles["VSC"] = [{'id': elm.idtag,
                                'active': profile_to_json(elm.active_prof),
                                'rate': profile_to_json(elm.rate_prof),
                                'contingency_factor1': profile_to_json(
                                    elm.contingency_factor_prof)} for elm in
                               circuit.get_vsc()]

    # HVDC
    elements["HVDC Line"] = [{'id': elm.idtag,
                              'type': 'hvdc',
                              'phases': 'ps',
                              'name': elm.name,
                              'name_code': elm.code,
                              'bus_from': get_obj_ref(elm.bus_from),
                              'bus_to': get_obj_ref(elm.bus_to),
                              'cn_from': get_obj_ref(elm.cn_from),
                              'cn_to': get_obj_ref(elm.cn_to),
                              'active': elm.active,
                              'rate': elm.rate,
                              'control_mode': elm.control_mode.value,
                              'contingency_factor1': elm.contingency_factor,
                              'contingency_factor2': elm.contingency_factor,
                              'contingency_factor3': elm.contingency_factor,
                              'r': elm.r,
                              'length': elm.length,
                              'loss_factor': elm.loss_factor,
                              'angle_droop': elm.angle_droop,
                              'vset_from': elm.Vset_f,
                              'vset_to': elm.Vset_t,
                              'Pset': elm.Pset,
                              'min_firing_angle_f': elm.min_firing_angle_f,
                              'max_firing_angle_f': elm.max_firing_angle_f,
                              'min_firing_angle_t': elm.min_firing_angle_t,
                              'max_firing_angle_t': elm.max_firing_angle_t,
                              'overload_cost': elm.Cost,
                              'base_temperature': 20,
                              'operational_temperature': 20,
                              'alpha': 0.00330,
                              'capex': elm.capex,
                              'opex': elm.opex,
                              'build_status': str(elm.build_status.value).lower(),
                              'locations': []
                              } for elm in circuit.get_hvdc()]
    element_profiles["HVDC Line"] = [{'id': elm.idtag,
                                      'active': profile_to_json(elm.active_prof),
                                      'rate': profile_to_json(elm.rate_prof),
                                      'contingency_factor1': profile_to_json(
                                          elm.contingency_factor_prof),
                                      'Pset': profile_to_json(elm.Pset_prof),
                                      'vset_from': profile_to_json(elm.Vset_f_prof),
                                      'vset_to': profile_to_json(elm.Vset_t_prof),
                                      'overload_cost': profile_to_json(elm.Cost_prof)} for elm in
                                     circuit.get_hvdc()]

    # results
    results = dict()
    if simulation_drivers is not None:
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

                    results["time_series"] = {'bus': bus_data, 'branch': branch_data}

    data = {'version': '3',
            'review': '4',
            'software': 'GridCal',
            'units': units_dict,
            'devices': elements,
            'profiles': element_profiles,
            'contingencies': get_contingencies_dict(circuit=circuit),
            'results': results,
            }

    data_str = json.dumps(data, indent=True, cls=CustomJSONizer)

    # Save json to a text file
    text_file = open(file_path, "w")
    text_file.write(data_str)
    text_file.close()

    return logger
