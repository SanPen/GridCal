from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Simulations.PowerFlow.jacobian_based_power_flow import Jacobian
from GridCal.Engine.Core.common_functions import compile_types
from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults

from GridCal.Engine.Core.DataStructures import *


def get_bus_data(circuit: MultiCircuit):
    """

    :param circuit:
    :return:
    """
    bus_data = BusData(nbus=len(circuit.buses))

    for i, bus in enumerate(circuit.buses):

        # bus parameters
        bus_data.bus_names[i] = bus.name
        bus_data.bus_active[i] = bus.active
        bus_data.bus_types[i] = bus.determine_bus_type().value

    return bus_data


def get_load_data(circuit: MultiCircuit, bus_dict, opf_results: OptimalPowerFlowResults = None):
    """

    :param circuit:
    :param bus_dict:
    :param opf_results:
    :return:
    """

    devices = circuit.get_loads()

    data = LoadData(nload=len(devices), nbus=len(circuit.buses))

    for i_ld, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.load_names[i_ld] = elm.name
        data.load_active[i_ld] = elm.active

        if opf_results is None:
            data.load_s[i_ld] = complex(elm.P, elm.Q)
        else:
            data.load_s[i_ld] = complex(elm.P, elm.Q) - opf_results.load_shedding[i_ld]

        data.C_bus_load[i, i_ld] = 1

    return data


def get_static_generator_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    devices = circuit.get_static_generators()

    data = StaticGeneratorData(nstagen=len(devices), nbus=len(circuit.buses))

    for i_stagen, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.static_generator_names[i_stagen] = elm.name
        data.static_generator_active[i_stagen] = elm.active
        data.static_generator_s[i_stagen] = complex(elm.P, elm.Q)

        data.C_bus_static_generator[i, i_stagen] = 1

    return data


def get_shunt_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    devices = circuit.get_shunts()

    data = ShuntData(nshunt=len(devices), nbus=len(circuit.buses))

    for i_sh, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.shunt_names[i_sh] = elm.name
        data.shunt_active[i_sh] = elm.active
        data.shunt_admittance[i_sh] = complex(elm.G, elm.B)

        data.C_bus_shunt[i, i_sh] = 1

    return data


def get_generator_data(circuit: MultiCircuit, bus_dict, Vbus, logger: Logger,
                       opf_results: OptimalPowerFlowResults = None):
    """

    :param circuit:
    :param bus_dict:
    :param Vbus:
    :param logger:
    :param opf_results:
    :return:
    """
    devices = circuit.get_generators()

    data = GeneratorData(ngen=len(devices), nbus=len(circuit.buses))

    for i_gen, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.generator_names[i_gen] = elm.name
        data.generator_pf[i_gen] = elm.Pf
        data.generator_v[i_gen] = elm.Vset
        data.generator_qmin[i_gen] = elm.Qmin
        data.generator_qmax[i_gen] = elm.Qmax
        data.generator_active[i_gen] = elm.active
        data.generator_controllable[i_gen] = elm.is_controlled
        data.generator_installed_p[i_gen] = elm.Snom

        if opf_results is None:
            data.generator_p[i_gen] = elm.P
        else:
            data.generator_p[i_gen] = opf_results.generators_power[i_gen] - opf_results.generation_shedding[i_gen]

        data.C_bus_gen[i, i_gen] = 1

        if Vbus[i].real == 1.0:
            Vbus[i] = complex(elm.Vset, 0)
        elif elm.Vset != Vbus[i]:
            logger.append('Different set points at ' + elm.bus.name + ': ' + str(elm.Vset) + ' !=' + str(Vbus[i]))

    return data


