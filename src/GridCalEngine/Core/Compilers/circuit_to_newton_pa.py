# GridCal
# Copyright (C) 2015 - 2023 Santiago Peñate Vera
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
import numpy as np
from typing import List, Dict, Union
from GridCalEngine.basic_structures import IntVec, Vec
from GridCalEngine.Core.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import TransformerControlType, HvdcControlType
import GridCalEngine.Core.Devices as dev
from GridCalEngine.basic_structures import SolverType, ReactivePowerControlMode
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Core.DataStructures.numerical_circuit import NumericalCircuit
# from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults
# from GridCalEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions, ZonalGrouping
# from GridCalEngine.Simulations.ContingencyAnalysis.contingency_analysis_options import ContingencyAnalysisOptions
from GridCalEngine.IO.file_system import get_create_gridcal_folder
import GridCalEngine.basic_structures as bs

try:
    import newtonpa as npa

    activation = npa.findAndActivateLicense()
    # activate
    if not npa.isLicenseActivated():
        npa_license = os.path.join(get_create_gridcal_folder(), 'newton.lic')
        if os.path.exists(npa_license):
            npa.activateLicense(npa_license)
            if npa.isLicenseActivated():
                NEWTON_PA_AVAILABLE = True
            else:
                # print('Newton Power Analytics v' + npa.get_version(),
                #       "installed, tried to activate with {} but the license did not work :/".format(npa_license))
                NEWTON_PA_AVAILABLE = False
        else:
            # print('Newton Power Analytics v' + npa.get_version(), "installed but not licensed")
            NEWTON_PA_AVAILABLE = False
    else:
        # print('Newton Power Analytics v' + npa.get_version())
        NEWTON_PA_AVAILABLE = True

except ImportError as e:
    NEWTON_PA_AVAILABLE = False
    # print('Newton Power Analytics is not available:', e)

# numpy integer type for Newton's uword
BINT = np.ulonglong


def get_newton_mip_solvers_list() -> List[str]:
    """
    Get list of available MIP solvers
    :return:
    """
    if NEWTON_PA_AVAILABLE:
        return npa.getAvailableSolverStrList()
    else:
        return list()


def get_final_profile(time_series: bool,
                      time_indices: Union[IntVec, None],
                      profile: Union[IntVec, Vec, None],
                      ntime=1,
                      default_val=0,
                      dtype=float) -> Union[Vec, IntVec]:
    """
    Generates a default time series
    :param time_series: use time series?
    :param time_indices: time series indices if any (optional)
    :param profile: Profile array (must be provided if time_series = True
    :param ntime: (if time_series = False) number of time steps
    :param default_val: Default value
    :param dtype: data type (float, int, etc...)
    :return: Profile array
    """

    if time_series:
        return profile if time_indices is None else profile[time_indices]
    else:
        return np.full(ntime, default_val, dtype=dtype)


def add_npa_areas(circuit: MultiCircuit,
                  npa_circuit: "npa.HybridCircuit",
                  n_time: int = 1) -> Dict[dev.Area, "npa.Area"]:
    """
    Add Newton Areas
    :param circuit: GridCal circuit
    :param npa_circuit: Newton Circuit
    :param n_time: number of time steps
    :return: Dictionary [GridCal area] -> Newton Area
    """
    d = dict()

    for i, area in enumerate(circuit.areas):
        elm = npa.Area(uuid=area.idtag,
                       secondary_id=str(area.code),
                       name=area.name,
                       time_steps=n_time)

        npa_circuit.addArea(elm)

        d[area] = elm

    return d


def add_npa_zones(circuit: MultiCircuit,
                  npa_circuit: "npa.HybridCircuit",
                  n_time: int = 1) -> Dict[dev.Zone, "npa.Zone"]:
    """
    Add Newton Zones
    :param circuit: GridCal circuit
    :param npa_circuit: Newton Circuit
    :param n_time: number of time steps
    :return: Dictionary [GridCal Zone] -> Newton Zone
    """
    d = dict()

    for i, area in enumerate(circuit.zones):
        elm = npa.Zone(uuid=area.idtag,
                       secondary_id=str(area.code),
                       name=area.name,
                       time_steps=n_time)

        npa_circuit.addZone(elm)

        d[area] = elm

    return d


def add_npa_contingency_groups(circuit: MultiCircuit,
                               npa_circuit: "npa.HybridCircuit",
                               n_time: int = 1) -> Dict[dev.ContingencyGroup, "npa.ContingenciesGroup"]:
    """
    Add Newton ContingenciesGroup
    :param circuit: GridCal circuit
    :param npa_circuit: Newton Circuit
    :param n_time: number of time steps
    :return: Dictionary [GridCal ContingenciesGroup] -> Newton ContingenciesGroup
    """
    d = dict()

    for i, elm in enumerate(circuit.contingency_groups):
        dev = npa.ContingenciesGroup(uuid=elm.idtag,
                                     secondary_id=str(elm.code),
                                     name=elm.name,
                                     time_steps=n_time,
                                     category=elm.category)

        npa_circuit.addContingenciesGroup(dev)

        d[elm] = dev

    return d


def add_npa_contingencies(circuit: MultiCircuit,
                          npa_circuit: "npa.HybridCircuit",
                          n_time: int,
                          groups_dict: Dict[dev.ContingencyGroup, "npa.ContingenciesGroup"]):
    """
    Add Newton ContingenciesGroup
    :param circuit: GridCal circuit
    :param npa_circuit: Newton Circuit
    :param n_time: number of time steps
    :param groups_dict: Contingency groups dictionary
    :return: Dictionary [GridCal ContingenciesGroup] -> Newton ContingenciesGroup
    """
    d = dict()

    for i, elm in enumerate(circuit.contingencies):
        dev = npa.Contingency(uuid=elm.idtag,
                              secondary_id=str(elm.code),
                              name=elm.name,
                              time_steps=n_time,
                              device_uuid=elm.device_idtag,
                              prop=elm.prop,
                              value=elm.value,
                              group=groups_dict[elm.group])

        npa_circuit.addContingency(dev)

        d[elm] = dev

    return d


