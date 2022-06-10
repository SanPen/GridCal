# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import os.path

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Devices.enumerations import ConverterControlType, TransformerControlType
from GridCal.Engine.Devices import *
from GridCal.Engine.basic_structures import Logger, SolverType, ReactivePowerControlMode, TapsControlMode
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.IO.file_system import get_create_gridcal_folder
import GridCal.Engine.basic_structures as bs

try:
    import bentayga as btg

    # activate
    if not btg.is_license_activated():
        btg_license = os.path.join(get_create_gridcal_folder(), 'bentayga.lic')
        if os.path.exists(btg_license):

            try:
                btg.activate_license(btg_license)
                if btg.is_license_activated():
                    BENTAYGA_AVAILABLE = True
                else:
                    print('Bentayga v' + btg.get_version(),
                          "installed, tried to activate with {} but the license did not work :/".format(btg_license))
                    BENTAYGA_AVAILABLE = False
            except RuntimeError:
                print("Bentayga: Error reading the license file :(")
                BENTAYGA_AVAILABLE = False
        else:
            print('Bentayga v' + btg.get_version(), "installed but not licensed")
            BENTAYGA_AVAILABLE = False
    else:
        print('Bentayga v' + btg.get_version())
        BENTAYGA_AVAILABLE = True

except ImportError:
    BENTAYGA_AVAILABLE = False
    print('Bentayga is not available')

# numpy integer type for bentayga's uword
BINT = np.ulonglong


def add_btg_buses(circuit: MultiCircuit, btg_circuit: "btg.Circuit", time_series: bool, ntime: int=1):
    """
    Convert the buses to bentayga buses
    :param circuit: GridCal circuit
    :param btg_circuit: bentayga circuit
    :param time_series: compile the time series from GridCal? otherwise, just the snapshot
    :param ntime: number of time steps
    :return: bus dictionary buses[uuid] -> Bus
    """
    areas_dict = {elm: k for k, elm in enumerate(circuit.areas)}
    bus_dict = dict()

    for i, bus in enumerate(circuit.buses):

        elm = btg.Node(uuid=bus.idtag,
                       name=bus.name,
                       time_steps=ntime,
                       is_slack=bus.is_slack,
                       is_dc=bus.is_dc,
                       nominal_voltage=bus.Vnom)

        if time_series and ntime > 1:
            elm.active = bus.active_prof.astype(BINT)
        else:
            elm.active = np.ones(ntime, dtype=BINT) * int(bus.active)

        btg_circuit.add_node(elm)
        bus_dict[elm.uuid] = elm

    return bus_dict


