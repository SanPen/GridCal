from __future__ import annotations

import csv
import math
import timeit
from pathlib import Path
from typing import List, Tuple
import numpy as np

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.Simulations.OPF.Formulations.ac_opf_problem import NonlinearOPFResults, NonLinearOptimalPfProblem
from VeraGridEngine.Simulations.OPF.ac_opf_worker import run_nonlinear_opf
from VeraGridEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from VeraGridEngine.Simulations.OPF.NumericalMethods.newton_raphson_ips_fx import interior_point_solver
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.basic_structures import IntVec, Logger
from VeraGridEngine.enumerations import AcOpfMode, SolverType
from VeraGridEngine import ShuntControlMode


class BaselineEntry:
    """
    One AC baseline row parsed from the PGLIB markdown file.
    """
    __slots__ = (
        "group_name",
        "case_name",
        "nodes",
        "edges",
        "ac_objective",
        "ac_time_seconds",
    )

    def __init__(self,
                 group_name: str,
                 case_name: str,
                 nodes: int,
                 edges: int,
                 ac_objective: float,
                 ac_time_seconds: float) -> None:
        """
        Build one baseline entry.

        :param group_name: Benchmark group name such as ``TYP``, ``API`` or ``SAD``.
        :param case_name: PGLIB case stem without file extension.
        :param nodes: Number of buses from the baseline table.
        :param edges: Number of edges from the baseline table.
        :param ac_objective: Baseline AC objective value.
        :param ac_time_seconds: Baseline AC solve time in seconds.
        """
        self.group_name: str = group_name
        self.case_name: str = case_name
        self.nodes: int = nodes
        self.edges: int = edges
        self.ac_objective: float = ac_objective
        self.ac_time_seconds: float = ac_time_seconds


class BenchmarkRow:
    """
    One VeraGrid ACOPF benchmark result row.
    """
    __slots__ = (
        "group_name",
        "case_name",
        "file_path",
        "nodes",
        "edges",
        "baseline_ac_objective",
        "baseline_ac_time_seconds",
        "veragrid_ac_objective",
        "objective_gap_percent",
        "runtime_seconds",
        "iterations",
        "converged",
        "pf_init_used",
        "solver_error",
        "status",
    )

    def __init__(self) -> None:
        """
        Build one empty benchmark row so fields can be filled explicitly step by step.
        """
        self.group_name: str = ""
        self.case_name: str = ""
        self.file_path: str = ""
        self.nodes: int = 0
        self.edges: int = 0
        self.baseline_ac_objective: float = math.nan
        self.baseline_ac_time_seconds: float = math.nan
        self.veragrid_ac_objective: float = math.nan
        self.objective_gap_percent: float = math.nan
        self.runtime_seconds: float = math.nan
        self.iterations: int = 0
        self.converged: bool = False
        self.pf_init_used: bool = False
        self.solver_error: float = math.nan
        self.status: str = ""


class BenchmarkConfig:
    """
    Explicit benchmark configuration for the standalone ACOPF benchmark script.
    """
    __slots__ = (
        "ips_tolerance",
        "ips_iterations",
        "verbose",
        "benchmark_root",
        "matpower_folder",
        "baseline_path",
        "output_path",
    )

    def __init__(self,
                 ips_tolerance: float,
                 ips_iterations: int,
                 verbose: int,
                 benchmark_root: Path,
                 baseline_path: Path,
                 output_path: Path) -> None:
        """
        Build one immutable-like benchmark configuration object.

        :param ips_tolerance: IPS convergence tolerance.
        :param ips_iterations: Maximum IPS iterations.
        :param verbose: VeraGrid ACOPF verbosity.
        :param benchmark_root: Root directory of the benchmark archive.
        :param baseline_path: Path to the benchmark baseline markdown.
        :param output_path: CSV file destination path.
        """
        self.ips_tolerance: float = ips_tolerance
        self.ips_iterations: int = ips_iterations
        self.verbose: int = verbose
        self.benchmark_root: Path = benchmark_root
        self.baseline_path: Path = baseline_path
        self.output_path: Path = output_path


def split_markdown_row(line: str) -> List[str]:
    """
    Split one markdown table row into stripped cell values.

    :param line: Markdown table row.
    :return: Cell values without the leading and trailing pipe characters.
    """
    parts_raw: List[str] = line.strip().split("|")
    parts: List[str] = list()
    for part in parts_raw[1:-1]:
        parts.append(part.strip())
    return parts


