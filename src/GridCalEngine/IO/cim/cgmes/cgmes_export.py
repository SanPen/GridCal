from rdflib.util import first
from rdflib import Graph, RDFS, RDF, Namespace, OWL, IdentifiedNode, plugin
import rdflib
from rdflib.plugins.parsers.RDFVOC import RDFVOC
from rdflib.plugins.serializers.rdfxml import PrettyXMLSerializer
from rdflib.serializer import Serializer
import os
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit
import pandas as pd

plugin.register("cim_xml", Serializer, "GridCalEngine.IO.cim.cgmes.cgmes_export", "CimSerializer")

about_dict = dict()


class CimSerializer(PrettyXMLSerializer):
    def __init__(self, store: Graph):
        super().__init__(store)
        self.about_list = self.get_about_list()

    def subject(self, subject: IdentifiedNode, depth: int = 1):
        store = self.store
        writer = self.writer

        if subject in self.forceRDFAbout:
            writer.push(RDFVOC.Description)
            writer.attribute(RDFVOC.about, self.relativize(subject))
            writer.pop(RDFVOC.Description)
            self.forceRDFAbout.remove(subject)  # type: ignore[arg-type]

        elif subject not in self._PrettyXMLSerializer__serialized:
            self._PrettyXMLSerializer__serialized[subject] = 1
            tpe = first(store.objects(subject, RDF.type))

            try:
                # type error: Argument 1 to "qname" of "NamespaceManager" has incompatible type "Optional[Node]";
                # expected "str"
                self.nm.qname(tpe)  # type: ignore[arg-type]
            except Exception:
                tpe = None

            element = tpe or RDFVOC.Description
            writer.push(element)

            if store.value(subject, RDF.type).__str__() in self.about_list:
                writer.attribute(RDFVOC.about, self.relativize(subject))
            else:
                writer.attribute(RDFVOC.ID, self.relativize(subject))

            if (subject, None, None) in store:
                for predicate, obj in store.predicate_objects(subject):
                    if not (predicate == RDF.type and obj == tpe):
                        self.predicate(predicate, obj, depth + 1)

            writer.pop(element)

    def get_about_list(self):
        about_list = list()
        profile = self.store.objects(None,
                                     rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#profile"))
        for pro in profile:
            try:
                pro = pro.__str__()
                if pro == "http://entsoe.eu/CIM/EquipmentCore/3/1":
                    about_list = about_dict["eq"]
                    break
                elif pro == "http://entsoe.eu/CIM/StateVariables/4/1":
                    about_list = about_dict["sv"]
                    break
                elif pro == "http://entsoe.eu/CIM/SteadyStateHypothesis/1/1":
                    about_list = about_dict["ssh"]
                    break
                elif pro == "http://entsoe.eu/CIM/Topology/4/1":
                    about_list = about_dict["tp"]
                    break
            except:
                about_list = []

        return about_list


class CgmesExporter:
    def __init__(self, cgmes_circuit: CgmesCircuit = None):
        self.cgmes_circuit = cgmes_circuit

    def export_to_xml(self):
        import time
        start = time.time()
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

            if str(s_i).split("#")[1] == "RdfAbout":
                about_list = list()
                for s, p, o in rdf_serialization.triples((s_i, OWL.members, None)):
                    about_list.append(str(o))
                if str(s_i).split("#")[0] == "http://entsoe.eu/CIM/EquipmentCore/3/1":
                    about_dict["eq"] = about_list
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/StateVariables/4/1":
                    about_dict["sv"] = about_list
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/SteadyStateHypothesis/1/1":
                    about_dict["ssh"] = about_list
                elif str(s_i).split("#")[0] == "http://entsoe.eu/CIM/Topology/4/1":
                    about_dict["tp"] = about_list

        profiles_info = pd.read_excel(absolute_path_to_excel, sheet_name="Profiles")
        endt = time.time()
        print("Serialization and excel load time: ", endt - start, "sec")

        start = time.time()
        eq_graph = self.create_graph()
        eq_graph.add((rdflib.URIRef("urn:uuid:7d06cd3f-a6dc-9642-826a-266fc538e942"),
                      rdflib.URIRef(RDF.type),
                      rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#FullModel")))
        eq_graph.add((rdflib.URIRef("urn:uuid:7d06cd3f-a6dc-9642-826a-266fc538e942"),
                      rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#profile"),
                      rdflib.Literal("http://entsoe.eu/CIM/EquipmentCore/3/1")))
        ssh_graph = self.create_graph()
        ssh_graph.add((rdflib.URIRef("urn:uuid:7d06cd3f-a6dc-9642-826a-266fc538e942"),
                       rdflib.URIRef(RDF.type),
                       rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#FullModel")))
        ssh_graph.add((rdflib.URIRef("urn:uuid:7d06cd3f-a6dc-9642-826a-266fc538e942"),
                       rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#profile"),
                       rdflib.Literal("http://entsoe.eu/CIM/SteadyStateHypothesis/1/1")))
        tp_graph = self.create_graph()
        tp_graph.add((rdflib.URIRef("urn:uuid:7d06cd3f-a6dc-9642-826a-266fc538e942"),
                      rdflib.URIRef(RDF.type),
                      rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#FullModel")))
        tp_graph.add((rdflib.URIRef("urn:uuid:7d06cd3f-a6dc-9642-826a-266fc538e942"),
                      rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#profile"),
                      rdflib.Literal("http://entsoe.eu/CIM/Topology/4/1")))
        sv_graph = self.create_graph()
        sv_graph.add((rdflib.URIRef("urn:uuid:7d06cd3f-a6dc-9642-826a-266fc538e942"),
                      rdflib.URIRef(RDF.type),
                      rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#FullModel")))
        sv_graph.add((rdflib.URIRef("urn:uuid:7d06cd3f-a6dc-9642-826a-266fc538e942"),
                      rdflib.URIRef("http://iec.ch/TC57/61970-552/ModelDescription/1#profile"),
                      rdflib.Literal("http://entsoe.eu/CIM/StateVariables/4/1")))

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

        relative_path_to_files = "export_docs/"
        absolute_path_to_files = os.path.join(current_directory, relative_path_to_files)
        endt = time.time()
        print("Graph load time: ", endt - start, "sec")
        start = time.time()
        eq_graph.serialize(destination=absolute_path_to_files + "eq.xml", format="cim_xml",
                           base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        ssh_graph.serialize(destination=absolute_path_to_files + "ssh.xml", format="cim_xml",
                            base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        tp_graph.serialize(destination=absolute_path_to_files + "tp.xml", format="cim_xml",
                           base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        sv_graph.serialize(destination=absolute_path_to_files + "sv.xml", format="cim_xml",
                           base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        print("CGMES graph export completed.")
        endt = time.time()
        print("Serialize time: ", endt - start, "sec")

    def create_graph(self):

        graph_with_ns = Graph()
        graph_with_ns.bind("cim", Namespace("http://iec.ch/TC57/2013/CIM-schema-cim16#"))
        graph_with_ns.bind("entsoe", Namespace("http://entsoe.eu/CIM/SchemaExtension/3/1#"))
        graph_with_ns.bind("md", Namespace("http://iec.ch/TC57/61970-552/ModelDescription/1#"))
        return graph_with_ns
