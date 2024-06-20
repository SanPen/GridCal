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

import zipfile
from io import BytesIO
from rdflib import OWL
from rdflib.graph import Graph
from rdflib.namespace import RDF, RDFS
from typing import List

import json
import os
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from GridCalEngine.IO.cim.cgmes.rdfs_serializations import RDFS_serialization_2_4_15, RDFS_serialization_3_0_0
from GridCalEngine.IO.cim.cgmes.rdfs_infos import RDFS_INFO_2_4_15, RDFS_INFO_3_0_0
from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile
from GridCalEngine.enumerations import CGMESVersions
import xml.etree.ElementTree as Et
import xml.dom.minidom


class CimExporter:
    def __init__(self, cgmes_circuit: CgmesCircuit, profiles_to_export: List[cgmesProfile], one_file_per_profile: bool):
        self.cgmes_circuit = cgmes_circuit

        self.profiles_to_export = profiles_to_export
        self.one_file_per_profile = one_file_per_profile
        self.export_OP = False
        self.export_SC = False

        current_directory = os.path.dirname(__file__)

        rdf_serialization = Graph()

        if cgmes_circuit.cgmes_version == CGMESVersions.v2_4_15:
            rdf_serialization.parse(data=RDFS_serialization_2_4_15, format="ttl")

            if cgmesProfile.OP in profiles_to_export:
                self.export_OP = True
            if cgmesProfile.SC in profiles_to_export:
                self.export_SC = True

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
                "SV": ["http://entsoe.eu/CIM/StateVariables/4/1"],
                "GL": ["http://entsoe.eu/CIM/GeographicalLocation/2/1"]
            }

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
                    elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/GeographicalLocation/2/1":
                        self.enum_dict["GL"] = enum_list_dict
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
                    elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/GeographicalLocation/2/1":
                        self.about_dict["GL"] = about_list

            self.class_filters = {}
            json_dict = json.loads(RDFS_INFO_2_4_15)
        elif cgmes_circuit.cgmes_version == CGMESVersions.v3_0_0:
            rdf_serialization.parse(data=RDFS_serialization_3_0_0, format="ttl")

            self.namespaces = {
                "xmlns:cim": "http://iec.ch/TC57/CIM100#",
                "xmlns:md": "http://iec.ch/TC57/61970-552/ModelDescription/1#",
                "xmlns:eu": "http://iec.ch/TC57/CIM100-European#",
                "xmlns:rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            }
            self.profile_uris = {
                "EQ": ["http://iec.ch/TC57/ns/CIM/CoreEquipment-EU/3.0"],
                "OP": ["http://iec.ch/TC57/ns/CIM/Operation-EU/3.0"],
                "SC": ["http://iec.ch/TC57/ns/CIM/ShortCircuit-EU/3.0"],
                "SSH": ["http://iec.ch/TC57/ns/CIM/SteadyStateHypothesis-EU/3.0"],
                "TP": ["http://iec.ch/TC57/ns/CIM/Topology-EU/3.0"],
                "SV": ["http://iec.ch/TC57/ns/CIM/StateVariables-EU/3.0"],
                "GL": ["http://iec.ch/TC57/ns/CIM/GeographicalLocation-EU/3.0"]
            }
            self.enum_dict = dict()
            self.about_dict = dict()
            for s_i, p_i, o_i in rdf_serialization.triples((None, RDF.type, RDFS.Class)):
                if str(s_i).split("#")[1] == "RdfEnum":
                    enum_list_dict = dict()
                    for s, p, o in rdf_serialization.triples((s_i, OWL.members, None)):
                        enum_list_dict[str(o).split("#")[-1]] = str(o)
                    if str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/CoreEquipment-EU/3.0":
                        self.enum_dict["EQ"] = enum_list_dict
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/StateVariables-EU/3.0":
                        self.enum_dict["SV"] = enum_list_dict
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/SteadyStateHypothesis-EU/3.0":
                        self.enum_dict["SSH"] = enum_list_dict
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/Topology-EU/3.0":
                        self.enum_dict["TP"] = enum_list_dict
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/ShortCircuit-EU/3.0":
                        self.enum_dict["SC"] = enum_list_dict
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/Operation-EU/3.0":
                        self.enum_dict["OP"] = enum_list_dict
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/GeographicalLocation-EU/3.0":
                        self.enum_dict["GL"] = enum_list_dict
                if str(s_i).split("#")[1] == "RdfAbout":
                    about_list = list()
                    for s, p, o in rdf_serialization.triples((s_i, OWL.members, None)):
                        about_list.append(str(o).split("#")[-1])
                    if str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/CoreEquipment-EU/3.0":
                        self.about_dict["EQ"] = about_list
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/StateVariables-EU/3.0":
                        self.about_dict["SV"] = about_list
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/SteadyStateHypothesis-EU/3.0":
                        self.about_dict["SSH"] = about_list
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/Topology-EU/3.0":
                        self.about_dict["TP"] = about_list
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/ShortCircuit-EU/3.0":
                        self.about_dict["SC"] = about_list
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/Operation-EU/3.0":
                        self.about_dict["OP"] = about_list
                    elif str(s_i).split("#")[0] == "http://iec.ch/TC57/ns/CIM/GeographicalLocation-EU/3.0":
                        self.about_dict["GL"] = about_list

            self.class_filters = {}
            json_dict = json.loads(RDFS_INFO_3_0_0)
        else:
            raise ValueError(f"CGMES format not supported {cgmes_circuit.cgmes_version}")

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

    def export(self, file_name):
        fname = os.path.basename(file_name)
        fpath = os.path.dirname(file_name)
        name, extension = os.path.splitext(fname)

        profiles_to_export = []
        for prof_enum in self.profiles_to_export:
            if self.cgmes_circuit.cgmes_version == CGMESVersions.v2_4_15:
                if prof_enum.value not in ["OP", "SC"]:
                    profiles_to_export.append(prof_enum.value)
            elif self.cgmes_circuit.cgmes_version == CGMESVersions.v3_0_0:
                profiles_to_export.append(prof_enum.value)
            else:
                raise ValueError(f"Unrecognized CGMES version {self.cgmes_circuit.cgmes_version}")

        if self.one_file_per_profile:
            i = 1
            for prof in profiles_to_export:
                with zipfile.ZipFile(os.path.join(fpath, f"{name}_{prof}_001{extension}"), 'w', zipfile.ZIP_DEFLATED) as f_zip_ptr:
                    self.cgmes_circuit.emit_text(f"Export {prof} profile file")
                    self.cgmes_circuit.emit_progress(i / profiles_to_export.__len__() * 100)
                    i += 1
                    with BytesIO() as buffer:
                        self.serialize(stream=buffer, profile=prof)
                        f_zip_ptr.writestr(f"{name}_{prof}_001.xml", buffer.getvalue())
        else:
            i = 1
            with zipfile.ZipFile(file_name, 'w', zipfile.ZIP_DEFLATED) as f_zip_ptr:
                for prof in profiles_to_export:
                    self.cgmes_circuit.emit_text(f"Export {prof} profile file")
                    self.cgmes_circuit.emit_progress(i / profiles_to_export.__len__() * 100)
                    i += 1
                    with BytesIO() as buffer:
                        self.serialize(stream=buffer, profile=prof)
                        f_zip_ptr.writestr(f"{name}_{prof}_001.xml", buffer.getvalue())

    def serialize(self, stream, profile):
        root = Et.Element("rdf:RDF", self.namespaces)
        full_model_elements = self.generate_full_model_elements(profile)
        root.extend(full_model_elements)
        other_elements = self.generate_other_elements(profile)
        root.extend(other_elements)

        # Convert ElementTree to string
        xml_str = Et.tostring(root, encoding="utf-8", method="xml")

        # Write the XML declaration manually
        xml_declaration = b'<?xml version="1.0" encoding="utf-8"?>\n'
        stream.write(xml_declaration)

        # Parse the XML string and prettify it
        dom = xml.dom.minidom.parseString(xml_str)
        xml_str_pretty = dom.toprettyxml(indent="  ", encoding="utf-8")

        # Write the prettified XML content (excluding the XML declaration) to the stream
        xml_content = xml_str_pretty.decode("utf-8").split("\n")[1:]  # Exclude the XML declaration
        stream.write("\n".join(xml_content).encode("utf-8"))

        stream.seek(0)

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

        for instance in self.cgmes_circuit.cgmes_assets.FullModel_list:
            instance_dict = instance.__dict__
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

    def attr_in_profile(self, attr_filters: dict, profile):
        if profile in attr_filters["Profile"]:
            return True
        else:
            if self.cgmes_circuit.cgmes_version == CGMESVersions.v2_4_15 and profile == "EQ":
                if self.export_OP:
                    if "OP" in attr_filters["Profile"]:
                        return True
                if self.export_SC:
                    if "SC" in attr_filters["Profile"]:
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
                    element = Et.Element("cim:" + class_name, {"rdf:about": "#_" + obj.rdfid})
                else:
                    element = Et.Element("cim:" + class_name, {"rdf:ID": "_" + obj.rdfid})
                has_child = False
                for attr_name, attr_value in obj_dict.items():
                    if attr_value is None:
                        continue
                    if attr_name not in filters:
                        continue
                    attr_filters = filters[attr_name]
                    if not self.attr_in_profile(attr_filters, profile):
                        continue
                    attr_type = attr_filters["Type"]
                    prop_split = str(attr_filters["Property-AttributeAssociationFull"]).split('#')
                    if prop_split[0] == "http://entsoe.eu/CIM/SchemaExtension/3/1":
                        prop_text = "entsoe:" + prop_split[-1]
                    elif prop_split[0] == "http://iec.ch/TC57/CIM100-European":
                        prop_text = "eu:" + prop_split[-1]
                    else:
                        prop_text = "cim:" + prop_split[-1]
                    child = Et.Element(prop_text)
                    if attr_type == "Association":
                        if isinstance(attr_value, list):
                            for v in attr_value:
                                child = Et.Element(prop_text)
                                child.attrib = {"rdf:resource": "#_" + v.rdfid}
                                element.append(child)
                                has_child = True
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
                                has_child = True
                            continue
                        else:
                            child.text = str(attr_value)
                    element.append(child)
                    has_child = True
                if has_child:
                    other_elements.append(element)
        return other_elements