def parse_baseline_time(value: str) -> float:
    """
    Parse one baseline time cell from ``BASELINE.md``.

    :param value: Markdown cell content.
    :return: Solve time in seconds, using ``0.5`` for ``<1`` and ``inf`` for ``inf.``.
    """
    parsed_value: float

    if value == "<1":
        parsed_value = 0.5
    else:
        if value.lower().startswith("inf"):
            parsed_value = math.inf
        else:
            parsed_value = float(value)

    return parsed_value


def parse_baseline_float(value: str) -> float:
    """
    Parse one baseline numeric cell.

    :param value: Markdown cell content.
    :return: Parsed float, including ``inf`` values.
    """
    parsed_value: float

    if value.lower().startswith("inf"):
        parsed_value = math.inf
    else:
        parsed_value = float(value)

    return parsed_value


def parse_baseline_group_name(line: str) -> str:
    """
    Translate one section heading from the baseline markdown into the compact group code.

    :param line: Section heading line from the markdown file.
    :return: ``TYP``, ``API`` or ``SAD``.
    """
    group_name: str

    if "(TYP)" in line:
        group_name = "TYP"
    else:
        if "(API)" in line:
            group_name = "API"
        else:
            if "(SAD)" in line:
                group_name = "SAD"
            else:
                group_name = ""

    return group_name


def parse_baseline_file(baseline_path: Path) -> List[BaselineEntry]:
    """
    Parse the PGLIB baseline markdown and extract the AC objective/time rows.

    :param baseline_path: Path to ``BASELINE.md``.
    :return: Parsed baseline entries in file order.
    """
    entries: List[BaselineEntry] = list()
    active_group_name: str = ""

    with baseline_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line: str = raw_line.strip()

            if line.startswith("## "):
                parsed_group_name: str = parse_baseline_group_name(line)
                if parsed_group_name != "":
                    active_group_name = parsed_group_name
                else:
                    pass
            else:
                if line.startswith("| pglib_opf_case"):
                    cells: List[str] = split_markdown_row(line)
                    entry: BaselineEntry = BaselineEntry(
                        group_name=active_group_name,
                        case_name=cells[0],
                        nodes=int(cells[1]),
                        edges=int(cells[2]),
                        ac_objective=parse_baseline_float(cells[4]),
                        ac_time_seconds=parse_baseline_time(cells[8]),
                    )
                    entries.append(entry)
                else:
                    pass

    return entries


def build_baseline_lookup(entries: List[BaselineEntry]) -> dict[str, BaselineEntry]:
    """
    Build a lookup by case stem for quick baseline comparison.

    :param entries: Parsed baseline entries.
    :return: Lookup keyed by PGLIB case stem.
    """
    lookup: dict[str, BaselineEntry] = dict()

    for entry in entries:
        lookup[entry.case_name] = entry

    return lookup


def collect_case_files(benchmark_root: Path, matpower_folder: Path) -> List[Path]:
    """
    Collect all benchmark case files that should be run by VeraGrid.

    :param benchmark_root: Root directory of the PGLIB OPF benchmark archive.
    :param matpower_folder: Relative folder under ``benchmark_root`` that contains the case files.
    :return: Sorted list of ``.matpower`` case files.
    """
    case_files: List[Path] = list()
    case_root: Path = benchmark_root / matpower_folder

    # Use "." for the top-level base set, which must not recurse into ``api`` or ``sad``.
    if matpower_folder == Path("."):
        for case_path in sorted(case_root.glob("*.matpower")):
            case_files.append(case_path)
    else:
        # For any explicit subfolder, recurse under that folder so custom benchmark folders work too.
        for case_path in sorted(case_root.rglob("*.matpower")):
            case_files.append(case_path)

    return case_files


def detect_case_group(case_path: Path, pglib_root: Path) -> str:
    """
    Detect the benchmark group from the case file location.

    :param case_path: Full path to one benchmark file.
    :param pglib_root: Root directory of the PGLIB OPF benchmark archive.
    :return: ``TYP``, ``API``, ``SAD`` or ``""`` when the file is outside the supported groups.
    """
    group_name: str

    if case_path.parent == pglib_root:
        group_name = "TYP"
    else:
        if case_path.parent.name == "api":
            group_name = "API"
        else:
            if case_path.parent.name == "sad":
                group_name = "SAD"
            else:
                group_name = ""

    return group_name


