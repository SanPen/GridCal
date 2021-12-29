from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Devices.enumerations import ConverterControlType, TransformerControlType
from GridCal.Engine.Devices import *

try:
    import bentayga as btg
    BENTAYGA_AVAILABLE = True
    print('Bentayga v' + btg.get_version())
except ImportError:
    BENTAYGA_AVAILABLE = False
    print('Bentayga is not available')


def add_btg_buses(circuit: MultiCircuit, btgCircuit: btg.Circuit, time_series: bool, ntime=1):
    """

    :param circuit:
    :param btgCircuit:
    :param ntime:
    :return:
    """
    areas_dict = {elm: k for k, elm in enumerate(circuit.areas)}
    bus_dict = dict()

    for i, bus in enumerate(circuit.buses):

        elm = btg.Node(uuid=bus.idtag, name=bus.name, time_steps=ntime,
                       is_slack=bus.is_slack, is_dc=bus.is_dc,
                       nominal_voltage=bus.Vnom)

        if time_series and ntime > 1:
            elm.active = bus.active_prof.astype(int)
        else:
            elm.active = bus.active

        btgCircuit.add_node(elm)
        bus_dict[elm.uuid] = elm

    return bus_dict


def add_btg_loads(circuit: MultiCircuit, btgCircuit: btg.Circuit, bus_dict, time_series: bool, ntime=1):
    """

    :param circuit:
    :param btgCircuit:
    :param bus_dict:
    :param time_series:
    :param ntime:
    :return:
    """

    devices = circuit.get_loads()
    for k, elm in enumerate(devices):

        load = btg.Load(uuid=elm.idtag,
                        name=elm.name,
                        bus=bus_dict[elm.bus.idtag],
                        time_steps=ntime,
                        P0=elm.P,
                        Q0=elm.Q)

        if time_series:
            load.active = elm.active_prof
            load.P = elm.P_prof
            load.Q = elm.Q_prof
        else:
            load.active = elm.active

        btgCircuit.add_load(load)


def add_btg_static_generators(circuit: MultiCircuit, btgCircuit: btg.Circuit, bus_dict, time_series: bool, ntime=1):
    """

    :param circuit:
    :param btgCircuit:
    :param bus_dict:
    :param time_series:
    :param ntime:
    :return:
    """
    devices = circuit.get_static_generators()
    for k, elm in enumerate(devices):

        load = btg.Load(uuid=elm.idtag,
                        name=elm.name,
                        bus=bus_dict[elm.bus.idtag],
                        time_steps=ntime,
                        P0=-elm.P,
                        Q0=-elm.Q)

        if time_series:
            load.active = elm.active_prof
            load.P = -elm.P_prof
            load.Q = -elm.Q_prof
        else:
            load.active = elm.active

        btgCircuit.add_load(load)


def add_btg_shunts(circuit: MultiCircuit, btgCircuit: btg.Circuit, bus_dict, time_series: bool, ntime=1):
    """

    :param circuit:
    :param btgCircuit:
    :param bus_dict:
    :param time_series:
    :param ntime:
    :return:
    """
    devices = circuit.get_shunts()
    for k, elm in enumerate(devices):

        sh = btg.ShuntFixed(uuid=elm.idtag,
                            name=elm.name,
                            bus=bus_dict[elm.bus.idtag],
                            time_steps=ntime,
                            G0=elm.G,
                            B0=elm.B)

        if time_series:
            sh.active = elm.active_prof
            sh.G = elm.G_prof
            sh.B = elm.B_prof
        else:
            sh.active = elm.active

        btgCircuit.add_shunt_fixed(sh)


