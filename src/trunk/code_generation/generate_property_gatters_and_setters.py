def create_getter(prop_name, tpe):
    return f'''
@property
def {prop_name}(self) -> {tpe}:
    """
    {prop_name} getter
    :return: {tpe}
    """
    return self._{prop_name}
    '''


def create_setter(prop_name, tpe):
    return f'''
@{prop_name}.setter
def {prop_name}(self, val: {tpe}):
    """
    {prop_name} getter
    :param val: value
    """
    if isinstance(val, {tpe}):
        self._{prop_name} = val
    else:
        raise Exception(str(type(val)) + 'not supported to be set into a {prop_name} of type {tpe}')
    '''


"""
self.area: Union[Area, None] = area
self.zone: Union[Zone, None] = zone
self.country: Union[Country, None] = country
self.community: Union[Community, None] = community
self.region: Union[Region, None] = region
self.municipality: Union[Municipality, None] = municipality
"""

data = [

    # ('area', 'Union[Area, None]'),
    # ('zone', 'Union[Zone, None]'),
    # ('country', 'Union[Country, None]'),
    # ('community', 'Union[Community, None]'),
    # ('region', 'Union[Region, None]'),
    ('voltage_level', 'Union[VoltageLevel, None]'),
]

with open("getters_and_setters_code.py", "w") as f:
    for prop_name, tpe in data:
        f.write("\n")
        f.write("# " + "-" * 118 + "\n")
        f.write(f"# {prop_name}\n")
        f.write("# " + "-" * 118 + "\n")

        f.write(create_getter(prop_name=prop_name, tpe=tpe))
        f.write(create_setter(prop_name=prop_name, tpe=tpe))