def compute_total_ac_objective(results: NonlinearOPFResults,
                               sbase: float,
                               active_generator_mask: np.ndarray,
                               cost_0: np.ndarray,
                               cost_1: np.ndarray,
                               cost_2: np.ndarray) -> float:
    """
    Compute the total AC generator objective in the same units used by the ACOPF formulation.

    :param results: VeraGrid nonlinear ACOPF results.
    :param sbase: System power base in MVA.
    :param active_generator_mask: Active-state mask from the compiled numerical circuit.
    :param cost_0: Constant generator cost coefficients.
    :param cost_1: Linear generator cost coefficients.
    :param cost_2: Quadratic generator cost coefficients.
    :return: Total active-power generation cost.
    """
    total_cost: float = 0.0

    # The solver works on the compiled numerical circuit, so the benchmark
    # objective should be rebuilt only from the compiled numerical quantities
    # that match the OPF solve.
    #
    # The solver stores ``Pg`` in per-unit on ``sbase``, while the
    # economic coefficients are defined on MW. Rebuild the benchmark objective
    # from the solved dispatch in MW so the CSV uses the same units as the
    # internal ACOPF objective and as the PGLIB baseline tables.
    for index in range(len(results.Pg)):
        if bool(active_generator_mask[index]):
            pg_mw: float = float(results.Pg[index]) * float(sbase)
            total_cost += float(cost_0[index]) + float(cost_1[index]) * pg_mw + float(cost_2[index]) * (pg_mw * pg_mw)
        else:
            pass

    return total_cost


def compute_objective_gap_percent(veragrid_ac_objective: float, baseline_ac_objective: float) -> float:
    """
    Compute the relative gap between VeraGrid and the PGLIB AC baseline objective.

    :param veragrid_ac_objective: VeraGrid AC objective value.
    :param baseline_ac_objective: PGLIB baseline AC objective value.
    :return: Relative gap in percent.
    """
    gap_percent: float

    if math.isfinite(baseline_ac_objective) and baseline_ac_objective != 0.0:
        gap_percent = 100.0 * (veragrid_ac_objective - baseline_ac_objective) / baseline_ac_objective
    else:
        gap_percent = math.nan

    return gap_percent


def build_opf_options_with_pf_init(grid: MultiCircuit,
                                   ips_tolerance: float,
                                   ips_iterations: int,
                                   verbose: int) -> Tuple[OptimalPowerFlowOptions, bool, bool]:
    """
    Build ACOPF options and, when possible, seed them with a converged power-flow point.

    :param grid: Loaded benchmark grid.
    :param ips_tolerance: IPS convergence tolerance.
    :param ips_iterations: Maximum IPS iterations.
    :param verbose: Solver verbosity level.
    :return: ``(opf_options, pf_init_used, pf_converged)``.
    """
    # First solve a plain PF because ACOPF is substantially more stable when it starts from a
    # physically consistent voltage profile instead of the flat or parser-provided default point.
    pf_options: PowerFlowOptions = PowerFlowOptions(control_q=False)
    pf_driver: PowerFlowDriver = PowerFlowDriver(grid=grid, options=pf_options)
    pf_driver.run()

    opf_options: OptimalPowerFlowOptions = OptimalPowerFlowOptions(
        ips_method=SolverType.NR,
        ips_tolerance=ips_tolerance,
        ips_iterations=ips_iterations,
        acopf_mode=AcOpfMode.ACOPFstd,
        verbose=verbose,
    )

    pf_init_used: bool = False
    pf_converged: bool = False

    # Match MATPOWER's large-case behavior more closely: when PF fails, do not feed the
    # failed iterate into ACOPF as the primal seed. MIPS falls back to its own interior
    # initialization in that situation, which is materially more robust on cases such as
    # ``pglib_opf_case10480_goc``.
    if pf_driver.results is not None and bool(pf_driver.results.converged):
        opf_options.ips_init_with_pf = True
        opf_options.acopf_v0 = pf_driver.results.voltage
        opf_options.acopf_S0 = pf_driver.results.Sbus
        opf_options.acopf_pf_converged = bool(pf_driver.results.converged)
        pf_init_used = True
        pf_converged = bool(pf_driver.results.converged)
    else:
        opf_options.ips_init_with_pf = False
        opf_options.acopf_v0 = pf_driver.results.voltage if pf_driver.results is not None else None
        opf_options.acopf_S0 = pf_driver.results.Sbus if pf_driver.results is not None else None
        opf_options.acopf_pf_converged = False
        pf_init_used = False
        pf_converged = bool(pf_driver.results.converged) if pf_driver.results is not None else False

    return opf_options, pf_init_used, pf_converged