def add_btg_loads(circuit: MultiCircuit, btg_circuit: "btg.Circuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param btg_circuit: bentayga circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to bentayga bus object
    :param ntime: number of time steps
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
            load.active = elm.active_prof.astype(BINT)
            load.P = elm.P_prof
            load.Q = elm.Q_prof
        else:
            load.active = np.ones(ntime, dtype=BINT) * int(elm.active)

        btg_circuit.add_load(load)


def add_btg_static_generators(circuit: MultiCircuit, btg_circuit: "btg.Circuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param btg_circuit: bentayga circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to bentayga bus object
    :param ntime: number of time steps
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
            load.active = elm.active_prof.astype(BINT)
            load.P = -elm.P_prof
            load.Q = -elm.Q_prof
        else:
            load.active = np.ones(ntime, dtype=BINT) * int(elm.active)

        btg_circuit.add_load(load)


def add_btg_shunts(circuit: MultiCircuit, btg_circuit: "btg.Circuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param btg_circuit: bentayga circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to bentayga bus object
    :param ntime: number of time steps
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
            sh.active = elm.active_prof.astype(BINT)
            sh.G = elm.G_prof
            sh.B = elm.B_prof
        else:
            sh.active = np.ones(ntime, dtype=BINT) * int(elm.active)

        btg_circuit.add_shunt_fixed(sh)


def add_btg_generators(circuit: MultiCircuit, btg_circuit: "btg.Circuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param btg_circuit: bentayga circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to bentayga bus object
    :param ntime: number of time steps
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
        gen.Qmin = elm.Qmin
        gen.Qmax = elm.Qmax
        gen.Pmin = elm.Pmin
        gen.Pmax = elm.Pmax
        gen.generation_cost = elm.Cost

        if time_series:
            gen.active = elm.active_prof.astype(BINT)
            gen.P = elm.P_prof
            gen.vset = elm.Vset_prof
        else:
            gen.active = np.ones(ntime, dtype=BINT) * int(elm.active)
            gen.P = np.ones(ntime, dtype=float) * elm.P
            gen.vset = np.ones(ntime, dtype=float) * elm.Vset

        btg_circuit.add_generator(gen)


def get_battery_data(circuit: MultiCircuit, btg_circuit: "btg.Circuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param btg_circuit: bentayga circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to bentayga bus object
    :param ntime: number of time steps
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
        gen.Qmin = elm.Qmin
        gen.Qmax = elm.Qmax
        gen.Pmin = elm.Pmin
        gen.Pmax = elm.Pmax

        if time_series:
            gen.active = elm.active_prof.astype(BINT)
            gen.P = elm.P_prof
            gen.vset = elm.Vset_prof
        else:
            gen.active = np.ones(ntime, dtype=BINT) * int(elm.active)
            gen.P = np.ones(ntime, dtype=float) * elm.P
            gen.vset = np.ones(ntime, dtype=float) * elm.Vset

        btg_circuit.add_battery(gen)


def add_btg_line(circuit: MultiCircuit, btg_circuit: "btg.Circuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param btg_circuit: bentayga circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to bentayga bus object
    :param ntime: number of time steps
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

        lne.monitor_loading = np.ones(ntime, dtype=BINT) * int(elm.monitor_loading)
        lne.contingency_enabled = np.ones(ntime, dtype=BINT) * int(elm.contingency_enabled)

        if time_series:
            lne.active = elm.active_prof.astype(BINT)
            lne.rates = elm.rate_prof
            lne.contingency_rates = elm.rate_prof * elm.contingency_factor

        btg_circuit.add_ac_line(lne)


def get_transformer_data(circuit: MultiCircuit, btg_circuit: "btg.Circuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param btg_circuit: bentayga circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to bentayga bus object
    :param ntime: number of time steps
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

        tr2.monitor_loading = np.ones(ntime, dtype=BINT) * int(elm.monitor_loading)
        tr2.contingency_enabled = np.ones(ntime, dtype=BINT) * int(elm.contingency_enabled)

        if time_series:
            tr2.active = elm.active_prof.astype(BINT)
            tr2.rates = elm.rate_prof
            tr2.contingency_rates = elm.rate_prof * elm.contingency_factor
            tr2.tap = elm.tap_module_prof
            tr2.phase = elm.angle_prof
        else:
            tr2.tap = np.ones(ntime, dtype=float) * elm.tap_module
            tr2.phase = np.ones(ntime, dtype=float) * elm.angle

        btg_circuit.add_transformer_all(tr2)


def get_vsc_data(circuit: MultiCircuit, btg_circuit: "btg.Circuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param btg_circuit: bentayga circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to bentayga bus object
    :param ntime: number of time steps
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

        vsc.monitor_loading = np.ones(ntime, dtype=BINT) * int(elm.monitor_loading)
        vsc.contingency_enabled = np.ones(ntime, dtype=BINT) * int(elm.contingency_enabled)

        if time_series:
            vsc.active = elm.active_prof.astype(BINT)
            vsc.rates = elm.rate_prof
            vsc.contingency_rates = elm.rate_prof * elm.contingency_factor

        btg_circuit.add_vsc(vsc)


def get_dc_line_data(circuit: MultiCircuit, btg_circuit: "btg.Circuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param btg_circuit: bentayga circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to bentayga bus object
    :param ntime: number of time steps
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

        lne.monitor_loading = np.ones(ntime, dtype=BINT) * int(elm.monitor_loading)
        lne.contingency_enabled = np.ones(ntime, dtype=BINT) * int(elm.contingency_enabled)

        if time_series:
            lne.active = elm.active_prof.astype(BINT)
            lne.rates = elm.rate_prof
            lne.contingency_rates = elm.rate_prof * elm.contingency_factor

        btg_circuit.add_dc_line(lne)


def get_hvdc_data(circuit: MultiCircuit, btg_circuit: "btg.Circuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param btg_circuit: bentayga circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to bentayga bus object
    :param ntime: number of time steps
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
                            min_firing_angle_f=elm.min_firing_angle_f,
                            min_firing_angle_t=elm.min_firing_angle_t,
                            max_firing_angle_f=elm.max_firing_angle_f,
                            max_firing_angle_t=elm.max_firing_angle_t,
                            control_mode=cmode_dict[elm.control_mode])

        # hvdc.monitor_loading = elm.monitor_loading
        # hvdc.contingency_enabled = elm.contingency_enabled

        if time_series:
            hvdc.active = elm.active_prof.astype(BINT)
            hvdc.rates = elm.rate_prof
            hvdc.v_set_f = elm.Vset_f_prof
            hvdc.v_set_t = elm.Vset_t_prof
            hvdc.contingency_rates = elm.rate_prof * elm.contingency_factor
            hvdc.angle_droop = elm.angle_droop_prof
        else:
            hvdc.contingency_rates = elm.rate * elm.contingency_factor
            hvdc.angle_droop = elm.angle_droop

        btg_circuit.add_hvdc_line(hvdc)


def to_bentayga(circuit: MultiCircuit, time_series: bool):
    """
    Convert GridCal circuit to Bentayga
    :param circuit: MultiCircuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :return: btg.Circuit instance
    """
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


class FakeAdmittances:

    def __init__(self):
        self.Ybus = None
        self.Yf = None
        self.Yt = None


def get_snapshots_from_bentayga(circuit: MultiCircuit):

    from GridCal.Engine.Core.snapshot_pf_data import SnapshotData

    btgCircuit = to_bentayga(circuit, time_series=False)

    btg_data_lst = btg.compile_at(btgCircuit, t=0)

    data_lst = list()

    for btg_data in btg_data_lst:

        data = SnapshotData(nbus=0,
                            nline=0,
                            ndcline=0,
                            ntr=0,
                            nvsc=0,
                            nupfc=0,
                            nhvdc=0,
                            nload=0,
                            ngen=0,
                            nbatt=0,
                            nshunt=0,
                            nstagen=0,
                            sbase=0,
                            ntime=1)

        data.Vbus_ = btg_data.Vbus.reshape(-1, 1)
        data.Sbus_ = btg_data.Sbus.reshape(-1, 1)
        data.Ibus_ = btg_data.Ibus
        data.branch_data.branch_names = np.array(btg_data.branch_data.names)
        data.branch_data.tap_f = btg_data.branch_data.virtual_tap_f
        data.branch_data.tap_t = btg_data.branch_data.virtual_tap_t

        data.bus_data.bus_names = np.array(btg_data.bus_data.names)

        data.Admittances = FakeAdmittances()
        data.Admittances.Ybus = btg_data.admittances.Ybus
        data.Admittances.Yf = btg_data.admittances.Yf
        data.Admittances.Yt = btg_data.admittances.Yt

        data.Bbus_ = btg_data.linear_admittances.Bbus
        data.Bf_ = btg_data.linear_admittances.Bf

        data.Yseries_ = btg_data.split_admittances.Yseries
        data.Yshunt_ = btg_data.split_admittances.Yshunt

        data.B1_ = btg_data.fast_decoupled_admittances.B1
        data.B2_ = btg_data.fast_decoupled_admittances.B2

        data.Cf_ = btg_data.Cf
        data.Ct_ = btg_data.Ct

        data.bus_data.bus_types = [x.value for x in btg_data.bus_data.bus_types]
        data.pq_ = btg_data.bus_types_data.pq
        data.pv_ = btg_data.bus_types_data.pv
        data.vd_ = btg_data.bus_types_data.vd
        data.pqpv_ = btg_data.bus_types_data.pqpv

        data.original_bus_idx = btg_data.bus_data.original_indices
        data.original_branch_idx = btg_data.branch_data.original_indices

        data.Qmax_bus_ = btg_data.Qmax_bus
        data.Qmin_bus_ = btg_data.Qmin_bus

        data.iPfsh = btg_data.control_indices.iPfsh
        data.iQfma = btg_data.control_indices.iQfma
        data.iBeqz = btg_data.control_indices.iBeqz
        data.iBeqv = btg_data.control_indices.iBeqv
        data.iVtma = btg_data.control_indices.iVtma
        data.iQtma = btg_data.control_indices.iQtma
        data.iPfdp = btg_data.control_indices.iPfdp
        data.iVscL = btg_data.control_indices.iVscL
        data.VfBeqbus = btg_data.control_indices.iVfBeqBus
        data.Vtmabus = btg_data.control_indices.iVtmaBus

        data_lst.append(data)

    return data_lst


def get_bentayga_pf_options(opt: PowerFlowOptions):
    """
    Translate GridCal power flow options to Bentayga power flow options
    :param opt:
    :return:
    """
    solver_dict = {SolverType.NR: btg.PowerFlowSolvers.NewtonRaphson,
                   SolverType.DC: btg.PowerFlowSolvers.LinearDc,
                   # SolverType.HELM: nn.NativeSolverType.HELM,
                   # SolverType.IWAMOTO: nn.NativeSolverType.IWAMOTO,
                   SolverType.LM: btg.PowerFlowSolvers.LevenbergMarquardt,
                   # SolverType.LACPF: nn.NativeSolverType.LACPF,
                   SolverType.FASTDECOUPLED: btg.PowerFlowSolvers.FastDecoupled
                   }

    q_control_dict = {ReactivePowerControlMode.NoControl: btg.QControlMode.NoControl,
                      ReactivePowerControlMode.Direct: btg.QControlMode.Direct}

    if opt.solver_type in solver_dict.keys():
        solver_type = solver_dict[opt.solver_type]
    else:
        solver_type = btg.PowerFlowSolvers.NewtonRaphson

    return btg.PowerFlowOptions(solver=solver_type,
                                tolerance=opt.tolerance,
                                max_iter=opt.max_iter,
                                retry_with_other_methods=opt.retry_with_other_methods,
                                q_control_mode=q_control_dict[opt.control_Q])


def bentayga_pf(circuit: MultiCircuit, opt: PowerFlowOptions, time_series=False):
    """
    Bentayga power flow
    :param circuit: MultiCircuit instance
    :param opt: Power Flow Options
    :param time_series: Compile with GridCal time series?
    :return: Bentayga Power flow results object
    """
    btgCircuit = to_bentayga(circuit, time_series=time_series)

    pf_options = get_bentayga_pf_options(opt)
    logger = btg.Logger()
    pf_res = btg.run_power_flow(circuit=btgCircuit,
                                options=pf_options,
                                logger=logger,
                                parallel=True)

    return pf_res


def bentayga_linear_matrices(circuit: MultiCircuit, distributed_slack=False):
    """
    Bentayga linear analysis
    :param circuit: MultiCircuit instance
    :param distributed_slack: distribute the PTDF slack
    :return: Bentayga LinearAnalysisMatrices object
    """
    btg_circuit = to_bentayga(circuit, time_series=False)
    lin_mat = btg.compute_linear_matrices_at(t=0,
                                             circuit=btg_circuit,
                                             distributed_slack=distributed_slack)

    return lin_mat


def translate_bentayga_pf_results(grid: MultiCircuit, res) -> PowerFlowResults:
    results = PowerFlowResults(n=grid.get_bus_number(),
                               m=grid.get_branch_number_wo_hvdc(),
                               n_tr=grid.get_transformers2w_number(),
                               n_hvdc=grid.get_hvdc_number(),
                               bus_names=res.bus_names,
                               branch_names=res.branch_names,
                               transformer_names=[],
                               hvdc_names=res.hvdc_names,
                               bus_types=res.bus_types)

    results.voltage = res.V[0, :]
    results.Sbus = res.S[0, :]
    results.Sf = res.Sf[0, :]
    results.St = res.St[0, :]
    results.loading = res.loading[0, :]
    results.losses = res.losses[0, :]
    results.Vbranch = res.Vbranch[0, :]
    results.If = res.If[0, :]
    results.It = res.It[0, :]
    results.Beq = res.Beq[0, :]
    results.m = res.tap_modules[0, :]
    results.theta = res.tap_angles[0, :]
    results.F = res.F
    results.T = res.T
    results.hvdc_F = res.F_hvdc
    results.hvdc_T = res.T_hvdc
    results.hvdc_Pf = res.hvdc_Pf[0, :]
    results.hvdc_Pt = res.hvdc_Pt[0, :]
    results.hvdc_loading = res.hvdc_loading[0, :]
    results.hvdc_losses = res.hvdc_losses[0, :]
    results.bus_area_indices = grid.get_bus_area_indices()
    results.area_names = [a.name for a in grid.areas]

    for rep in res.stats[0]:
        report = bs.ConvergenceReport()
        for i in range(len(rep.converged)):
            report.add(method=rep.solver[i].name,
                       converged=rep.converged[i],
                       error=rep.norm_f[i],
                       elapsed=rep.elapsed[i],
                       iterations=rep.iterations[i])
            results.convergence_reports.append(report)

    return results

def debug_bentayga_circuit_at(btg_circuit: "btg.Circuit", t: int = None):

    if t is None:
        t = 0

    data = btg.compile_at(btg_circuit, t=t)

    for i in range(len(data)):

        print('_' * 200)
        print('Island', i)
        print('_' * 200)

        print("Ybus")
        print(data[i].admittances.Ybus.toarray())

        print('Yseries')
        print(data[i].split_admittances.Yseries.toarray())

        print('Yshunt')
        print(data[i].split_admittances.Yshunt)

        print("Bbus")
        print(data[i].linear_admittances.Bbus.toarray())

        print('B1')
        print(data[i].fast_decoupled_admittances.B1.toarray())

        print('B2')
        print(data[i].fast_decoupled_admittances.B2.toarray())

        print('Sbus')
        print(data[i].Sbus)

        print('Vbus')
        print(data[i].Vbus)

        print('Qmin')
        print(data[i].Qmin_bus)

        print('Qmax')
        print(data[i].Qmax_bus)
