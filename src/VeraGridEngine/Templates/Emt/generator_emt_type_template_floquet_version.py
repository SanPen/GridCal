from __future__ import annotations

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.Emt.stamp_synchronous_generator_emt_template import get_stamp_synchronous_machine_6th_order_emt_template
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowReferenceType


def get_floquet_generator_template_emt(vf: VarFactory, name: str = "floquet_generator_emt_template") -> EmtModelTemplate:
    """
    Build one reduced EMT synchronous-generator wrapper for Floquet comparison.

    This version is intentionally closer to the electromechanical benchmark goal:
    it keeps the sixth-order synchronous machine and removes the exciter, governor,
    and stabilizer dynamic blocks from the comparison model. Mechanical torque and
    field voltage are frozen to the PF seed through runtime parameters, which makes
    the resulting Floquet spectrum much more directly comparable to the reduced RMS
    small-signal modes.

    :param vf: Shared variable factory.
    :param name: Template name.
    :return: EMT model template.
    """
    template: EmtModelTemplate = EmtModelTemplate(name=name)
    template.tpe = DeviceType.GeneratorDevice
    template.name = name
    template.block.name = name

    v_a_in = vf.add_var(name=f"v_A_{name}", reference=VarPowerFlowReferenceType.v_A)
    v_b_in = vf.add_var(name=f"v_B_{name}", reference=VarPowerFlowReferenceType.v_B)
    v_c_in = vf.add_var(name=f"v_C_{name}", reference=VarPowerFlowReferenceType.v_C)
    tm_seed = vf.add_var(name=f"Tm_{name}", shared_reference="Tm_reference")
    vf_seed = vf.add_var(name=f"Vf_{name}", shared_reference="v_f_reference")

    gen_mdl: Block = get_stamp_synchronous_machine_6th_order_emt_template(vf=vf, name=f"{name}_gen").block

    # Bind wrapper voltage inputs directly into the machine child block.
    gen_mdl.update_model(gen_mdl.in_vars[0], v_a_in)
    gen_mdl.update_model(gen_mdl.in_vars[1], v_b_in)
    gen_mdl.update_model(gen_mdl.in_vars[2], v_c_in)
    gen_mdl.update_model(gen_mdl.in_vars[3], tm_seed)
    gen_mdl.update_model(gen_mdl.in_vars[4], vf_seed)

    template.block.children.append(gen_mdl)
    template.block.in_vars = [v_a_in, v_b_in, v_c_in]
    template.block.out_vars = [gen_mdl.out_vars[0], gen_mdl.out_vars[1], gen_mdl.out_vars[2]]

    template.block.external_mapping = {
        VarPowerFlowReferenceType.v_A: v_a_in,
        VarPowerFlowReferenceType.v_B: v_b_in,
        VarPowerFlowReferenceType.v_C: v_c_in,
        VarPowerFlowReferenceType.i_A: gen_mdl.out_vars[0],
        VarPowerFlowReferenceType.i_B: gen_mdl.out_vars[1],
        VarPowerFlowReferenceType.i_C: gen_mdl.out_vars[2],
        VarPowerFlowReferenceType.d_v_A: gen_mdl.external_mapping[VarPowerFlowReferenceType.d_v_A],
        VarPowerFlowReferenceType.d_v_B: gen_mdl.external_mapping[VarPowerFlowReferenceType.d_v_B],
        VarPowerFlowReferenceType.d_v_C: gen_mdl.external_mapping[VarPowerFlowReferenceType.d_v_C],
        VarPowerFlowReferenceType.P_A: gen_mdl.external_mapping[VarPowerFlowReferenceType.P_A],
        VarPowerFlowReferenceType.Q_A: gen_mdl.external_mapping[VarPowerFlowReferenceType.Q_A],
        VarPowerFlowReferenceType.P_B: gen_mdl.external_mapping[VarPowerFlowReferenceType.P_B],
        VarPowerFlowReferenceType.Q_B: gen_mdl.external_mapping[VarPowerFlowReferenceType.Q_B],
        VarPowerFlowReferenceType.P_C: gen_mdl.external_mapping[VarPowerFlowReferenceType.P_C],
        VarPowerFlowReferenceType.Q_C: gen_mdl.external_mapping[VarPowerFlowReferenceType.Q_C],
    }

    # Seed runtime parameters for the frozen actuator channels.
    template.block.event_dict[tm_seed] = vf.add_const(1.0)
    template.block.event_dict[vf_seed] = vf.add_const(1.0)

    return template