def add_npa_investment_groups(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit", n_time: int):
    """

    :param circuit:
    :param npa_circuit:
    :param n_time:
    :return:
    """
    d = dict()

    for i, elm in enumerate(circuit.investments_groups):
        dev = npa.InvestmentsGroup(uuid=elm.idtag,
                                   secondary_id=str(elm.code),
                                   name=elm.name,
                                   time_steps=n_time,
                                   category=elm.category)

        npa_circuit.addInvestmentsGroup(dev)

        d[elm] = dev

    return d


def add_npa_investments(circuit: MultiCircuit,
                        npa_circuit: "npa.HybridCircuit",
                        n_time: int,
                        groups_dict: Dict[dev.InvestmentsGroup, "npa.InvestmentsGroup"]):
    """

    :param circuit:
    :param npa_circuit:
    :param n_time:
    :param groups_dict:
    :return:
    """
    d = dict()

    for i, elm in enumerate(circuit.investments):
        dev = npa.Investment(uuid=elm.idtag,
                             secondary_id=str(elm.code),
                             name=elm.name,
                             time_steps=n_time,
                             device_uuid=elm.device_idtag,
                             group=groups_dict[elm.group],
                             capex=elm.CAPEX,
                             opex=elm.OPEX)

        npa_circuit.addInvestment(dev)

        d[elm] = dev

    return d


def add_npa_buses(circuit: MultiCircuit,
                  npa_circuit: "npa.HybridCircuit",
                  time_series: bool,
                  n_time: int = 1,
                  time_indices: Union[IntVec, None] = None,
                  area_dict: Union[Dict[dev.Area, "npa.Area"], None] = None) -> Dict[str, "npa.CalculationNode"]:
    """
    Convert the buses to Newton buses
    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise, just the snapshot
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param area_dict: Area object translation dictionary
    :return: bus dictionary buses[uuid] -> Bus
    """

    if time_indices is not None:
        assert (len(time_indices) == n_time)

    if area_dict is None:
        area_dict = {elm: k for k, elm in enumerate(circuit.areas)}

    bus_dict: Dict[str, "npa.CalculationNode"] = dict()

    for i, bus in enumerate(circuit.buses):

        elm = npa.CalculationNode(uuid=bus.idtag,
                                  secondary_id=str(bus.code),
                                  name=bus.name,
                                  time_steps=n_time,
                                  slack=bus.is_slack,
                                  dc=bus.is_dc,
                                  nominal_voltage=bus.Vnom,
                                  vm_min=bus.Vmin,
                                  vm_max=bus.Vmax,
                                  va_min=-6.28,
                                  va_max=6.28,
                                  area=area_dict.get(bus.area, None))

        if time_series and n_time > 1:
            elm.active = bus.active_prof.astype(BINT) if time_indices is None else bus.active_prof.astype(BINT)[
                time_indices]
        else:
            elm.active = np.ones(n_time, dtype=BINT) * int(bus.active)

        npa_circuit.addCalculationNode(elm)
        bus_dict[bus.idtag] = elm

    return bus_dict


def add_npa_loads(circuit: MultiCircuit,
                  npa_circuit: "npa.HybridCircuit",
                  bus_dict: Dict[str, "npa.CalculationNode"],
                  time_series: bool,
                  n_time=1,
                  time_indices: Union[IntVec, None] = None,
                  opf_results: "OptimelPowerFlowResults" = None):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param bus_dict: dictionary of bus id to Newton bus object
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param n_time: number of time steps
    :param time_indices:
    :return:
    """
    devices = circuit.get_loads()
    for k, elm in enumerate(devices):

        load = npa.Load(uuid=elm.idtag,
                        secondary_id=str(elm.code),
                        name=elm.name,
                        calc_node=bus_dict[elm.bus.idtag],
                        time_steps=n_time,
                        P=elm.P if opf_results is None else elm.P - opf_results.load_shedding[k],
                        Q=elm.Q)

        if time_series:
            load.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
                time_indices]

            if opf_results is None:
                P = elm.P_prof
            else:
                P = elm.P_prof - opf_results.load_shedding[:, k]

            load.P = P if time_indices is None else P[time_indices]
            load.Q = elm.Q_prof if time_indices is None else elm.Q_prof[time_indices]
            load.cost_1 = elm.Cost_prof if time_indices is None else elm.Cost_prof[time_indices]
        else:
            load.active = np.ones(n_time, dtype=BINT) * int(elm.active)
            load.setAllCost1(elm.Cost)

        npa_circuit.addLoad(load)


def add_npa_static_generators(circuit: MultiCircuit, npa_circuit: "npa.HybridCircuit",
                              bus_dict: Dict[str, "npa.CalculationNode"],
                              time_series: bool,
                              n_time=1,
                              time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """
    devices = circuit.get_static_generators()
    for k, elm in enumerate(devices):

        pe_inj = npa.PowerElectronicsInjection(uuid=elm.idtag,
                                               secondary_id=str(elm.code),
                                               name=elm.name,
                                               calc_node=bus_dict[elm.bus.idtag],
                                               time_steps=n_time,
                                               P=elm.P,
                                               Q=elm.Q)

        if time_series:
            pe_inj.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
                time_indices]
            pe_inj.P = elm.P_prof if time_indices is None else elm.P_prof[time_indices]
            pe_inj.Q = elm.Q_prof if time_indices is None else elm.Q_prof[time_indices]
            pe_inj.cost_1 = elm.Cost_prof if time_indices is None else elm.Cost_prof[time_indices]
        else:
            pe_inj.active = np.ones(n_time, dtype=BINT) * int(elm.active)
            pe_inj.setAllCost1(elm.Cost)

        npa_circuit.addPowerElectronicsInjection(pe_inj)


