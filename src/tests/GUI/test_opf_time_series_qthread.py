from __future__ import annotations

import multiprocessing
import os
import queue
import time
import traceback
from pathlib import Path
from typing import Any

import faulthandler
import numpy as np
from PySide6 import QtWidgets

from VeraGrid.Gui.Main.VeraGridMain import VeraGridMainGUI
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely
from VeraGrid.Session.file_handler import FileOpenThread
from VeraGrid.Session.session import GcThread
from VeraGrid.Session.session import SimulationSession
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.Simulations.OPF.opf_options import OptimalPowerFlowOptions
from VeraGridEngine.Simulations.OPF.opf_ts_driver import OptimalPowerFlowTimeSeriesDriver
from VeraGridEngine.enumerations import EngineType
from VeraGridEngine.enumerations import MIPSolvers
from VeraGridEngine.enumerations import MIPFramework, SolverType
from VeraGridEngine.enumerations import SimulationTypes
from tests.GUI.conftest import ModalDialogAutoCloser


TESTS_ROOT: Path = Path(__file__).resolve().parents[1]
HYDRO_TIME_SERIES_GRID: Path = TESTS_ROOT / "data" / "grids" / "hydro_grid2.gridcal"
NEW_ENGLAND_OPF_GRID: Path = TESTS_ROOT / "data" / "grids" / "New England_solar_case_OPF.gridcal"
IEEE39_HYDRO_GRID: Path = TESTS_ROOT / "data" / "grids" / "hydro_grid_IEEE39.gridcal"


def wait_for_session_driver(
        session: SimulationSession,
        app: QtWidgets.QApplication,
        simulation_type: SimulationTypes,
        timeout_s: float,
) -> GcThread:
    """
    Process Qt events until one session worker finishes.

    :param session: GUI-style simulation session.
    :param app: Qt application processing queued thread signals.
    :param simulation_type: Simulation type to wait for.
    :param timeout_s: Maximum wait time in seconds.
    :return: Finished worker thread.
    """
    deadline_s: float = time.monotonic() + timeout_s
    thread: GcThread | None = None

    while time.monotonic() < deadline_s:
        app.processEvents()
        thread = session.threads.get(simulation_type, None)

        if thread is None:
            time.sleep(0.01)
        elif thread.isRunning():
            time.sleep(0.01)
        else:
            thread.wait(5000)
            return thread

    raise AssertionError(f"{simulation_type.value} QThread did not finish within {timeout_s} s")


def wait_for_file_open(gui: VeraGridMainGUI, app: QtWidgets.QApplication, timeout_s: float) -> None:
    """
    Process Qt events until the GUI file-open worker has finished.

    :param gui: Main GUI instance running the file-open worker.
    :param app: Qt application processing queued thread signals.
    :param timeout_s: Maximum wait time in seconds.
    :return: None.
    """
    deadline_s: float = time.monotonic() + timeout_s

    while time.monotonic() < deadline_s:
        app.processEvents()
        open_thread: FileOpenThread | None = gui.open_file_thread_object

        if open_thread is None:
            if gui.circuit.has_time_series:
                return
            else:
                time.sleep(0.01)
        elif open_thread.isRunning():
            time.sleep(0.01)
        elif SimulationTypes.FileOpen in gui.stuff_running_now:
            time.sleep(0.01)
        else:
            open_thread.wait(5000)
            if gui.circuit.has_time_series:
                return
            else:
                time.sleep(0.01)

    raise AssertionError(f"GUI file open did not finish within {timeout_s} s")


def wait_for_gui_simulation(
        gui: VeraGridMainGUI,
        app: QtWidgets.QApplication,
        simulation_type: SimulationTypes,
        timeout_s: float,
) -> GcThread:
    """
    Process Qt events until one GUI simulation worker and post hook finish.

    :param gui: Main GUI instance running the simulation.
    :param app: Qt application processing queued thread signals.
    :param simulation_type: Simulation type to wait for.
    :param timeout_s: Maximum wait time in seconds.
    :return: Finished worker thread.
    """
    deadline_s: float = time.monotonic() + timeout_s
    thread: GcThread | None = None

    while time.monotonic() < deadline_s:
        app.processEvents()
        thread = gui.session.threads.get(simulation_type, None)

        if thread is None:
            time.sleep(0.01)
        elif thread.isRunning():
            time.sleep(0.01)
        elif simulation_type in gui.stuff_running_now:
            time.sleep(0.01)
        else:
            thread.wait(5000)
            app.processEvents()
            return thread

    raise AssertionError(f"{simulation_type.value} GUI simulation did not finish within {timeout_s} s")