def remap_original_bus_indices(n_bus: int, original_bus_idx: IntVec) -> Tuple[IntVec, IntVec]:
    """
    Build island/original bus-index maps for one benchmark island.

    :param n_bus: Number of buses in the original compiled circuit.
    :param original_bus_idx: Original bus indices referenced by the island.
    :return: ``(original_indices, island_indices)``.
    """
    original_idx: IntVec = np.arange(n_bus, dtype=int)
    mapping: dict[int, int] = dict()
    island_indices: List[int] = list()
    original_indices: List[int] = list()

    for index, original in enumerate(original_idx):
        mapping[int(original)] = index

    for array_index, original in enumerate(original_bus_idx):
        mapped_index: int | None = mapping.get(int(original), None)
        if mapped_index is not None:
            island_indices.append(mapped_index)
            original_indices.append(array_index)
        else:
            pass

    return np.array(original_indices, dtype=int), np.array(island_indices, dtype=int)


def run_nonlinear_opf_with_pf_seed_and_default_multiplier_init(
        grid: MultiCircuit,
        opf_options: OptimalPowerFlowOptions) -> NonlinearOPFResults:
    """
    Run benchmark ACOPF using the PF state for ``x0`` while skipping the PF-specific multiplier bootstrap.

    :param grid: Benchmark grid.
    :param opf_options: Configured ACOPF options carrying the PF state seed.
    :return: Nonlinear ACOPF results.
    """
    logger: Logger = Logger()
    nc = compile_numerical_circuit_at(circuit=grid, t_idx=None, logger=logger)
    Sbus_pf = opf_options.acopf_S0 if opf_options.acopf_S0 is not None else nc.bus_data.installed_power
    voltage_pf = opf_options.acopf_v0 if opf_options.acopf_v0 is not None else nc.bus_data.Vbus
    islands = nc.split_into_islands(ignore_single_node_islands=True, consider_hvdc_as_island_links=True)

    results: NonlinearOPFResults = NonlinearOPFResults()
    results.initialize(nbus=nc.nbus,
                       nbr=nc.nbr,
                       nsh=nc.nshunt,
                       ng=nc.ngen,
                       nil=len(nc.passive_branch_data.get_monitor_enabled_indices()),
                       nhvdc=nc.nhvdc,
                       ncap=0,
                       nvsc=nc.vsc_data.nelm)

    for island_index, island in enumerate(islands):
        problem: NonLinearOptimalPfProblem = NonLinearOptimalPfProblem(
            nc=island,
            options=opf_options,
            pf_init=True,
            Sbus_pf=Sbus_pf[island.bus_data.original_idx],
            voltage_pf=voltage_pf[island.bus_data.original_idx],
            optimize_nodal_capacity=False,
            nodal_capacity_sign=1.0,
            capacity_nodes_idx=None,
            logger=logger,
        )

        xi: float = 0.995 if problem.nvsc else 0.99995
        # Mirror the main worker path so benchmark fallback runs follow the same
        # undamped IPS trajectory on hard large-scale ACOPF cases.
        use_step_control: bool = False
        ips_results = interior_point_solver(problem=problem,
                                            max_iter=opf_options.ips_iterations,
                                            tol=opf_options.ips_tolerance,
                                            pf_init=False,
                                            trust=opf_options.ips_trust_radius,
                                            verbose=opf_options.verbose,
                                            step_control=use_step_control,
                                            xi=xi)

        island_res: NonlinearOPFResults = problem.get_solution(ips_results=ips_results,
                                                               verbose=opf_options.verbose,
                                                               plot_error=False)

        results.merge(other=island_res,
                      bus_idx=island.bus_data.original_idx,
                      br_idx=island.passive_branch_data.original_idx,
                      il_idx=island.passive_branch_data.get_monitor_enabled_indices(),
                      gen_idx=island.generator_data.original_idx,
                      hvdc_idx=island.hvdc_data.original_idx,
                      ncap_idx=np.zeros(0, dtype=int),
                      contshunt_idx=np.where(island.shunt_data.control_mode_int == ShuntControlMode.Continuous.idx())[0],
                      acopf_mode=opf_options.acopf_mode,
                      vsc_idx=island.vsc_data.original_idx)

        if island_index > 0:
            results.error = max(results.error, island_res.error)
            results.iterations = max(results.iterations, island_res.iterations)
            results.converged = results.converged and island_res.converged
        else:
            results.error = island_res.error
            results.iterations = island_res.iterations
            results.converged = island_res.converged

    return results