def get_battery_data(circuit: MultiCircuit, bus_dict, Vbus, logger: Logger,
                     opf_results: OptimalPowerFlowResults = None):
    """

    :param circuit:
    :param bus_dict:
    :param Vbus:
    :param logger:
    :param opf_results:
    :return:
    """
    devices = circuit.get_batteries()

    data = BatteryData(nbatt=len(devices), nbus=len(circuit.buses))

    for i_batt, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.battery_names[i_batt] = elm.name

        data.battery_pf[i_batt] = elm.Pf
        data.battery_v[i_batt] = elm.Vset
        data.battery_qmin[i_batt] = elm.Qmin
        data.battery_qmax[i_batt] = elm.Qmax
        data.battery_active[i_batt] = elm.active
        data.battery_controllable[i_batt] = elm.is_controlled
        data.battery_installed_p[i_batt] = elm.Snom

        if opf_results is None:
            data.battery_p[i_batt] = elm.P
        else:
            data.battery_p[i_batt] = opf_results.battery_power[i_batt]

        data.C_bus_batt[i, i_batt] = 1

        if Vbus[i].real == 1.0:
            Vbus[i] = complex(elm.Vset, 0)
        elif elm.Vset != Vbus[i]:
            logger.append('Different set points at ' + elm.bus.name + ': ' + str(elm.Vset) + ' !=' + str(Vbus[i]))

    return data


def get_line_data(circuit: MultiCircuit, bus_dict):

    nc = LinesData(nline=len(circuit.lines), nbus=len(circuit.buses))

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        # impedance
        nc.line_names[i] = elm.name
        nc.line_R[i] = elm.R
        nc.line_X[i] = elm.X
        nc.line_B[i] = elm.B
        nc.line_impedance_tolerance[i] = elm.tolerance
        nc.C_line_bus[i, f] = 1
        nc.C_line_bus[i, t] = 1

        # Thermal correction
        nc.line_temp_base[i] = elm.temp_base
        nc.line_temp_oper[i] = elm.temp_oper
        nc.line_alpha[i] = elm.alpha

    return nc


def get_transformer_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    data = TransformerData(ntr=len(circuit.transformers2w), nbus=len(circuit.buses))

    # 2-winding transformers
    for i, elm in enumerate(circuit.transformers2w):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        # impedance
        data.tr_names[i] = elm.name
        data.tr_R[i] = elm.R
        data.tr_X[i] = elm.X
        data.tr_G[i] = elm.G
        data.tr_B[i] = elm.B

        data.C_tr_bus[i, f] = 1
        data.C_tr_bus[i, t] = 1

        # tap changer
        data.tr_tap_mod[i] = elm.tap_module
        data.tr_tap_ang[i] = elm.angle
        data.tr_is_bus_to_regulated[i] = elm.bus_to_regulated
        data.tr_tap_position[i] = elm.tap_changer.tap
        data.tr_min_tap[i] = elm.tap_changer.min_tap
        data.tr_max_tap[i] = elm.tap_changer.max_tap
        data.tr_tap_inc_reg_up[i] = elm.tap_changer.inc_reg_up
        data.tr_tap_inc_reg_down[i] = elm.tap_changer.inc_reg_down
        data.tr_vset[i] = elm.vset
        data.tr_control_mode[i] = elm.control_mode

        data.tr_bus_to_regulated_idx[i] = t if elm.bus_to_regulated else f

        # virtual taps for transformers where the connection voltage is off
        data.tr_tap_f[i], data.tr_tap_t[i] = elm.get_virtual_taps()

    return data


def get_vsc_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    nc = VscData(nvsc=len(circuit.vsc_converters), nbus=len(circuit.buses))

    # VSC
    for i, elm in enumerate(circuit.vsc_converters):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        # vsc values
        nc.vsc_names[i] = elm.name
        nc.vsc_R1[i] = elm.R1
        nc.vsc_X1[i] = elm.X1
        nc.vsc_G0[i] = elm.G0
        nc.vsc_Beq[i] = elm.Beq
        nc.vsc_m[i] = elm.m
        nc.vsc_theta[i] = elm.theta
        # nc.vsc_Inom[i] = (elm.rate / nc.Sbase) / np.abs(nc.Vbus[f])
        nc.vsc_Pset[i] = elm.Pset
        nc.vsc_Qset[i] = elm.Qset
        nc.vsc_Vac_set[i] = elm.Vac_set
        nc.vsc_Vdc_set[i] = elm.Vdc_set
        nc.vsc_control_mode[i] = elm.control_mode

        nc.C_vsc_bus[i, f] = 1
        nc.C_vsc_bus[i, t] = 1

    return nc


