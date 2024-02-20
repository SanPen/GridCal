import polars as pl
from rdflib import Graph, RDFS, RDF, Namespace, XSD, OWL
import rdflib
from rdflib.plugins.parsers.RDFVOC import RDFVOC
import os
from cgmes_circuit import CgmesCircuit


class Cgmes_exporter:
    def __init__(self, cgmes_circuit: CgmesCircuit = None):
        self.cgmes_circuit = cgmes_circuit

    def export(self):
        current_directory = os.path.dirname(__file__)
        relative_path_to_excel = "export_docs/CGMES_2_4_EQ_SSH_TP_SV_ConcreteClassesAllProperties.xlsx"
        absolute_path_to_excel = os.path.join(current_directory, relative_path_to_excel)

        rdf_serialization = Graph()
        rdf_serialization.parse(source=os.path.join(current_directory, "export_docs\RDFSSerialisation.ttl"),
                                format="ttl")
        enum_dict = dict()
        enum_list = dict()
        for s_i, p_i, o_i in rdf_serialization.triples((None, RDF.type, RDFS.Class)):
            if str(s_i).split("#")[1] == "RdfEnum":
                for s, p, o in rdf_serialization.triples((s_i, OWL.members, None)):
                    enum_list[str(o).split("#")[1]] = str(o)
                enum_dict["eq"] = enum_list

        profiles_info = pl.read_excel(
            source=absolute_path_to_excel,
            sheet_name="Profiles")

        eq_graph = self.create_graph()
        ssh_graph = self.create_graph()
        tp_graph = self.create_graph()
        sv_graph = self.create_graph()

        for class_name in self.cgmes_circuit.classes:
            objects = self.cgmes_circuit.get_objects_list(elm_type=class_name)

            filt_class = profiles_info.filter(pl.col("ClassSimpleName") == class_name)

            for obj in objects:
                for attr_name, attr_value in obj.__dict__.items():
                    # print(f"{attr_name}: {attr_value}")
                    try:
                        if attr_value is not None or attr_value != "":
                            filt_property = filt_class.filter(
                                pl.col("Property-AttributeAssociationSimple") == attr_name)
                            profile = filt_property[0, 8].__str__()
                            obj_id = rdflib.URIRef("_" + obj.rdfid)
                            if hasattr(attr_value, "rdfid"):
                                # print("It's an assoc: " + attr_value.rdfid)

                                if profile == "EQ":
                                    eq_graph.add((obj_id, RDF.type,
                                                  rdflib.URIRef(filt_property[0, 1].__str__())))
                                    eq_graph.add(
                                        (rdflib.URIRef(obj_id), rdflib.URIRef(filt_property[0, 3].__str__()),
                                         rdflib.URIRef("#_" + attr_value.rdfid)))
                                elif profile == "SSH":
                                    ssh_graph.add((obj_id, RDF.type,
                                                   rdflib.URIRef(filt_property[0, 1].__str__())))
                                    ssh_graph.add(
                                        (rdflib.URIRef(obj_id), rdflib.URIRef(filt_property[0, 3].__str__()),
                                         rdflib.URIRef("#_" + attr_value.rdfid)))
                                elif profile == "TP":
                                    tp_graph.add((obj_id, RDF.type,
                                                  rdflib.URIRef(filt_property[0, 1].__str__())))
                                    tp_graph.add(
                                        (rdflib.URIRef(obj_id), rdflib.URIRef(filt_property[0, 3].__str__()),
                                         rdflib.URIRef("#_" + attr_value.rdfid)))
                                elif profile == "SV":
                                    sv_graph.add((obj_id, RDF.type,
                                                  rdflib.URIRef(filt_property[0, 1].__str__())))
                                    sv_graph.add(
                                        (rdflib.URIRef(obj_id), rdflib.URIRef(filt_property[0, 3].__str__()),
                                         rdflib.URIRef("#_" + attr_value.rdfid)))

                            elif filt_property[0, 6].__str__() == "Enumeration":
                                if profile == "EQ":
                                    eq_graph.add((obj_id, RDF.type,
                                                  rdflib.URIRef(filt_property[0, 1].__str__())))
                                    di = enum_dict.get("eq")
                                    va = di.get(str(attr_value))
                                    eq_graph.add((obj_id, rdflib.URIRef(filt_property[0, 3].__str__()),
                                                  rdflib.URIRef(va)))
                                elif profile == "SSH":
                                    ssh_graph.add((obj_id, RDF.type,
                                                   rdflib.URIRef(filt_property[0, 1].__str__())))
                                    di = enum_dict.get("ssh")
                                    va = di.get(str(attr_value))
                                    ssh_graph.add((obj_id, rdflib.URIRef(filt_property[0, 3].__str__()),
                                                   rdflib.URIRef(va)))
                                elif profile == "TP":
                                    tp_graph.add((obj_id, RDF.type,
                                                  rdflib.URIRef(filt_property[0, 1].__str__())))
                                    di = enum_dict.get("tp")
                                    va = di.get(str(attr_value))
                                    tp_graph.add((obj_id, rdflib.URIRef(filt_property[0, 3].__str__()),
                                                  rdflib.URIRef(va)))
                                elif profile == "SV":
                                    sv_graph.add((obj_id, RDF.type,
                                                  rdflib.URIRef(filt_property[0, 1].__str__())))
                                    di = enum_dict.get("sv")
                                    va = di.get(str(attr_value))
                                    sv_graph.add((obj_id, rdflib.URIRef(filt_property[0, 3].__str__()),
                                                  rdflib.URIRef(va)))
                            else:
                                # print(f"It's an attribute:  {attr_value}")
                                if isinstance(attr_value, bool):
                                    attr_value = str(attr_value).lower()
                                if profile == "EQ":
                                    eq_graph.add((obj_id, RDF.type,
                                                  rdflib.URIRef(filt_property[0, 1].__str__())))
                                    eq_graph.add((obj_id, rdflib.URIRef(filt_property[0, 3].__str__()),
                                                  rdflib.Literal(str(attr_value), datatype=None)))
                                elif profile == "SSH":
                                    ssh_graph.add((obj_id, RDF.type,
                                                   rdflib.URIRef(filt_property[0, 1].__str__())))
                                    ssh_graph.add(
                                        (obj_id, rdflib.URIRef(filt_property[0, 3].__str__()),
                                         rdflib.Literal(str(attr_value), datatype=None)))
                                elif profile == "TP":
                                    tp_graph.add((obj_id, RDF.type,
                                                  rdflib.URIRef(filt_property[0, 1].__str__())))
                                    tp_graph.add((obj_id, rdflib.URIRef(filt_property[0, 3].__str__()),
                                                  rdflib.Literal(str(attr_value), datatype=None)))
                                elif profile == "SV":
                                    sv_graph.add((obj_id, RDF.type,
                                                  rdflib.URIRef(filt_property[0, 1].__str__())))
                                    sv_graph.add((obj_id, rdflib.URIRef(filt_property[0, 3].__str__()),
                                                  rdflib.Literal(str(attr_value), datatype=None)))
                    except Exception:
                        continue

        relative_path_to_files = "export_docs/"
        absolute_path_to_files = os.path.join(current_directory, relative_path_to_files)

        eq_graph.serialize(destination=absolute_path_to_files + "eq.xml", format="pretty-xml",
                           base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        ssh_graph.serialize(destination=absolute_path_to_files + "ssh.xml", format="pretty-xml",
                            base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        tp_graph.serialize(destination=absolute_path_to_files + "tp.xml", format="pretty-xml",
                           base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        sv_graph.serialize(destination=absolute_path_to_files + "sv.xml", format="pretty-xml",
                           base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        print("CGMES graph export completed.")

    def create_graph(self):

        graph_with_ns = Graph()
        graph_with_ns.bind("cim", Namespace("http://iec.ch/TC57/2013/CIM-schema-cim16#"))
        graph_with_ns.bind("entsoe", Namespace("http://entsoe.eu/CIM/SchemaExtension/3/1#"))
        graph_with_ns.bind("md", Namespace("http://iec.ch/TC57/61970-552/ModelDescription/1#"))
        return graph_with_ns