def add_npa_shunts(circuit: MultiCircuit,
                   npa_circuit: "npa.HybridCircuit",
                   bus_dict: Dict[str, "npa.CalculationNode"],
                   time_series: bool,
                   n_time=1,
                   time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """
    devices = circuit.get_shunts()
    for k, elm in enumerate(devices):

        sh = npa.Capacitor(uuid=elm.idtag,
                           secondary_id=str(elm.code),
                           name=elm.name,
                           calc_node=bus_dict[elm.bus.idtag],
                           time_steps=n_time,
                           G=elm.G,
                           B=elm.B)

        if time_series:
            sh.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
                time_indices]
            sh.G = elm.G_prof if time_indices is None else elm.G_prof[time_indices]
            sh.B = elm.B_prof if time_indices is None else elm.B_prof[time_indices]
        else:
            sh.active = np.ones(n_time, dtype=BINT) * int(elm.active)

        npa_circuit.addCapacitor(sh)


def add_npa_generators(circuit: MultiCircuit,
                       npa_circuit: "npa.HybridCircuit",
                       bus_dict: Dict[str, "npa.CalculationNode"],
                       time_series: bool,
                       n_time=1,
                       time_indices: Union[IntVec, None] = None,
                       opf_results: "OptimelPowerFlowResults" = None):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param opf_results: OptimelPowerFlowResults (optional)
    """
    devices = circuit.get_generators()

    for k, elm in enumerate(devices):

        gen = npa.Generator(uuid=elm.idtag,
                            name=elm.name,
                            calc_node=bus_dict[elm.bus.idtag],
                            time_steps=n_time,
                            P=elm.P,
                            Vset=elm.Vset,
                            Pmin=elm.Pmin,
                            Pmax=elm.Pmax,
                            Qmin=elm.Qmin,
                            Qmax=elm.Qmax,
                            controllable_default=BINT(elm.is_controlled),
                            dispatchable_default=BINT(elm.enabled_dispatch)
                            )

        gen.nominal_power = elm.Snom

        if time_series:

            gen.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
                time_indices]

            if opf_results is None:
                P = elm.P_prof
            else:
                P = opf_results.generator_power[:, k] - opf_results.generator_shedding[:, k]

            gen.P = P if time_indices is None else P[time_indices]

            gen.Vset = elm.Vset_prof if time_indices is None else elm.Vset_prof[time_indices]
            gen.cost_0 = elm.Cost0_prof if time_indices is None else elm.Cost0_prof[time_indices]
            gen.cost_1 = elm.Cost_prof if time_indices is None else elm.Cost_prof[time_indices]
            gen.cost_2 = elm.Cost2_prof if time_indices is None else elm.Cost2_prof[time_indices]
        else:
            gen.active = np.ones(n_time, dtype=BINT) * int(elm.active)

            if opf_results is None:
                gen.P = np.full(n_time, elm.P, dtype=float)
            else:
                gen.P = np.full(n_time, opf_results.generator_power[k] - opf_results.generator_shedding[k], dtype=float)

            gen.Vset = np.ones(n_time, dtype=float) * elm.Vset
            gen.setAllCost0(elm.Cost0)
            gen.setAllCost1(elm.Cost)
            gen.setAllCost2(elm.Cost2)

        npa_circuit.addGenerator(gen)


def add_battery_data(circuit: MultiCircuit,
                     npa_circuit: "npa.HybridCircuit",
                     bus_dict: Dict[str, "npa.CalculationNode"],
                     time_series: bool,
                     n_time: int = 1,
                     time_indices: Union[IntVec, None] = None,
                     opf_results: "OptimelPowerFlowResults" = None):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param opf_results: OptimelPowerFlowResults (optional)
    """
    devices = circuit.get_batteries()

    for k, elm in enumerate(devices):

        gen = npa.Battery(uuid=elm.idtag,
                          name=elm.name,
                          calc_node=bus_dict[elm.bus.idtag],
                          time_steps=n_time,
                          nominal_energy=elm.Enom,
                          P=elm.P,
                          Vset=elm.Vset,
                          soc_max=elm.max_soc,
                          soc_min=elm.min_soc,
                          Qmin=elm.Qmin,
                          Qmax=elm.Qmax,
                          Pmin=elm.Pmin,
                          Pmax=elm.Pmax)

        gen.nominal_power = elm.Snom
        gen.charge_efficiency = elm.charge_efficiency
        gen.discharge_efficiency = elm.discharge_efficiency

        if elm.is_controlled:
            gen.setAllControllable(1)
        else:
            gen.setAllControllable(0)

        if time_series:
            gen.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
                time_indices]

            if opf_results is None:
                P = elm.P_prof
            else:
                P = opf_results.generator_power[:, k] - opf_results.generator_shedding[:, k]

            gen.P = P if time_indices is None else P[time_indices]

            # gen.P = elm.P_prof if time_indices is None else elm.P_prof[time_indices]
            gen.Vset = elm.Vset_prof if time_indices is None else elm.Vset_prof[time_indices]
            gen.cost_0 = elm.Cost0_prof if time_indices is None else elm.Cost0_prof[time_indices]
            gen.cost_1 = elm.Cost_prof if time_indices is None else elm.Cost_prof[time_indices]
            gen.cost_2 = elm.Cost2_prof if time_indices is None else elm.Cost2_prof[time_indices]
        else:
            gen.active = np.ones(n_time, dtype=BINT) * int(elm.active)

            if opf_results is None:
                gen.P = np.full(n_time, elm.P, dtype=float)
            else:
                gen.P = np.full(n_time, opf_results.battery_power[k], dtype=float)

            gen.Vset = np.ones(n_time, dtype=float) * elm.Vset
            gen.setAllCost0(elm.Cost0)
            gen.setAllCost1(elm.Cost)
            gen.setAllCost2(elm.Cost2)

        npa_circuit.addBattery(gen)


def add_npa_line(circuit: MultiCircuit,
                 npa_circuit: "npa.HybridCircuit",
                 bus_dict: Dict[str, "npa.CalculationNode"],
                 time_series: bool,
                 n_time: int = 1,
                 time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        lne = npa.AcLine(uuid=elm.idtag,
                         secondary_id=str(elm.code),
                         name=elm.name,
                         calc_node_from=bus_dict[elm.bus_from.idtag],
                         calc_node_to=bus_dict[elm.bus_to.idtag],
                         time_steps=n_time,
                         length=elm.length,
                         rate=elm.rate,
                         active_default=elm.active,
                         r=elm.R,
                         x=elm.X,
                         b=elm.B,
                         monitor_loading_default=elm.monitor_loading,
                         monitor_contingency_default=elm.contingency_enabled)

        if time_series:
            lne.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
                time_indices]
            lne.rates = elm.rate_prof if time_indices is None else elm.rate_prof[time_indices]
            contingency_rates = elm.rate_prof * elm.contingency_factor
            lne.contingency_rates = contingency_rates if time_indices is None else contingency_rates[time_indices]
            lne.overload_cost = elm.Cost_prof if time_indices is None else elm.Cost_prof[time_indices]
        else:
            lne.setAllOverloadCost(elm.Cost)

        npa_circuit.addAcLine(lne)


def add_transformer_data(circuit: MultiCircuit,
                         npa_circuit: "npa.HybridCircuit",
                         bus_dict: Dict[str, "npa.CalculationNode"],
                         time_series: bool,
                         n_time: int = 1,
                         time_indices: Union[IntVec, None] = None,
                         override_controls=False):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param override_controls: If true the controls are set to Fix
    """

    ctrl_dict = {
        TransformerControlType.fixed: npa.BranchControlModes.Fixed,
        TransformerControlType.Pt: npa.BranchControlModes.BranchPt,
        TransformerControlType.Qt: npa.BranchControlModes.BranchQt,
        TransformerControlType.PtQt: npa.BranchControlModes.BranchPt,
        TransformerControlType.Vt: npa.BranchControlModes.BranchVt,
        TransformerControlType.PtVt: npa.BranchControlModes.BranchPt,
    }

    for i, elm in enumerate(circuit.transformers2w):
        tr2 = npa.Transformer2WFull(uuid=elm.idtag,
                                    secondary_id=str(elm.code),
                                    name=elm.name,
                                    calc_node_from=bus_dict[elm.bus_from.idtag],
                                    calc_node_to=bus_dict[elm.bus_to.idtag],
                                    time_steps=n_time,
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
                                    phase=elm.tap_phase)
        if time_series:
            contingency_rates = elm.rate_prof * elm.contingency_factor
            active_prof = elm.active_prof.astype(BINT)

            tr2.active = active_prof if time_indices is None else active_prof[time_indices]
            tr2.rates = elm.rate_prof if time_indices is None else elm.rate_prof[time_indices]
            tr2.contingency_rates = contingency_rates if time_indices is None else contingency_rates[time_indices]
            tr2.tap = elm.tap_module_prof if time_indices is None else elm.tap_module_prof[time_indices]
            tr2.phase = elm.tap_phase_prof if time_indices is None else elm.tap_phase_prof[time_indices]
            tr2.overload_cost = elm.Cost_prof
        else:
            tr2.setAllOverloadCost(elm.Cost)

        # control vars
        if override_controls:
            tr2.setAllControlMode(npa.BranchControlModes.Fixed)
        else:
            tr2.setAllControlMode(ctrl_dict[elm.control_mode])  # TODO: Warn about this

        tr2.phase_min = elm.tap_phase_min
        tr2.phase_max = elm.tap_phase_max
        tr2.tap_min = elm.tap_module_min
        tr2.tap_max = elm.tap_module_max
        npa_circuit.addTransformers2wFul(tr2)


