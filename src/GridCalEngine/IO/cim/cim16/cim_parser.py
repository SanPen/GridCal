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
from math import sqrt
from typing import Dict
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.gridcal.zip_interface import get_xml_from_zip, get_xml_content
from GridCalEngine.Devices.multi_circuit import MultiCircuit
import GridCalEngine.Devices as gcdev
import GridCalEngine.IO.cim.cim16.cim_devices as cimdev
from GridCalEngine.IO.cim.cim16.cim_circuit import CIMCircuit
from GridCalEngine.data_logger import DataLogger


def read_cim_files(cim_files):
    """
    Reads a list of .zip or xml into a dictionary of file name -> list of text lines
    :param cim_files: list of file names
    :return: dictionary of file name -> list of text lines
    """
    # read files and sort them in the preferred reading order
    data = dict()

    if isinstance(cim_files, list):

        for f in cim_files:
            _, file_extension = os.path.splitext(f)
            name = os.path.basename(f)

            if file_extension == '.xml':
                file_ptr = open(f, 'rb')
                data[name] = get_xml_content(file_ptr)
                file_ptr.close()
            elif file_extension == '.zip':
                # read the content of a zip file
                d = get_xml_from_zip(file_name_zip=f)
                for key, value in d.items():
                    data[key] = value
    else:
        name, file_extension = os.path.splitext(cim_files)

        if file_extension == '.xml':
            file_ptr = open(cim_files, 'rb')
            data[name] = get_xml_content(file_ptr)
            file_ptr.close()

        elif file_extension == '.zip':
            # read the content of a zip file
            d = get_xml_from_zip(file_name_zip=cim_files)
            for key, value in d.items():
                data[key] = value

    return data


def sort_cim_files(file_names):
    """
    Sorts the CIM files in the preferred reading order
    :param file_names: lis of file names
    :return: sorted list of file names
    """
    # sort the files
    lst = list()
    nn = len(file_names)
    for i in range(nn - 1, -1, -1):
        f = file_names[i]
        if 'TP' in f or 'TPDB' in f:
            lst.append(file_names.pop(i))

    nn = len(file_names)
    for i in range(nn - 1, -1, -1):
        f = file_names[i]
        if 'EQ' in f or 'EQBD' in f:
            lst.append(file_names.pop(i))

    lst2 = lst + file_names

    return lst2


def get_elements(d: Dict, keys):
    elm = list()

    for k in keys:
        try:
            lst = d[k]
            elm += lst
        except KeyError:
            pass

    return elm


def any_in_dict(d: Dict, keys):
    found = False

    for k in keys:
        try:
            lst = d[k]
            found = True
        except KeyError:
            pass

    return found


def try_buses(b1, b2, bus_duct):
    try:
        B1 = bus_duct[b1]
    except KeyError:
        B1 = None

    try:
        B2 = bus_duct[b2]
    except KeyError:
        B2 = None

    return B1, B2


def try_bus(b1, bus_duct):
    try:
        B1 = bus_duct[b1]
    except KeyError:
        B1 = None

    return B1