def add_btg_generators(circuit: MultiCircuit, btgCircuit: btg.Circuit, bus_dict, time_series: bool, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :param Vbus:
    :param logger:
    :param opf_results:
    :param time_series:
    :param opf:
    :param ntime:
    :return:
    """
    devices = circuit.get_generators()

    for k, elm in enumerate(devices):

        gen = btg.Generator(uuid=elm.idtag,
                            name=elm.name,
                            bus=bus_dict[elm.bus.idtag],
                            time_steps=ntime,
                            P0=elm.G,
                            Q0=elm.B,
                            Vset0=elm.vset)

        gen.generation_cost = elm.Cost

        if time_series:
            gen.active = elm.active_prof
            gen.P = elm.P_prof
            gen.vset = elm.Vset_prof
        else:
            gen.active = elm.active
            gen.P = elm.P
            gen.vset = elm.Vset

        btgCircuit.add_generator(gen)


def get_battery_data(circuit: MultiCircuit, btgCircuit: btg.Circuit, bus_dict, time_series: bool, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :param Vbus:
    :param logger:
    :param opf_results:
    :param time_series:
    :param opf:
    :param ntime:
    :return:
    """
    devices = circuit.get_batteries()

    for k, elm in enumerate(devices):

        gen = btg.Battery(uuid=elm.idtag,
                          name=elm.name,
                          bus=bus_dict[elm.bus.idtag],
                          time_steps=ntime,
                          capacity=elm.Enom,
                          P0=elm.G,
                          Q0=elm.B,
                          Vset0=elm.vset)

        gen.soc_max = elm.max_soc
        gen.soc_min = elm.min_soc
        gen.charge_efficiency = elm.charge_efficiency
        gen.discharge_efficiency = elm.discharge_efficiency
        gen.generation_cost = elm.Cost

        if time_series:
            gen.active = elm.active_prof
            gen.P = elm.P_prof
            gen.vset = elm.Vset_prof
        else:
            gen.active = elm.active
            gen.P = elm.P
            gen.vset = elm.Vset

        btgCircuit.add_battery(gen)


def get_line_data(circuit: MultiCircuit, bus_dict,
                  apply_temperature, branch_tolerance_mode: BranchImpedanceMode, time_series=False, ntime=1):

    """

    :param circuit:
    :param bus_dict:
    :param apply_temperature:
    :param branch_tolerance_mode:
    :return:
    """

    nc = LinesData(nline=len(circuit.lines), nbus=len(circuit.buses))

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        nc.line_names[i] = elm.name

        if apply_temperature:
            nc.line_R[i] = elm.R_corrected
        else:
            nc.line_R[i] = elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            nc.line_R[i] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            nc.line_R[i] *= (1 + elm.tolerance / 100.0)

        nc.line_X[i] = elm.X
        nc.line_B[i] = elm.B
        nc.C_line_bus[i, f] = 1
        nc.C_line_bus[i, t] = 1

    return nc


def get_transformer_data(circuit: MultiCircuit, bus_dict, time_series=False, ntime=1):
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


def get_vsc_data(circuit: MultiCircuit, bus_dict, time_series=False, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    nc = VscData(nvsc=len(circuit.vsc_devices), nbus=len(circuit.buses), ntime=ntime)

    # VSC
    for i, elm in enumerate(circuit.vsc_devices):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        # vsc values
        nc.names[i] = elm.name
        nc.R1[i] = elm.R1
        nc.X1[i] = elm.X1
        nc.G0[i] = elm.G0
        nc.Beq[i] = elm.Beq
        nc.m[i] = elm.m
        nc.theta[i] = elm.theta
        # nc.Inom[i] = (elm.rate / nc.Sbase) / np.abs(nc.Vbus[f])
        nc.Pfset[i] = elm.Pdc_set
        nc.Qtset[i] = elm.Qac_set
        nc.Vac_set[i] = elm.Vac_set
        nc.Vdc_set[i] = elm.Vdc_set
        nc.control_mode[i] = elm.control_mode

        nc.C_vsc_bus[i, f] = 1
        nc.C_vsc_bus[i, t] = 1

    return nc


def get_upfc_data(circuit: MultiCircuit, bus_dict, time_series=False, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    data = UpfcData(nelm=len(circuit.upfc_devices), nbus=len(circuit.buses), ntime=ntime)

    # UPFC
    for i, elm in enumerate(circuit.upfc_devices):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        # vsc values
        data.names[i] = elm.name
        data.Rl[i] = elm.Rl
        data.Xl[i] = elm.Xl
        data.Bl[i] = elm.Bl

        data.Rs[i] = elm.Rs
        data.Xs[i] = elm.Xs

        data.Rsh[i] = elm.Rsh
        data.Xsh[i] = elm.Xsh

        data.Pset[i] = elm.Pfset
        data.Qset[i] = elm.Qfset
        data.Vsh[i] = elm.Vsh

        data.C_elm_bus[i, f] = 1
        data.C_elm_bus[i, t] = 1

    return data


def get_dc_line_data(circuit: MultiCircuit, bus_dict,
                     apply_temperature, branch_tolerance_mode: BranchImpedanceMode, time_series=False, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :param apply_temperature:
    :param branch_tolerance_mode:
    :return:
    """
    data = DcLinesData(ndcline=len(circuit.dc_lines), nbus=len(circuit.buses), ntime=ntime)

    # DC-lines
    for i, elm in enumerate(circuit.dc_lines):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        # dc line values
        data.dc_line_names[i] = elm.name

        if apply_temperature:
            data.dc_line_R[i] = elm.R_corrected
        else:
            data.dc_line_R[i] = elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.dc_line_R[i] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.dc_line_R[i] *= (1 + elm.tolerance / 100.0)

        data.dc_line_impedance_tolerance[i] = elm.tolerance
        data.C_dc_line_bus[i, f] = 1
        data.C_dc_line_bus[i, t] = 1
        data.dc_F[i] = f
        data.dc_T[i] = t

        # Thermal correction
        data.dc_line_temp_base[i] = elm.temp_base
        data.dc_line_temp_oper[i] = elm.temp_oper
        data.dc_line_alpha[i] = elm.alpha

    return data


def get_branch_data(circuit: MultiCircuit, bus_dict, Vbus, apply_temperature,
                    branch_tolerance_mode: BranchImpedanceMode,
                    time_series=False, opf=False, ntime=1,
                    opf_results: "OptimalPowerFlowResults" = None):
    """

    :param circuit:
    :param bus_dict:
    :param Vbus: Array of bus voltages to be modified
    :param apply_temperature:
    :param branch_tolerance_mode:
    :param time_series:
    :param opf:
    :param ntime:
    :return:
    """
    nline = len(circuit.lines)
    ntr = len(circuit.transformers2w)
    nvsc = len(circuit.vsc_devices)
    nupfc = len(circuit.upfc_devices)
    ndcline = len(circuit.dc_lines)
    nbr = nline + ntr + nvsc + ndcline + nupfc

    if opf:
        data = BranchOpfData(nbr=nbr, nbus=len(circuit.buses), ntime=ntime)
    else:
        data = BranchData(nbr=nbr, nbus=len(circuit.buses), ntime=ntime)

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        # generic stuff
        data.branch_names[i] = elm.name

        if time_series:
            data.branch_active[i, :] = elm.active_prof
            data.branch_rates[i, :] = elm.rate_prof
            data.branch_contingency_rates[i, :] = elm.rate_prof * elm.contingency_factor

            if opf:
                data.branch_cost[i, :] = elm.Cost_prof

        else:
            data.branch_active[i] = elm.active
            data.branch_rates[i] = elm.rate
            data.branch_contingency_rates[i] = elm.rate * elm.contingency_factor

            if opf:
                data.branch_cost[i] = elm.Cost

        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]
        data.C_branch_bus_f[i, f] = 1
        data.C_branch_bus_t[i, t] = 1
        data.F[i] = f
        data.T[i] = t

        if apply_temperature:
            data.R[i] = elm.R_corrected
        else:
            data.R[i] = elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.R[i] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.R[i] *= (1 + elm.tolerance / 100.0)

        data.X[i] = elm.X
        data.B[i] = elm.B

        data.contingency_enabled[i] = int(elm.contingency_enabled)
        data.monitor_loading[i] = int(elm.monitor_loading)

    # 2-winding transformers
    for i, elm in enumerate(circuit.transformers2w):
        ii = i + nline

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.branch_names[ii] = elm.name

        if time_series:
            data.branch_active[ii, :] = elm.active_prof
            data.branch_rates[ii, :] = elm.rate_prof
            data.branch_contingency_rates[ii, :] = elm.rate_prof * elm.contingency_factor

            if opf:
                data.branch_cost[ii, :] = elm.Cost_prof
        else:
            data.branch_active[ii] = elm.active
            data.branch_rates[ii] = elm.rate
            data.branch_contingency_rates[ii] = elm.rate * elm.contingency_factor

            if opf:
                data.branch_cost[ii, :] = elm.Cost

        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

        data.R[ii] = elm.R
        data.X[ii] = elm.X
        data.G[ii] = elm.G
        data.B[ii] = elm.B

        if time_series:
            if opf_results is not None:
                data.m[ii] = elm.tap_module
                data.theta[ii, :] = opf_results.phase_shift[:, ii]
            else:
                data.m[ii] = elm.tap_module_prof
                data.theta[ii, :] = elm.angle_prof
        else:
            if opf_results is not None:
                data.m[ii] = elm.tap_module
                data.theta[ii] = opf_results.phase_shift[ii]
            else:
                data.m[ii] = elm.tap_module
                data.theta[ii] = elm.angle

        data.m_min[ii] = elm.tap_module_min
        data.m_max[ii] = elm.tap_module_max
        data.theta_min[ii] = elm.angle_min
        data.theta_max[ii] = elm.angle_max

        data.Pfset[ii] = elm.Pset

        data.control_mode[ii] = elm.control_mode
        data.tap_f[ii], data.tap_t[ii] = elm.get_virtual_taps()

        data.contingency_enabled[ii] = int(elm.contingency_enabled)
        data.monitor_loading[ii] = int(elm.monitor_loading)

        if elm.control_mode == TransformerControlType.Vt:
            Vbus[t] = elm.vset

        elif elm.control_mode == TransformerControlType.PtVt:  # 2a:Vdc
            Vbus[t] = elm.vset

    # VSC
    for i, elm in enumerate(circuit.vsc_devices):
        ii = i + nline + ntr

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.branch_names[ii] = elm.name

        if time_series:
            data.branch_active[ii, :] = elm.active_prof
            data.branch_rates[ii, :] = elm.rate_prof
            data.branch_contingency_rates[ii, :] = elm.rate_prof * elm.contingency_factor

            if opf:
                data.branch_cost[ii, :] = elm.Cost_prof
        else:
            data.branch_active[ii] = elm.active
            data.branch_rates[ii] = elm.rate
            data.branch_contingency_rates[ii] = elm.rate * elm.contingency_factor

            if opf:
                data.branch_cost[ii] = elm.Cost

        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

        data.R[ii] = elm.R1
        data.X[ii] = elm.X1
        data.G0[ii] = elm.G0
        data.Beq[ii] = elm.Beq
        data.m[ii] = elm.m
        data.m_max[ii] = elm.m_max
        data.m_min[ii] = elm.m_min
        data.alpha1[ii] = elm.alpha1
        data.alpha2[ii] = elm.alpha2
        data.alpha3[ii] = elm.alpha3
        data.k[ii] = elm.k  # 0.8660254037844386  # sqrt(3)/2 (do not confuse with k droop)

        if time_series:
            if opf_results is not None:
                data.theta[ii, :] = opf_results.phase_shift[:, ii]
            else:
                data.theta[ii, :] = elm.theta
        else:
            if opf_results is not None:
                data.theta[ii] = opf_results.phase_shift[ii]
            else:
                data.theta[ii] = elm.theta

        data.theta_min[ii] = elm.theta_min
        data.theta_max[ii] = elm.theta_max
        data.Pfset[ii] = elm.Pdc_set
        data.Qtset[ii] = elm.Qac_set
        data.Kdp[ii] = elm.kdp
        data.vf_set[ii] = elm.Vac_set
        data.vt_set[ii] = elm.Vdc_set
        data.control_mode[ii] = elm.control_mode
        data.contingency_enabled[ii] = int(elm.contingency_enabled)
        data.monitor_loading[ii] = int(elm.monitor_loading)

        '''
        type_0_free = '0:Free'
        type_I_1 = '1:Vac'
        type_I_2 = '2:Pdc+Qac'
        type_I_3 = '3:Pdc+Vac'
        type_II_4 = '4:Vdc+Qac'
        type_II_5 = '5:Vdc+Vac'
        type_III_6 = '6:Droop+Qac'
        type_III_7 = '7:Droop+Vac'
        '''

        if elm.control_mode == ConverterControlType.type_I_1:  # 1a:Vac
            Vbus[t] = elm.Vac_set

        elif elm.control_mode == ConverterControlType.type_I_3:  # 3:Pdc+Vac
            Vbus[t] = elm.Vac_set

        elif elm.control_mode == ConverterControlType.type_II_4:  # 4:Vdc+Qac
            Vbus[f] = elm.Vdc_set

        elif elm.control_mode == ConverterControlType.type_II_5:  # 5:Vdc+Vac
            Vbus[f] = elm.Vdc_set
            Vbus[t] = elm.Vac_set

        elif elm.control_mode == ConverterControlType.type_III_7:  # 7:Droop+Vac
            Vbus[t] = elm.Vac_set

        elif elm.control_mode == ConverterControlType.type_IV_I:  # 8:Vdc
            Vbus[f] = elm.Vdc_set

    # DC-lines
    for i, elm in enumerate(circuit.dc_lines):
        ii = i + nline + ntr + nvsc

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.branch_names[ii] = elm.name
        data.branch_dc[ii] = 1

        if time_series:
            data.branch_active[ii, :] = elm.active_prof
            data.branch_rates[ii, :] = elm.rate_prof
            data.branch_contingency_rates[ii, :] = elm.rate_prof * elm.contingency_factor

            if opf:
                data.branch_cost[ii, :] = elm.Cost_prof
        else:
            data.branch_active[ii] = elm.active
            data.branch_rates[ii] = elm.rate
            data.branch_contingency_rates[ii] = elm.rate * elm.contingency_factor

            if opf:
                data.branch_cost[ii] = elm.Cost

        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

        data.contingency_enabled[ii] = int(elm.contingency_enabled)
        data.monitor_loading[ii] = int(elm.monitor_loading)

        if apply_temperature:
            data.R[ii] = elm.R_corrected
        else:
            data.R[ii] = elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.R[ii] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.R[ii] *= (1 + elm.tolerance / 100.0)

    # UPFC
    for i, elm in enumerate(circuit.upfc_devices):
        ii = i + nline + ntr + nvsc + ndcline

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.branch_names[ii] = elm.name

        if time_series:
            data.branch_active[ii, :] = elm.active_prof
            data.branch_rates[ii, :] = elm.rate_prof
            data.branch_contingency_rates[ii, :] = elm.rate_prof * elm.contingency_factor

            if opf:
                data.branch_cost[ii, :] = elm.Cost_prof
        else:
            data.branch_active[ii] = elm.active
            data.branch_rates[ii] = elm.rate
            data.branch_contingency_rates[ii] = elm.rate * elm.contingency_factor

            if opf:
                data.branch_cost[ii] = elm.Cost

        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

        data.R[ii] = elm.Rl
        data.X[ii] = elm.Xl
        data.Beq[ii] = elm.Bl

        data.Pfset[ii] = elm.Pfset

        data.contingency_enabled[ii] = int(elm.contingency_enabled)
        data.monitor_loading[ii] = int(elm.monitor_loading)

    return data


def get_hvdc_data(circuit: MultiCircuit, bus_dict, bus_types, time_series=False, ntime=1,
                  opf_results: "OptimalPowerFlowResults" = None):
    """

    :param circuit:
    :param bus_dict:
    :param bus_types:
    :param time_series:
    :param ntime:
    :param opf_results:
    :return:
    """
    data = HvdcData(nhvdc=len(circuit.hvdc_lines), nbus=len(circuit.buses), ntime=ntime)

    # HVDC
    for i, elm in enumerate(circuit.hvdc_lines):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        # hvdc values
        data.names[i] = elm.name
        data.dispatchable[i] = int(elm.dispatchable)

        if time_series:
            data.active[i, :] = elm.active_prof
            data.rate[i, :] = elm.rate_prof

            if opf_results is not None:
                data.Pf[i, :] = -opf_results.hvdc_Pf[:, i]
                data.Pt[i, :] = opf_results.hvdc_Pf[:, i]
            else:
                data.Pf[i, :], data.Pt[i, :] = elm.get_from_and_to_power()

            data.Vset_f[i, :] = elm.Vset_f_prof
            data.Vset_t[i, :] = elm.Vset_t_prof
        else:
            data.active[i] = elm.active
            data.rate[i] = elm.rate

            if opf_results is not None:
                data.Pf[i] = -opf_results.hvdc_Pf[i]
                data.Pt[i] = opf_results.hvdc_Pf[i]
            else:
                data.Pf[i], data.Pt[i] = elm.get_from_and_to_power()

            data.Vset_f[i] = elm.Vset_f
            data.Vset_t[i] = elm.Vset_t

        data.loss_factor[i] = elm.loss_factor
        data.r[i] = elm.r
        data.control_mode[i] = elm.control_mode

        data.Qmin_f[i] = elm.Qmin_f
        data.Qmax_f[i] = elm.Qmax_f
        data.Qmin_t[i] = elm.Qmin_t
        data.Qmax_t[i] = elm.Qmax_t

        # hack the bus types to believe they are PV
        if elm.active:
            bus_types[f] = BusMode.PV.value
            bus_types[t] = BusMode.PV.value

        # the the bus-hvdc line connectivity
        data.C_hvdc_bus_f[i, f] = 1
        data.C_hvdc_bus_t[i, t] = 1

    return data
