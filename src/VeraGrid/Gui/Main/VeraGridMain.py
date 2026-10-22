# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.  
# SPDX-License-Identifier: MPL-2.0

import os.path
import sys
import faulthandler
import traceback
from datetime import datetime
from pathlib import Path
from typing import TextIO, Any
from types import TracebackType

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from VeraGrid.Gui.Main.MainWindow import QApplication
from PySide6.QtCore import QDirIterator, QResource
from PySide6.QtSvg import QSvgRenderer
from VeraGrid.Gui.i18n import ApplicationTranslator, read_saved_language
from VeraGrid.Gui.update_gui_all import update_all_icons
from VeraGrid.Gui.Main.SubClasses.Scripting.scripting import ScriptingMain
from VeraGrid.Gui.messages import yes_no_question
import VeraGrid.ThirdParty.qdarktheme as qdarktheme
from VeraGrid.__version__ import __VeraGrid_VERSION__
from VeraGridEngine.IO.file_system import get_create_veragrid_folder
from VeraGridEngine.Utils.cache import clean_pycache_folders

__author__ = 'Santiago Peñate Vera'

"""
This class is the handler of the main gui of VeraGrid.
"""


def get_crash_log_path() -> str:
    """
    Return the persistent GUI crash log path.

    :return: Crash log path.
    """
    return os.path.join(get_create_veragrid_folder(), "veragrid_crash.log")


def get_qt_log_path() -> str:
    """
    Return the persistent Qt message log path.

    :return: Qt message log path.
    """
    return os.path.join(get_create_veragrid_folder(), "veragrid_qt.log")


def write_log_header(file_path: str, title: str) -> None:
    """
    Append one process-start header to a diagnostic log.

    :param file_path: Log file path.
    :param title: Header title.
    :return: None.
    """
    timestamp: str = datetime.now().isoformat(timespec="seconds")
    with open(file_path, "a", encoding="utf-8") as file_pointer:
        file_pointer.write(f"\n[{timestamp}] {title} VeraGrid {__VeraGrid_VERSION__}\n")


def qt_message_handler(mode: QtCore.QtMsgType,
                       context: QtCore.QMessageLogContext,
                       message: str) -> None:
    """
    Persist Qt warnings and fatal messages that desktop launchers hide.

    :param mode: Qt message severity.
    :param context: Qt message context.
    :param message: Message text.
    :return: None.
    """
    try:
        timestamp: str = datetime.now().isoformat(timespec="seconds")
        mode_name: str = mode.name
        source_file: str = context.file if context.file is not None else ""
        function_name: str = context.function if context.function is not None else ""
        line_number: int = context.line
        with open(get_qt_log_path(), "a", encoding="utf-8") as file_pointer:
            file_pointer.write(f"[{timestamp}] {mode_name} {source_file}:{line_number} {function_name}: {message}\n")
    except Exception:
        pass


def exception_hook(exception_type: type[BaseException],
                   exception_value: BaseException,
                   exception_traceback: TracebackType | None) -> None:
    """
    Persist uncaught Python exceptions before delegating to Python's default hook.

    :param exception_type: Exception class.
    :param exception_value: Exception instance.
    :param exception_traceback: Traceback object.
    :return: None.
    """
    try:
        with open(get_crash_log_path(), "a", encoding="utf-8") as file_pointer:
            timestamp: str = datetime.now().isoformat(timespec="seconds")
            file_pointer.write(f"[{timestamp}] Uncaught Python exception\n")
            traceback.print_exception(exception_type, exception_value, exception_traceback, file=file_pointer)
    except Exception:
        pass
    sys.__excepthook__(exception_type, exception_value, exception_traceback)


def write_runtime_state_log(window: "VeraGridMainGUI", title: str) -> None:
    """
    Persist the GUI worker/session state around risky lifecycle transitions.

    :param window: Main VeraGrid window.
    :param title: Log section title.
    :return: None.
    """
    try:
        timestamp: str = datetime.now().isoformat(timespec="seconds")
        with open(get_crash_log_path(), "a", encoding="utf-8") as file_pointer:
            file_pointer.write(f"[{timestamp}] {title}\n")
            file_pointer.write(f"stuff_running_now={list(window.stuff_running_now)}\n")
            file_pointer.write(f"session_drivers={list(window.session.drivers.keys())}\n")
            file_pointer.write(f"session_threads={list(window.session.threads.keys())}\n")

            threads: list[Any] = window.get_all_threads()
            thread_index: int
            thread: Any
            for thread_index, thread in enumerate(threads):
                if thread is None:
                    file_pointer.write(f"thread[{thread_index}]=None\n")
                else:
                    file_pointer.write(
                        f"thread[{thread_index}]={type(thread).__name__} running={thread.isRunning()}\n"
                    )
    except Exception:
        pass


########################################################################################################################
# Main Window
########################################################################################################################