def get_dc_line_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    nc = DcLinesData(ndcline=len(circuit.dc_lines), nbus=len(circuit.buses))

    # DC-lines
    for i, elm in enumerate(circuit.dc_lines):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        # dc line values
        nc.dc_line_names[i] = elm.name
        nc.dc_line_R[i] = elm.R
        nc.dc_line_impedance_tolerance[i] = elm.tolerance
        nc.C_dc_line_bus[i, f] = 1
        nc.C_dc_line_bus[i, t] = 1
        nc.dc_F[i] = f
        nc.dc_T[i] = t

        # Thermal correction
        nc.dc_line_temp_base[i] = elm.temp_base
        nc.dc_line_temp_oper[i] = elm.temp_oper
        nc.dc_line_alpha[i] = elm.alpha

    return nc


def get_branch_data(circuit: MultiCircuit, bus_dict):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    nline = len(circuit.lines)
    ntr = len(circuit.transformers2w)
    nvsc = len(circuit.vsc_converters)
    ndcline = len(circuit.dc_lines)

    data = BranchData(nbr=nline + ntr + nvsc + ndcline, nbus=len(circuit.buses))

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        # generic stuff
        data.branch_names[i] = elm.name
        data.branch_active[i] = elm.active
        data.branch_rates[i] = elm.rate
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]
        data.C_branch_bus_f[i, f] = 1
        data.C_branch_bus_t[i, t] = 1
        data.F[i] = f
        data.T[i] = t

    # 2-winding transformers
    for i, elm in enumerate(circuit.transformers2w):
        ii = i + nline

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.branch_names[ii] = elm.name
        data.branch_active[ii] = elm.active
        data.branch_rates[ii] = elm.rate
        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

    # VSC
    for i, elm in enumerate(circuit.vsc_converters):
        ii = i + nline + ntr

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.branch_names[ii] = elm.name
        data.branch_active[ii] = elm.active
        data.branch_rates[ii] = elm.rate
        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

    # DC-lines
    for i, elm in enumerate(circuit.dc_lines):
        ii = i + nline + ntr + nvsc

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.branch_names[ii] = elm.name
        data.branch_active[ii] = elm.active
        data.branch_rates[ii] = elm.rate
        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

    return data


def get_hvdc_data(circuit: MultiCircuit, bus_dict, bus_types):
    """

    :param circuit:
    :param bus_dict:
    :param bus_types:
    :return:
    """
    data = HvdcData(nhvdc=len(circuit.hvdc_lines), nbus=len(circuit.buses))

    # HVDC
    for i, elm in enumerate(circuit.hvdc_lines):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        # hvdc values
        data.hvdc_names[i] = elm.name
        data.hvdc_active[i] = elm.active
        data.hvdc_rate[i] = elm.rate

        data.hvdc_Pf[i], data.hvdc_Pt[i] = elm.get_from_and_to_power()

        data.hvdc_loss_factor[i] = elm.loss_factor
        data.hvdc_Vset_f[i] = elm.Vset_f
        data.hvdc_Vset_t[i] = elm.Vset_t
        data.hvdc_Qmin_f[i] = elm.Qmin_f
        data.hvdc_Qmax_f[i] = elm.Qmax_f
        data.hvdc_Qmin_t[i] = elm.Qmin_t
        data.hvdc_Qmax_t[i] = elm.Qmax_t

        # hack the bus types to believe they are PV
        bus_types[f] = BusMode.PV.value
        bus_types[t] = BusMode.PV.value

        # the the bus-hvdc line connectivity
        data.C_hvdc_bus_f[i, f] = 1
        data.C_hvdc_bus_t[i, t] = 1

    return data

