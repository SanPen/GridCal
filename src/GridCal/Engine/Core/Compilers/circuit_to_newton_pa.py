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
    import newtonpa as npa

    npa.findAndActivateLicense()
    # activate
    if not npa.isLicenseActivated():
        npa_license = os.path.join(get_create_gridcal_folder(), 'newton.lic')
        if os.path.exists(npa_license):
            npa.activateLicense(npa_license)
            if npa.isLicenseActivated():
                NEWTON_PA_AVAILABLE = True
            else:
                print('Newton Power Analytics v' + npa.get_version(),
                      "installed, tried to activate with {} but the license did not work :/".format(npa_license))
                NEWTON_PA_AVAILABLE = False
        else:
            print('Newton Power Analytics v' + npa.get_version(), "installed but not licensed")
            NEWTON_PA_AVAILABLE = False
    else:
        print('Newton Power Analytics v' + npa.get_version())
        NEWTON_PA_AVAILABLE = True

except ImportError as e:
    NEWTON_PA_AVAILABLE = False
    print('Newton Power Analytics is not available:', e)

# numpy integer type for Newton's uword
BINT = np.ulonglong


def add_npa_buses(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", time_series: bool, ntime: int=1):
    """
    Convert the buses to Newton buses
    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise, just the snapshot
    :param ntime: number of time steps
    :return: bus dictionary buses[uuid] -> Bus
    """
    areas_dict = {elm: k for k, elm in enumerate(circuit.areas)}
    bus_dict = dict()

    for i, bus in enumerate(circuit.buses):

        elm = npa.CalculationNode(uuid=bus.idtag,
                                  secondary_id=bus.code,
                                  name=bus.name,
                                  time_steps=ntime,
                                  slack=bus.is_slack,
                                  dc=bus.is_dc,
                                  nominal_voltage=bus.Vnom)

        if time_series and ntime > 1:
            elm.active = bus.active_prof.astype(BINT)
        else:
            elm.active = np.ones(ntime, dtype=BINT) * int(bus.active)

        npa_circuit.addCalculationNode(elm)
        bus_dict[bus.idtag] = elm

    return bus_dict


def add_npa_loads(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param ntime: number of time steps
    """

    devices = circuit.get_loads()
    for k, elm in enumerate(devices):

        load = npa.Load(uuid=elm.idtag,
                        secondary_id=elm.code,
                        name=elm.name,
                        calc_node=bus_dict[elm.bus.idtag],
                        time_steps=ntime,
                        P=elm.P,
                        Q=elm.Q)

        if time_series:
            load.active = elm.active_prof.astype(BINT)
            load.P = elm.P_prof
            load.Q = elm.Q_prof
        else:
            load.active = np.ones(ntime, dtype=BINT) * int(elm.active)

        npa_circuit.addLoad(load)


def add_npa_static_generators(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", bus_dict,
                              time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param ntime: number of time steps
    """
    devices = circuit.get_static_generators()
    for k, elm in enumerate(devices):

        pe_inj = npa.PowerElectronicsInjection(uuid=elm.idtag,
                                               secondary_id=elm.code,
                                               name=elm.name,
                                               calc_node=bus_dict[elm.bus.idtag],
                                               time_steps=ntime,
                                               P=elm.P,
                                               Q=elm.Q)

        if time_series:
            pe_inj.active = elm.active_prof.astype(BINT)
            pe_inj.P = elm.P_prof
            pe_inj.Q = elm.Q_prof
        else:
            pe_inj.active = np.ones(ntime, dtype=BINT) * int(elm.active)

        npa_circuit.addPowerElectronicsInjection(pe_inj)


def add_npa_shunts(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param ntime: number of time steps
    """
    devices = circuit.get_shunts()
    for k, elm in enumerate(devices):

        sh = npa.Capacitor(uuid=elm.idtag,
                           secondary_id=elm.code,
                           name=elm.name,
                           calc_node=bus_dict[elm.bus.idtag],
                           time_steps=ntime,
                           G=elm.G,
                           B=elm.B)

        if time_series:
            sh.active = elm.active_prof.astype(BINT)
            sh.G = elm.G_prof
            sh.B = elm.B_prof
        else:
            sh.active = np.ones(ntime, dtype=BINT) * int(elm.active)

        npa_circuit.addCapacitor(sh)


def add_npa_generators(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param ntime: number of time steps
    """
    devices = circuit.get_generators()

    for k, elm in enumerate(devices):

        gen = npa.Generator(uuid=elm.idtag,
                            name=elm.name,
                            calc_node=bus_dict[elm.bus.idtag],
                            time_steps=ntime,
                            P=elm.P,
                            Vset=elm.Vset,
                            Pmin=elm.Pmin,
                            Pmax=elm.Pmax,
                            Qmin=elm.Qmin,
                            Qmax=elm.Qmax)

        gen.cost_b = elm.Cost

        if time_series:
            gen.active = elm.active_prof.astype(BINT)
            gen.P = elm.P_prof
            gen.Vset = elm.Vset_prof
        else:
            gen.active = np.ones(ntime, dtype=BINT) * int(elm.active)
            gen.P = np.ones(ntime, dtype=float) * elm.P
            gen.Vset = np.ones(ntime, dtype=float) * elm.Vset

        npa_circuit.addGenerator(gen)


def get_battery_data(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param ntime: number of time steps
    """
    devices = circuit.get_batteries()

    for k, elm in enumerate(devices):

        gen = npa.Battery(uuid=elm.idtag,
                          name=elm.name,
                          calc_node=bus_dict[elm.bus.idtag],
                          time_steps=ntime,
                          nominal_energy=elm.Enom,
                          P=elm.P,
                          Vset=elm.Vset,
                          soc_max=elm.max_soc,
                          soc_min=elm.min_soc,
                          Qmin=elm.Qmin,
                          Qmax=elm.Qmax,
                          Pmin=elm.Pmin,
                          Pmax=elm.Pmax,
                          )

        gen.charge_efficiency = elm.charge_efficiency
        gen.discharge_efficiency = elm.discharge_efficiency
        gen.cost_b = elm.Cost

        if time_series:
            gen.active = elm.active_prof.astype(BINT)
            gen.P = elm.P_prof
            gen.Vset = elm.Vset_prof
        else:
            gen.active = np.ones(ntime, dtype=BINT) * int(elm.active)
            gen.P = np.ones(ntime, dtype=float) * elm.P
            gen.Vset = np.ones(ntime, dtype=float) * elm.Vset

        npa_circuit.addBattery(gen)


def add_npa_line(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param ntime: number of time steps
    """

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        lne = npa.AcLine(uuid=elm.idtag,
                         secondary_id=elm.code,
                         name=elm.name,
                         calc_node_from=bus_dict[elm.bus_from.idtag],
                         calc_node_to=bus_dict[elm.bus_to.idtag],
                         time_steps=ntime,
                         length=elm.length,
                         rate=elm.rate,
                         active_default=elm.active,
                         r=elm.R,
                         x=elm.X,
                         b=elm.B,
                         monitor_loading_default=elm.monitor_loading,
                         monitor_contingency_default=elm.contingency_enabled)

        if time_series:
            lne.active = elm.active_prof.astype(BINT)
            lne.rates = elm.rate_prof
            lne.contingency_rates = elm.rate_prof * elm.contingency_factor

        npa_circuit.addAcLine(lne)


def get_transformer_data(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param ntime: number of time steps
    """
    for i, elm in enumerate(circuit.transformers2w):
        tr2 = npa.Transformer2WFull(uuid=elm.idtag,
                                    secondary_id=elm.code,
                                    name=elm.name,
                                    calc_node_from=bus_dict[elm.bus_from.idtag],
                                    calc_node_to=bus_dict[elm.bus_to.idtag],
                                    time_steps=ntime,
                                    Vhigh=elm.HV,
                                    Vlow=elm.LV,
                                    rate=elm.rate,
                                    active_default=elm.active,
                                    r=elm.R,
                                    x=elm.X,
                                    g=elm.G,
                                    b=elm.B,
                                    monitor_loading_default=elm.monitor_loading,
                                    monitor_contingency_default=elm.contingency_enabled,
                                    tap=elm.tap_module,
                                    phase=elm.angle)
        if time_series:
            tr2.active = elm.active_prof.astype(BINT)
            tr2.rates = elm.rate_prof
            tr2.contingency_rates = elm.rate_prof * elm.contingency_factor
            tr2.tap = elm.tap_module_prof
            tr2.phase = elm.angle_prof

        npa_circuit.addTransformers2wFul(tr2)


def get_vsc_data(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param ntime: number of time steps
    """
    for i, elm in enumerate(circuit.vsc_devices):
        vsc = npa.AcDcConverter(uuid=elm.idtag,
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
                                alpha3=elm.alpha3,
                                monitor_loading_default=elm.monitor_loading,
                                monitor_contingency_default=elm.contingency_enabled)

        if time_series:
            vsc.active = elm.active_prof.astype(BINT)
            vsc.rates = elm.rate_prof
            vsc.contingency_rates = elm.rate_prof * elm.contingency_factor

        npa_circuit.addAcDcConverter(vsc)


def get_dc_line_data(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param ntime: number of time steps
    """
    # Compile the lines
    for i, elm in enumerate(circuit.dc_lines):
        lne = npa.DcLine(uuid=elm.idtag,
                         name=elm.name,
                         calc_node_from=bus_dict[elm.bus_from.idtag],
                         calc_node_to=bus_dict[elm.bus_to.idtag],
                         time_steps=ntime,
                         length=elm.length,
                         rate=elm.rate,
                         active_default=elm.active,
                         r=elm.R,
                         monitor_loading_default=elm.monitor_loading,
                         monitor_contingency_default=elm.contingency_enabled
                         )

        if time_series:
            lne.active = elm.active_prof.astype(BINT)
            lne.rates = elm.rate_prof
            lne.contingency_rates = elm.rate_prof * elm.contingency_factor

        npa_circuit.addDcLine(lne)


def get_hvdc_data(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", bus_dict, time_series: bool, ntime=1):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param ntime: number of time steps
    """

    cmode_dict = {HvdcControlType.type_0_free: npa.HvdcControlMode.HvdcControlAngleDroop,
                  HvdcControlType.type_1_Pset: npa.HvdcControlMode.HvdcControlPfix}

    for i, elm in enumerate(circuit.hvdc_lines):
        """
        (uuid: str = '', 
        secondary_id: str = '', 
        name: str = '', 
        calc_node_from: newtonpa.CalculationNode = None, 
        calc_node_to: newtonpa.CalculationNode = None, 
        cn_from: newtonpa.ConnectivityNode = None, 
        cn_to: newtonpa.ConnectivityNode = None, 
        time_steps: int = 1, 
        active_default: int = 1, 
        rate: float = 9999, 
        contingency_rate: float = 9999, 
        monitor_loading_default: int = 1, 
        monitor_contingency_default: int = 1, 
        P: float = 0.0, 
        Vf: float = 1.0, 
        Vf: float = 1.0, 
        r: float = 1e-20, 
        angle_droop: float = 360.0, 
        length: float = 0.0, 
        min_firing_angle_f: float = -1.0, 
        max_firing_angle_f: float = 1.0, 
        min_firing_angle_t: float = -1.0, 
        max_firing_angle_t: float = -1.0, 
        control_mode: newtonpa.HvdcControlMode = <HvdcControlMode.HvdcControlPfix: 1>)
        """
        hvdc = npa.HvdcLine(uuid=elm.idtag,
                            secondary_id=elm.code,
                            name=elm.name,
                            calc_node_from=bus_dict[elm.bus_from.idtag],
                            calc_node_to=bus_dict[elm.bus_to.idtag],
                            cn_from=None,
                            cn_to=None,
                            time_steps=ntime,
                            active_default=int(elm.active),
                            rate=elm.rate,
                            contingency_rate=elm.rate * elm.contingency_factor,
                            monitor_loading_default=1,
                            monitor_contingency_default=1,
                            P=elm.Pset,
                            Vf=elm.Vset_f,
                            Vt=elm.Vset_t,
                            r=elm.r,
                            angle_droop=elm.angle_droop,
                            length=elm.length,
                            min_firing_angle_f=elm.min_firing_angle_f,
                            max_firing_angle_f=elm.max_firing_angle_f,
                            min_firing_angle_t=elm.min_firing_angle_t,
                            max_firing_angle_t=elm.max_firing_angle_t,
                            control_mode=cmode_dict[elm.control_mode])

        # hvdc.monitor_loading = elm.monitor_loading
        # hvdc.contingency_enabled = elm.contingency_enabled

        if time_series:
            hvdc.active = elm.active_prof.astype(BINT)
            hvdc.rates = elm.rate_prof
            hvdc.Vf = elm.Vset_f_prof
            hvdc.Vt = elm.Vset_t_prof
            hvdc.contingency_rates = elm.rate_prof * elm.contingency_factor
            hvdc.angle_droop = elm.angle_droop_prof
        else:
            hvdc.contingency_rates = elm.rate * elm.contingency_factor
            hvdc.angle_droop = elm.angle_droop

        npa_circuit.addHvdcLine(hvdc)


def to_newton_pa(circuit: MultiCircuit, time_series: bool):
    """
    Convert GridCal circuit to Newton
    :param circuit: MultiCircuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :return: npa.HybridCircuit instance
    """
    ntime = circuit.get_time_number() if time_series else 1
    if ntime == 0:
        ntime = 1

    npaCircuit = npa.HybridCircuit(uuid=circuit.idtag, name=circuit.name, time_steps=ntime)

    bus_dict = add_npa_buses(circuit, npaCircuit, time_series, ntime)
    add_npa_loads(circuit, npaCircuit, bus_dict, time_series, ntime)
    add_npa_static_generators(circuit, npaCircuit, bus_dict, time_series, ntime)
    add_npa_shunts(circuit, npaCircuit, bus_dict, time_series, ntime)
    add_npa_generators(circuit, npaCircuit, bus_dict, time_series, ntime)
    get_battery_data(circuit, npaCircuit, bus_dict, time_series, ntime)
    add_npa_line(circuit, npaCircuit, bus_dict, time_series, ntime)
    get_transformer_data(circuit, npaCircuit, bus_dict, time_series, ntime)
    get_vsc_data(circuit, npaCircuit, bus_dict, time_series, ntime)
    get_dc_line_data(circuit, npaCircuit, bus_dict, time_series, ntime)
    get_hvdc_data(circuit, npaCircuit, bus_dict, time_series, ntime)

    return npaCircuit


class FakeAdmittances:

    def __init__(self):
        self.Ybus = None
        self.Yf = None
        self.Yt = None


def get_snapshots_from_bentayga(circuit: MultiCircuit):

    from GridCal.Engine.Core.snapshot_pf_data import SnapshotData

    npaCircuit = to_newton_pa(circuit, time_series=False)

    npa_data_lst = npa.compileAt(npaCircuit, t=0)

    data_lst = list()

    for npa_data in npa_data_lst:

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

        data.Vbus_ = npa_data.Vbus.reshape(-1, 1)
        data.Sbus_ = npa_data.Sbus.reshape(-1, 1)
        data.Ibus_ = npa_data.Ibus
        data.branch_data.branch_names = np.array(npa_data.branch_data.names)
        data.branch_data.tap_f = npa_data.branch_data.virtual_tap_f
        data.branch_data.tap_t = npa_data.branch_data.virtual_tap_t

        data.bus_data.bus_names = np.array(npa_data.bus_data.names)

        data.Admittances = FakeAdmittances()
        data.Admittances.Ybus = npa_data.admittances.Ybus
        data.Admittances.Yf = npa_data.admittances.Yf
        data.Admittances.Yt = npa_data.admittances.Yt

        data.Bbus_ = npa_data.linear_admittances.Bbus
        data.Bf_ = npa_data.linear_admittances.Bf

        data.Yseries_ = npa_data.split_admittances.Yseries
        data.Yshunt_ = npa_data.split_admittances.Yshunt

        data.B1_ = npa_data.fast_decoupled_admittances.B1
        data.B2_ = npa_data.fast_decoupled_admittances.B2

        data.Cf_ = npa_data.Cf
        data.Ct_ = npa_data.Ct

        data.bus_data.bus_types = [x.value for x in npa_data.bus_data.bus_types]
        data.pq_ = npa_data.bus_types_data.pq
        data.pv_ = npa_data.bus_types_data.pv
        data.vd_ = npa_data.bus_types_data.vd
        data.pqpv_ = npa_data.bus_types_data.pqpv

        data.original_bus_idx = npa_data.bus_data.original_indices
        data.original_branch_idx = npa_data.branch_data.original_indices

        data.Qmax_bus_ = npa_data.Qmax_bus
        data.Qmin_bus_ = npa_data.Qmin_bus

        data.iPfsh = npa_data.control_indices.iPfsh
        data.iQfma = npa_data.control_indices.iQfma
        data.iBeqz = npa_data.control_indices.iBeqz
        data.iBeqv = npa_data.control_indices.iBeqv
        data.iVtma = npa_data.control_indices.iVtma
        data.iQtma = npa_data.control_indices.iQtma
        data.iPfdp = npa_data.control_indices.iPfdp
        data.iVscL = npa_data.control_indices.iVscL
        data.VfBeqbus = npa_data.control_indices.iVfBeqBus
        data.Vtmabus = npa_data.control_indices.iVtmaBus

        data_lst.append(data)

    return data_lst


def get_newton_pa_pf_options(opt: PowerFlowOptions):
    """
    Translate GridCal power flow options to Newton power flow options
    :param opt:
    :return:
    """
    solver_dict = {SolverType.NR: npa.SolverType.NR,
                   SolverType.DC: npa.SolverType.DC,
                   SolverType.HELM: npa.SolverType.HELM,
                   SolverType.IWAMOTO: npa.SolverType.IWAMOTO,
                   SolverType.LM: npa.SolverType.LM,
                   SolverType.LACPF: npa.SolverType.LACPF,
                   SolverType.FASTDECOUPLED: npa.SolverType.FD
                   }

    q_control_dict = {ReactivePowerControlMode.NoControl: npa.ReactivePowerControlMode.NoControl,
                      ReactivePowerControlMode.Direct: npa.ReactivePowerControlMode.Direct}

    if opt.solver_type in solver_dict.keys():
        solver_type = solver_dict[opt.solver_type]
    else:
        solver_type = npa.SolverType.NR

    """
    solver_type: newtonpa.SolverType = <SolverType.NR: 0>, 
    retry_with_other_methods: bool = True, 
    verbose: bool = False, 
    initialize_with_existing_solution: bool = False, 
    tolerance: float = 1e-06, 
    max_iter: int = 15, 
    control_q_mode: newtonpa.ReactivePowerControlMode = <ReactivePowerControlMode.NoControl: 0>, 
    tap_control_mode: newtonpa.TapsControlMode = <TapsControlMode.NoControl: 0>, 
    distributed_slack: bool = False, 
    ignore_single_node_islands: bool = False, 
    correction_parameter: float = 0.5, 
    mu0: float = 1.0
    """

    return npa.PowerFlowOptions(solver_type=solver_type,
                                tolerance=opt.tolerance,
                                max_iter=opt.max_iter,
                                retry_with_other_methods=opt.retry_with_other_methods,
                                control_q_mode=q_control_dict[opt.control_Q])


def newton_pa_pf(circuit: MultiCircuit, opt: PowerFlowOptions, time_series=False):
    """
    Newton power flow
    :param circuit: MultiCircuit instance
    :param opt: Power Flow Options
    :param time_series: Compile with GridCal time series?
    :return: Newton Power flow results object
    """
    npaCircuit = to_newton_pa(circuit, time_series=time_series)

    pf_options = get_newton_pa_pf_options(opt)

    if time_series:
        time_indices = [i for i in range(circuit.get_time_number())]
        n_threads = 0  # max threads
    else:
        time_indices = [0]
        n_threads = 1

    pf_res = npa.runPowerFlow(numeric_circuit=npaCircuit,
                              pf_options=pf_options,
                              time_indices=time_indices,
                              n_threads=n_threads)

    return pf_res


def newton_pa_linear_matrices(circuit: MultiCircuit, distributed_slack=False):
    """
    Newton linear analysis
    :param circuit: MultiCircuit instance
    :param distributed_slack: distribute the PTDF slack
    :return: Newton LinearAnalysisMatrices object
    """
    npa_circuit = to_newton_pa(circuit, time_series=False)

    options = npa.LinearAnalysisOptions(distribute_slack=distributed_slack)
    results = npa.runLinearAnalysisAt(t=0, grid=npa_circuit, options=options)

    return results


def translate_newton_pa_pf_results(grid: MultiCircuit, res) -> PowerFlowResults:
    results = PowerFlowResults(n=grid.get_bus_number(),
                               m=grid.get_branch_number_wo_hvdc(),
                               n_tr=grid.get_transformers2w_number(),
                               n_hvdc=grid.get_hvdc_number(),
                               bus_names=res.bus_names,
                               branch_names=res.branch_names,
                               transformer_names=[],
                               hvdc_names=res.hvdc_names,
                               bus_types=res.bus_types)

    results.voltage = res.voltage[0, :]
    results.Sbus = res.Scalc[0, :]
    results.Sf = res.Sf[0, :]
    results.St = res.St[0, :]
    results.loading = res.Loading[0, :]
    results.losses = res.Losses[0, :]
    # results.Vbranch = res.Vbranch[0, :]
    # results.If = res.If[0, :]
    # results.It = res.It[0, :]
    results.Beq = res.Beq[0, :]
    results.m = res.tap_module[0, :]
    results.theta = res.tap_angle[0, :]
    results.F = res.F
    results.T = res.T
    results.hvdc_F = res.hvdc_F
    results.hvdc_T = res.hvdc_T
    results.hvdc_Pf = res.hvdc_Pf[0, :]
    results.hvdc_Pt = res.hvdc_Pt[0, :]
    results.hvdc_loading = res.hvdc_loading[0, :]
    results.hvdc_losses = res.hvdc_losses[0, :]
    results.bus_area_indices = grid.get_bus_area_indices()
    results.area_names = [a.name for a in grid.areas]
    results.bus_types = res.bus_types[0, :]

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


def debug_newton_pa_circuit_at(npa_circuit: "npa.HybridCircuit", t: int = None):

    if t is None:
        t = 0

    data = npa.compileAt(npa_circuit, t=t)

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


if __name__ == '__main__':

    from GridCal.Engine import *

    # fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE14_from_raw.gridcal'
    fname = '/home/santi/Documentos/Git/GitHub/GridCal/Grids_and_profiles/grids/IEEE39.gridcal'
    _grid = FileOpen(fname).open()

    # _newton_grid = to_newton_pa(circuit=_grid, time_series=False)
    _options = PowerFlowOptions()
    _res = newton_pa_pf(circuit=_grid, opt=_options, time_series=True)

    _res2 = translate_newton_pa_pf_results(_grid, _res)

    print()