class VeraGridMainGUI(ScriptingMain):
    """
    MainGUI
    """

    def __init__(self, translation_controller: ApplicationTranslator | None = None) -> None:
        """
        Main constructor
        """

        # create main window
        ScriptingMain.__init__(self, parent=None)
        if translation_controller is not None:
            self.set_translation_controller(translation_controller)
        else:
            pass
        self.setWindowTitle(self.tr("VeraGrid {version}").format(version=__VeraGrid_VERSION__))
        self.setAcceptDrops(True)

        self.ui.mainTabWidget.setCurrentIndex(0)
        self.ui.modelTabWidget.setCurrentIndex(0)
        self.ui.settingsTabWidget.setCurrentIndex(0)
        self.ui.resultsTabWidget.setCurrentIndex(0)

        ################################################################################################################
        # Set splitters
        ################################################################################################################

        # 1:4
        self.ui.dataStructuresSplitter.setStretchFactor(0, 3)
        self.ui.dataStructuresSplitter.setStretchFactor(1, 4)

        self.ui.simulationDataSplitter.setStretchFactor(1, 15)

        self.ui.results_splitter.setStretchFactor(0, 2)
        self.ui.results_splitter.setStretchFactor(1, 4)

        self.ui.diagram_selection_splitter.setStretchFactor(0, 10)
        self.ui.diagram_selection_splitter.setStretchFactor(1, 2)

        ################################################################################################################
        # Other actions
        ################################################################################################################

        self.ui.grid_colouring_frame.setVisible(True)

        self.ui.actionSync.setVisible(False)

        self.modify_ui_options_according_to_the_engine()

        # this is the contingency planner tab, invisible until done
        self.ui.modelTabWidget.setTabVisible(4, True)

        self.clear_results()

        self.load_all_config()

        self.add_complete_bus_branch_diagram()
        # self.add_map_diagram(ask=False)
        self.set_diagram_widget(self.diagram_widgets_list[0])
        self.update_available_results()

        self.ui.actionRun_Dynamic_RMS_Simulation.setVisible(True)
        self.ui.actionRun_Small_Signal_RMS_Simulation.setVisible(True)

        # global delete function
        self.ui.actionDelete_selected.triggered.connect(self.global_delete)
        self.ui.actionClear_cache.triggered.connect(self.clear_cache)

    def clear_cache(self) -> None:
        """
        Clear Python bytecode cache folders from the VeraGrid source packages.

        :return: None.
        """
        veragrid_root_path: Path = Path(__file__).resolve().parents[2]
        veragrid_engine_root_path: Path = veragrid_root_path.parent / "VeraGridEngine"

        # Remove only Python bytecode caches below the two source package roots.
        removed_count: int = clean_pycache_folders(veragrid_root_path)
        removed_count += clean_pycache_folders(veragrid_engine_root_path)

        self.show_info_toast(
            message=self.tr("Removed {count} __pycache__ folders").format(count=removed_count),
        )

    def refresh_runtime_translations(self) -> None:
        """
        Refresh runtime-owned main-window strings after a language change.

        :returns: None.
        """
        super().refresh_runtime_translations()
        self.setWindowTitle(self.tr("VeraGrid {version}").format(version=__VeraGrid_VERSION__))

    def global_delete(self):
        """
        Function to dispatch what to do when [supr] is pressed
        :return:
        """
        if self.ui.mainTabWidget.currentIndex() == 0:  # Model
            if self.ui.modelTabWidget.currentIndex() == 0:  # Diagrams
                self.delete_selected_diagram_widgets()

            elif self.ui.modelTabWidget.currentIndex() == 1:  # Database
                self.delete_selected_db_table_objects()

            else:
                self.show_warning_toast(self.tr("No effect, select diagrams or database"))
        else:
            self.show_warning_toast(self.tr("No effect, select diagrams or database"))

    def save_all_config(self) -> None:
        """
        Save all configuration files needed
        """
        try:
            self.save_gui_config()
        except OSError as error:
            print(f"Could not save GUI config: {error}")

        try:
            self.save_server_config()
        except OSError as error:
            print(f"Could not save server config: {error}")

        try:
            self.save_ai_config()
        except OSError as error:
            print(f"Could not save AI config: {error}")

    def load_all_config(self) -> None:
        """
        Load all configuration files needed
        """
        self.load_gui_config()
        self.load_server_config()
        self.load_ai_config()
        self.add_plugins()

        # apply the theme selected by the settings
        self.change_theme_mode()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """
        Close event
        :param event:
        :return:
        """
        write_runtime_state_log(window=self, title="Close requested")

        if self.circuit.get_bus_number() > 0:
            quit_msg = self.tr("Are you sure that you want to exit VeraGrid?")
            reply: bool = yes_no_question(text=quit_msg, title=self.tr("Close"), parent=self)

            if not reply:
                # save config regardless
                self.save_all_config()
                event.ignore()
                return

        # save config regardless
        self.save_all_config()
        ai_stopped: bool = self.shutdown_ai_dialogue_if_available()
        threads_stopped: bool = self.stop_all_threads()

        if not threads_stopped or not ai_stopped:
            event.ignore()
            self.show_warning_toast(
                self.tr("Some operations are still stopping. Try again after they finish.")
            )
            return

        self.window_manager.close_all()
        event.accept()



