import rdflib.term
from rdflib import Graph, RDF, RDFS
from pprint import pprint

# Select which CGMES version you want to import
# CGMESv2.4.15: 2, GCMESv3: 3
version = 3
rdf_graph = Graph()  # 1st define the graph
if version == 2:
    # CGMESv2_4_15
    files_list = ["RDFS/cgmes_v2_4_15/EquipmentProfileCoreOperationShortCircuitRDFSAugmented-v2_4_15-4Sep2020.rdf",
                  "RDFS/cgmes_v2_4_15/StateVariableProfileRDFSAugmented-v2_4_15-4Sep2020.rdf",
                  "RDFS/cgmes_v2_4_15/SteadyStateHypothesisProfileRDFSAugmented-v2_4_15-4Sep2020.rdf",
                  "RDFS/cgmes_v2_4_15/TopologyProfileRDFSAugmented-v2_4_15-4Sep2020.rdf",
                  "RDFS/cgmes_v2_4_15/GeographicalLocationProfileRDFSAugmented-v2_4_15-4Sep2020.rdf"]
elif version == 3:
    # CGMESv3
    files_list = ["RDFS/cgmes_v3_0_0/IEC61970-600-2_CGMES_3_0_0_RDFS2020_EQ.rdf",
                  "RDFS/cgmes_v3_0_0/IEC61970-600-2_CGMES_3_0_0_RDFS2020_SV.rdf",
                  "RDFS/cgmes_v3_0_0/IEC61970-600-2_CGMES_3_0_0_RDFS2020_TP.rdf",
                  "RDFS/cgmes_v3_0_0/IEC61970-600-2_CGMES_3_0_0_RDFS2020_GL.rdf",
                  "RDFS/cgmes_v3_0_0/IEC61970-600-2_CGMES_3_0_0_RDFS2020_SSH.rdf", ]
else:
    files_list = []

for file in files_list:
    rdf_graph.parse(source=file, format='xml')

# NAMESPACE prefixes
cims = "http://iec.ch/TC57/1999/rdf-schema-extensions-19990926#"
if version == 2:
    # CGMESv2_4_15
    base = "http://iec.ch/TC57/2013/CIM-schema-cim16"
elif version == 3:
    # CGMESv3
    base = "http://iec.ch/TC57/CIM100"
entsoe = "http://entsoe.eu/CIM/SchemaExtension/3/1#"
cims_multiplicity = rdflib.term.URIRef(cims + 'multiplicity')
cims_stereotype = rdflib.term.URIRef(cims + 'stereotype')
cims_datatype = rdflib.term.URIRef(cims + 'dataType')
cims_isFixed = rdflib.term.URIRef(cims + 'isFixed')
cims_inverseRoleName = rdflib.term.URIRef(cims + "inverseRoleName")

all_class = []
cgmes_class_list = []
assoc_datatype_dict = dict()


