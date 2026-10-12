from __future__ import annotations

import multiprocessing
import queue
import shutil
import time
import traceback
from pathlib import Path
from typing import Any

from PySide6 import QtCore
from PySide6 import QtWidgets

from VeraGrid.Gui.Diagrams.SchematicWidget.Fluid.fluid_node_graphics import FluidNodeGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.Fluid.fluid_turbine_graphics import FluidTurbineGraphicItem
from VeraGrid.Gui.Diagrams.SchematicWidget.schematic_widget import SchematicWidget
from VeraGrid.Gui.Diagrams.graphics_manager import ALL_GRAPHICS
from VeraGrid.Gui.Main.VeraGridMain import VeraGridMainGUI
from VeraGrid.Gui.dialog_lifecycle import delete_dialog_safely
from VeraGrid.Session.file_handler import FileOpenThread
from VeraGrid.Session.file_handler import FileSaveThread
from VeraGrid.Session.session import GcThread
from VeraGridEngine.Compilers.circuit_to_data import compile_numerical_circuit_at
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Fluid.fluid_node import FluidNode
from VeraGridEngine.Devices.Fluid.fluid_turbine import FluidTurbine
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import EngineType, MIPFramework, MIPSolvers, SimulationTypes, SolverType
from tests.GUI.conftest import ModalDialogAutoCloser


TESTS_ROOT: Path = Path(__file__).resolve().parents[1]
HYDRO_GUI_FIXTURE: Path = TESTS_ROOT / "data" / "grids" / "cnd_enee_15_bus_hydro_b.veragrid"


def wait_for_file_open(gui: VeraGridMainGUI, app: QtWidgets.QApplication, timeout_s: float) -> None:
    """
    Process Qt events until the GUI file-open worker has finished.

    :param gui: Main GUI instance running the file-open worker.
    :param app: Shared Qt application.
    :param timeout_s: Maximum wait time in seconds.
    :return: None.
    """
    deadline_s: float = time.monotonic() + timeout_s
    open_finished: bool = False

    while time.monotonic() < deadline_s and not open_finished:
        app.processEvents()
        open_thread: FileOpenThread | None = gui.open_file_thread_object

        if open_thread is None:
            open_finished = True
        elif open_thread.isRunning():
            time.sleep(0.01)
        elif SimulationTypes.FileOpen in gui.stuff_running_now:
            time.sleep(0.01)
        else:
            open_thread.wait(5000)
            open_finished = True

    assert open_finished


def wait_for_file_save(gui: VeraGridMainGUI, app: QtWidgets.QApplication, timeout_s: float) -> None:
    """
    Process Qt events until the GUI file-save worker has finished.

    :param gui: Main GUI instance running the file-save worker.
    :param app: Shared Qt application.
    :param timeout_s: Maximum wait time in seconds.
    :return: None.
    """
    deadline_s: float = time.monotonic() + timeout_s
    save_finished: bool = False

    while time.monotonic() < deadline_s and not save_finished:
        app.processEvents()
        save_thread: FileSaveThread | None = gui.save_file_thread_object

        if save_thread is None:
            save_finished = True
        elif save_thread.isRunning():
            time.sleep(0.01)
        elif SimulationTypes.FileSave in gui.stuff_running_now:
            time.sleep(0.01)
        else:
            save_thread.wait(5000)
            save_finished = True

    assert save_finished


def wait_for_simulation(gui: VeraGridMainGUI,
                        app: QtWidgets.QApplication,
                        simulation_type: SimulationTypes,
                        timeout_s: float) -> None:
    """
    Process Qt events until one GUI simulation worker has finished.

    :param gui: Main GUI instance running the simulation worker.
    :param app: Shared Qt application.
    :param simulation_type: Simulation type to wait for.
    :param timeout_s: Maximum wait time in seconds.
    :return: None.
    """
    deadline_s: float = time.monotonic() + timeout_s
    simulation_finished: bool = False

    while time.monotonic() < deadline_s and not simulation_finished:
        app.processEvents()
        simulation_thread: GcThread | None = gui.session.threads.get(simulation_type, None)

        if simulation_thread is None:
            simulation_finished = True
        elif simulation_thread.isRunning():
            time.sleep(0.01)
        elif simulation_type in gui.stuff_running_now:
            time.sleep(0.01)
        else:
            simulation_thread.wait(5000)
            simulation_finished = True

    assert simulation_finished


def find_first_fluid_node_graphic(gui: VeraGridMainGUI) -> tuple[FluidNode, FluidNodeGraphicItem]:
    """
    Find the first fluid node and its schematic graphic from the launched GUI.

    :param gui: Loaded GUI instance.
    :return: Fluid node and matching graphic item.
    """
    diagram_widget: SchematicWidget | None = gui.get_selected_diagram_widget()
    assert isinstance(diagram_widget, SchematicWidget)

    selected_node: FluidNode | None = None
    node: FluidNode

    for node in gui.circuit.fluid_nodes:
        if selected_node is None:
            selected_node = node
        else:
            pass

    assert selected_node is not None

    graphic: ALL_GRAPHICS | None = diagram_widget.graphics_manager.query(elm=selected_node)
    assert isinstance(graphic, FluidNodeGraphicItem)

    return selected_node, graphic