def create_linux_desktop_entry(app_name: str, qrc_icon_path: str):
    """
    Create a .desktop entry for a PySide app using a resource icon (":/path/to/icon.svg").

    Parameters
    ----------
    app_name : str
        Name of the application (also used for StartupWMClass).
    qrc_icon_path : str
        Path to the icon inside the .qrc (e.g. ':/icons/app_icon.svg')
    """
    if not sys.platform.startswith("linux"):
        # print("[INFO] Not running on Linux, skipping .desktop creation.")
        return None

    # Extract icon from Qt resource to a real file
    icon = QIcon(qrc_icon_path)
    if icon.isNull():
        print(f"[WARNING] Could not find icon in resource: {qrc_icon_path}")
        return None

    # Temporary export path (user local cache)
    cache_dir = os.path.expanduser(f"~/.cache/{app_name}")
    os.makedirs(cache_dir, exist_ok=True)
    icon_path = os.path.join(cache_dir, f"{app_name}.png")

    # Save first available icon size
    pixmap = icon.pixmap(256, 256)
    pixmap.save(icon_path, "PNG")

    # Create .desktop entry
    desktop_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(desktop_dir, exist_ok=True)
    desktop_file = os.path.join(desktop_dir, f"{app_name}.desktop")

    if not os.path.exists(desktop_file):
        exec_path = f"{sys.executable} {os.path.abspath(sys.argv[0])}"
        content = f"""[Desktop Entry]
Version={__VeraGrid_VERSION__}
Type=Application
Name={app_name}
Exec={exec_path}
Icon={icon_path}
Terminal=false
StartupWMClass={app_name}
Categories=Utility;
"""
        with open(desktop_file, "w") as f:
            f.write(content)
        os.chmod(desktop_file, 0o755)
        print(f"[OK] Created .desktop entry: {desktop_file}")
    else:
        pass
        # print(f"[INFO] .desktop entry already exists: {desktop_file}")

    return desktop_file


def check_all_svgs():
    """
    Iterate through all resources registered by icons_rc and check SVG validity.
    :returns: if any icon has errors
    """
    it = QDirIterator(":/Icons", QDirIterator.IteratorFlag.Subdirectories)
    bad_files = []

    while it.hasNext():
        path = it.next()
        if path.lower().endswith(".svg"):
            res = QResource(path)
            if not res.isValid():
                print(f"[MISSING] {path}")
                bad_files.append((path, "missing"))
                continue

            renderer = QSvgRenderer(path)
            if not renderer.isValid():
                print(f"[INVALID] {path}")
                bad_files.append((path, "invalid"))
            else:
                pass

    if len(bad_files) > 0:
        print("\nSVG compatibility summary:")
        for path, status in bad_files:
            print(f"  {status.upper():<8} {path}")

        update_all_icons()
    else:
        print("SVG compatibility summary: all ok")


def shutdown_main_window(window: "VeraGridMainGUI") -> None:
    """
    Stop owned GUI workers before Qt/Python starts destroying widgets.

    :param window: Main GUI window.
    :return: None.
    """
    window.shutdown_ai_dialogue_if_available()
    window.stop_all_threads()


def runVeraGrid() -> None:
    """
    Main function to run the GUI
    :return:
    """
    crash_log_path: str = get_crash_log_path()
    qt_log_path: str = get_qt_log_path()
    write_log_header(file_path=crash_log_path, title="Starting")
    write_log_header(file_path=qt_log_path, title="Starting")
    crash_log_file: TextIO = open(crash_log_path, "a", encoding="utf-8")
    faulthandler.enable(file=crash_log_file, all_threads=True)
    sys.excepthook = exception_hook
    QtCore.qInstallMessageHandler(qt_message_handler)

    # if hasattr(qdarktheme, 'enable_hi_dpi'):
    qdarktheme.enable_hi_dpi()

    app = QApplication(sys.argv)
    translation_controller = ApplicationTranslator(app)
    translation_controller.set_language(read_saved_language())

    # MacOS: display icons in menus
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

    icon_name = ':/Program icon/icons/VeraGrid_icon.png'
    icon = QtGui.QIcon(icon_name)

    # will check os internally
    create_linux_desktop_entry("veragrid", qrc_icon_path=icon_name)

    # macOS: Fix to show the icon on the task bar
    app.setWindowIcon(icon)

    window_ = VeraGridMainGUI(translation_controller=translation_controller)
    window_.setWindowIcon(icon)  # also apply directly
    app.aboutToQuit.connect(window_.shutdown_ai_dialogue_if_available)
    app.aboutToQuit.connect(window_.stop_all_threads)

    # process the argument if provided
    if len(sys.argv) > 1:
        f_name = sys.argv[1]
        if os.path.exists(f_name):
            window_.open_file_now(filenames=[f_name])

    # launch
    h_ = 780
    window_.resize(int(1.7 * h_), h_)  # almost the golden ratio :)
    window_.show()
    result: int = app.exec()
    shutdown_main_window(window=window_)
    sys.exit(result)


if __name__ == "__main__":
    runVeraGrid()
