import os

enum_name_list = set()


def get_format_name(class_name, is_folder=False):
    """
    Generating the class or folder name that we create.

    :param is_folder: It doesn't put .py in the end of the name if true.
    :param class_name: The name of the class which we want to make it as a file name.
    :return: example: file_name.py
    """
    py_name = ''
    py_name += class_name[0].lower()
    i = 1
    for char in class_name[1:]:
        if char.isupper():
            if class_name[i + 1].isupper():
                py_name += char.lower()
            else:
                py_name += '_'
                py_name += char.lower()
        else:
            py_name += char.lower()
        i += 1
    if not is_folder:
        py_name += '.py'

    return py_name


def write_py_for_class(cgmes_version, cgmes_class):
    """
    Generates .py file for the given Class

    :param cgmes_class: CGMES class object with its properties
    :param cgmes_version: CGMES version of the class v2.4.15: 2, v3.0.0: 3
    later with multiplier, unit, description, profiles for property staff
    :return:
    """
    global class_enum_list
    global cgmes_folder

    class_enum_list = set()
    name = cgmes_class.name
    if len(cgmes_class.inheritance_list) != 0:
        parent = cgmes_class.inheritance_list[0]
    else:
        parent = None
    # inheritance_list = cgmes_class.inheritance_list
    attributes = cgmes_class.attributes
    # CGMES folder name
    if cgmes_version == 2:
        cgmes_folder = "cgmes_v2_4_15"
    elif cgmes_version == 3:
        cgmes_folder = "cgmes_v3_0_0"
    code = ""

    # IMPORTED classes
    # Default imports only
    import_text = "\nfrom GridCalEngine.IO.base.units import UnitMultiplier, UnitSymbol\n"
    if parent:
        import_text += (f"from GridCalEngine.IO.cim.cgmes.{cgmes_folder}.devices.{get_format_name(parent, True)}"
                        f" import {parent}\n")
    else:
        import_text += f"from GridCalEngine.IO.cim.cgmes.base import Base\n"
    # Not sure how to generate all of this as we need to know the path to some of the imported classes.
    # CLASS specification
    code += get_class_spec_code(name, parent)

    # Write attribute code
    code += get_attribute_code(attributes)

    code += "\n"
    # Property register
    reg_prop = get_reg_prop_code(attributes)

    code += reg_prop
    # print(code)

    # Enumeration import
    import_text += f"from GridCalEngine.IO.cim.cgmes.cgmes_enums import cgmesProfile"
    for enum_name in class_enum_list:
        import_text += f", {enum_name}"
    import_text += "\n"
    import_text += "\n\n"
    # Save to file
    py_name = get_format_name(class_name=name)
    folder_name = ""
    # folder_list = ["ACDCTerminal",
    #                "TapChanger",
    #                "ConnectivityNodeContainer",
    #                "DCConductingEquipment",
    #                "GeneratingUnit",
    #                "ConductingEquipment"]

    file_path = f"{cgmes_folder}/devices/" + folder_name
    if not os.path.exists(file_path):
        os.makedirs(file_path)
        with open(file_path + "/__init__.py", 'w'):
            pass
    file_path = os.path.join(file_path, py_name)
    with open(file_path, "w") as file:
        with open("copyright_text.txt", "r") as cr_file:
            file.write(cr_file.read())  # Reading the copyright text and adding it to the top of the file
        file.write(import_text)
        file.write(code)
    print(f"{name} class .py generated")


def get_reg_prop_code(attributes):
    reg_prop = ""
    for attribute in attributes:
        attr_name = attribute["name"]
        class_type = ""
        multiplier = "UnitMultiplier.none"
        unit = "UnitSymbol.none"
        try:
            description = attribute["description"]
        except:
            description = ""
        if "datatype" in attribute:  # Attribute
            data_type = attribute["datatype"]
            if data_type == "Float" or data_type == "Decimal":
                class_type = "float"
            elif data_type == "Integer":
                class_type = "int"
            elif data_type == "DateTime" or data_type == "MonthDay":
                class_type = "datetime.datetime"
            elif data_type == "Boolean":
                class_type = "bool"
            elif data_type == "String":
                class_type = "str"
            if "multiplier" in attribute and "range" in attribute and "unit" in attribute:
                if attribute["multiplier"] != "None.none":
                    multiplier = attribute["multiplier"]
                if attribute["range"] != "None":
                    unit = attribute["range"] + "." + attribute["unit"]
                    enum_name_list.update({attribute["range"]})
                    class_enum_list.update({attribute["range"]})
        elif "range" in attribute:  # Association
            assoc_range = attribute["range"]
            class_type = assoc_range
        if "enum_range_list" in attribute:  # Enumeration
            enum_range_list = attribute["enum_range_list"]
            class_type = enum_range_list[0].split("#")[1]
        reg_prop += f"\t\tself.register_property(\n"
        reg_prop += f"\t\t\tname='{attr_name}',\n"
        reg_prop += f"\t\t\tclass_type={class_type},\n"
        reg_prop += f"\t\t\tmultiplier={multiplier},\n"
        reg_prop += f"\t\t\tunit={unit},\n"
        reg_prop += f"\t\t\tdescription='''{description}''',\n"
        reg_prop += f"\t\t\tprofiles=[]\n"
        reg_prop += f"\t\t)\n"
    return reg_prop


