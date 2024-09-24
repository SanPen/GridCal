from __future__ import annotations

import numpy as np
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.DataStructures.numerical_circuit import NumericalCircuit, compile_numerical_circuit_at
from GridCalEngine.ThirdParty.ParaEMT.Lib_BW import PFData, DyData
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import multi_island_pf_nc
from GridCalEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCalEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.common_functions import compute_zip_power


def get_pf_data(grid: MultiCircuit,
                t_idx: None | int = None,
                pf_options: PowerFlowOptions | None = None) -> PFData:
    """
    Compile GridCal data at t_idx for ParaEMT
    :param grid: MultiCircuit
    :param t_idx: some time index of the profile or None for the snapshot
    :param pf_options: Power Flow options, if None some default ones will be used
    :return:
    """
    if pf_options is None:
        pf_options = PowerFlowOptions()

    # compile the numerical circuit
    nc: NumericalCircuit = compile_numerical_circuit_at(grid, t_idx=t_idx)

    # compute the power flow
    pf_results: PowerFlowResults = multi_island_pf_nc(nc=nc, options=pf_options)

    # start filling the ParaEMT data
    emt_data = PFData()

    # system data
    emt_data.basemva = [grid.Sbase]
    emt_data.ws = [2.0 * np.pi * grid.fBase]

    # bus data
    emt_data.bus_num = np.arange(nc.nbus) + 1
    emt_data.bus_type = nc.bus_data.bus_types
    emt_data.bus_Vm = np.abs(pf_results.voltage)
    emt_data.bus_Va = np.angle(pf_results.voltage)  # TODO: deg or rad? seems to be RAD
    emt_data.bus_kV = nc.bus_data.Vnom * emt_data.bus_Vm
    emt_data.bus_basekV = nc.bus_data.Vnom
    emt_data.bus_name = nc.bus_data.names

    # load data
    S_load = compute_zip_power(
        S=nc.load_data.C_bus_elm @ (nc.load_data.S * nc.load_data.active),
        I=nc.load_data.C_bus_elm @ (nc.load_data.I * nc.load_data.active),
        Y=nc.load_data.C_bus_elm @ (nc.load_data.Y * nc.load_data.active),
        Vm=emt_data.bus_Vm
    )
    emt_data.load_id = np.arange(nc.nload) + 1
    emt_data.load_bus = nc.load_data.get_bus_indices() + 1
    emt_data.load_Z = 1.0 / nc.load_data.Y * nc.load_data.active
    emt_data.load_I = nc.load_data.I * nc.load_data.active
    emt_data.load_P = nc.load_data.S * nc.load_data.active
    emt_data.load_MW = S_load.real
    emt_data.load_Mvar = S_load.imag

    # IBR data
    emt_data.ibr_bus = np.asarray([])
    emt_data.ibr_id = np.asarray([])
    emt_data.ibr_MW = np.asarray([])
    emt_data.ibr_Mvar = np.asarray([])
    emt_data.ibr_MVA_base = np.asarray([])

    # generator data
    emt_data.gen_id = np.arange(nc.ngen) + 1
    emt_data.gen_bus = np.asarray([])
    emt_data.gen_S = np.asarray([])
    emt_data.gen_mod = np.asarray([])
    emt_data.gen_MW = np.asarray([])
    emt_data.gen_Mvar = np.asarray([])
    emt_data.gen_MVA_base = np.asarray([])

    # line data
    emt_data.line_from = np.asarray([])
    emt_data.line_to = np.asarray([])
    emt_data.line_id = np.asarray([])
    emt_data.line_P = np.asarray([])
    emt_data.line_Q = np.asarray([])
    emt_data.line_RX = np.asarray([])
    emt_data.line_chg = np.asarray([])

    # xfmr data
    emt_data.xfmr_from = np.asarray([])
    emt_data.xfmr_to = np.asarray([])
    emt_data.xfmr_id = np.asarray([])
    emt_data.xfmr_P = np.asarray([])
    emt_data.xfmr_Q = np.asarray([])
    emt_data.xfmr_RX = np.asarray([])
    emt_data.xfmr_k = np.asarray([])

    # shunt data
    emt_data.shnt_bus = np.asarray([])
    emt_data.shnt_id = np.asarray([])
    emt_data.shnt_gb = np.asarray([])

    # switched shunt data
    emt_data.shnt_sw_bus = np.asarray([])
    emt_data.shnt_sw_gb = np.asarray([])

    return emt_data


def get_dyn_data(grid: MultiCircuit) -> DyData:
    dyd0 = DyData()

    return dyd0