def run_opf_time_series_qthread_flow(message_queue: Any) -> None:
    """
    Run OPF time series through the same QThread wrapper used by the GUI.

    :param message_queue: Parent-visible progress/failure queue.
    :return: None.
    """
    faulthandler.enable(all_threads=True)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(list(("opf-time-series-qthread-regression",)))
    else:
        pass

    session: SimulationSession = SimulationSession()

    try:
        message_queue.put("opening grid")
        grid = FileOpen(file_name=str(HYDRO_TIME_SERIES_GRID)).open()

        options = OptimalPowerFlowOptions(mip_solver=MIPSolvers.HIGHS)
        driver = OptimalPowerFlowTimeSeriesDriver(
            grid=grid,
            options=options,
            engine=EngineType.VeraGrid,
        )

        message_queue.put("starting qthread opf time series")
        session.run(driver=driver)

        thread: GcThread = wait_for_session_driver(
            session=session,
            app=app,
            simulation_type=SimulationTypes.OPFTimeSeries_run,
            timeout_s=180.0,
        )
        message_queue.put("qthread opf time series finished")

        assert not thread.has_failed(), thread.logger.to_df()
        stored_driver, stored_results = session.optimal_power_flow_ts
        assert stored_driver is driver
        assert stored_results is not None
        assert stored_results.converged.any()
        assert np.isfinite(stored_results.generator_power).all()
    except Exception:
        message_queue.put(traceback.format_exc())
        raise
    finally:
        for thread in list(session.threads.values()):
            if thread.isRunning():
                thread.cancel()
                thread.wait(10000)
            else:
                thread.wait(10000)
        app.processEvents()


def test_opf_time_series_runs_from_gui_qthread_without_crashing() -> None:
    """
    OPF time series must survive the GUI's QThread execution boundary.

    :return: None.
    """
    process_context: multiprocessing.context.BaseContext = multiprocessing.get_context("spawn")
    message_queue: Any = process_context.Queue()
    process: multiprocessing.Process = process_context.Process(
        target=run_opf_time_series_qthread_flow,
        args=(message_queue,),
    )

    process.start()
    process.join(240.0)

    message: str = ""
    try:
        while True:
            queued_message: object = message_queue.get_nowait()
            if isinstance(queued_message, str):
                message = queued_message
            else:
                message = repr(queued_message)
    except queue.Empty:
        pass

    if process.is_alive():
        process.terminate()
        process.join(10.0)
        raise AssertionError(f"OPF time-series QThread subprocess timed out: {message}")
    else:
        pass

    assert process.exitcode == 0, message


def set_combo_to_data(combo: QtWidgets.QComboBox, data: object) -> bool:
    """
    Select a combo-box entry by item data.

    :param combo: Combo box to modify.
    :param data: Item data to select.
    :return: True if the data was found.
    """
    for index in range(combo.count()):
        if combo.itemData(index) == data:
            combo.setCurrentIndex(index)
            return True
        else:
            pass

    return False