class CIMExport:

    def __init__(self, circuit: MultiCircuit):

        self.circuit = circuit

        self.logger = Logger()

    def save(self, file_name):
        """
        Save XML CIM version of a grid
        Args:
            file_name: file path
        """

        # open CIM file for writing
        text_file = open(file_name, "w")

        # header
        text_file.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        text_file.write('<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
                        'xmlns:cim="http://iec.ch/TC57/2009/CIM-schema-cim14#">\n')

        # Model
        model = cimdev.IdentifiedObject(rdfid=self.circuit.idtag, tpe='Model')
        model.parsed_properties['name'] = self.circuit.name
        model.parsed_properties['version'] = 1
        model.parsed_properties['description'] = self.circuit.comments
        text_file.write(model.get_xml(1))

        bus_id_dict = dict()
        base_voltages = set()
        base_voltages_dict = dict()

        # dictionary of Substation given a bus
        substation_bus = dict()

        # buses sweep to gather previous data (base voltages, etc..)
        for i, bus in enumerate(self.circuit.buses):

            Vnom = bus.Vnom

            # add the nominal voltage to the set of bus_voltages
            base_voltages.add(Vnom)

            # if the Substation was not accounted for, create the list of voltage levels
            if bus.substation not in substation_bus.keys():
                substation_bus[bus.substation] = dict()

            if Vnom not in substation_bus[bus.substation].keys():
                substation_bus[bus.substation][Vnom] = list()

            # add bus to the categorization
            substation_bus[bus.substation][Vnom].append(bus)

        # generate Base voltages
        for V in base_voltages:
            conn_node_id = 'Base_voltage_' + str(V).replace('.', '_')

            base_voltages_dict[V] = conn_node_id

            model = cimdev.IdentifiedObject(rdfid=conn_node_id, tpe='BaseVoltage')
            model.parsed_properties['name'] = conn_node_id
            model.parsed_properties['nominalVoltage'] = V
            text_file.write(model.get_xml(1))

        # generate voltage levels, substations and buses and their objects
        substation_idx = 0
        voltage_level_idx = 0
        bus_idx = 0
        terminal_resources = ['TopologicalNode', 'ConductingEquipment']

        bus_to_voltage_level_dict = dict()

        for substation in substation_bus.keys():

            substation_id = substation.idtag
            substation_idx += 1

            model = cimdev.IdentifiedObject(rdfid=substation_id, tpe='Substation',
                                            resources=['Location', 'SubGeographicalRegion'])
            model.parsed_properties['name'] = substation
            model.parsed_properties['aliasName'] = substation
            model.parsed_properties['PSRType'] = ''
            model.parsed_properties['Location'] = ''
            model.parsed_properties['SubGeographicalRegion'] = ''
            text_file.write(model.get_xml(1))

            for voltage_level in substation_bus[substation].keys():

                voltage_level_id = 'VoltageLevel_' + str(voltage_level).replace('.', '_') + '_' + str(voltage_level_idx)
                voltage_level_idx += 1

                base_voltage = base_voltages_dict[voltage_level]

                model = cimdev.IdentifiedObject(rdfid=voltage_level_id,
                                                tpe='VoltageLevel',
                                                resources=['BaseVoltage', 'Substation'])
                model.parsed_properties['name'] = substation
                model.parsed_properties['aliasName'] = substation
                model.parsed_properties['BaseVoltage'] = base_voltage
                model.parsed_properties['Substation'] = substation_id
                text_file.write(model.get_xml(1))

                # buses sweep to actually generate XML
                for bus in substation_bus[substation][voltage_level]:

                    # make id
                    conn_node_id = 'BUS_' + str(bus_idx)

                    Vnom = bus.Vnom

                    # make dictionary entry
                    bus_id_dict[bus] = conn_node_id

                    base_voltage = base_voltages_dict[Vnom]

                    bus_to_voltage_level_dict[bus] = (voltage_level_id, base_voltage)

                    if bus.Vnom <= 0.0:
                        self.logger.add_error('Zero nominal voltage', bus.name)

                    # generate model
                    model = cimdev.IdentifiedObject(rdfid=conn_node_id, tpe='ConnectivityNode',
                                                    resources=['BaseVoltage',
                                                               'VoltageLevel',
                                                               'ConnectivityNodeContainer'],
                                                    class_replacements={'name': 'IdentifiedObject',
                                                                        'aliasName': 'IdentifiedObject'}
                                                    )
                    model.parsed_properties['name'] = bus.name
                    model.parsed_properties['aliasName'] = bus.name
                    model.parsed_properties['BaseVoltage'] = base_voltage
                    # model.parsed_properties['VoltageLevel'] = voltage_level_id
                    model.parsed_properties['ConnectivityNodeContainer'] = voltage_level_id
                    text_file.write(model.get_xml(1))

                    if bus.is_slack:
                        equivalent_network_id = conn_node_id + '_EqNetwork'

                        model = cimdev.IdentifiedObject(rdfid=equivalent_network_id, tpe='EquivalentNetwork',
                                                        resources=['BaseVoltage', 'VoltageLevel'],
                                                        class_replacements={'name': 'IdentifiedObject',
                                                                            'aliasName': 'IdentifiedObject'})
                        model.parsed_properties['name'] = bus.name + '_Slack'
                        model.parsed_properties['aliasName'] = bus.name + '_Slack'
                        model.parsed_properties['BaseVoltage'] = base_voltage
                        model.parsed_properties['VoltageLevel'] = voltage_level_id
                        text_file.write(model.get_xml(1))

                        # Terminal 1 (from)
                        model = cimdev.IdentifiedObject(rdfid=equivalent_network_id + '_T', tpe='Terminal',
                                                        resources=terminal_resources,
                                                        class_replacements={'name': 'IdentifiedObject',
                                                                            'aliasName': 'IdentifiedObject'}
                                                        )
                        model.parsed_properties['name'] = equivalent_network_id + '_T'
                        model.parsed_properties['TopologicalNode'] = bus_id_dict[bus]
                        model.parsed_properties['ConductingEquipment'] = equivalent_network_id
                        model.parsed_properties['connected'] = 'true'
                        model.parsed_properties['sequenceNumber'] = '1'
                        text_file.write(model.get_xml(1))

                    # increment the bus index
                    bus_idx += 1

        for il, elm in enumerate(self.circuit.loads):
            id2 = elm.idtag + '_LOAD_' + str(il)
            id3 = id2 + '_LRC'

            model = cimdev.IdentifiedObject(rdfid=id2, tpe='ConformLoad',
                                            resources=['BaseVoltage',
                                                       'LoadResponse',
                                                       'VoltageLevel'],
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject',
                                                                'EquipmentContainer': 'Equipment'})

            voltage_level_id, base_voltage = bus_to_voltage_level_dict.get(elm.bus, ("", 0))

            model.parsed_properties['name'] = elm.name
            model.parsed_properties['aliasName'] = elm.name
            model.parsed_properties['BaseVoltage'] = base_voltage
            model.parsed_properties['EquipmentContainer'] = voltage_level_id
            model.parsed_properties['LoadResponse'] = id3
            model.parsed_properties['pfixed'] = elm.P
            model.parsed_properties['qfixed'] = elm.Q
            model.parsed_properties['normallyInService'] = elm.active
            text_file.write(model.get_xml(1))

            model = cimdev.IdentifiedObject(rdfid=id3, tpe='LoadResponseCharacteristic', resources=[])
            model.parsed_properties['name'] = elm.name
            model.parsed_properties['exponentModel'] = 'false'
            model.parsed_properties['pConstantCurrent'] = elm.Ir
            model.parsed_properties['pConstantImpedance'] = 1 / (elm.G + 1e-20)
            model.parsed_properties['pConstantPower'] = elm.P
            model.parsed_properties['pVoltageExponent'] = 0.0
            model.parsed_properties['pFrequencyExponent'] = 0.0
            model.parsed_properties['qConstantCurrent'] = elm.Ir
            model.parsed_properties['qConstantImpedance'] = 1 / (elm.B + 1e-20)
            model.parsed_properties['qConstantPower'] = elm.Q
            model.parsed_properties['qVoltageExponent'] = 0.0
            model.parsed_properties['qFrequencyExponent'] = 0.0
            text_file.write(model.get_xml(1))

            # Terminal 1 (from)
            model = cimdev.IdentifiedObject(rdfid=id2 + '_T', tpe='Terminal',
                                            resources=terminal_resources,
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject'})
            model.parsed_properties['name'] = elm.name
            model.parsed_properties['TopologicalNode'] = bus_id_dict[elm.bus]
            model.parsed_properties['ConductingEquipment'] = id2
            model.parsed_properties['connected'] = 'true'
            model.parsed_properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

        for il, elm in enumerate(self.circuit.static_generators):
            id2 = elm.idtag + '_StatGen_' + str(il)

            model = cimdev.IdentifiedObject(rdfid=id2, tpe='ConformLoad',
                                            resources=['BaseVoltage', 'LoadResponse', 'VoltageLevel'],
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject',
                                                                'EquipmentContainer': 'Equipment'}
                                            )

            voltage_level_id, base_voltage = bus_to_voltage_level_dict.get(elm.bus, ("", 0))

            model.parsed_properties['name'] = elm.name
            model.parsed_properties['aliasName'] = elm.name
            model.parsed_properties['BaseVoltage'] = base_voltage
            model.parsed_properties['EquipmentContainer'] = voltage_level_id
            model.parsed_properties['pfixed'] = -elm.P
            model.parsed_properties['qfixed'] = -elm.Q
            model.parsed_properties['normallyInService'] = elm.active
            text_file.write(model.get_xml(1))

            # Terminal 1 (from)
            model = cimdev.IdentifiedObject(rdfid=id2 + '_T', tpe='Terminal',
                                            resources=terminal_resources,
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject'}
                                            )
            model.parsed_properties['name'] = elm.name
            model.parsed_properties['TopologicalNode'] = bus_id_dict[elm.bus]
            model.parsed_properties['ConductingEquipment'] = id2
            model.parsed_properties['connected'] = 'true'
            model.parsed_properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

        for il, elm in enumerate(self.circuit.generators):
            id2 = elm.idtag + '_SyncGen_' + str(il)
            id3 = id2 + '_GU'
            id4 = id2 + '_RC'

            model = cimdev.IdentifiedObject(rdfid=id2, tpe='SynchronousMachine',
                                            resources=['BaseVoltage', 'RegulatingControl',
                                                       'GeneratingUnit', 'VoltageLevel'],
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject',
                                                                'EquipmentContainer': 'Equipment'}
                                            )

            voltage_level_id, base_voltage = bus_to_voltage_level_dict.get(elm.bus, ("", 0))

            model.parsed_properties['name'] = elm.name
            model.parsed_properties['aliasName'] = elm.name
            model.parsed_properties['BaseVoltage'] = base_voltage
            model.parsed_properties['EquipmentContainer'] = voltage_level_id
            model.parsed_properties['RegulatingControl'] = id3
            model.parsed_properties['GeneratingUnit'] = id4
            model.parsed_properties['maxQ'] = elm.Qmax
            model.parsed_properties['minQ'] = elm.Qmin
            model.parsed_properties['ratedS'] = elm.Snom
            model.parsed_properties['normallyInService'] = elm.active
            text_file.write(model.get_xml(1))

            model = cimdev.IdentifiedObject(rdfid=id3, tpe='RegulatingControl', resources=[])
            model.parsed_properties['name'] = elm.name
            model.parsed_properties['targetValue'] = elm.Vset * elm.bus.Vnom
            text_file.write(model.get_xml(1))

            model = cimdev.IdentifiedObject(rdfid=id4, tpe='GeneratingUnit', resources=[])
            model.parsed_properties['name'] = elm.name
            model.parsed_properties['initialP'] = elm.P
            text_file.write(model.get_xml(1))

            # Terminal 1 (from)
            model = cimdev.IdentifiedObject(rdfid=id2 + '_T', tpe='Terminal',
                                            resources=terminal_resources,
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject'}
                                            )
            model.parsed_properties['name'] = elm.name
            model.parsed_properties['TopologicalNode'] = bus_id_dict[elm.bus]
            model.parsed_properties['ConductingEquipment'] = id2
            model.parsed_properties['connected'] = 'true'
            model.parsed_properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

        for il, elm in enumerate(self.circuit.shunts):
            id2 = elm.idtag + '_Shunt_' + str(il)

            model = cimdev.IdentifiedObject(rdfid=id2, tpe='ShuntCompensator',
                                            resources=['BaseVoltage', 'VoltageLevel'],
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject',
                                                                'EquipmentContainer': 'Equipment'}
                                            )

            voltage_level_id, base_voltage = bus_to_voltage_level_dict.get(elm.bus, ("", 0))

            model.parsed_properties['name'] = elm.name
            model.parsed_properties['aliasName'] = elm.name
            model.parsed_properties['BaseVoltage'] = base_voltage
            model.parsed_properties['EquipmentContainer'] = voltage_level_id
            model.parsed_properties['gPerSection'] = elm.G
            model.parsed_properties['bPerSection'] = elm.B
            model.parsed_properties['g0PerSection'] = 0.0
            model.parsed_properties['b0PerSection'] = 0.0
            model.parsed_properties['normallyInService'] = elm.active
            text_file.write(model.get_xml(1))

            # Terminal 1 (from)
            model = cimdev.IdentifiedObject(rdfid=id2 + '_T', tpe='Terminal',
                                            resources=terminal_resources,
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject'}
                                            )
            model.parsed_properties['name'] = elm.name
            model.parsed_properties['TopologicalNode'] = bus_id_dict[elm.bus]
            model.parsed_properties['ConductingEquipment'] = id2
            model.parsed_properties['connected'] = 'true'
            model.parsed_properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

        # Branches
        winding_resources = ['connectionType', 'windingType', 'PowerTransformer']
        tap_changer_resources = ['TransformerWinding']
        for i, branch in enumerate(self.circuit.transformers2w):

            model = cimdev.IdentifiedObject(rdfid=branch.idtag, tpe='PowerTransformer',
                                            resources=[],
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject',
                                                                'EquipmentContainer': 'Equipment'}
                                            )
            model.parsed_properties['name'] = branch.name
            model.parsed_properties['aliasName'] = branch.name
            text_file.write(model.get_xml(1))

            #  warnings
            if branch.rate <= 0.0:
                self.logger.add_error('The rate is 0', branch.name)
                raise Exception(branch.name + ": The rate is 0, this will cause a problem when loading.")

            if branch.bus_from.Vnom <= 0.0:
                self.logger.add_error('Vfrom is zero', branch.name)
                raise Exception(branch.name + ": The voltage at the from side, this will cause a problem when loading.")

            if branch.bus_to.Vnom <= 0.0:
                self.logger.add_error('Vto is zero', branch.name)
                raise Exception(branch.name + ": The voltage at the to side, this will cause a problem when loading.")

            # W1 (from)
            winding_power_rate = branch.rate / 2
            z_base = (branch.bus_from.Vnom ** 2) / winding_power_rate
            y_base = 1 / z_base
            model = cimdev.IdentifiedObject(rdfid=branch.idtag + "_W1", tpe='PowerTransformerEnd',
                                            resources=winding_resources,
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject',
                                                                'BaseVoltage': 'ConductingEquipment'}
                                            )
            model.parsed_properties['name'] = branch.name
            model.parsed_properties['PowerTransformer'] = branch.idtag
            model.parsed_properties['BaseVoltage'] = base_voltages_dict[branch.bus_from.Vnom]
            model.parsed_properties['r'] = branch.R / 2 * z_base
            model.parsed_properties['x'] = branch.X / 2 * z_base
            model.parsed_properties['g'] = branch.G / 2 * y_base
            model.parsed_properties['b'] = branch.B / 2 * y_base
            model.parsed_properties['r0'] = 0.0
            model.parsed_properties['x0'] = 0.0
            model.parsed_properties['g0'] = 0.0
            model.parsed_properties['b0'] = 0.0
            model.parsed_properties['ratedS'] = winding_power_rate
            model.parsed_properties['ratedU'] = branch.bus_from.Vnom
            model.parsed_properties['rground'] = 0.0
            model.parsed_properties['xground'] = 0.0
            model.parsed_properties['connectionType'] = "http://iec.ch/TC57/2009/CIM-schema-cim14#WindingConnection.Y"
            model.parsed_properties['windingType'] = "http://iec.ch/TC57/2009/CIM-schema-cim14#WindingType.primary"
            text_file.write(model.get_xml(1))

            # W2 (To)
            z_base = (branch.bus_to.Vnom ** 2) / winding_power_rate
            y_base = 1 / z_base
            model = cimdev.IdentifiedObject(rdfid=branch.idtag + "_W2", tpe='PowerTransformerEnd',
                                            resources=winding_resources,
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject',
                                                                'BaseVoltage': 'ConductingEquipment'})
            model.parsed_properties['name'] = branch.name
            model.parsed_properties['PowerTransformer'] = branch.idtag
            model.parsed_properties['BaseVoltage'] = base_voltages_dict[branch.bus_to.Vnom]
            model.parsed_properties['r'] = branch.R / 2 * z_base
            model.parsed_properties['x'] = branch.X / 2 * z_base
            model.parsed_properties['g'] = branch.G / 2 * y_base
            model.parsed_properties['b'] = branch.B / 2 * y_base
            model.parsed_properties['r0'] = 0.0
            model.parsed_properties['x0'] = 0.0
            model.parsed_properties['g0'] = 0.0
            model.parsed_properties['b0'] = 0.0
            model.parsed_properties['ratedS'] = winding_power_rate
            model.parsed_properties['ratedU'] = branch.bus_to.Vnom
            model.parsed_properties['rground'] = 0.0
            model.parsed_properties['xground'] = 0.0
            model.parsed_properties['connectionType'] = "http://iec.ch/TC57/2009/CIM-schema-cim14#WindingConnection.Y"
            model.parsed_properties['windingType'] = "http://iec.ch/TC57/2009/CIM-schema-cim14#WindingType.secondary"
            text_file.write(model.get_xml(1))

            # add tap changer at the "to" winding
            if branch.tap_module != 1.0 and branch.tap_phase != 0.0:
                Vnom = branch.bus_to.Vnom
                SVI = (Vnom - Vnom * branch.tap_module) * 100.0 / Vnom

                model = cimdev.IdentifiedObject(rdfid=branch.idtag + 'Tap_2', tpe='RatioTapChanger',
                                                resources=tap_changer_resources)
                model.parsed_properties['TransformerWinding'] = branch.idtag + "_W2"
                model.parsed_properties['name'] = branch.name + 'tap changer'
                model.parsed_properties['neutralU'] = Vnom
                model.parsed_properties['stepVoltageIncrement'] = SVI
                model.parsed_properties['step'] = 0
                model.parsed_properties['lowStep'] = -1
                model.parsed_properties['highStep'] = 1
                model.parsed_properties['subsequentDelay'] = branch.tap_phase
                text_file.write(model.get_xml(1))

            # Terminal 1 (from)
            model = cimdev.IdentifiedObject(rdfid=branch.idtag + '_T1', tpe='Terminal',
                                            resources=terminal_resources,
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject'}
                                            )
            model.parsed_properties['name'] = branch.name + '_T1'
            model.parsed_properties['TopologicalNode'] = bus_id_dict[branch.bus_from]
            model.parsed_properties['ConductingEquipment'] = branch.idtag
            model.parsed_properties['connected'] = 'true'
            model.parsed_properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

            # Terminal 2 (to)
            model = cimdev.IdentifiedObject(rdfid=branch.idtag + '_T2', tpe='Terminal',
                                            resources=terminal_resources,
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject'}
                                            )
            model.parsed_properties['name'] = branch.name + '_T2'
            model.parsed_properties['TopologicalNode'] = bus_id_dict[branch.bus_to]
            model.parsed_properties['ConductingEquipment'] = branch.idtag
            model.parsed_properties['connected'] = 'true'
            model.parsed_properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

        for i, branch in enumerate(self.circuit.lines):

            if branch.branch_type == gcdev.BranchType.Line or branch.branch_type == gcdev.BranchType.Branch:

                z_base = (branch.bus_from.Vnom ** 2) / self.circuit.Sbase

                if branch.bus_from.Vnom <= 0.0:
                    y_base = 0
                else:
                    y_base = 1 / z_base

                model = cimdev.IdentifiedObject(rdfid=branch.idtag, tpe='ACLineSegment',
                                                resources=['BaseVoltage'],
                                                class_replacements={'name': 'IdentifiedObject',
                                                                    'aliasName': 'IdentifiedObject',
                                                                    'BaseVoltage': 'ConductingEquipment',
                                                                    'value': 'CurrentLimit'}
                                                )
                model.parsed_properties['name'] = branch.name
                model.parsed_properties['aliasName'] = branch.name
                model.parsed_properties['BaseVoltage'] = base_voltages_dict[branch.bus_from.Vnom]
                model.parsed_properties['r'] = branch.R * z_base
                model.parsed_properties['x'] = branch.X * z_base
                model.parsed_properties['gch'] = 0
                model.parsed_properties['bch'] = branch.B * y_base
                model.parsed_properties['r0'] = 0.0
                model.parsed_properties['x0'] = 0.0
                model.parsed_properties['g0ch'] = 0.0
                model.parsed_properties['b0ch'] = 0.0
                model.parsed_properties['length'] = 1.0
                model.parsed_properties['value'] = branch.rate / (branch.bus_from.Vnom * sqrt(3))  # kA
                text_file.write(model.get_xml(1))

            elif branch.branch_type == gcdev.BranchType.Switch:

                model = cimdev.IdentifiedObject(rdfid=branch.idtag, tpe='Switch', resources=['BaseVoltage'])
                model.parsed_properties['name'] = branch.name
                model.parsed_properties['aliasName'] = branch.name
                model.parsed_properties['BaseVoltage'] = base_voltages_dict[branch.bus_from.Vnom]
                model.parsed_properties['normalOpen'] = False
                model.parsed_properties['open'] = not branch.active
                text_file.write(model.get_xml(1))

            elif branch.branch_type == gcdev.BranchType.Reactance:
                self.logger.add_warning('Reactance CIM export not implemented yet, exported as a branch', branch.name)

                conn_node_id = 'Reactance_' + str(i)
                z_base = (branch.bus_from.Vnom ** 2) / self.circuit.Sbase

                if branch.bus_from.Vnom <= 0.0:
                    y_base = 0
                else:
                    y_base = 1 / z_base

                model = cimdev.IdentifiedObject(rdfid=branch.idtag, tpe='ACLineSegment', resources=['BaseVoltage'])
                model.parsed_properties['name'] = branch.name
                model.parsed_properties['aliasName'] = branch.name
                model.parsed_properties['BaseVoltage'] = base_voltages_dict[branch.bus_from.Vnom]
                model.parsed_properties['r'] = branch.R * z_base
                model.parsed_properties['x'] = branch.X * z_base
                model.parsed_properties['gch'] = branch.G * y_base
                model.parsed_properties['bch'] = branch.B * y_base
                model.parsed_properties['r0'] = 0.0
                model.parsed_properties['x0'] = 0.0
                model.parsed_properties['g0ch'] = 0.0
                model.parsed_properties['b0ch'] = 0.0
                model.parsed_properties['length'] = 1.0
                text_file.write(model.get_xml(1))

            # Terminal 1 (from)
            model = cimdev.IdentifiedObject(rdfid=branch.idtag + '_T1', tpe='Terminal',
                                            resources=terminal_resources,
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject'}
                                            )
            model.parsed_properties['name'] = bus.name + '_' + branch.name + '_T1'
            model.parsed_properties['TopologicalNode'] = bus_id_dict[branch.bus_from]
            model.parsed_properties['ConductingEquipment'] = branch.idtag
            model.parsed_properties['connected'] = 'true'
            model.parsed_properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

            # Terminal 2 (to)
            model = cimdev.IdentifiedObject(rdfid=branch.idtag + '_T2', tpe='Terminal',
                                            resources=terminal_resources,
                                            class_replacements={'name': 'IdentifiedObject',
                                                                'aliasName': 'IdentifiedObject'}
                                            )
            model.parsed_properties['name'] = bus.name + '_' + branch.name + '_T2'
            model.parsed_properties['TopologicalNode'] = bus_id_dict[branch.bus_to]
            model.parsed_properties['ConductingEquipment'] = branch.idtag
            model.parsed_properties['connected'] = 'true'
            model.parsed_properties['sequenceNumber'] = '1'
            text_file.write(model.get_xml(1))

        # end
        text_file.write("</rdf:RDF>")

        text_file.close()


