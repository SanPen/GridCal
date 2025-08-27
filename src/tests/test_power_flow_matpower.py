import os
import time
import pandas as pd
import multiprocessing as mp
import VeraGridEngine as gce


def run_grid(fname):
    """

    :param fname:
    :return:
    """
    grid = gce.open_file(fname)
    name = os.path.basename(fname)

    if grid.get_bus_number() > 0:

        res = gce.power_flow(
            grid=grid,
            options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                         retry_with_other_methods=False,
                                         use_stored_guess=False),
            # engine=gce.EngineType.GSLV
        )
        flat_start = True

        if not res.converged:
            # if it does not converge, retry with the provided solution
            res = gce.power_flow(
                grid=grid,
                options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                             retry_with_other_methods=False,
                                             use_stored_guess=True),
                # engine=gce.EngineType.GSLV
            )
            flat_start = False

        # info = {
        #     "name": name,
        #     "n_buses": grid.get_bus_number(),
        #     "n_branches": grid.get_branch_number(),
        #     "P imbalance (%)": grid.get_imbalance() * 100.0,
        #     "Flat start": flat_start,
        #     "converged": res.converged,
        #     "error (p.u.)": res.error,
        #     "iterations": res.iterations,
        #     "time (s)": res.elapsed,
        # }

        return res.converged
    else:
        # info = {
        #     "name": name,
        #     "n_buses": grid.get_bus_number(),
        #     "n_branches": grid.get_branch_number(),
        #     "P imbalance (%)": 0.0,
        #     "Flat start": True,
        #     "converged": True,
        #     "error (p.u.)": 0,
        #     "iterations": 0,
        #     "time (s)": 0,
        # }

        return True


def test_all_matpower_grids():
    """
    Check all matpower grids converge
    :return:
    """
    # run this one to compile the stuff
    folder = os.path.join("data", "grids", "Matpower")
    gce.power_flow(gce.open_file(os.path.join(folder, "case_ieee30.m")))


    start_time = time.time()

    for root, dirs, files in os.walk(folder):
        for file in files:
            if file.endswith(".m"):
                path = os.path.join(root, file)
                assert run_grid(path)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Execution time: {elapsed_time:.2f} seconds")


if __name__ == "__main__":

    test_all_matpower_grids()

