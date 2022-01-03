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
            elm.active = bus.active_prof.astype(np.uintc)
        else:
            elm.active = np.ones(ntime, dtype=np.uintc) * int(bus.active)

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
            load.active = elm.active_prof.astype(np.uintc)
            load.P = elm.P_prof
            load.Q = elm.Q_prof
        else:
            load.active = np.ones(ntime, dtype=np.uintc) * int(elm.active)

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
            load.active = elm.active_prof.astype(np.uintc)
            load.P = -elm.P_prof
            load.Q = -elm.Q_prof
        else:
            load.active = np.ones(ntime, dtype=np.uintc) * int(elm.active)

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
            sh.active = elm.active_prof.astype(np.uintc)
            sh.G = elm.G_prof
            sh.B = elm.B_prof
        else:
            sh.active = np.ones(ntime, dtype=np.uintc) * int(elm.active)

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
                            P0=elm.P,
                            Q0=0,
                            Vset0=elm.Vset)

        gen.generation_cost = elm.Cost

        if time_series:
            gen.active = elm.active_prof.astype(np.uintc)
            gen.P = elm.P_prof
            gen.vset = elm.Vset_prof
        else:
            gen.active = np.ones(ntime, dtype=np.uintc) * int(elm.active)
            gen.P = np.ones(ntime, dtype=float) * elm.P
            gen.vset = np.ones(ntime, dtype=float) * elm.Vset

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
                          P0=elm.P,
                          Q0=0,
                          Vset0=elm.Vset)

        gen.soc_max = elm.max_soc
        gen.soc_min = elm.min_soc
        gen.charge_efficiency = elm.charge_efficiency
        gen.discharge_efficiency = elm.discharge_efficiency
        gen.generation_cost = elm.Cost

        if time_series:
            gen.active = elm.active_prof.astype(np.uintc)
            gen.P = elm.P_prof
            gen.vset = elm.Vset_prof
        else:
            gen.active = np.ones(ntime, dtype=np.uintc) * int(elm.active)
            gen.P = np.ones(ntime, dtype=float) * elm.P
            gen.vset = np.ones(ntime, dtype=float) * elm.Vset

        btgCircuit.add_battery(gen)


def add_btg_line(circuit: MultiCircuit, btgCircuit: btg.Circuit, bus_dict, time_series: bool, ntime=1):
    """

    :param circuit:
    :param btgCircuit:
    :param bus_dict:
    :param time_series:
    :param ntime:
    :return:
    """

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        lne = btg.AcLine(uuid=elm.idtag,
                         name=elm.name,
                         node_from=bus_dict[elm.bus_from.idtag],
                         node_to=bus_dict[elm.bus_to.idtag],
                         time_steps=ntime,
                         length=elm.length,
                         rate=elm.rate,
                         active_default=elm.active,
                         r1=elm.R,
                         x1=elm.X,
                         b1=elm.B)

        lne.monitor_loading = np.ones(ntime, dtype=np.uintc) * int(elm.monitor_loading)
        lne.contingency_enabled = np.ones(ntime, dtype=np.uintc) * int(elm.contingency_enabled)

        if time_series:
            lne.active = elm.active_prof.astype(np.uintc)
            lne.rates = elm.rate_prof
            lne.contingency_rates = elm.rate_prof * elm.contingency_factor

        btgCircuit.add_ac_line(lne)


