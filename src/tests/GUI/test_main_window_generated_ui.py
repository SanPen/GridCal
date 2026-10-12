from typing import Tuple

from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.Main.MainWindow import Ui_mainWindow


def get_splitter_section_hint(splitter: QtWidgets.QSplitter, section_index: int) -> int:
    """
    Return the current size hint for one splitter section.

    :param splitter: Splitter to inspect.
    :param section_index: Section index inside the splitter.
    :returns: Preferred section size along the splitter orientation.
    """
    section_widget: QtWidgets.QWidget | None = splitter.widget(section_index)

    if section_widget is None:
        return 0
    else:
        section_widget.updateGeometry()

        if splitter.orientation() == QtCore.Qt.Orientation.Horizontal:
            return max(section_widget.minimumSizeHint().width(), section_widget.minimumWidth())
        else:
            return max(section_widget.minimumSizeHint().height(), section_widget.minimumHeight())


def refresh_translated_splitter_layouts(root_widget: QtWidgets.QWidget) -> None:
    """
    Refresh splitter sections after a language change.

    When translated labels become wider, Qt retranslates the text but can keep
    old splitter allocations until another layout pass happens. This helper
    nudges every splitter to re-evaluate its section sizes against the updated
    widget hints.

    :param root_widget: Top-level widget owning the splitters.
    :returns: None.
    """
    splitter: QtWidgets.QSplitter

    for splitter in root_widget.findChildren(QtWidgets.QSplitter):
        current_sizes: list[int] = splitter.sizes()
        desired_sizes: list[int] = list(current_sizes)
        section_index: int

        if len(current_sizes) == 0:
            pass
        else:
            for section_index in range(splitter.count()):
                section_hint: int = get_splitter_section_hint(splitter=splitter, section_index=section_index)

                if desired_sizes[section_index] < section_hint:
                    desired_sizes[section_index] = section_hint
                else:
                    pass

            splitter.setSizes(desired_sizes)


def build_main_window() -> Tuple[QtWidgets.QMainWindow, Ui_mainWindow]:
    """
    Build the generated main-window UI on a plain Qt main window.

    :return: Main window and configured generated UI object.
    """
    window: QtWidgets.QMainWindow = QtWidgets.QMainWindow()
    ui: Ui_mainWindow = Ui_mainWindow()
    ui.setupUi(window)
    return window, ui


def test_generated_main_window_builds_core_tab_widgets(qt_app: object) -> None:
    """
    Check that generated MainWindow UI exposes the tab widgets used by VeraGridMainGUI.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    window: QtWidgets.QMainWindow
    ui: Ui_mainWindow
    window, ui = build_main_window()

    assert ui.mainTabWidget.count() > 0
    assert ui.modelTabWidget.count() > 0
    assert ui.settingsTabWidget.count() > 0
    assert ui.resultsTabWidget.count() > 0
    assert ui.mainTabWidget.currentIndex() >= 0
    assert ui.modelTabWidget.currentIndex() >= 0

    window.close()
    window.deleteLater()


def test_generated_main_window_exposes_splitters_used_by_main_gui(qt_app: object) -> None:
    """
    Check that generated MainWindow UI exposes the splitters configured by VeraGridMainGUI.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    window: QtWidgets.QMainWindow
    ui: Ui_mainWindow
    window, ui = build_main_window()

    assert ui.dataStructuresSplitter.count() >= 2
    assert ui.simulationDataSplitter.count() >= 2
    assert ui.results_splitter.count() >= 2
    assert ui.diagram_selection_splitter.count() >= 2

    window.close()
    window.deleteLater()


def test_generated_main_window_exposes_main_actions(qt_app: object) -> None:
    """
    Check that generated MainWindow UI exposes actions connected by Main subclasses.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    window: QtWidgets.QMainWindow
    ui: Ui_mainWindow
    window, ui = build_main_window()

    assert ui.actionPower_flow.text() != ""
    assert ui.actionPower_flow_3ph.text() != ""
    assert ui.actionLinearAnalysis.text() != ""
    assert ui.actionRun_Dynamic_RMS_Simulation.text() != ""
    assert ui.actionRun_Dynamic_EMT_Simulation.text() != ""
    assert ui.actionRun_Small_Signal_RMS_Simulation.text() != ""
    assert ui.actionRun_Small_Signal_EMT_Simulation.text() != ""
    assert ui.actionDelete_selected.text() != ""
    assert ui.actionSync.text() != ""

    window.close()
    window.deleteLater()


def test_refresh_translated_splitter_layouts_respects_updated_widget_hints(qt_app: object) -> None:
    """
    Check that the splitter refresh helper keeps sections large enough for updated hints.

    :param qt_app: Shared Qt application fixture.
    :return: Nothing.
    """
    del qt_app

    window: QtWidgets.QWidget = QtWidgets.QWidget()
    layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(window)
    splitter: QtWidgets.QSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
    left_label: QtWidgets.QLabel = QtWidgets.QLabel("Short")
    right_label: QtWidgets.QLabel = QtWidgets.QLabel("Right")
    sizes: list[int]

    splitter.addWidget(left_label)
    splitter.addWidget(right_label)
    layout.addWidget(splitter)
    window.resize(400, 100)
    window.show()
    QtWidgets.QApplication.processEvents()

    left_label.setMinimumWidth(220)
    refresh_translated_splitter_layouts(window)
    QtWidgets.QApplication.processEvents()
    sizes = splitter.sizes()

    assert sizes[0] >= 220

    window.close()
    window.deleteLater()


