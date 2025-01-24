import numpy as np
import pandas as pd
import pandapower as pp
import GridCalEngine.api as gce  # For interfacing with the GridCal API
from typing import Tuple
import os
from GridCalEngine.basic_structures import Logger
from GridCalEngine.IO.file_handler import FileOpen
from GridCalEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from GridCalEngine.Simulations.PowerFlow.power_flow_options import SolverType
from GridCalEngine.Simulations.PowerFlow.power_flow_results import NumericPowerFlowResults

from GridCalEngine.Simulations.PowerFlow.Formulations.pf_generalized_formulation import PfGeneralizedFormulation
from GridCalEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx


def create_pp_network():
    # Create an empty network
    net = pp.create_empty_network()

    # Adding buses
    bus1 = pp.create_bus(net, name="Bus 1", vn_kv=110, min_vm_pu=0.9, max_vm_pu=1.1)
    bus2 = pp.create_bus(net, name="Bus 2", vn_kv=110, min_vm_pu=0.9, max_vm_pu=1.1)
    bus3 = pp.create_bus(net, name="Bus 3", vn_kv=20, min_vm_pu=0.9, max_vm_pu=1.1)
    bus4 = pp.create_bus(net, name="Bus 4", vn_kv=20, min_vm_pu=0.9, max_vm_pu=1.1)

    # Adding an external grid connection at Bus 1
    ext_grid = pp.create_ext_grid(net, name="Grid Connection", bus=bus1, vm_pu=1.02)

    # Adding line
    # It has the following parameters: r=0.642 ohm/km, x=0.083 ohm/km, c=210.0 nF/km
    line1 = pp.create_line(net, name="line 1", from_bus=bus1, to_bus=bus2, length_km=10, std_type="NAYY 4x50 SE")
    line2 = pp.create_line(net, name="line 2", from_bus=bus3, to_bus=bus4, length_km=3, std_type="NAYY 4x50 SE")
    line3 = pp.create_line(net, name="line 3", from_bus=bus2, to_bus=bus3, length_km=3, std_type="NAYY 4x50 SE")

    trafo1 = pp.create_transformer_from_parameters(net, bus2, bus3,
                                                   name="110kV/20kV transformer",
                                                   sn_mva=100,
                                                   vn_hv_kv=110, vn_lv_kv=20,
                                                   vkr_percent=0.8, vk_percent=0.8, pfe_kw=1,
                                                   i0_percent=0.1)


    # Adding load to Bus 2
    load1 = pp.create_load(net, name="Load 1", bus=bus4, p_mw=30.0, q_mvar=20.0)

    sgen1 = pp.create_sgen(net, name="sgen 1", bus=bus3, p_mw=4.0, q_mvar=2,
                           min_p_mw=0, max_p_mw=4.0, min_q_mvar=0,  max_q_mvar=2,
                           sn_mva=100, in_service=True)

    # switch1 = pp.create_switch(net, name="switch 1", bus=bus3, et='l', element=line2)

    shunt1 = pp.create_shunt(net, name="shunt 1", bus=bus2, p_mw=0, q_mvar=30)


    return net