def add_transformer3w_data(circuit: MultiCircuit,
                           npa_circuit: "npa.HybridCircuit",
                           bus_dict: Dict[str, "npa.CalculationNode"],
                           time_series: bool,
                           n_time=1,
                           time_indices: Union[IntVec, None] = None,
                           override_controls=False):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    :param override_controls: If true the controls are set to Fix
    """

    ctrl_dict = {
        TransformerControlType.fixed: npa.BranchControlModes.Fixed,
        TransformerControlType.Pt: npa.BranchControlModes.BranchPt,
        TransformerControlType.Qt: npa.BranchControlModes.BranchQt,
        TransformerControlType.PtQt: npa.BranchControlModes.BranchPt,
        TransformerControlType.Vt: npa.BranchControlModes.BranchVt,
        TransformerControlType.PtVt: npa.BranchControlModes.BranchPt,
    }

    for i, elm in enumerate(circuit.transformers3w):
        tr3 = npa.Transformer3W(uuid=elm.idtag,
                                secondary_id=str(elm.code),
                                name=elm.name,
                                time_steps=n_time,
                                active_default=elm.active,
                                calc_node_1=bus_dict[elm.bus1.idtag] if elm.bus1 else None,
                                calc_node_2=bus_dict[elm.bus2.idtag] if elm.bus2 else None,
                                calc_node_3=bus_dict[elm.bus3.idtag] if elm.bus3 else None,
                                V1=elm.V1,
                                V2=elm.V2,
                                V3=elm.V3,
                                r12=elm.r12, r23=elm.r23, r31=elm.r31,
                                x12=elm.x12, x23=elm.x23, x31=elm.x31,
                                rate12=elm.rate12, rate23=elm.rate23, rate31=elm.rate31,
                                contingency_rate12=elm.rate12,
                                contingency_rate23=elm.rate23,
                                contingency_rate31=elm.rate31, )

        if time_series:
            pass
        else:
            pass

        npa_circuit.addTransformers3w(tr3)


def add_vsc_data(circuit: MultiCircuit,
                 npa_circuit: "npa.HybridCircuit",
                 bus_dict: Dict[str, "npa.CalculationNode"],
                 time_series: bool,
                 n_time: int = 1,
                 time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """
    for i, elm in enumerate(circuit.vsc_devices):
        vsc = npa.AcDcConverter(uuid=elm.idtag,
                                secondary_id=str(elm.code),
                                name=elm.name,
                                calc_node_from=bus_dict[elm.bus_from.idtag],
                                calc_node_to=bus_dict[elm.bus_to.idtag],
                                time_steps=n_time,
                                active_default=elm.active)

        vsc.r = elm.R
        vsc.x = elm.X
        vsc.g0 = elm.G0sw

        vsc.setAllBeq(elm.Beq)
        vsc.beq_max = elm.Beq_max
        vsc.beq_min = elm.Beq_min

        vsc.k = elm.k

        vsc.setAllTapModule(elm.tap_module)
        vsc.tap_max = elm.tap_module_max
        vsc.tap_min = elm.tap_module_min

        vsc.setAllTapPhase(elm.tap_phase)
        vsc.phase_max = elm.tap_phase_max
        vsc.phase_min = elm.tap_phase_min

        vsc.setAllPdcSet(elm.Pdc_set)
        vsc.setAllVacSet(elm.Vac_set)
        vsc.setAllVdcSet(elm.Vdc_set)
        vsc.k_droop = elm.kdp

        vsc.alpha1 = elm.alpha1
        vsc.alpha2 = elm.alpha2
        vsc.alpha3 = elm.alpha3

        vsc.setAllMonitorloading(elm.monitor_loading)
        vsc.setAllContingencyenabled(elm.contingency_enabled)

        if time_series:
            vsc.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
                time_indices]
            vsc.rates = elm.rate_prof if time_indices is None else elm.rate_prof[time_indices]
            contingency_rates = elm.rate_prof * elm.contingency_factor
            vsc.contingency_rates = contingency_rates if time_indices is None else contingency_rates[time_indices]
            vsc.overload_cost = elm.Cost_prof
        else:
            vsc.setAllRates(elm.rate)
            vsc.setAllOverloadCost(elm.Cost)

        npa_circuit.addAcDcConverter(vsc)


