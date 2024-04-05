"""
This script generates the getters and setters of new objects lists in the MultiCircuit Object
"""


def generate_declaraion(list_name, cls_name):
    return f'''
self.{list_name}: List[dev.{cls_name}] = list()
    '''


def list_getter(list_name, plural_name, cls_name):
    return f'''
def get_{plural_name}(self) -> List[dev.{cls_name}]:
    """
    List of {plural_name}
    :return: List[dev.{cls_name}]
    """
    return self.{list_name}
    '''


def list_size(list_name, plural_name):
    return f'''
def get_{plural_name}_number(self) -> int:
    """
    Size of the list of {plural_name}
    :return: size of {plural_name}
    """
    return len(self.{list_name})
    '''


def element_getter(list_name, singular_name, cls_name):
    return f'''
def get_{singular_name}_at(self, i: int) -> dev.{cls_name}:
    """
    Get {singular_name} at i
    :param i: index
    :return: {cls_name}
    """
    return self.{list_name}[i]
    '''


def names_getter(list_name, singular_name):
    return f'''
def get_{singular_name}_names(self) -> StrVec:
    """
    Array of {singular_name} names
    :return: StrVec
    """
    return np.array([e.name for e in self.{list_name}])
    '''


def element_adder(list_name, singular_name, cls_name):
    return f'''
def add_{singular_name}(self, obj: dev.{cls_name}):
    """
    Add a {cls_name} object
    :param obj: {cls_name} instance
    """

    if self.time_profile is not None:
        obj.create_profiles(self.time_profile)
    self.{list_name}.append(obj)
    '''


def element_deleter(list_name, singular_name, cls_name):
    return f'''
def delete_{singular_name}(self, obj: dev.{cls_name}) -> None:
    """
    Add a {cls_name} object
    :param obj: {cls_name} instance
    """

    self.{list_name}.remove(obj)
    '''


if __name__ == '__main__':
    entries = [
        {"singular_name": "modelling_authority",
         "plural_name": "modelling_authorities",
         "cls_name": "ModellingAuthority", },
    ]

    with open('code_generated.py', "w") as f:

        for entry in entries:
            f.write(generate_declaraion(list_name=entry["plural_name"],
                                        cls_name=entry["cls_name"]))

        for entry in entries:
            f.write("\n")
            f.write("# " + "-" * 118 + "\n")
            f.write(f"# {entry['singular_name']}\n")
            f.write("# " + "-" * 118 + "\n\n")

            f.write(list_getter(list_name=entry["plural_name"],
                                plural_name=entry["plural_name"],
                                cls_name=entry["cls_name"]) + "\n")

            f.write(list_size(list_name=entry["plural_name"],
                              plural_name=entry["plural_name"]) + "\n")

            f.write(element_getter(list_name=entry["plural_name"],
                                   singular_name=entry["singular_name"],
                                   cls_name=entry["cls_name"]) + "\n")

            f.write(names_getter(list_name=entry["plural_name"],
                                 singular_name=entry["singular_name"]) + "\n")

            f.write(element_adder(list_name=entry["plural_name"],
                                  singular_name=entry["singular_name"],
                                  cls_name=entry["cls_name"]) + "\n")

            f.write(element_deleter(list_name=entry["plural_name"],
                                    singular_name=entry["singular_name"],
                                    cls_name=entry["cls_name"]) + "\n")