def generate_cgmes_classes():
    from write_py import (write_py_for_class, write_class_list_and_dict, write_class_import, write_enums,
                          write_assoc_dict)
    from cgmes_class import CGMES_class
    # LOOP on all classes:
    for s_i, p_i, o_i in rdf_graph.triples((None, RDF.type, RDFS.Class)):
        # print(s_i, p_i, o_i)

        # Importing the class names that are not in the scope
        with open("not_in_scope_list.txt", "r") as file:
            not_in_scope_list = [line.strip() for line in file]

        # children: rdf_graph.subjects(RDFS.subClasOf, s_i)
        class_stereotypes = rdf_graph.objects(s_i, cims_stereotype)
        class_stereotypes = [str(value) for value in class_stereotypes]
        stereotype_filter = ["http://iec.ch/TC57/NonStandard/UML#concrete", "Operation", "ShortCircuit"]
        # NAME
        label = rdf_graph.value(s_i, RDFS.label).__str__()

        # Filtering classes that are in the scope
        if (label not in not_in_scope_list and (len(class_stereotypes) == 0 or
                                                any(element in class_stereotypes for element in stereotype_filter))):

            all_class.append(label)
            print(label)

            # PARENTS
            inheritance_list = []
            try:
                print(f'Inheritance chain of {label}:')
                inheritance_list = get_inheritance_list(subject=s_i)
                print(inheritance_list)
            except:
                print("Don't have parent class.")

            # ATTRIBUTES
            attributes = []  # list of attribute dictionaries
            # list of the subjects directly as URIRef
            attr_list = list(rdf_graph.subjects(RDFS.domain, s_i))
            # print("\nAttr list")
            # pprint(attr_list)

            # attr_labels = []
            # stereotype_list = []

            # LOOP on properties: can be two types: attr or asso.
            for s in rdf_graph.subjects(RDFS.domain, s_i):
                attribute_i = {}  # one attribute as a dictionary

                in_scope = True
                # NAME
                attr_label = rdf_graph.objects(s, RDFS.label).__next__().__str__()
                # attr_labels.append(attr_label)
                attribute_i["name"] = attr_label
                # print(f'\nATTR: {attr_label}')

                # DATATYPE
                # check if attribute_i or association
                stereotypes_for_attr = list(rdf_graph.objects(s, cims_stereotype))
                # stereotype_list.append(stereotypes_for_attr)
                # pprint(stereotypes_for_attr)

                attr_term = rdflib.term.URIRef('http://iec.ch/TC57/NonStandard/UML#attribute')
                if attr_term in stereotypes_for_attr:  # ATTRIBUTE or ENUMERATION

                    # ENUMERATION: should not have rdfs.range.
                    # v = list(rdf_graph.objects(s, RDFS.range))
                    if list(rdf_graph.objects(s, RDFS.range)):
                        # print("it is an enumeration!")
                        attribute_i["enum_range_list"] = list(rdf_graph.objects(s, RDFS.range))
                        attribute_i["description"] = rdf_graph.value(s, RDFS.comment).__str__()
                    # ATTRIBUTE
                    else:
                        datatype = rdf_graph.objects(s, cims_datatype).__next__()
                        datatype_value = None
                        # chech if it is a primitive:
                        datatype_stereotype_list = list(rdf_graph.objects(datatype, cims_stereotype))

                        # print(f'Datatype stereotype list: '
                        #       f'{datatype_stereotype_list}')

                        if rdflib.term.Literal('Primitive') in datatype_stereotype_list:
                            try:
                                datatype_value = datatype.__str__().split('#')[1]
                            except:
                                datatype_value = datatype.__str__()
                            # Py Datatypes: int, float, str, bool
                            # RDFS Datatypes: ..., daytime
                            attribute_i["description"] = rdf_graph.value(s, RDFS.comment).__str__()
                        if rdflib.term.Literal('CIMDatatype') in datatype_stereotype_list:
                            # print("\nthis is a CIMDatatype")
                            # .value: it has the primitive
                            try:
                                datatype_value = \
                                    rdf_graph.value(datatype + '.value', cims_datatype).__str__().split('#')[1]
                            except:
                                datatype_value = rdf_graph.value(datatype + '.value', cims_datatype).__str__()
                            # .unit: play with range and isFixed
                            try:
                                datatype_range = rdf_graph.value(datatype + '.unit', RDFS.range).__str__().split('#')[1]
                            except:
                                datatype_range = rdf_graph.value(datatype + '.unit', RDFS.range).__str__()
                            datatype_unit = rdf_graph.value(datatype + '.unit', cims_isFixed).__str__()
                            # .multiplier
                            #      e.g.: =UnitMultiplier.none
                            try:
                                datatype_multiplier = rdf_graph.value(datatype + '.multiplier',
                                                                      RDFS.range).__str__().split('#')[1]
                            except:
                                datatype_multiplier = rdf_graph.value(datatype + '.multiplier',
                                                                      RDFS.range).__str__()
                            multiply_unit = rdf_graph.value(datatype + '.multiplier', cims_isFixed).__str__()
                            if multiply_unit != "None":
                                datatype_multiplier = datatype_multiplier + "." + multiply_unit
                            else:
                                datatype_multiplier = datatype_multiplier + ".none"
                            datatype_description = rdf_graph.value(datatype, RDFS.comment).__str__()

                            attribute_i["range"] = datatype_range
                            attribute_i["unit"] = datatype_unit
                            attribute_i["multiplier"] = datatype_multiplier
                            attribute_i["description"] = datatype_description

                        attribute_i["datatype"] = datatype_value
                # ASSOCIATION
                else:
                    # print("this is an ASSOCIATION")

                    try:
                        aso_range = rdf_graph.value(s, RDFS.range).__str__().split('#')[1]
                    except:
                        aso_range = rdf_graph.value(s, RDFS.range).__str__()
                    # could be active p: value or multiplier
                    if aso_range not in not_in_scope_list:
                        inv_role_name = rdf_graph.value(s, cims_inverseRoleName).__str__().split('#')[-1]
                        assoc_datatype_dict[inv_role_name] = label + "." + attr_label
                        attribute_i["range"] = aso_range
                        attribute_i["description"] = rdf_graph.value(s, RDFS.comment).__str__()
                    else:
                        in_scope = False
                if in_scope:
                    attributes.append(attribute_i)

            # print(f'\n ----------------------------------------------------- \n')
            # print(f'Class name  : {label}')
            # if subclass_of_label and subclass_of:
            #     print(f'Parent name : {subclass_of_label} ({subclass_of})')
            # print(f'Attributes  : ')
            # pprint(attributes)

            cgmes_class_list.append(CGMES_class(name=label, inheritance_list=inheritance_list, attributes=attributes))

    # Writing the .py file for each CGMES classes in scope
    for cgmes_class in cgmes_class_list:
        write_py_for_class(cgmes_version=version, cgmes_class=cgmes_class)
    # Creating a list and dictionary if needed
    write_class_list_and_dict(all_class)
    # Creating import line to all generated classes
    write_class_import(all_class)
    # Creating .py file for all the enums used
    write_enums()
    # Creating a dict for association types
    write_assoc_dict(assoc_datatype_dict)

    # print(f'\n ----------------------------------------------------- ')
    # print("\nALL CLASSES:")
    # pprint(all_class)
    print(f"{len(all_class)} classes generated.")