def get_transformer_data(circuit: MultiCircuit, btgCircuit: btg.Circuit, bus_dict, time_series: bool, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    for i, elm in enumerate(circuit.transformers2w):
        tr2 = btg.Transformer2WAll(uuid=elm.idtag,
                                   name=elm.name,
                                   node_from=bus_dict[elm.bus_from.idtag],
                                   node_to=bus_dict[elm.bus_to.idtag],
                                   time_steps=ntime,
                                   HV=elm.HV,
                                   LV=elm.LV,
                                   rate=elm.rate,
                                   active_default=elm.active,
                                   r1=elm.R,
                                   x1=elm.X,
                                   g1=elm.G,
                                   b1=elm.B)

        tr2.monitor_loading = np.ones(ntime, dtype=np.uintc) * int(elm.monitor_loading)
        tr2.contingency_enabled = np.ones(ntime, dtype=np.uintc) * int(elm.contingency_enabled)

        if time_series:
            tr2.active = elm.active_prof.astype(np.uintc)
            tr2.rates = elm.rate_prof
            tr2.contingency_rates = elm.rate_prof * elm.contingency_factor
            tr2.tap = elm.tap_module_prof
            tr2.phase = elm.angle_prof
        else:
            tr2.tap = np.ones(ntime, dtype=float) * elm.tap_module
            tr2.phase = np.ones(ntime, dtype=float) * elm.angle

        btgCircuit.add_transformer_all(tr2)


def get_vsc_data(circuit: MultiCircuit, btgCircuit: btg.Circuit, bus_dict, time_series: bool, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    for i, elm in enumerate(circuit.vsc_devices):
        vsc = btg.VSC(uuid=elm.idtag,
                      name=elm.name,
                      node_from=bus_dict[elm.bus_from.idtag],
                      node_to=bus_dict[elm.bus_to.idtag],
                      time_steps=ntime,
                      rate=elm.rate,
                      active_default=elm.active,
                      r1=elm.R1,
                      x1=elm.X1,
                      g0=elm.G0,
                      beq=elm.Beq,
                      beq_max=elm.Beq_max,
                      beq_min=elm.Beq_min,
                      k=elm.k,
                      tap=elm.m,
                      tap_max=elm.m_max,
                      tap_min=elm.m_min,
                      phase=elm.theta,
                      phase_max=elm.theta_max,
                      phase_min=elm.theta_min,
                      Pf_set=elm.Pdc_set,
                      vac_set=elm.Vac_set,
                      vdc_set=elm.Vdc_set,
                      kdp=elm.kdp,
                      alpha1=elm.alpha1,
                      alpha2=elm.alpha2,
                      alpha3=elm.alpha3)

        vsc.monitor_loading = np.ones(ntime, dtype=np.uintc) * int(elm.monitor_loading)
        vsc.contingency_enabled = np.ones(ntime, dtype=np.uintc) * int(elm.contingency_enabled)

        if time_series:
            vsc.active = elm.active_prof.astype(np.uintc)
            vsc.rates = elm.rate_prof
            vsc.contingency_rates = elm.rate_prof * elm.contingency_factor

        btgCircuit.add_vsc(vsc)


def get_dc_line_data(circuit: MultiCircuit, btgCircuit: btg.Circuit, bus_dict, time_series: bool, ntime=1):
    """

    :param circuit:
    :param btgCircuit:
    :param bus_dict:
    :param time_series:
    :param ntime:
    :return:
    """
    # Compile the lines
    for i, elm in enumerate(circuit.dc_lines):
        lne = btg.DcLine(uuid=elm.idtag,
                         name=elm.name,
                         node_from=bus_dict[elm.bus_from.idtag],
                         node_to=bus_dict[elm.bus_to.idtag],
                         time_steps=ntime,
                         length=elm.length,
                         rate=elm.rate,
                         active_default=elm.active,
                         r1=elm.R)

        lne.monitor_loading = np.ones(ntime, dtype=np.uintc) * int(elm.monitor_loading)
        lne.contingency_enabled = np.ones(ntime, dtype=np.uintc) * int(elm.contingency_enabled)

        if time_series:
            lne.active = elm.active_prof.astype(np.uintc)
            lne.rates = elm.rate_prof
            lne.contingency_rates = elm.rate_prof * elm.contingency_factor

        btgCircuit.add_dc_line(lne)


def get_hvdc_data(circuit: MultiCircuit, btgCircuit: btg.Circuit, bus_dict, time_series: bool, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :param bus_types:
    :param time_series:
    :param ntime:
    :param opf_results:
    :return:
    """

    cmode_dict = {HvdcControlType.type_0_free: btg.HvdcControlType.free,
                  HvdcControlType.type_1_Pset: btg.HvdcControlType.Pdc}

    for i, elm in enumerate(circuit.hvdc_lines):
        hvdc = btg.HvdcLine(uuid=elm.idtag,
                            name=elm.name,
                            node_from=bus_dict[elm.bus_from.idtag],
                            node_to=bus_dict[elm.bus_to.idtag],
                            time_steps=ntime,
                            length=elm.length,
                            rate=elm.rate,
                            active_default=elm.active,
                            r1=elm.r,
                            Pset=elm.Pset,
                            v_set_f=elm.Vset_f,
                            v_set_t=elm.Vset_t,
                            control_mode=cmode_dict[elm.control_mode])

        # hvdc.monitor_loading = elm.monitor_loading
        # hvdc.contingency_enabled = elm.contingency_enabled

        if time_series:
            hvdc.active = elm.active_prof.astype(np.uintc)
            hvdc.rates = elm.rate_prof
            hvdc.v_set_f = elm.Vset_f_prof
            hvdc.v_set_t = elm.Vset_t_prof
            hvdc.contingency_rates = elm.rate_prof * elm.contingency_factor
        else:
            hvdc.contingency_rates = elm.rate * elm.contingency_factor

        btgCircuit.add_hvdc_line(hvdc)


def to_bentayga(circuit: MultiCircuit, time_series: bool):

    ntime = circuit.get_time_number() if time_series else 1
    if ntime == 0:
        ntime = 1

    btgCircuit = btg.Circuit(uuid=circuit.idtag, name=circuit.name, time_steps=ntime)

    bus_dict = add_btg_buses(circuit, btgCircuit, time_series, ntime)
    add_btg_loads(circuit, btgCircuit, bus_dict, time_series, ntime)
    add_btg_static_generators(circuit, btgCircuit, bus_dict, time_series, ntime)
    add_btg_shunts(circuit, btgCircuit, bus_dict, time_series, ntime)
    add_btg_generators(circuit, btgCircuit, bus_dict, time_series, ntime)
    get_battery_data(circuit, btgCircuit, bus_dict, time_series, ntime)
    add_btg_line(circuit, btgCircuit, bus_dict, time_series, ntime)
    get_transformer_data(circuit, btgCircuit, bus_dict, time_series, ntime)
    get_vsc_data(circuit, btgCircuit, bus_dict, time_series, ntime)
    get_dc_line_data(circuit, btgCircuit, bus_dict, time_series, ntime)
    get_hvdc_data(circuit, btgCircuit, bus_dict, time_series, ntime)

    return btgCircuit


def bentayga_pf(circuit: MultiCircuit, gridcal_pf_options, time_series=False):

    btgCircuit = to_bentayga(circuit, time_series=time_series)

    pf_options = btg.PowerFlowOptions(btg.PowerFlowSolvers.NewtonRaphson,
                                      tolerance=gridcal_pf_options.tolerance,
                                      max_iter=gridcal_pf_options.max_iter)
    logger = btg.Logger()
    pf_res = btg.run_power_flow(circuit=btgCircuit, options=pf_options, logger=logger, parallel=True)

    return pf_res