def add_dc_line_data(circuit: MultiCircuit,
                     npa_circuit: "npa.HybridCircuit",
                     bus_dict: Dict[str, "npa.CalculationNode"],
                     time_series: bool,
                     n_time: int = 1,
                     time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """
    # Compile the lines
    for i, elm in enumerate(circuit.dc_lines):
        lne = npa.DcLine(uuid=elm.idtag,
                         name=elm.name,
                         calc_node_from=bus_dict[elm.bus_from.idtag],
                         calc_node_to=bus_dict[elm.bus_to.idtag],
                         time_steps=n_time,
                         length=elm.length,
                         rate=elm.rate,
                         active_default=elm.active,
                         r=elm.R,
                         monitor_loading_default=elm.monitor_loading,
                         monitor_contingency_default=elm.contingency_enabled
                         )

        if time_series:
            lne.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
                time_indices]
            lne.rates = elm.rate_prof if time_indices is None else elm.rate_prof[time_indices]

            contingency_rates = elm.rate_prof * elm.contingency_factor
            lne.contingency_rates = contingency_rates if time_indices is None else contingency_rates[time_indices]
            lne.overload_cost = elm.Cost_prof
        else:
            lne.setAllOverloadCost(elm.Cost)

        npa_circuit.addDcLine(lne)


def add_hvdc_data(circuit: MultiCircuit,
                  npa_circuit: "npa.HybridCircuit",
                  bus_dict: Dict[str, "npa.CalculationNode"],
                  time_series: bool,
                  n_time=1,
                  time_indices: Union[IntVec, None] = None):
    """

    :param circuit: GridCal circuit
    :param npa_circuit: Newton circuit
    :param time_series: compile the time series from GridCal? otherwise just the snapshot
    :param bus_dict: dictionary of bus id to Newton bus object
    :param n_time: number of time steps
    :param time_indices: Array of time indices
    """

    cmode_dict = {HvdcControlType.type_0_free: npa.HvdcControlMode.HvdcControlAngleDroop,
                  HvdcControlType.type_1_Pset: npa.HvdcControlMode.HvdcControlPfix}

    for i, elm in enumerate(circuit.hvdc_lines):
        hvdc = npa.HvdcLine(uuid=elm.idtag,
                            secondary_id=str(elm.code),
                            name=elm.name,
                            calc_node_from=bus_dict[elm.bus_from.idtag],
                            calc_node_to=bus_dict[elm.bus_to.idtag],
                            cn_from=None,
                            cn_to=None,
                            time_steps=n_time,
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
            hvdc.active = elm.active_prof.astype(BINT) if time_indices is None else elm.active_prof.astype(BINT)[
                time_indices]
            hvdc.rates = elm.rate_prof if time_indices is None else elm.rate_prof[time_indices]
            hvdc.Vf = elm.Vset_f_prof if time_indices is None else elm.Vset_f_prof[time_indices]
            hvdc.Vt = elm.Vset_t_prof if time_indices is None else elm.Vset_t_prof[time_indices]

            contingency_rates = elm.rate_prof * elm.contingency_factor
            hvdc.contingency_rates = contingency_rates if time_indices is None else contingency_rates[time_indices]

            hvdc.angle_droop = elm.angle_droop_prof if time_indices is None else elm.angle_droop_prof[time_indices]
            hvdc.overload_cost = elm.overload_cost_prof
        else:
            hvdc.contingency_rates = elm.rate * elm.contingency_factor
            hvdc.angle_droop = elm.angle_droop
            hvdc.setAllOverloadCost(elm.Cost)
            hvdc.setAllControlMode(cmode_dict[elm.control_mode])

        npa_circuit.addHvdcLine(hvdc)


def to_newton_pa(circuit: MultiCircuit,
                 use_time_series: bool,
                 time_indices: Union[IntVec, None] = None,
                 override_branch_controls=False,
                 opf_results: "OptimelPowerFlowResults" = None):
    """
    Convert GridCal circuit to Newton
    :param circuit: MultiCircuit
    :param use_time_series: compile the time series from GridCal? otherwise just the snapshot
    :param time_indices: Array of time indices
    :param override_branch_controls: If true the branch controls are set to Fix
    :return: npa.HybridCircuit instance
    """

    if time_indices is None:
        n_time = circuit.get_time_number() if use_time_series else 1
        if n_time == 0:
            n_time = 1
    else:
        n_time = len(time_indices)

    npa_circuit = npa.HybridCircuit(uuid=circuit.idtag, name=circuit.name, time_steps=n_time)

    area_dict = add_npa_areas(circuit, npa_circuit, n_time)
    zone_dict = add_npa_zones(circuit, npa_circuit, n_time)

    con_groups_dict = add_npa_contingency_groups(circuit, npa_circuit, n_time)
    add_npa_contingencies(circuit, npa_circuit, n_time, con_groups_dict)
    inv_groups_dict = add_npa_investment_groups(circuit, npa_circuit, n_time)
    add_npa_investments(circuit, npa_circuit, n_time, inv_groups_dict)

    bus_dict = add_npa_buses(circuit, npa_circuit, use_time_series, n_time, time_indices, area_dict)
    add_npa_loads(circuit, npa_circuit, bus_dict, use_time_series, n_time, time_indices)
    add_npa_static_generators(circuit, npa_circuit, bus_dict, use_time_series, n_time, time_indices)
    add_npa_shunts(circuit, npa_circuit, bus_dict, use_time_series, n_time, time_indices)
    add_npa_generators(circuit, npa_circuit, bus_dict, use_time_series, n_time, time_indices, opf_results)
    add_battery_data(circuit, npa_circuit, bus_dict, use_time_series, n_time, time_indices, opf_results)
    add_npa_line(circuit, npa_circuit, bus_dict, use_time_series, n_time, time_indices)
    add_transformer_data(circuit, npa_circuit, bus_dict, use_time_series, n_time, time_indices, override_branch_controls)
    add_transformer3w_data(circuit, npa_circuit, bus_dict, use_time_series, n_time, time_indices, override_branch_controls)
    add_vsc_data(circuit, npa_circuit, bus_dict, use_time_series, n_time, time_indices)
    add_dc_line_data(circuit, npa_circuit, bus_dict, use_time_series, n_time, time_indices)
    add_hvdc_data(circuit, npa_circuit, bus_dict, use_time_series, n_time, time_indices)

    # npa.FileHandler().save(npaCircuit, circuit.name + "_circuit.newton")

    return npa_circuit, (bus_dict, area_dict, zone_dict)


class FakeAdmittances:
    """
    Fake admittances class needed to make the translation
    """

    def __init__(self):
        self.Ybus = None
        self.Yf = None
        self.Yt = None


def get_snapshots_from_newtonpa(circuit: MultiCircuit, override_branch_controls=False) -> List[NumericalCircuit]:
    """

    :param circuit:
    :param override_branch_controls:
    :return:
    """

    npa_circuit, (bus_dict, area_dict, zone_dict) = to_newton_pa(circuit,
                                                                 use_time_series=False,
                                                                 override_branch_controls=override_branch_controls)

    npa_data_lst = npa.compileAt(npa_circuit, t=0).splitIntoIslands()

    data_lst = list()

    for npa_data in npa_data_lst:
        data = NumericalCircuit(nbus=0,
                                nbr=0,
                                nhvdc=0,
                                nload=0,
                                ngen=0,
                                nbatt=0,
                                nshunt=0,
                                sbase=0,
                                t_idx=0)

        conn = npa_data.getConnectivity()
        inj = npa_data.getInjections()
        tpes = npa_data.getSimulationIndices(inj.S0)
        adm = npa_data.getAdmittances(conn)
        lin = npa_data.getLinearMatrices(conn)
        series_adm = npa_data.getSeriesAdmittances(conn)
        fd_adm = npa_data.getFastDecoupledAdmittances(conn, tpes)
        qlim = npa_data.getQLimits()

        data.Vbus_ = npa_data.Vbus.reshape(-1, 1)
        data.Sbus_ = inj.S0.reshape(-1, 1)
        data.Ibus_ = inj.I0.reshape(-1, 1)
        data.branch_data.names = np.array(npa_data.branch_data.names)
        data.branch_data.virtual_tap_f = npa_data.branch_data.vtap_f
        data.branch_data.virtual_tap_t = npa_data.branch_data.vtap_t
        data.branch_data.original_idx = npa_data.branch_data.original_indices

        data.bus_data.names = np.array(npa_data.bus_data.names)
        data.bus_data.original_idx = npa_data.bus_data.original_indices

        data.admittances_ = FakeAdmittances()
        data.admittances_.Ybus = adm.Ybus
        data.admittances_.Yf = adm.Yf
        data.admittances_.Yt = adm.Yt

        data.Bbus_ = lin.Bbus
        data.Bf_ = lin.Bf

        data.Yseries_ = series_adm.Yseries
        data.Yshunt_ = series_adm.Yshunt

        data.B1_ = fd_adm.B1
        data.B2_ = fd_adm.B2

        data.Cf_ = conn.Cf
        data.Ct_ = conn.Ct

        data.bus_data.bus_types = tpes.types
        data.pq_ = tpes.pq
        data.pv_ = tpes.pv
        data.vd_ = tpes.vd
        data.pqpv_ = tpes.no_slack

        data.Qmax_bus_ = qlim.qmax_bus
        data.Qmin_bus_ = qlim.qmin_bus

        control_indices = npa_data.getSimulationIndices(Sbus=data.Sbus_[:, 0])

        data.k_pf_tau = control_indices.k_pf_tau
        data.k_qf_m = control_indices.k_qf_m
        data.k_zero_beq = control_indices.k_zero_beq
        data.k_vf_beq = control_indices.k_vf_beq
        data.k_vt_m = control_indices.k_vt_m
        data.k_qt_m = control_indices.k_qt_m
        data.k_pf_dp = control_indices.k_pf_dp
        data.i_vsc = control_indices.i_vsc
        # data.VfBeqbus = control_indices.iVfBeqBus
        # data.Vtmabus = control_indices.iVtmaBus

        data_lst.append(data)

    return data_lst


def get_newton_pa_pf_options(opt: PowerFlowOptions) -> "npa.PowerFlowOptions":
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
                                retry_with_other_methods=opt.retry_with_other_methods,
                                verbose=opt.verbose,
                                initialize_with_existing_solution=opt.initialize_with_existing_solution,
                                tolerance=opt.tolerance,
                                max_iter=opt.max_iter,
                                control_q_mode=q_control_dict[opt.control_Q],
                                distributed_slack=opt.distributed_slack,
                                correction_parameter=0.5,
                                mu0=opt.mu)


def get_newton_pa_nonlinear_opf_options(pf_opt: PowerFlowOptions,
                                        opf_opt: "OptimalPowerFlowOptions") -> "npa.NonlinearOpfOptions":
    """
    Translate GridCal power flow options to Newton power flow options
    :param pf_opt: PowerFlowOptions instance
    :param opf_opt: OptimalPowerFlowOptions instance
    :return: NonlinearOpfOptions
    """
    q_control_dict = {ReactivePowerControlMode.NoControl: npa.ReactivePowerControlMode.NoControl,
                      ReactivePowerControlMode.Direct: npa.ReactivePowerControlMode.Direct}

    solver_dict = {bs.MIPSolvers.CBC: npa.LpSolvers.Highs,
                   bs.MIPSolvers.HIGHS: npa.LpSolvers.Highs,
                   bs.MIPSolvers.XPRESS: npa.LpSolvers.Xpress,
                   bs.MIPSolvers.CPLEX: npa.LpSolvers.CPLEX,
                   bs.MIPSolvers.GLOP: npa.LpSolvers.Highs,
                   bs.MIPSolvers.SCIP: npa.LpSolvers.Highs,
                   bs.MIPSolvers.GUROBI: npa.LpSolvers.Gurobi}

    return npa.NonlinearOpfOptions(tolerance=pf_opt.tolerance,
                                   max_iter=pf_opt.max_iter,
                                   mu0=pf_opt.mu,
                                   control_q_mode=q_control_dict[pf_opt.control_Q],
                                   flow_control=True,
                                   voltage_control=True,
                                   solver=solver_dict[opf_opt.mip_solver],
                                   initialize_with_existing_solution=pf_opt.initialize_with_existing_solution,
                                   verbose=pf_opt.verbose,
                                   max_vm=opf_opt.max_vm,
                                   max_va=opf_opt.max_va)


def get_newton_pa_linear_opf_options(opf_opt: "OptimalPowerFlowOptions",
                                     pf_opt: PowerFlowOptions,
                                     area_dict):
    """
    Translate GridCal power flow options to Newton power flow options
    :param opf_opt:
    :param pf_opt:
    :param area_dict:
    :return:
    """
    from GridCalEngine.Simulations.OPF.opf_options import ZonalGrouping
    solver_dict = {bs.MIPSolvers.CBC: npa.LpSolvers.Highs,
                   bs.MIPSolvers.HIGHS: npa.LpSolvers.Highs,
                   bs.MIPSolvers.XPRESS: npa.LpSolvers.Xpress,
                   bs.MIPSolvers.CPLEX: npa.LpSolvers.CPLEX,
                   bs.MIPSolvers.GLOP: npa.LpSolvers.Highs,
                   bs.MIPSolvers.SCIP: npa.LpSolvers.Scip,
                   bs.MIPSolvers.GUROBI: npa.LpSolvers.Gurobi}

    grouping_dict = {bs.TimeGrouping.NoGrouping: npa.TimeGrouping.NoGrouping,
                     bs.TimeGrouping.Daily: npa.TimeGrouping.Daily,
                     bs.TimeGrouping.Weekly: npa.TimeGrouping.Weekly,
                     bs.TimeGrouping.Monthly: npa.TimeGrouping.Monthly,
                     bs.TimeGrouping.Hourly: npa.TimeGrouping.Hourly}

    opt = npa.LinearOpfOptions(solver=solver_dict[opf_opt.mip_solver],
                               grouping=grouping_dict[opf_opt.grouping],
                               unit_commitment=opf_opt.unit_commitment,
                               compute_flows=opf_opt.zonal_grouping == ZonalGrouping.NoGrouping,
                               pf_options=get_newton_pa_pf_options(pf_opt))

    opt.check_with_power_flow = False
    opt.add_contingencies = opf_opt.consider_contingencies
    opt.skip_generation_limits = opf_opt.skip_generation_limits
    opt.maximize_area_exchange = opf_opt.maximize_flows
    opt.use_ramp_constraints = False
    opt.lodf_threshold = opf_opt.lodf_tolerance

    if opf_opt.areas_from is not None:
        opt.areas_from = [area_dict[e] for e in opf_opt.areas_from]

    if opf_opt.areas_to is not None:
        opt.areas_to = [area_dict[e] for e in opf_opt.areas_to]

    return opt


def newton_pa_pf(circuit: MultiCircuit,
                 pf_opt: PowerFlowOptions,
                 time_series: bool = False,
                 time_indices: Union[IntVec, None] = None,
                 opf_results: "OptimelPowerFlowResults" = None) -> "npa.PowerFlowResults":
    """
    Newton power flow
    :param circuit: MultiCircuit instance
    :param pf_opt: Power Flow Options
    :param time_series: Compile with GridCal time series?
    :param time_indices: Array of time indices
    :param opf_results: Instance of
    :return: Newton Power flow results object
    """
    npa_circuit, _ = to_newton_pa(circuit,
                                  use_time_series=time_series,
                                  time_indices=None,
                                  override_branch_controls=pf_opt.override_branch_controls,
                                  opf_results=opf_results)

    pf_options = get_newton_pa_pf_options(pf_opt)

    if time_series:
        # it is already sliced to the relevant time indices
        if time_indices is None:
            time_indices = [i for i in range(circuit.get_time_number())]
        else:
            time_indices = list(time_indices)
        n_threads = 0  # max threads
    else:
        time_indices = [0]
        n_threads = 1

    pf_res = npa.runPowerFlow(circuit=npa_circuit,
                              pf_options=pf_options,
                              time_indices=time_indices,
                              n_threads=n_threads,
                              V0=circuit.get_voltage_guess() if pf_opt.initialize_with_existing_solution else None)

    return pf_res


def newton_pa_contingencies(circuit: MultiCircuit,
                            pf_opt: PowerFlowOptions,
                            con_opt: "ContingencyAnalysisOptions",
                            time_series: bool = False,
                            time_indices: Union[IntVec, None] = None) -> "npa.ContingencyAnalysisResults":
    """
    Newton power flow
    :param circuit: MultiCircuit instance
    :param pf_opt: Power Flow Options
    :param con_opt: ContingencyAnalysisOptions
    :param time_series: Compile with GridCal time series?
    :param time_indices: Array of time indices
    :return: Newton Power flow results object
    """
    npa_circuit, _ = to_newton_pa(circuit,
                                  use_time_series=time_series,
                                  time_indices=None,
                                  override_branch_controls=pf_opt.override_branch_controls)

    pf_options = get_newton_pa_pf_options(pf_opt)

    if time_series:
        # it is already sliced to the relevant time indices
        if time_indices is None:
            time_indices = [i for i in range(circuit.get_time_number())]
        else:
            time_indices = list(time_indices)
        n_threads = 0  # max threads
    else:
        time_indices = [0]
        n_threads = 1

    if con_opt.engine == bs.ContingencyEngine.PTDF:
        mode = npa.ContingencyAnalysisMode.Linear
    elif con_opt.engine == bs.ContingencyEngine.PowerFlow:
        mode = npa.ContingencyAnalysisMode.Full
    else:
        mode = npa.ContingencyAnalysisMode.Full

    # npa.FileHandler().save(npa_circuit, "whatever.newton")

    # print('time_indices')
    # print(time_indices)

    con_res = npa.runContingencyAnalysis(circuit=npa_circuit,
                                         pf_options=pf_options,
                                         time_indices=time_indices,
                                         mode=mode,
                                         n_threads=n_threads)

    return con_res


def newton_pa_linear_opf(circuit: MultiCircuit,
                         opf_options: "OptimalPowerFlowOptions",
                         pf_opt: PowerFlowOptions,
                         time_series=False,
                         time_indices: Union[IntVec, None] = None) -> "npa.LinearOpfResults":
    """
    Newton power flow
    :param circuit: MultiCircuit instance
    :param opf_options:
    :param pf_opt: Power Flow Options
    :param time_series: Compile with GridCal time series?
    :param time_indices: Array of time indices
    :return: Newton Power flow results object
    """
    npa_circuit, (bus_dict, area_dict, zone_dict) = to_newton_pa(circuit=circuit,
                                                                 use_time_series=time_series,
                                                                 time_indices=None,  # the slicing is done below
                                                                 override_branch_controls=False)

    if time_series:
        # it is already sliced to the relevant time indices
        if time_indices is None:
            time_indices = [i for i in range(circuit.get_time_number())]
        else:
            time_indices = list(time_indices)
        n_threads = 0  # max threads
    else:
        time_indices = [0]
        n_threads = 1

    options = get_newton_pa_linear_opf_options(opf_options, pf_opt, area_dict)

    pf_res = npa.runLinearOpf(circuit=npa_circuit,
                              options=options,
                              time_indices=time_indices,
                              n_threads=n_threads,
                              mute_pg_bar=False)

    return pf_res


def newton_pa_nonlinear_opf(circuit: MultiCircuit,
                            pf_opt: PowerFlowOptions,
                            opf_opt: "OptimalPowerFlowOptions",
                            time_series=False,
                            time_indices: Union[IntVec, None] = None) -> "npa.NonlinearOpfResults":
    """
    Newton power flow
    :param circuit: MultiCircuit instance
    :param pf_opt: Power Flow Options
    :param opf_opt: OptimalPowerFlowOptions
    :param time_series: Compile with GridCal time series?
    :param time_indices: Array of time indices
    :return: Newton Power flow results object (NonlinearOpfResults)
    """
    npa_circuit, (bus_dict, area_dict, zone_dict) = to_newton_pa(circuit=circuit,
                                                                 use_time_series=time_series,
                                                                 time_indices=None,  # the slicing is done below
                                                                 override_branch_controls=False)

    pf_options = get_newton_pa_nonlinear_opf_options(pf_opt, opf_opt)

    if time_series:
        # it is already sliced to the relevant time indices
        if time_indices is None:
            time_indices = [i for i in range(circuit.get_time_number())]
        else:
            time_indices = list(time_indices)
        n_threads = 0  # max threads
    else:
        time_indices = [0]
        n_threads = 1

    pf_res = npa.runNonlinearOpf(circuit=npa_circuit,
                                 pf_options=pf_options,
                                 time_indices=time_indices,
                                 n_threads=n_threads,
                                 mute_pg_bar=False,
                                 V0=circuit.get_voltage_guess() if pf_opt.use_stored_guess else None)

    return pf_res


def newton_pa_linear_matrices(circuit: MultiCircuit, distributed_slack=False, override_branch_controls=False):
    """
    Newton linear analysis
    :param circuit: MultiCircuit instance
    :param distributed_slack: distribute the PTDF slack
    :param override_branch_controls: Override branch controls
    :return: Newton LinearAnalysisMatrices object
    """
    npa_circuit, _ = to_newton_pa(circuit=circuit,
                                  use_time_series=False,
                                  override_branch_controls=override_branch_controls)

    options = npa.LinearAnalysisOptions(distribute_slack=distributed_slack)
    results = npa.runLinearAnalysisAt(t=0, circuit=npa_circuit, options=options)

    return results


def convert_bus_types(arr: List["npa.BusType"]) -> IntVec:
    """
    Convert list of Newton bus types to an array of GridCal compatible bus type integers
    :param arr: Array of Newton bus types
    :return: Array of integers representing GridCal bus types
    """
    tpe = np.zeros(len(arr), dtype=int)
    for i, val in enumerate(arr):
        if val == npa.BusType.VD:
            tpe[i] = 3
        elif val == npa.BusType.PV:
            tpe[i] = 2
        elif val == npa.BusType.PQ:
            tpe[i] = 1
    return tpe


def translate_newton_pa_pf_results(grid: MultiCircuit, res: "npa.PowerFlowResults") -> PowerFlowResults:
    """
    Translate the Newton Power Analytics results back to GridCal
    :param grid: MultiCircuit instance
    :param res: Newton's PowerFlowResults instance
    :return: PowerFlowResults instance
    """
    results = PowerFlowResults(n=grid.get_bus_number(),
                               m=grid.get_branch_number_wo_hvdc(),
                               n_hvdc=grid.get_hvdc_number(),
                               bus_names=res.bus_names,
                               branch_names=res.branch_names,
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
    results.tap_angle = res.tap_angle[0, :]
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
    results.bus_types = convert_bus_types(res.bus_types[0])  # this is a list of lists

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


def translate_newton_pa_opf_results(grid: MultiCircuit, res: "npa.NonlinearOpfResults") -> "OptimalPowerFlowResults":
    """
    Translate Newton OPF results to GridCal
    :param grid: MultiCircuit instance
    :param res: NonlinearOpfResults instance
    :return: OptimalPowerFlowResults instance
    """
    from GridCalEngine.Simulations.OPF.opf_results import OptimalPowerFlowResults
    results = OptimalPowerFlowResults(bus_names=res.bus_names,
                                      branch_names=res.branch_names,
                                      load_names=res.load_names,
                                      generator_names=res.generator_names,
                                      battery_names=res.battery_names,
                                      hvdc_names=res.hvdc_names,
                                      bus_types=convert_bus_types(res.bus_types[0]),
                                      area_names=[a.name for a in grid.areas],
                                      F=res.F,
                                      T=res.T,
                                      F_hvdc=res.hvdc_F,
                                      T_hvdc=res.hvdc_T,
                                      bus_area_indices=grid.get_bus_area_indices())

    results.Sbus = res.Scalc[0, :],
    results.voltage = res.voltage[0, :],
    results.load_shedding = res.load_shedding[0, :],
    results.hvdc_power = res.hvdc_Pf[0, :],
    results.hvdc_loading = res.hvdc_loading[0, :] * 100.0,
    results.phase_shift = res.tap_angle[0, :],
    results.bus_shadow_prices = res.bus_shadow_prices[0, :],
    results.generator_shedding = res.generator_shedding[0, :],
    results.battery_power = res.battery_p[0, :],
    results.controlled_generation_power = res.generator_p[0, :],
    results.Sf = res.Sf[0, :],
    results.St = res.St[0, :],
    results.overloads = res.branch_overload[0, :],
    results.loading = res.Loading[0, :],
    results.rates = res.rates[0, :],
    results.contingency_rates = res.contingency_rates[0, :],
    results.converged = res.converged[0],

    results.contingency_flows_list = list()
    results.losses = res.Losses[0, :]

    results.hvdc_F = res.hvdc_F
    results.hvdc_T = res.hvdc_T
    results.hvdc_loading = res.hvdc_loading[0, :]
    # results.hvdc_losses = res.hvdc_losses[0, :]
    results.bus_area_indices = grid.get_bus_area_indices()
    results.area_names = [a.name for a in grid.areas]
    results.bus_types = convert_bus_types(res.bus_types[0])
    results.converged = res.stats[0][0].converged[0]

    print(res.stats[0][0].getTable())

    return results


def debug_newton_pa_circuit_at(npa_circuit: "npa.HybridCircuit", t: int = None):
    """
    Debugging function
    :param npa_circuit: Newton's HybridCircuit
    :param t: time index
    """
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