def get_inheritance_list(subject):
    inheritance_list = []
    subclass_of = rdf_graph.value(subject, RDFS.subClassOf)
    subclass_of_label = subclass_of.__str__().split('#')[1]
    # print(subclass_of)
    inheritance_list.append(subclass_of.__str__().split('#')[1])

    # print(subclass_of_label)
    # print(" --- ")
    while subclass_of != rdflib.term.URIRef(base + "#IdentifiedObject"):
        subclass_of = rdf_graph.value(subclass_of, RDFS.subClassOf)
        subclass_name = subclass_of.__str__().split('#')[1]
        inheritance_list.append(subclass_name)
    return inheritance_list


def get_class_by_name(class_name):
    for cgmes_class in cgmes_class_list:
        if cgmes_class.name == class_name:
            return cgmes_class
    return None


if __name__ == "__main__":
    generate_cgmes_classes()

# --------------------------  NOTES  -----------------------------------
# pprint(rdf_graph.items())
# all_nodes = rdf_graph.all_nodes()
# pprint(all_nodes)
# node1 = all_nodes.pop()
# pprint(node1)
# quit()

# triples((subj, pred, obj))
# RDF.type -
# RDFS.Class -
# RDF.Property -

# DIRECTIONS
# RDFS.domain ~ parent
# RDFS.range ~ child: object that is exchanged

# RDFS.label - name of the thing
# RDFS.comment - description

# Enumerartion
# no Class, no Property
# list to choose from (phases)

# stereotypes: class, abstract, enumeration

# rdf_graph.objects(??)
# rdf_graph.subjects(??)

# list of the triples
# attr_list = list(rdf_graph.triples((None, RDFS.domain, s_i)))
# list of the subjects directly
# attr_list = list(rdf_graph.subjects(RDFS.domain, s_i))

# # all stereotypes
# for s_i, p_i, o_i in rdf_graph.triples((None, cims_stereotype, None)):
#     print(s_i, p_i, o_i)
# quit()

# get generator content as a list
# list(rdf_graph.triples((literal[0], RDFS.range, None)))

# subclass_of = rdf_graph.triples((s_i, RDFS.subClassOf, None)).__next__()
# print(subclass_of)
#
# how to access a generator?
# for s_i3, p_i3, o_i3 in subclass_of:
#     rdflib.term.URIRef(o_i3)
#
#     print(f"{s_i} is a subclass of {o_i3}")
#
#     # o_i3.defrag() - to get namespace
#     # rdflib.util.
# ATTRIBUTE ?
# for s_i2, p_i2, o_i2 in rdf_graph.triples((None, RDFS.domain, s_i)):
#
#     print(s_i2, p_i2, o_i2)
