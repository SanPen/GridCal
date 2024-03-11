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
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
from rdflib import OWL
import rdflib
from rdflib.graph import Graph
from rdflib.namespace import RDF, RDFS, Namespace

from typing import List

import os
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
import pandas as pd


class CgmesDataValidator:
    def __init__(self, cgmes_circuit: CgmesCircuit = None):
        self.cgmes_circuit = cgmes_circuit

    def create_graph(self, profile: List[str]):
        graph = Graph()
        graph.bind("cim", Namespace("http://iec.ch/TC57/2013/CIM-schema-cim16#"))
        graph.bind("entsoe", Namespace("http://entsoe.eu/CIM/SchemaExtension/3/1#"))
        graph.bind("md", Namespace("http://iec.ch/TC57/61970-552/ModelDescription/1#"))

        full_model_list = self.cgmes_circuit.FullModel_list

        filter_props = ["scenarioTime",
                        "created",
                        "version",
                        "profile",
                        "modelingAuthoritySet",
                        "DependentOn",
                        "longDependentOnPF",
                        "Supersedes",
                        "description"]
        # populate graph with header
        for model in full_model_list:
            obj_dict = model.__dict__
            obj_id = rdflib.URIRef("urn:uuid:" + model.rdfid)
            if obj_dict.get("profile") in profile:
                for attr_name, attr_value in obj_dict.items():
                    if attr_name not in filter_props:
                        continue
                    if attr_value is None:
                        continue
                    if hasattr(attr_value, "rdfid"):
                        graph.add((rdflib.URIRef(obj_id),
                                   rdflib.URIRef(RDF.type),
                                   rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#FullModel")))
                        graph.add((rdflib.URIRef(obj_id),
                                   rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#Model." + attr_name),
                                   rdflib.URIRef("urn:uuid:" + attr_value.rdfid)))
                    else:
                        graph.add((rdflib.URIRef(obj_id),
                                   rdflib.URIRef(RDF.type),
                                   rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#FullModel")))
                        graph.add((rdflib.URIRef(obj_id),
                                   rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#Model." + attr_name),
                                   rdflib.Literal(str(attr_value))))

        return graph

    def load_graph(self):
        current_directory = os.path.dirname(__file__)
        relative_path_to_excel = "export_docs/CGMES_2_4_EQ_SSH_TP_SV_ConcreteClassesAllProperties.xlsx"
        absolute_path_to_excel = os.path.join(current_directory, relative_path_to_excel)

        rdf_serialization = Graph()
        rdf_serialization.parse(source=os.path.join(current_directory, "export_docs\RDFSSerialisation.ttl"),
                                format="ttl")
        enum_dict = dict()

        for s_i, p_i, o_i in rdf_serialization.triples((None, RDF.type, RDFS.Class)):
            if str(s_i).split("#")[1] == "RdfEnum":
                enum_list_dict = dict()
                for s, p, o in rdf_serialization.triples((s_i, OWL.members, None)):
                    enum_list_dict[str(o).split("#")[1]] = str(o)
                if str(s_i).split("#")[0] == "http://entsoe.eu/CIM/EquipmentCore/3/1":
                    enum_dict["eq"] = enum_list_dict
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/StateVariables/4/1":
                    enum_dict["sv"] = enum_list_dict
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/SteadyStateHypothesis/1/1":
                    enum_dict["ssh"] = enum_list_dict
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/Topology/4/1":
                    enum_dict["tp"] = enum_list_dict

        profiles_info = pd.read_excel(absolute_path_to_excel, sheet_name="Profiles")

        eq_graph = self.create_graph(["http://entsoe.eu/CIM/EquipmentCore/3/1",
                                      "http://entsoe.eu/CIM/EquipmentShortCircuit/3/1",
                                      "http://entsoe.eu/CIM/EquipmentOperation/3/1"])
        ssh_graph = self.create_graph(["http://entsoe.eu/CIM/SteadyStateHypothesis/1/1"])
        tp_graph = self.create_graph(["http://entsoe.eu/CIM/Topology/4/1"])
        sv_graph = self.create_graph(["http://entsoe.eu/CIM/StateVariables/4/1"])

        graphs_dict = {
            "EQ": eq_graph,
            "SSH": ssh_graph,
            "TP": tp_graph,
            "SV": sv_graph
        }

        class_filters = {}
        for class_name in self.cgmes_circuit.classes:
            filt_class = profiles_info[profiles_info["ClassSimpleName"] == class_name]
            filters = {}

            for _, row in filt_class.iterrows():
                prop = row["Property-AttributeAssociationSimple"]
                if prop not in filters:
                    filters[prop] = {
                        "Profile": [],
                        "ClassFullName": row["ClassFullName"],
                        "Property-AttributeAssociationFull": row["Property-AttributeAssociationFull"],
                        "Type": row["Type"]
                    }
                filters[prop]["Profile"].append(row["Profile"])

            class_filters[class_name] = filters

        for class_name, filters in class_filters.items():
            objects = self.cgmes_circuit.get_objects_list(elm_type=class_name)

            for obj in objects:
                obj_dict = obj.__dict__
                obj_id = rdflib.URIRef("_" + obj.rdfid)

                for attr_name, attr_value in obj_dict.items():
                    if attr_value is None:
                        continue

                    if attr_name not in filters:
                        continue

                    attr_filters = filters[attr_name]
                    for profile in attr_filters["Profile"]:
                        graph = graphs_dict.get(profile)
                        if graph is None:
                            continue

                        attr_type = attr_filters["Type"]
                        if attr_type == "Association":
                            graph.add(
                                (obj_id, RDF.type, rdflib.URIRef(attr_filters["ClassFullName"])))
                            graph.add((rdflib.URIRef(obj_id),
                                       rdflib.URIRef(attr_filters["Property-AttributeAssociationFull"]),
                                       rdflib.URIRef("#_" + attr_value.rdfid)))
                        elif attr_type == "Enumeration":
                            enum_dict_key = profile.lower()
                            enum_dict_value = enum_dict.get(enum_dict_key)
                            enum_value = enum_dict_value.get(str(attr_value))
                            graph.add(
                                (obj_id, RDF.type, rdflib.URIRef(attr_filters["ClassFullName"])))
                            graph.add((obj_id, rdflib.URIRef(attr_filters["Property-AttributeAssociationFull"]),
                                       rdflib.URIRef(enum_value)))
                        elif attr_type == "Attribute":
                            if isinstance(attr_value, bool):
                                attr_value = str(attr_value).lower()
                            graph.add(
                                (obj_id, RDF.type, rdflib.URIRef(attr_filters["ClassFullName"])))
                            graph.add((obj_id, rdflib.URIRef(attr_filters["Property-AttributeAssociationFull"]),
                                       rdflib.Literal(str(attr_value))))