class CIMImport:

    def __init__(self, text_func=None, progress_func=None):

        self.logger = Logger()

        self.cim = CIMCircuit(logger=self.logger)

        # relations between connectivity nodes and terminals
        # node_terminal[some_node] = list of terminals
        self.node_terminal = dict()
        self.terminal_node = dict()

        self.text_func = text_func
        self.progress_func = progress_func

        self.needs_compiling = True

        self.topology = None

    def emit_text(self, val):
        if self.text_func is not None:
            self.text_func(val)

    def emit_progress(self, val):
        if self.progress_func is not None:
            self.progress_func(val)

    @staticmethod
    def parse_model(cim: CIMCircuit, circuit: MultiCircuit):
        """

        :param cim:
        :param circuit:
        :return:
        """
        if 'Model' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['Model']:
                if 'description' in elm.parsed_properties.keys():
                    circuit.comments = elm.parsed_properties['description']

                if 'name' in elm.parsed_properties.keys():
                    circuit.name = elm.parsed_properties['name']

    def parse_bus_bars(self, cim: CIMCircuit, circuit: MultiCircuit):
        """

        :param cim:
        :param circuit:
        :return:
        """

        busbar_dict = dict()

        if 'BusbarSection' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['BusbarSection']:
                obj = gcdev.Bus(name=str(elm.name),
                                idtag=elm.uuid)

                circuit.add_bus(obj)

                busbar_dict[elm] = obj
        else:
            self.logger.add_error("No BusbarSections: There is no chance to reduce the grid")

        return busbar_dict

    def parse_ac_line_segment(self, cim: CIMCircuit, circuit: MultiCircuit, busbar_dict):
        """

        :param cim:
        :param circuit:
        :param busbar_dict:
        :return:
        """

        if 'ACLineSegment' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['ACLineSegment']:

                b1, b2 = elm.get_buses()

                B1, B2 = try_buses(b1, b2, busbar_dict)

                if B1 is not None and B2 is not None:
                    R, X, G, B = elm.get_pu_values()
                    rate = elm.get_rate()

                    # create AcLineSegment (Line)
                    line = gcdev.Line(idtag=elm.uuid,
                                      bus_from=B1,
                                      bus_to=B2,
                                      name=str(elm.name),
                                      r=R,
                                      x=X,
                                      b=B,
                                      rate=rate,
                                      active=True,
                                      mttf=0,
                                      mttr=0)

                    circuit.add_line(line)
                else:
                    self.logger.add_error('Bus not found', elm.rdfid)

    def parse_power_transformer(self, cim: CIMCircuit, circuit: MultiCircuit, busbar_dict, logger: DataLogger):
        """

        :param cim:
        :param circuit:
        :param busbar_dict:
        :return:
        """
        if 'PowerTransformer' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['PowerTransformer']:
                b1, b2 = elm.get_buses()
                B1, B2 = try_buses(b1, b2, busbar_dict)

                if B1 is not None and B2 is not None:
                    R, X, G, B = elm.get_pu_values()
                    rate = elm.get_rate()

                    voltages = elm.get_voltages(logger=logger)
                    voltages.sort()

                    if len(voltages) == 2:
                        lv, hv = voltages
                    else:
                        lv = 1
                        hv = 1
                        self.logger.add_error('Could not parse transformer nominal voltages', elm.name)

                    line = gcdev.Transformer2W(idtag=cimdev.rfid2uuid(elm.rdfid),
                                               bus_from=B1,
                                               bus_to=B2,
                                               name=str(elm.name),
                                               r=R,
                                               x=X,
                                               g=G,
                                               b=B,
                                               rate=rate,
                                               tap_module=1.0,
                                               tap_phase=0,
                                               active=True,
                                               HV=hv,
                                               LV=lv)

                    circuit.add_transformer2w(line)
                else:
                    self.logger.add_error('Bus not found', elm.rdfid)

    def parse_switches(self, cim: CIMCircuit, circuit: MultiCircuit, busbar_dict):
        """

        :param cim:
        :param circuit:
        :param busbar_dict:
        :return:
        """
        EPS = 1e-20
        cim_switches = ['Switch', 'Disconnector', 'Breaker', 'LoadBreakSwitch']
        if any_in_dict(cim.elements_by_type, cim_switches):
            for elm in get_elements(cim.elements_by_type, cim_switches):
                b1, b2 = elm.get_buses()
                B1, B2 = try_buses(b1, b2, busbar_dict)

                if B1 is not None and B2 is not None:
                    state = True
                    line = gcdev.Switch(idtag=elm.uuid,
                                        bus_from=B1,
                                        bus_to=B2,
                                        name=str(elm.name),
                                        r=EPS,
                                        x=EPS,
                                        rate=EPS,
                                        active=state)

                    circuit.add_switch(line)
                else:
                    self.logger.add_error('Bus not found', elm.rdfid)

    def parse_loads(self, cim: CIMCircuit, circuit: MultiCircuit, busbar_dict):
        """

        :param cim:
        :param circuit:
        :param busbar_dict:
        :return:
        """
        cim_loads = ['ConformLoad', 'EnergyConsumer', 'NonConformLoad']
        if any_in_dict(cim.elements_by_type, cim_loads):
            for elm in get_elements(cim.elements_by_type, cim_loads):

                b1 = elm.get_bus()
                B1 = try_bus(b1, busbar_dict)

                if B1 is not None:

                    p, q = elm.get_pq()

                    load = gcdev.Load(idtag=elm.uuid,
                                      name=str(elm.name),
                                      G=0,
                                      B=0,
                                      Ir=0,
                                      Ii=0,
                                      P=p if p is not None else 0,
                                      Q=q if q is not None else 0)
                    circuit.add_load(B1, load)
                else:
                    self.logger.add_error('Bus not found', elm.rdfid)

    def parse_shunts(self, cim: CIMCircuit, circuit: MultiCircuit, busbar_dict):
        """

        :param cim:
        :param circuit:
        :param busbar_dict:
        :return:
        """
        if 'ShuntCompensator' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['ShuntCompensator']:
                b1 = elm.get_bus()
                B1 = try_bus(b1, busbar_dict)

                if B1 is not None:
                    g = 0
                    b = 0
                    sh = gcdev.Shunt(idtag=elm.uuid,
                                     name=str(elm.name),
                                     G=g,
                                     B=b)
                    circuit.add_shunt(B1, sh)
                else:
                    self.logger.add_error('Bus not found', elm.rdfid)

    def parse_generators(self, cim: CIMCircuit, circuit: MultiCircuit, busbar_dict):
        """

        :param cim:
        :param circuit:
        :param busbar_dict:
        :return:
        """
        if 'SynchronousMachine' in cim.elements_by_type.keys():
            for elm in cim.elements_by_type['SynchronousMachine']:
                b1 = elm.get_bus()
                B1 = try_bus(b1, busbar_dict)

                if B1 is not None:

                    gen = gcdev.Generator(idtag=elm.uuid,
                                          name=str(elm.name),
                                          P=-elm.p,
                                          # CGMES defines the generator P as negative to indicate a positive injection
                                          vset=1.0)
                    circuit.add_generator(B1, gen)

                else:
                    self.logger.add_error('Bus not found', elm.rdfid)

    def load_cim_file(self, cim_files):
        """
        Load CIM file
        :param cim_files: list of CIM files (.xml)
        """

        # declare GridCal circuit
        circuit = MultiCircuit()
        EPS = 1e-16

        # declare CIM circuit to process the file(s)
        self.cim = CIMCircuit(text_func=self.text_func, progress_func=self.progress_func, logger=self.logger)

        # import the cim files' content into a dictionary
        data = read_cim_files(cim_files)

        lst2 = sort_cim_files(list(data.keys()))
        # Parse the files
        for f in lst2:
            name, file_extension = os.path.splitext(f)
            self.emit_text('Parsing xml structure of ' + name)
            self.cim.parse_xml_text(text_lines=data[f])

        # replace CIM references in the CIM objects
        self.emit_text('Looking for CIM references...')
        self.cim.find_references()

        # Parse devices into GridCal
        self.emit_text('Converting CIM to GridCal...')
        self.parse_model(self.cim, circuit)
        busbar_dict = self.parse_bus_bars(self.cim, circuit)
        self.parse_ac_line_segment(self.cim, circuit, busbar_dict)
        self.parse_ac_line_segment(self.cim, circuit, busbar_dict)
        self.parse_power_transformer(self.cim, circuit, busbar_dict, logger=self.logger)
        self.parse_switches(self.cim, circuit, busbar_dict)
        self.parse_loads(self.cim, circuit, busbar_dict)
        self.parse_shunts(self.cim, circuit, busbar_dict)
        self.parse_generators(self.cim, circuit, busbar_dict)

        self.emit_text('Done!')
        return circuit