def benchmark_case(case_path: Path,
                   pglib_root: Path,
                   baseline_lookup: dict[str, BaselineEntry],
                   ips_tolerance: float,
                   ips_iterations: int,
                   verbose: int) -> BenchmarkRow:
    """
    Run VeraGrid ACOPF on one benchmark case and compare it against the baseline row.

    :param case_path: Full path to the ``.matpower`` case file.
    :param pglib_root: Root directory of the PGLIB archive.
    :param baseline_lookup: Baseline lookup by case stem.
    :param ips_tolerance: IPS convergence tolerance.
    :param ips_iterations: Maximum IPS iterations.
    :param verbose: Solver verbosity level.
    :return: Filled benchmark row.
    """
    row: BenchmarkRow = BenchmarkRow()
    row.case_name = case_path.stem
    row.file_path = str(case_path)
    row.group_name = detect_case_group(case_path=case_path, pglib_root=pglib_root)

    # Copy the baseline metadata first so the row stays informative even if VeraGrid later fails.
    baseline_entry: BaselineEntry | None = baseline_lookup.get(row.case_name, None)
    if baseline_entry is not None:
        row.baseline_ac_objective = baseline_entry.ac_objective
        row.baseline_ac_time_seconds = baseline_entry.ac_time_seconds
        row.nodes = baseline_entry.nodes
        row.edges = baseline_entry.edges
    else:
        pass

    start_time: float = timeit.default_timer()

    # Unsupported directories are not a hard error for the batch runner. Mark the row explicitly
    # and leave the rest of the run intact so one bad path does not destroy the whole benchmark.
    if row.group_name == "":
        row.status = "skipped:unknown_group"
    else:
        file_open_driver: FileOpen = FileOpen(file_name=str(case_path))
        try:
            # Load the Matpower case and refresh the topology counts from the parsed network so the
            # CSV reflects what VeraGrid actually solved, not only what the markdown baseline says.
            grid: MultiCircuit = file_open_driver.open()
            row.nodes = grid.get_bus_number()
            row.edges = grid.get_branch_number(add_vsc=False, add_hvdc=False, add_switch=True)

            opf_options, pf_init_used, pf_converged = build_opf_options_with_pf_init(
                grid=grid,
                ips_tolerance=ips_tolerance,
                ips_iterations=ips_iterations,
                verbose=verbose,
            )
            row.pf_init_used = pf_init_used

            # Run ACOPF through the same worker path used elsewhere so benchmark
            # results stay aligned with the current IPS initialization logic.
            results = run_nonlinear_opf(grid=grid, opf_options=opf_options)

            objective_nc = compile_numerical_circuit_at(circuit=grid, t_idx=None, logger=Logger())
            row.veragrid_ac_objective = compute_total_ac_objective(
                results=results,
                sbase=float(objective_nc.Sbase),
                active_generator_mask=objective_nc.generator_data.active.astype(bool),
                cost_0=objective_nc.generator_data.cost_0,
                cost_1=objective_nc.generator_data.cost_1,
                cost_2=objective_nc.generator_data.cost_2,
            )
            row.objective_gap_percent = compute_objective_gap_percent(
                veragrid_ac_objective=row.veragrid_ac_objective,
                baseline_ac_objective=row.baseline_ac_objective,
            )
            row.iterations = results.iterations
            row.converged = results.converged
            row.solver_error = results.error

            if results.converged:
                row.status = "ok"
            else:
                row.status = "not_converged"
        except (RuntimeError, ValueError, TypeError, ArithmeticError, OSError) as exc:
            row.status = f"failed:{exc.__class__.__name__}"
        else:
            pass

    row.runtime_seconds = timeit.default_timer() - start_time
    return row