def run_fluid_turbine_gui_flow(working_file_name: str, message_queue: Any) -> None:
    """
    Launch the GUI, load a hydro case, add a turbine, save, and run OPF.

    :param working_file_name: Writable grid file used by the GUI.
    :param message_queue: Parent-visible queue receiving failure details.
    :return: None.
    """
    app: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(list(("fluid-turbine-gui-regression",)))
    else:
        pass

    gui: VeraGridMainGUI = VeraGridMainGUI()
    gui.show()
    app.processEvents()
    modal_closer: ModalDialogAutoCloser = ModalDialogAutoCloser(app=app, protected_widget=gui, parent=gui)
    modal_closer.start()

    try:
        message_queue.put("opening file")
        gui.open_file_now(filenames=working_file_name)
        message_queue.put("waiting for file open")
        wait_for_file_open(gui=gui, app=app, timeout_s=60.0)
        message_queue.put("file opened")

        fluid_node, fluid_node_graphic = find_first_fluid_node_graphic(gui=gui)
        del fluid_node

        message_queue.put("adding turbine")
        turbine_graphic: FluidTurbineGraphicItem = fluid_node_graphic.add_turbine()
        assert isinstance(turbine_graphic, FluidTurbineGraphicItem)

        turbine: FluidTurbine = turbine_graphic.api_object
        turbine.max_flow_rate = 20.0
        turbine.efficiency = 10.0
        diagram_widget: SchematicWidget | None = gui.get_selected_diagram_widget()
        assert isinstance(diagram_widget, SchematicWidget)
        diagram_widget.set_editor_model(api_object=turbine)
        app.processEvents()

        message_queue.put("saving file")
        gui.save_file_now(filename=working_file_name)
        message_queue.put("waiting for file save")
        wait_for_file_save(gui=gui, app=app, timeout_s=60.0)
        message_queue.put("file saved")

        reopened_circuit: MultiCircuit = FileOpen(file_name=working_file_name).open()
        assert len(reopened_circuit.turbines) == len(gui.circuit.turbines)
        assert reopened_circuit.turbines[-1].max_flow_rate == 20.0
        assert reopened_circuit.turbines[-1].efficiency == 10.0

        message_queue.put("running OPF")
        # Exercise the native hydro formulation independently of saved GUI preferences.
        for combo, value in (
            (gui.ui.engineComboBox, EngineType.VeraGrid),
            (gui.ui.mip_framework_comboBox, MIPFramework.PuLP),
            (gui.ui.mip_solver_comboBox, MIPSolvers.HIGHS),
            (gui.ui.lpf_solver_comboBox, SolverType.LINEAR_OPF),
        ):
            index = combo.findData(value)
            assert index >= 0, f"Required OPF option unavailable: {value}"
            combo.setCurrentIndex(index)
        gui.ui.actionOPF.trigger()
        wait_for_simulation(gui=gui, app=app, simulation_type=SimulationTypes.OPF_run, timeout_s=180.0)
        message_queue.put("OPF finished")

        opf_driver: Any
        opf_results: Any
        opf_driver, opf_results = gui.session.optimal_power_flow
        assert opf_driver is not None
        opf_thread = gui.session.threads.get(SimulationTypes.OPF_run)
        assert opf_results is not None, (
            f"engine={opf_driver.engine}, solver={opf_driver.options.solver}, "
            f"worker_failed={opf_thread.has_failed() if opf_thread is not None else None}\n"
            f"{opf_thread.logger if opf_thread is not None else opf_driver.logger}"
        )
    except Exception:
        message_queue.put(traceback.format_exc())
        raise
    finally:
        modal_closer.stop()
        gui.hide()
        gui.stop_all_threads()
        delete_dialog_safely(dialog=gui)
        QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        app.processEvents()


def test_gui_added_turbine_with_high_efficiency_saves_and_runs_opf(tmp_path: Path) -> None:
    """
    Check the GUI crash path for a turbine with ``max_flow_rate=20`` and ``efficiency=10``.

    :param tmp_path: Temporary output directory.
    :return: None.
    """
    working_file: Path = tmp_path / HYDRO_GUI_FIXTURE.name
    shutil.copyfile(src=HYDRO_GUI_FIXTURE, dst=working_file)

    process_context: multiprocessing.context.BaseContext = multiprocessing.get_context("spawn")
    message_queue: Any = process_context.Queue()
    process: multiprocessing.Process = process_context.Process(
        target=run_fluid_turbine_gui_flow,
        args=(str(working_file), message_queue),
    )

    process.start()
    process.join(300.0)

    message: str = ""
    try:
        while True:
            queued_message: Any = message_queue.get_nowait()
            if isinstance(queued_message, str):
                message = queued_message
            else:
                message = repr(queued_message)
    except queue.Empty:
        pass

    if process.is_alive():
        process.terminate()
        process.join(10.0)
        raise AssertionError(f"Fluid turbine GUI subprocess timed out: {message}")
    else:
        pass

    assert process.exitcode == 0, message


def test_compiler_skips_fluid_turbine_without_generator() -> None:
    """
    Check that an incomplete GUI-created turbine does not dereference a missing generator.

    :return: None.
    """
    grid: MultiCircuit = MultiCircuit()
    bus: Bus = Bus(name="Slack", is_slack=True)
    node: FluidNode = FluidNode(name="Reservoir")
    turbine: FluidTurbine = FluidTurbine(name="Incomplete turbine",
                                         plant=node,
                                         max_flow_rate=20.0,
                                         efficiency=10.0)
    logger: Logger = Logger()

    grid.add_bus(obj=bus)
    grid.add_fluid_node(obj=node)
    grid.add_fluid_turbine(node=node, api_obj=turbine)

    nc: NumericalCircuit = compile_numerical_circuit_at(circuit=grid, logger=logger)

    assert nc.nfluidturbine == 0
    assert nc.fluid_turbine_data.nelm == 0
    assert len(logger) > 0
