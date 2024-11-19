import os
import pandas as pd
import GridCalEngine as gce

folder = "/home/santi/matpower8.0b1/data"

# run this one to compile the stuff
# gce.power_flow(gce.open_file(os.path.join(folder, "/home/santi/matpower8.0b1/data/case5.m")))
gce.power_flow(gce.open_file(os.path.join(folder, "case_ieee30.m")))

data = list()
for root, dirs, files in os.walk(folder):
    for file in files:
        if file.endswith(".m"):
            path = os.path.join(root, file)

            print(path)
            grid = gce.open_file(path)

            if grid.get_bus_number() > 0:

                res = gce.power_flow(
                    grid=grid,
                    options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                                 retry_with_other_methods=False,
                                                 use_stored_guess=False)
                )
                used_v0 = False

                if not res.converged:
                    # if it does not converge, retry with the provided solution
                    res = gce.power_flow(
                        grid=grid,
                        options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                                     retry_with_other_methods=False,
                                                     use_stored_guess=True)
                    )
                    used_v0 = True

                info = {
                    "name": file,
                    "n_buses": grid.get_bus_number(),
                    "n_branches": grid.get_branch_number(),
                    "P imbalance (%)": grid.get_imbalance() * 100.0,
                    "Used V0": used_v0,
                    "converged": res.converged,
                    "error (p.u.)": res.error,
                    "iterations": res.iterations,
                    "time (s)": res.elapsed,
                }

                print(info)

                data.append(info)

df = pd.DataFrame(data)
df.to_excel("All matpower grids.xlsx", index=False)