def run_opf_time_series_full_gui_flow(
        grid_file_name: str,
        run_count: int,
        forced_mip_solver_name: str | None,
        message_queue: Any,
) -> None:
    """
    Launch the main GUI, open a grid, and trigger OPF time series.

    :param message_queue: Parent-visible progress/failure queue.
    :return: None.
    """
    faulthandler.enable(all_threads=True)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(list(("opf-time-series-full-gui-regression",)))
    else:
        pass

    gui: VeraGridMainGUI = VeraGridMainGUI()
    gui.show()
    app.processEvents()
    modal_closer: ModalDialogAutoCloser = ModalDialogAutoCloser(app=app, protected_widget=gui, parent=gui)
    modal_closer.start()

    try:
        message_queue.put(f"opening grid in GUI: {Path(grid_file_name).name}")
        gui.open_file_now(filenames=grid_file_name)
        wait_for_file_open(gui=gui, app=app, timeout_s=60.0)
        message_queue.put("GUI grid opened")

        assert gui.circuit.has_time_series
        gui.ui.actionactivate_time_series.setChecked(True)
        # Keep engine/framework choices independent of persisted user preferences.
        # The dedicated CBC case still exercises CBC through the native formulation.
        for combo, value in (
            (gui.ui.engineComboBox, EngineType.VeraGrid),
            (gui.ui.mip_framework_comboBox, MIPFramework.PuLP),
            (gui.ui.lpf_solver_comboBox, SolverType.LINEAR_OPF),
        ):
            assert set_combo_to_data(combo=combo, data=value), f"Required OPF option unavailable: {value}"
        mip_solver = (MIPSolvers.argparse(forced_mip_solver_name)
                      if forced_mip_solver_name is not None else MIPSolvers.HIGHS)
        assert set_combo_to_data(combo=gui.ui.mip_solver_comboBox, data=mip_solver), (
            f"Required MIP solver unavailable: {mip_solver}"
        )
        message_queue.put(f"selected native PuLP MIP solver {mip_solver.value}")
        app.processEvents()

        for run_idx in range(run_count):
            message_queue.put(f"triggering GUI OPF time series run {run_idx + 1}")
            gui.ui.actionOPF_time_series.trigger()
            thread: GcThread = wait_for_gui_simulation(
                gui=gui,
                app=app,
                simulation_type=SimulationTypes.OPFTimeSeries_run,
                timeout_s=240.0,
            )
            message_queue.put(f"GUI OPF time series run {run_idx + 1} finished")

            assert not thread.has_failed(), thread.logger.to_df()
            opf_driver, opf_results = gui.session.optimal_power_flow_ts
            assert opf_driver is not None
            assert opf_results is not None
            if forced_mip_solver_name == MIPSolvers.CBC.value and not opf_results.converged.any():
                # A broken CBC installation must yield a diagnosed, non-converged
                # result rather than crash while extracting missing duals.
                assert any(
                    "Pulp: Error while" in entry.msg
                    or "Pulp: cannot execute" in entry.msg
                    or "no CBC executable is available" in entry.msg
                    for entry in opf_driver.logger.entries
                ), opf_driver.logger.to_df()
            else:
                assert opf_results.converged.any(), opf_driver.logger.to_df()
            assert np.isfinite(opf_results.generator_power).all()
    except Exception:
        message_queue.put(traceback.format_exc())
        raise
    finally:
        modal_closer.stop()
        gui.hide()
        gui.stop_all_threads()
        delete_dialog_safely(dialog=gui)
        app.processEvents()


def run_full_gui_subprocess(
        grid_file: Path,
        run_count: int = 1,
        timeout_s: float = 300.0,
        forced_mip_solver: MIPSolvers | None = None,
) -> None:
    """
    Run the full GUI OPF time-series flow in a crash-contained subprocess.

    :param grid_file: Grid to load in the GUI.
    :param timeout_s: Maximum child-process runtime.
    :return: None.
    """
    process_context: multiprocessing.context.BaseContext = multiprocessing.get_context("spawn")
    message_queue: Any = process_context.Queue()
    process: multiprocessing.Process = process_context.Process(
        target=run_opf_time_series_full_gui_flow,
        args=(
            str(grid_file),
            run_count,
            forced_mip_solver.value if forced_mip_solver is not None else None,
            message_queue,
        ),
    )

    process.start()
    process.join(timeout_s)

    message: str = ""
    try:
        while True:
            queued_message: object = message_queue.get_nowait()
            if isinstance(queued_message, str):
                message = queued_message
            else:
                message = repr(queued_message)
    except queue.Empty:
        pass

    if process.is_alive():
        process.terminate()
        process.join(10.0)
        raise AssertionError(f"OPF time-series GUI subprocess timed out: {message}")
    else:
        pass

    assert process.exitcode == 0, message


def test_opf_time_series_runs_from_full_gui_without_crashing() -> None:
    """
    OPF time series must survive the full GUI launch/action/post-processing path.

    :return: None.
    """
    run_full_gui_subprocess(grid_file=HYDRO_TIME_SERIES_GRID)


def test_opf_time_series_full_gui_new_england_case_without_crashing() -> None:
    """
    Exercise the GUI OPF time-series path on a larger 24-step OPF fixture.

    :return: None.
    """
    run_full_gui_subprocess(grid_file=NEW_ENGLAND_OPF_GRID)


def test_opf_time_series_full_gui_ieee39_hydro_case_without_crashing() -> None:
    """
    Exercise the GUI OPF time-series path on the IEEE39 hydro fixture.

    :return: None.
    """
    run_full_gui_subprocess(grid_file=IEEE39_HYDRO_GRID)


def test_opf_time_series_full_gui_repeated_runs_without_crashing() -> None:
    """
    Re-running OPF time series in one GUI window must not crash native solver teardown/reuse.

    :return: None.
    """
    run_full_gui_subprocess(grid_file=HYDRO_TIME_SERIES_GRID, run_count=2)


def test_opf_time_series_full_gui_cbc_selection_without_crashing() -> None:
    """
    A persisted CBC selection must not crash the GUI OPF time-series launch path.

    :return: None.
    """
    run_full_gui_subprocess(grid_file=HYDRO_TIME_SERIES_GRID, forced_mip_solver=MIPSolvers.CBC)