def write_csv_results(rows: List[BenchmarkRow], output_path: Path) -> None:
    """
    Write the benchmark comparison table to CSV.

    :param rows: Benchmark rows in output order.
    :param output_path: CSV file destination.
    """
    # The CSV is the durable artifact for later analysis, so every solved or failed row is written.
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "group",
            "case_name",
            "file_path",
            "nodes",
            "edges",
            "baseline_ac_objective",
            "baseline_ac_time_seconds",
            "veragrid_ac_objective",
            "objective_gap_percent",
            "runtime_seconds",
            "iterations",
            "converged",
            "pf_init_used",
            "solver_error",
            "status",
        ])

        for row in rows:
            writer.writerow([
                row.group_name,
                row.case_name,
                row.file_path,
                row.nodes,
                row.edges,
                row.baseline_ac_objective,
                row.baseline_ac_time_seconds,
                row.veragrid_ac_objective,
                row.objective_gap_percent,
                row.runtime_seconds,
                row.iterations,
                row.converged,
                row.pf_init_used,
                row.solver_error,
                row.status,
            ])


def print_summary(rows: List[BenchmarkRow]) -> None:
    """
    Print a compact benchmark summary for quick terminal inspection.

    :param rows: Benchmark rows in output order.
    """
    total_cases: int = len(rows)
    converged_cases: int = 0
    failed_cases: int = 0

    for row in rows:
        # The summary intentionally groups hard failures and non-convergence together because both
        # outcomes mean the benchmark row did not produce a valid ACOPF optimum for comparison.
        if row.status == "ok":
            converged_cases += 1
        else:
            failed_cases += 1

    print(f"Cases: {total_cases}")
    print(f"Converged: {converged_cases}")
    print(f"Failed or not converged: {failed_cases}")


def build_benchmark_config(matpower_folder: Path) -> BenchmarkConfig:
    """
    Build the explicit configuration used by this standalone benchmark script.

    :param matpower_folder: Relative folder under ``pglib-opf`` that contains the ``.matpower`` files.
    :return: Benchmark configuration.
    """
    script_dir: Path = Path(__file__).resolve().parent

    benchmark_root: Path = script_dir / "pglib-opf"
    baseline_path: Path = benchmark_root / "BASELINE.md"
    output_suffix: str = str(matpower_folder).replace("/", "_").replace("\\", "_").replace(".", "base")
    output_path: Path = script_dir / f"pglib_opf_veragrid_acopf_benchmark_{output_suffix}.csv"

    config: BenchmarkConfig = BenchmarkConfig(
        ips_tolerance=1e-6,
        ips_iterations=300,
        verbose=0,
        benchmark_root=benchmark_root,
        baseline_path=baseline_path,
        output_path=output_path,
    )
    return config


def main(matpower_folder: str = ".") -> None:
    """
    Execute the full PGLIB ACOPF benchmark run and write the CSV comparison table.

    :param matpower_folder: Relative folder under ``pglib-opf`` that contains the case files.
                            Use ``"."`` for base, ``"api"`` for API, or ``"sad"`` for SAD.
    :return: ``None``.
    """
    matpower_folder_path: Path = Path(matpower_folder)
    config: BenchmarkConfig = build_benchmark_config(matpower_folder=matpower_folder_path)
    benchmark_root: Path = config.benchmark_root
    baseline_path: Path = config.baseline_path
    output_path: Path = config.output_path.resolve()

    baseline_entries: List[BaselineEntry] = parse_baseline_file(baseline_path=baseline_path)
    baseline_lookup: dict[str, BaselineEntry] = build_baseline_lookup(entries=baseline_entries)
    case_files: List[Path] = collect_case_files(
        benchmark_root=benchmark_root,
        matpower_folder=matpower_folder_path,
    )
    benchmark_rows: List[BenchmarkRow] = list()

    # Print the selected relative folder so the run log states exactly which benchmark set was used.
    print(f"Matpower folder: {matpower_folder_path}")
    for case_path in case_files:
        row: BenchmarkRow = benchmark_case(
            case_path=case_path,
            pglib_root=benchmark_root,
            baseline_lookup=baseline_lookup,
            ips_tolerance=config.ips_tolerance,
            ips_iterations=config.ips_iterations,
            verbose=config.verbose,
        )
        benchmark_rows.append(row)
        print(
            f"{row.case_name}: status={row.status}, converged={row.converged}, "
            f"objective={row.veragrid_ac_objective}, gap_pct={row.objective_gap_percent}, "
            f"time={row.runtime_seconds:.3f}s"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv_results(rows=benchmark_rows, output_path=output_path)
    print_summary(rows=benchmark_rows)
    print(f"CSV written to {output_path}")
    return None


if __name__ == "__main__":
    main()
else:
    pass
