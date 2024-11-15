from pypower import loadcase, runpf
import pandapower as pp
from pandapower.converter import from_mpc
import pandas as pd
import GridCalEngine as gce

fname = "/home/santi/matpower8.0b1/data/case1354pegase.m"

br_data_mp = pd.read_csv("output.csv")
br_data_gc = pd.read_csv("output_gc.csv")

# net = from_mpc(fname)
# pp.runpp(net)
#
# if net["converged"]:
#     print("Power flow solved successfully!")
#     print(net.res_bus)  # Bus results (voltage, angle, etc.)
#     print(net.res_gen)  # Generator results (generation, cost, etc.)
#     print(net.res_line)  # Branch results (power flow, losses, etc.)

grid = gce.open_file(filename=fname)
gc_res = gce.power_flow(grid=grid,
                        options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                                     retry_with_other_methods=False,
                                                     use_stored_guess=True))

print(gc_res.get_bus_df())

# pp_case = loadcase.loadcase(fname)
# pp_res = runpf.runpf(pp_case)

print()