def create_gc_network():
    # Create a new Grid
    grid = gce.MultiCircuit()

    # Create buses
    bus1 = gce.Bus(name='Bus 1', Vnom=float(110.))
    bus2 = gce.Bus(name='Bus 2', Vnom=float(110.))
    bus3 = gce.Bus(name='Bus 3', Vnom=float(20.))
    bus4 = gce.Bus(name='Bus 4', Vnom=float(20.))

    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus3)
    grid.add_bus(bus4)

    # Adding a line between Bus 1 and Bus 2
    # zzz1, yyy1 = z_ohm_to_pu(r=0.642, x=0.083, c=210.0, length=10, Sbase=100, Vbase=110., fbase=50)
    line1 = gce.Line(bus_from=bus1,  bus_to=bus2)
    line1.fill_design_properties(r_ohm=0.642, x_ohm=0.083, c_nf=210.0, length=10, Imax=100,
                                 freq=grid.fBase, Sbase=grid.Sbase)

    grid.add_line(line1)

    # Adding a line between Bus 3 and Bus 4
    # zzz2, yyy2 = z_ohm_to_pu(r=0.642, x=0.083, c=210.0, length=3, Sbase=100, Vbase=20., fbase=50)
    line2 = gce.Line(bus_from=bus3, bus_to=bus4)
    line2.fill_design_properties(r_ohm=0.642, x_ohm=0.083, c_nf=210.0, length=3, Imax=100,
                                 freq=grid.fBase, Sbase=grid.Sbase)
    grid.add_line(line2)

    # Adding a line between Bus 2 and Bus 3
    # zzz2, yyy2 = z_ohm_to_pu(r=0.642, x=0.083, c=210.0, length=3, Sbase=100, Vbase=110., fbase=50)
    line3 = gce.Line(bus_from=bus2, bus_to=bus3)
    line3.fill_design_properties(r_ohm=0.642, x_ohm=0.083, c_nf=210.0, length=3, Imax=100,
                                 freq=grid.fBase, Sbase=grid.Sbase)
    grid.add_line(line3)

    Transformer1 = gce.Transformer2W(bus_from=bus2, bus_to=bus3, name='Transformer 1',
                                     HV=110, LV=20, nominal_power=100,
                                     copper_losses=1, r=0.01, x=0.1)
    Transformer1.fill_design_properties(Pcu=0, Pfe=1, Vsc=0.8, I0=0.1, Sbase=grid.Sbase)
    grid.add_transformer2w(Transformer1)

    # Adding a load at Bus 2
    load = gce.Load(name="Load 1", P=30.0, Q=20.0)  # Active and reactive power in MW and MVar
    grid.add_load(bus=bus4, api_obj=load)  # Adding the load to the bus

    # Adding a generator at Bus 1
    gen = gce.ExternalGrid(name="Grid Connection", Vm=1.02, mode=gce.ExternalGridMode.VD)  # Active power in MW and voltage set point in p.u.
    grid.add_external_grid(bus=bus1, api_obj=gen)  # Adding the generator to the bus

    gen = gce.StaticGenerator(name="sgen1", P=4.0, Q=2, )  # Active power in MW and voltage set point in p.u.
    grid.add_static_generator(bus=bus3, api_obj=gen)  # Adding the generator to the bus

    # Adding a generator at Switch 1
    # switch1 = gce.Switch(name="switch1", bus_from=bus3,
    #                  bus_to=bus4,
    #                  r=zzz2.real,
    #                  x=zzz2.imag,
    #                  active = True,
    #                  normal_open=False)
    # grid.add_switch(switch1)  # Adding the generator to the bus

    # adding a shunt to bus2
    shunt1 = gce.Shunt(name="shunt1", G=0, B=30, active=True)
    grid.add_shunt(bus=bus2, api_obj=shunt1)

    return grid


def solve_generalized(grid: gce.MultiCircuit,
                      options: PowerFlowOptions) -> Tuple[PfGeneralizedFormulation, NumericPowerFlowResults]:
    """

    :param grid:
    :param options:
    :return:
    """
    nc = gce.compile_numerical_circuit_at(
        grid,
        t_idx=None,
        apply_temperature=False,
        branch_tolerance_mode=gce.BranchImpedanceMode.Specified,
        opf_results=None,
        use_stored_guess=False,
        bus_dict=None,
        areas_dict=None,
        control_taps_modules=options.control_taps_modules,
        control_taps_phase=options.control_taps_phase,
        control_remote_voltage=options.control_remote_voltage,
    )

    islands = nc.split_into_islands(consider_hvdc_as_island_links=True)
    logger = Logger()

    island = islands[0]

    Vbus = island.bus_data.Vbus
    S0 = island.get_power_injections_pu()
    I0 = island.get_current_injections_pu()
    Y0 = island.get_admittance_injections_pu()
    Qmax_bus, Qmin_bus = island.get_reactive_power_limits()
    problem = PfGeneralizedFormulation(V0=Vbus,
                                       S0=S0,
                                       I0=I0,
                                       Y0=Y0,
                                       Qmin=Qmin_bus,
                                       Qmax=Qmax_bus,
                                       nc=island,
                                       options=options,
                                       logger=logger)

    solution = newton_raphson_fx(problem=problem,
                                 tol=options.tolerance,
                                 max_iter=options.max_iter,
                                 trust=options.trust_radius,
                                 verbose=options.verbose,
                                 logger=logger)

    logger.print("Logger")

    return problem, solution


gridPP1 = create_pp_network()
gridGC1 = create_gc_network()

#Pandapower power flow
pp.runpp(gridPP1)


#GridCal network power flow
options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
power_flowGC1 = gce.power_flow(gridGC1, options)

pp_df = pd.DataFrame(data={
    "Vm": gridPP1.res_bus.vm_pu,
    "Va": gridPP1.res_bus.va_degree,
    "P": gridPP1.res_bus.p_mw,
    "Q": gridPP1.res_bus.q_mvar,
})

# Generalized
formulation, res = solve_generalized(gridGC1, options)

# print(f"result from PandaPower file : {gridPP1.res_line.pl_mw.sum()*1000}+{gridPP1.res_line.ql_mvar.sum()*1000}j")
# print(f"    {np.array(gridPP1.res_bus.vm_pu[:8])}")

# print(f"result from GridCal file : Converged:{power_flowGC1.results.converged}  {power_flowGC1.results.losses.sum()/1000}")
# print(f"    {power_flowGC1.results.voltage.real[:8]}")

print("PP results\n", pp_df)
# print("error:", gridPP1._ppc["internal"]["residual_p"])

print("GC results\n", power_flowGC1.get_bus_df())
print("error:", power_flowGC1.error)

print(res.Scalc)