def get_class_spec_code(name, parent):
    code = ""
    if parent is None:
        code += f"class {name}(Base):\n"
        code += f"\tdef __init__(self, rdfid, tpe, resources=list(), class_replacements=dict()):\n"
        code += (f"\t\tBase.__init__(self, rdfid=rdfid, tpe=tpe, resources=resources, "
                 f"class_replacements=class_replacements)\n\n")
    else:
        code += f"class {name}({parent}):\n"  # Could be 2 parent?
        code += f"\tdef __init__(self, rdfid='', tpe='{name}'):\n"
        code += f"\t\t{parent}.__init__(self, rdfid, tpe)\n\n"
    return code


def get_attribute_code(attributes):
    code = ""
    for attribute in attributes:
        attr_name = attribute["name"]
        default_value = ""
        if "datatype" in attribute:  # Attribute
            data_type = attribute["datatype"]
            if data_type == "Float" or data_type == "Decimal":
                default_value = "float = None"
            elif data_type == "Integer":
                default_value = "int = None"
            elif data_type == "DateTime" or data_type == "MonthDay":
                default_value = "datetime.datetime | None = None"
                code += f"\t\timport datetime\n"
            elif data_type == "Boolean":
                default_value = "bool = None"
            elif data_type == "String":
                default_value = "str = None"
            code += f"\t\tself.{attr_name}: {default_value}\n"
        elif "range" in attribute:  # Association
            assoc_range = attribute["range"]
            default_value = assoc_range + " | None = None"
            code += (
                f"\t\tfrom GridCalEngine.IO.cim.cgmes.{cgmes_folder}.devices.{get_format_name(assoc_range, True)} "
                f"import {assoc_range}\n")
            code += f"\t\tself.{attr_name}: {default_value}\n"
        elif "enum_range_list" in attribute:  # Enumeration
            enum_range_list = attribute["enum_range_list"]
            enum_name = enum_range_list[0].split("#")[1]
            enum_name_list.update({enum_name})
            class_enum_list.update({enum_name})
            default_value = enum_range_list[0].split("#")[1] + " = None"
            code += f"\t\tself.{attr_name}: {default_value}\n"
    return code


def write_class_list_and_dict(name):
    """
    Generate a list and a dictionary for the classes that generated.
    :param name: Class name list.
    :return:
    """
    # List generation
    list_code = ""
    for class_name in name:
        list_code += f"self.{class_name}_list: List[{class_name}] = list()\n"
    with open(f"{cgmes_folder}/class_list.py", 'w') as file:
        file.write(list_code)

    # Dictionary generation
    dict_code = "self.class_dict = {\n"
    for class_name in name:
        dict_code += f"\t'{class_name}': {class_name},\n"
    dict_code += "}"
    with open(f"{cgmes_folder}/class_dict_list.py", 'w') as file:
        file.write(dict_code)

    name_list_code = ""
    for class_name in name:
        name_list_code += f"{class_name}\n"
    with open(f"{cgmes_folder}/implemented_classes.txt", 'w') as file:
        file.write(name_list_code)


def write_class_import(name):
    import_code = ""
    for class_name in name:
        import_code += \
            (f"from GridCalEngine.IO.cim.cgmes.{cgmes_folder}.devices.{get_format_name(class_name, True)} import "
             f"{class_name}\n")
    with open(f"{cgmes_folder}/class_imports.py", 'w') as file:
        file.write(import_code)


def import_enum_data():
    from rdflib import Graph, RDF, RDFS, OWL

    enum_dict = dict()

    current_directory = os.path.dirname(__file__)
    rdf_serialization = Graph()
    rdf_serialization.parse(source=os.path.join(current_directory,
                                                "RDFS/cgmes_v2_4_15/CGMES_v2.4.15_RDFSSerialisation.ttl"),
                            format="ttl")
    rdf_serialization.parse(source=os.path.join(current_directory,
                                                "RDFS/cgmes_v3_0_0/CGMES_v3.0.0_RDFSSerialisation.ttl"),
                            format="ttl")

    for s_i, p_i, o_i in rdf_serialization.triples((None, RDF.type, RDFS.Class)):
        if str(s_i).split("#")[1] == "RdfEnum":
            for enum in rdf_serialization.objects(s_i, OWL.members):
                enum_wns = str(enum).split("#")[-1]
                enum_class, enum_value = enum_wns.split('.')
                if enum_class not in enum_dict:
                    enum_dict[enum_class] = set()
                enum_dict[enum_class].add(enum_value)

    return enum_dict


def write_enums():
    code = "\nfrom enum import Enum\n\n\n"
    enums_to_generate = import_enum_data()
    for enum_class, enum_values in enums_to_generate.items():
        enum_name = enum_class

        code += f"class {enum_name}(Enum):\n"
        for value in enum_values:
            code += f"\t{value} = '{value}'\n"
        code += f"""
    def __str__(self):
        return '{enum_name}.' + str(self.value)

    def __repr__(self):
        return str(self)

    @staticmethod
    def argparse(s):
        try:
            return {enum_name}[s]
        except KeyError:
            return s

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))
        """
        code += "\n\n"
    with open(f"{cgmes_folder}/cgmes_enums.py", 'w') as file:
        with open("copyright_text.txt", "r") as cr_file:
            file.write(cr_file.read())
        file.write(code)


def write_assoc_dict(assoc_datatype_dict: dict):
    dict_code = "self.association_inverse_dict = {\n"
    for name, tpe in assoc_datatype_dict.items():
        dict_code += f"\t'{name}': '{tpe}',\n"
    dict_code += "}"
    with open(f"{cgmes_folder}/assoc_inverse_dict.py", 'w') as file:
        file.write(dict_code)
