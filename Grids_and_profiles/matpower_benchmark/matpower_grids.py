import os
import pandas as pd
import multiprocessing as mp
import VeraGridEngine as gce

folder = "/home/santi/matpower8.0b1/data"


def run_grid(fname):
    """
    Run individual grid
    :param fname: file name
    :return: information about the run
    """
    grid = gce.open_file(fname)
    name = os.path.basename(fname)

    if grid.get_bus_number() > 0:

        res = gce.power_flow(
            grid=grid,
            options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                         retry_with_other_methods=False,
                                         use_stored_guess=False)
        )
        flat_start = True

        if not res.converged:
            # if it does not converge, retry with the provided solution
            res = gce.power_flow(
                grid=grid,
                options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                             retry_with_other_methods=False,
                                             use_stored_guess=True)
            )
            flat_start = False

        info = {
            "name": name,
            "n_buses": grid.get_bus_number(),
            "n_branches": grid.get_branch_number(add_vsc=False,
                                                 add_hvdc=False,
                                                 add_switch=True),
            "P imbalance (%)": grid.get_imbalance() * 100.0,
            "Flat start": flat_start,
            "converged": res.converged,
            "error (p.u.)": res.error,
            "iterations": res.iterations,
            "time (s)": res.elapsed,
        }

    else:
        info = {
            "name": name,
            "n_buses": grid.get_bus_number(),
            "n_branches": grid.get_branch_number(add_vsc=False,
                                                 add_hvdc=False,
                                                 add_switch=True),
            "P imbalance (%)": 0.0,
            "Flat start": True,
            "converged": True,
            "error (p.u.)": 0,
            "iterations": 0,
            "time (s)": 0,
        }

    return info


# run this one to compile the stuff
# gce.power_flow(gce.open_file(os.path.join(folder, "/home/santi/matpower8.0b1/data/case5.m")))
gce.power_flow(gce.open_file(os.path.join(folder, "case_ieee30.m")))

data = list()
files_list = list()
for root, dirs, files in os.walk(folder):
    for file in files:
        if file.endswith(".m"):
            path = os.path.join(root, file)
            files_list.append(path)

with mp.Pool(mp.cpu_count()) as p:
    data = p.map(run_grid, files_list)

df = pd.DataFrame(data).sort_values(by='n_buses', ascending=False)
df.to_excel("All matpower grids.xlsx", index=False)
