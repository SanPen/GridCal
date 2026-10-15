import os
import pandas as pd
import multiprocessing as mp
import VeraGridEngine as gce

folder = "/home/santi/matpower8.1/data"


def run_grid(fname: str) -> dict[str, object]:
    """
    Run a power flow case and collect benchmark metadata.

    :param fname:
        Path to the MATPOWER grid file.
    :return:
        Dictionary with the benchmark result fields for the grid.
    """
    # Load the grid once inside the worker process so each process owns its state.
    grid = gce.open_file(fname)
    # Keep the file name separate from the full path for the report output.
    name = os.path.basename(fname)

    if grid.get_bus_number() > 0:
        # Run the normal Newton-Raphson flow first because that is the benchmark target.
        res = gce.power_flow(
            grid=grid,
            options=gce.PowerFlowOptions(solver_type=gce.SolverType.NR,
                                         retry_with_other_methods=False,
                                         use_stored_guess=False)
        )
        flat_start = True

        if not res.converged:
            # Retry from the stored guess so difficult cases still get a fair second attempt.
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


def collect_matpower_files(root_folder: str) -> list[str]:
    """
    Collect MATPOWER case files from a root directory.

    :param root_folder:
        Folder containing MATPOWER `.m` case files.
    :return:
        List of absolute file paths for the discovered cases.
    """
    files_list: list[str] = list()

    # Walk the tree once and keep only MATPOWER case files for the benchmark pool.
    for root, dirs, files in os.walk(root_folder):
        del dirs
        for file_name in files:
            if file_name.endswith(".m"):
                path: str = os.path.join(root, file_name)
                files_list.append(path)
            else:
                pass

    return files_list


def main() -> None:
    """
    Execute the MATPOWER benchmark suite.

    :return:
        None.
    """
    # Trigger one serial run first so the engine performs any one-time initialization up front.
    gce.power_flow(gce.open_file(os.path.join(folder, "case_ieee30.m")))

    # Build the workload list before creating the process pool.
    files_list: list[str] = collect_matpower_files(folder)

    # The pool must only be created under the main guard because Python 3.14 uses
    # spawn/forkserver semantics that re-import this module in child processes.
    with mp.Pool(mp.cpu_count()) as pool:
        data: list[dict[str, object]] = pool.map(run_grid, files_list)

    # Export the benchmark table after all worker results have been collected.
    df = pd.DataFrame(data).sort_values(by='n_buses', ascending=False)
    df.to_excel("All matpower grids.xlsx", index=False)


if __name__ == "__main__":
    mp.freeze_support()
    main()
