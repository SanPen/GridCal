def create_getter(profile_name):
    return f'''
@property
def {profile_name}(self) -> Profile:
    """
    Cost profile
    :return: Profile
    """
    return self._{profile_name}
    '''


def create_setter(profile_name):
    return f'''
@{profile_name}.setter
def {profile_name}(self, val: Union[Profile, np.ndarray]):
    if isinstance(val, Profile):
        self._{profile_name} = val
    elif isinstance(val, np.ndarray):
        self._{profile_name}.set(arr=val)
    else:
        raise Exception(str(type(val)) + 'not supported to be set into a {profile_name}')
    '''


data = [

    ('Bus', 'active_prof'),
    ('Generator', 'active_prof'),
    ('Generator', 'Cost_prof'),
    ('Generator', 'P_prof'),
    ('Generator', 'Pf_prof'),
    ('Generator', 'Vset_prof'),
    ('Generator', 'Cost2_prof'),
    ('Generator', 'Cost0_prof'),
    ('Generator', 'active_prof'),
    ('Generator', 'Cost_prof'),
    ('Generator', 'P_prof'),
    ('Generator', 'Pf_prof'),
    ('Generator', 'Vset_prof'),
    ('Generator', 'Cost2_prof'),
    ('Generator', 'Cost0_prof'),
    ('Load', 'active_prof'),
    ('Load', 'Cost_prof'),
    ('Load', 'P_prof'),
    ('Load', 'Q_prof'),
    ('Load', 'Ir_prof'),
    ('Load', 'Ii_prof'),
    ('Load', 'G_prof'),
    ('Load', 'B_prof'),
    ('Static Generator', 'active_prof'),
    ('Static Generator', 'Cost_prof'),
    ('Static Generator', 'P_prof'),
    ('Static Generator', 'Q_prof'),
    ('External grid', 'active_prof'),
    ('External grid', 'Cost_prof'),
    ('External grid', 'P_prof'),
    ('External grid', 'Q_prof'),
    ('External grid', 'Vm_prof'),
    ('External grid', 'Va_prof'),
    ('Shunt', 'active_prof'),
    ('Shunt', 'Cost_prof'),
    ('Shunt', 'G_prof'),
    ('Shunt', 'B_prof'),
    ('Line', 'active_prof'),
    ('Line', 'rate_prof'),
    ('Line', 'contingency_factor_prof'),
    ('Line', 'Cost_prof'),
    ('Line', 'temp_oper_prof'),
    ('DC line', 'active_prof'),
    ('DC line', 'rate_prof'),
    ('DC line', 'contingency_factor_prof'),
    ('DC line', 'Cost_prof'),
    ('Transformer', 'active_prof'),
    ('Transformer', 'rate_prof'),
    ('Transformer', 'contingency_factor_prof'),
    ('Transformer', 'Cost_prof'),
    ('Transformer', 'tap_module_prof'),
    ('Transformer', 'tap_phase_prof'),
    ('Transformer', 'temp_oper_prof'),
    ('Winding', 'active_prof'),
    ('Winding', 'rate_prof'),
    ('Winding', 'contingency_factor_prof'),
    ('Winding', 'Cost_prof'),
    ('Winding', 'tap_module_prof'),
    ('Winding', 'tap_phase_prof'),
    ('Winding', 'temp_oper_prof'),
    ('Bus', 'active_prof'),
    ('Winding', 'active_prof'),
    ('Winding', 'rate_prof'),
    ('Winding', 'contingency_factor_prof'),
    ('Winding', 'Cost_prof'),
    ('Winding', 'tap_module_prof'),
    ('Winding', 'tap_phase_prof'),
    ('Winding', 'temp_oper_prof'),
    ('Winding', 'active_prof'),
    ('Winding', 'rate_prof'),
    ('Winding', 'contingency_factor_prof'),
    ('Winding', 'Cost_prof'),
    ('Winding', 'tap_module_prof'),
    ('Winding', 'tap_phase_prof'),
    ('Winding', 'temp_oper_prof'),
    ('Winding', 'active_prof'),
    ('Winding', 'rate_prof'),
    ('Winding', 'contingency_factor_prof'),
    ('Winding', 'Cost_prof'),
    ('Winding', 'tap_module_prof'),
    ('Winding', 'tap_phase_prof'),
    ('Winding', 'temp_oper_prof'),
    ('Transformer3W', 'active_prof'),
    ('HVDC Line', 'active_prof'),
    ('HVDC Line', 'rate_prof'),
    ('HVDC Line', 'contingency_factor_prof'),
    ('HVDC Line', 'Cost_prof'),
    ('HVDC Line', 'Pset_prof'),
    ('HVDC Line', 'angle_droop_prof'),
    ('HVDC Line', 'Vset_f_prof'),
    ('HVDC Line', 'Vset_t_prof'),
    ('VSC', 'active_prof'),
    ('VSC', 'rate_prof'),
    ('VSC', 'contingency_factor_prof'),
    ('VSC', 'Cost_prof'),
    ('UPFC', 'active_prof'),
    ('UPFC', 'rate_prof'),
    ('UPFC', 'contingency_factor_prof'),
    ('UPFC', 'Cost_prof'),
    ('Fluid node', 'spillage_cost_prof'),
    ('Fluid node', 'inflow_prof'),
    ('Fuel', 'cost_prof'),
    ('Emission', 'cost_prof'),
]

groups = dict()
for cls_name, name in data:
    lst = groups.get(cls_name)

    if lst is None:
        groups[cls_name] = [name]
    else:
        lst.append(name)

with open("getters_and_setters_code.py", "w") as f:

    for cls_name, names in groups.items():
        f.write("\n")
        f.write("# " + "-" * 118 + "\n")
        f.write(f"# {cls_name}\n")
        f.write("# " + "-" * 118 + "\n")

        for name in names:
            f.write(create_getter(profile_name=name))
            f.write(create_setter(profile_name=name))
