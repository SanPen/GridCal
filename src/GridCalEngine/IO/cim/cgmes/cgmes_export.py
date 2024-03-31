# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
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

from rdflib import OWL
from rdflib.graph import Graph
from rdflib.namespace import RDF, RDFS

import json
import os
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
import xml.etree.ElementTree as Et
import xml.dom.minidom


class CimExporter:
    def __init__(self, cgmes_circuit: CgmesCircuit):
        self.cgmes_circuit = cgmes_circuit
        self.namespaces = {
            "xmlns:cim": "http://iec.ch/TC57/2013/CIM-schema-cim16#",
            "xmlns:md": "http://iec.ch/TC57/61970-552/ModelDescription/1#",
            "xmlns:entsoe": "http://entsoe.eu/CIM/SchemaExtension/3/1#",
            "xmlns:rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        }
        self.profile_uris = {
            "EQ": ["http://entsoe.eu/CIM/EquipmentCore/3/1",
                   "http://entsoe.eu/CIM/EquipmentShortCircuit/3/1",
                   "http://entsoe.eu/CIM/EquipmentOperation/3/1"],
            "SSH": ["http://entsoe.eu/CIM/SteadyStateHypothesis/1/1"],
            "TP": ["http://entsoe.eu/CIM/Topology/4/1"],
            "SV": ["http://entsoe.eu/CIM/StateVariables/4/1"]
        }

        current_directory = os.path.dirname(__file__)

        rdf_serialization = Graph()
        rdf_serialization.parse(source=os.path.join(current_directory, "export_docs\RDFSSerialisation.ttl"),
                                format="ttl")

        self.enum_dict = dict()
        self.about_dict = dict()
        for s_i, p_i, o_i in rdf_serialization.triples((None, RDF.type, RDFS.Class)):
            if str(s_i).split("#")[1] == "RdfEnum":
                enum_list_dict = dict()
                for s, p, o in rdf_serialization.triples((s_i, OWL.members, None)):
                    enum_list_dict[str(o).split("#")[-1]] = str(o)
                if str(s_i).split("#")[0] == "http://entsoe.eu/CIM/EquipmentCore/3/1":
                    self.enum_dict["EQ"] = enum_list_dict
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/StateVariables/4/1":
                    self.enum_dict["SV"] = enum_list_dict
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/SteadyStateHypothesis/1/1":
                    self.enum_dict["SSH"] = enum_list_dict
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/Topology/4/1":
                    self.enum_dict["TP"] = enum_list_dict
            if str(s_i).split("#")[1] == "RdfAbout":
                about_list = list()
                for s, p, o in rdf_serialization.triples((s_i, OWL.members, None)):
                    about_list.append(str(o).split("#")[-1])
                if str(s_i).split("#")[0] == "http://entsoe.eu/CIM/EquipmentCore/3/1":
                    self.about_dict["EQ"] = about_list
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/StateVariables/4/1":
                    self.about_dict["SV"] = about_list
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/SteadyStateHypothesis/1/1":
                    self.about_dict["SSH"] = about_list
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/Topology/4/1":
                    self.about_dict["TP"] = about_list

        self.class_filters = {}
        with open(os.path.join(current_directory, "export_docs/rdfs_info_CGMES2415.json"), "r") as json_file:
            json_dict = json.load(json_file)
        for class_name in self.cgmes_circuit.classes:
            self.class_filters[class_name] = {}
        for i, prop_name in enumerate(json_dict['Property-AttributeAssociation']):
            if json_dict["Class Name"][i] in self.cgmes_circuit.classes:
                p_key = str(prop_name).split('.')[-1]
                if p_key not in self.class_filters[json_dict["Class Name"][i]]:
                    temp_dict = {
                        "Profile": json_dict['ProfileKeyword'][i].strip('[]').split(','),
                        "ClassFullName": json_dict["Class"][i],
                        "Property-AttributeAssociationFull": json_dict["Property-AttributeAssociation"][i],
                        "Type": json_dict["Type"][i]
                    }
                    self.class_filters[json_dict["Class Name"][i]][p_key] = temp_dict
                else:
                    new_prof = json_dict['ProfileKeyword'][i].strip('[]').split(',')
                    self.class_filters[json_dict["Class Name"][i]][p_key]["Profile"].extend(new_prof)

    def export(self):
        current_directory = os.path.dirname(__file__)
        with open(os.path.join(current_directory, "export_docs/eq.xml"), 'wb') as f:
            self.serialize(f, "EQ")
        with open(os.path.join(current_directory, "export_docs/ssh.xml"), 'wb') as f:
            self.serialize(f, "SSH")
        with open(os.path.join(current_directory, "export_docs/sv.xml"), 'wb') as f:
            self.serialize(f, "SV")
        with open(os.path.join(current_directory, "export_docs/tp.xml"), 'wb') as f:
            self.serialize(f, "TP")

    def serialize(self, stream, profile):
        root = Et.Element("rdf:RDF", self.namespaces)
        full_model_elements = self.generate_full_model_elements(profile)
        root.extend(full_model_elements)
        other_elements = self.generate_other_elements(profile)
        root.extend(other_elements)

        xmlstr = xml.dom.minidom.parseString(Et.tostring(root)).toprettyxml(indent="   ")
        stream.write(xmlstr.encode('utf-8'))

    def is_in_profile(self, instance_profiles, model_profile):
        if isinstance(instance_profiles, list):
            for profile in instance_profiles:
                if profile in self.profile_uris[model_profile]:
                    return True
        else:
            if instance_profiles in self.profile_uris[model_profile]:
                return True
        return False

    def generate_full_model_elements(self, profile):
        full_model_elements = []
        filter_props = {"scenarioTime": "str",
                        "created": "str",
                        "version": "str",
                        "profile": "str",
                        "modelingAuthoritySet": "str",
                        "DependentOn": "Association",
                        "longDependentOnPF": "str",
                        "Supersedes": "str",
                        "description": "str"}

        for instance in self.cgmes_circuit.FullModel_list:
            instance_dict = instance.parsed_properties
            if self.is_in_profile(instance_profiles=instance_dict.get("profile"), model_profile=profile):
                element = Et.Element("md:FullModel", {"rdf:about": "urn:uuid:" + instance.rdfid})
                for attr_name, attr_value in instance_dict.items():
                    if attr_name not in filter_props or attr_value is None:
                        continue
                    child = Et.Element(f"md:Model.{attr_name}")
                    if filter_props.get(attr_name) == "Association":
                        if isinstance(attr_value, list):
                            for v in attr_value:
                                child = Et.Element(f"md:Model.{attr_name}")
                                child.attrib = {"rdf:resource": "urn:uuid:" + v}
                                element.append(child)
                            continue
                        else:
                            child.attrib = {"rdf:resource": "urn:uuid:" + attr_value}
                    else:
                        if isinstance(attr_value, list):
                            for v in attr_value:
                                child = Et.Element(f"md:Model.{attr_name}")
                                child.text = str(v)
                                element.append(child)
                            continue
                        else:
                            child.text = str(attr_value)
                    element.append(child)
                full_model_elements.append(element)
        return full_model_elements

    @staticmethod
    def in_profile(filters, profile):
        for k, v in filters.items():
            if profile in v["Profile"]:
                return True
        return False

    def generate_other_elements(self, profile):
        other_elements = []
        for class_name, filters in self.class_filters.items():
            objects = self.cgmes_circuit.get_objects_list(elm_type=class_name)
            if not self.in_profile(filters, profile):
                continue
            for obj in objects:
                obj_dict = obj.__dict__
                if self.about_dict.get(profile) is not None and class_name in self.about_dict.get(profile):
                    element = Et.Element("cim:" + class_name, {"rdf:about": "_" + obj.rdfid})
                else:
                    element = Et.Element("cim:" + class_name, {"rdf:ID": "_" + obj.rdfid})

                for attr_name, attr_value in obj_dict.items():
                    if attr_value is None:
                        continue
                    if attr_name not in filters:
                        continue
                    attr_filters = filters[attr_name]
                    if profile not in attr_filters["Profile"]:
                        continue
                    attr_type = attr_filters["Type"]
                    prop_split = str(attr_filters["Property-AttributeAssociationFull"]).split('#')
                    if prop_split[0] == "http://entsoe.eu/CIM/SchemaExtension/3/1":
                        prop_text = "entsoe:" + prop_split[-1]
                    else:
                        prop_text = "cim:" + prop_split[-1]
                    child = Et.Element(prop_text)
                    if attr_type == "Association":
                        if isinstance(attr_value, list):
                            for v in attr_value:
                                child = Et.Element(prop_text)
                                child.attrib = {"rdf:resource": "#_" + v.rdfid}
                                element.append(child)
                            continue
                        else:
                            child.attrib = {"rdf:resource": "#_" + attr_value.rdfid}
                    elif attr_type == "Enumeration":
                        enum_dict_key = profile
                        enum_dict_value = self.enum_dict.get(enum_dict_key)
                        enum_value = enum_dict_value.get(str(attr_value))
                        child.attrib = {"rdf:resource": enum_value}
                    elif attr_type == "Attribute":
                        if isinstance(attr_value, bool):
                            attr_value = str(attr_value).lower()
                        if isinstance(attr_value, list):
                            for v in attr_value:
                                child = Et.Element(prop_text)
                                child.text = str(v)
                                element.append(child)
                            continue
                        else:
                            child.text = str(attr_value)
                    element.append(child)
                other_elements.append(element)
        return other_elements
