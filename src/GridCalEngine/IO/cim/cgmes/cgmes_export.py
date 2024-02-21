import polars as pl
from rdflib.util import first
from rdflib import Graph, RDFS, RDF, Namespace, OWL, IdentifiedNode, plugin
import rdflib
from rdflib.plugins.parsers.RDFVOC import RDFVOC
from rdflib.plugins.serializers.rdfxml import PrettyXMLSerializer
from rdflib.serializer import Serializer
import os
from GridCalEngine.IO.cim.cgmes.cgmes_circuit import CgmesCircuit

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
        # Todo test phase only modify needed in future
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

        profiles_info = pl.read_excel(
            source=absolute_path_to_excel,
            sheet_name="Profiles")

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

        eq_graph.serialize(destination=absolute_path_to_files + "eq.xml", format="cim_xml",
                           base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        ssh_graph.serialize(destination=absolute_path_to_files + "ssh.xml", format="cim_xml",
                            base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        tp_graph.serialize(destination=absolute_path_to_files + "tp.xml", format="cim_xml",
                           base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        sv_graph.serialize(destination=absolute_path_to_files + "sv.xml", format="cim_xml",
                           base="http://iec.ch/TC57/2013/CIM-schema-cim16#")
        print("CGMES graph export completed.")

    def create_graph(self):

        graph_with_ns = Graph()
        graph_with_ns.bind("cim", Namespace("http://iec.ch/TC57/2013/CIM-schema-cim16#"))
        graph_with_ns.bind("entsoe", Namespace("http://entsoe.eu/CIM/SchemaExtension/3/1#"))
        graph_with_ns.bind("md", Namespace("http://iec.ch/TC57/61970-552/ModelDescription/1#"))
        return graph_with_ns
