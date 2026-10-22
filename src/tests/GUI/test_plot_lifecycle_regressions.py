"""Regression coverage for plot ownership, input validation and painter cleanup."""

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path
from types import TracebackType

import numpy as np
import pandas as pd
import pytest
import shiboken6
from PySide6 import QtCore, QtGui, QtWidgets

from VeraGrid.Gui.FileDialogues.ProfilesInput.profile_dialogue import ProfileInputGUI
from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue
from VeraGrid.Gui.PlotDialogue.plot_export import save_chart_image
from VeraGrid.Gui.PlotDialogue.qt_chart_widget import GraphsWidget, prepare_chart_points
from VeraGrid.Gui.gui_functions import LookupMatrixEditorDialog, SequenceEditorDialog
from VeraGrid.Gui.rms_plot_variables_dialog import RmsPlotDialog
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.enumerations import DeviceType, WaveformSequenceType
from tests.GUI.test_dialog_smoke import FakeRmsResults


class PlotEditorKind(Enum):
    """Editors retaining one externally closable plot."""

    SEQUENCE = auto()
    LOOKUP = auto()
    RMS = auto()


@pytest.mark.parametrize('kind', tuple(PlotEditorKind))
def test_editors_can_update_and_reopen_a_manually_closed_plot(
        qt_app: QtWidgets.QApplication, kind: PlotEditorKind) -> None:
    """Keep editor updates and cleanup safe after Qt deletes a plot window.

    :param qt_app: Shared Qt application.
    :param kind: Editor whose cached reference is exercised.
    :return: None.
    """
    editor: SequenceEditorDialog | LookupMatrixEditorDialog | RmsPlotDialog
    if kind == PlotEditorKind.SEQUENCE:
        editor = SequenceEditorDialog(None, WaveformSequenceType)
        editor.set_points([(0.0, 1.0), (1.0, 2.0)])
        editor.show_plot()
    elif kind == PlotEditorKind.LOOKUP:
        editor = LookupMatrixEditorDialog()
        editor.show_plot()
    else:
        results: FakeRmsResults = FakeRmsResults(Generator(name='Generator'), Var(name='speed', uid=1))
        editor = RmsPlotDialog(results)
        editor.selected_vars.append(1)
        editor.show_external_plot()
    original: PlotDialogue = editor._plot_dialogue
    original.close()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    assert not shiboken6.isValid(original)
    if isinstance(editor, SequenceEditorDialog):
        editor.update_plot()
        editor.show_plot()
    elif isinstance(editor, LookupMatrixEditorDialog):
        editor._update_plot()
        editor.show_plot()
    else:
        editor.plot_selected()
        editor.show_external_plot()
    assert editor._plot_dialogue is not original
    assert shiboken6.isValid(editor._plot_dialogue)
    editor.close_plot_dialogue()
    assert editor._plot_dialogue is None
    editor.close()


@pytest.mark.parametrize('invalid', (np.array(1.0), np.ones((3, 1)), np.ones((3, 1, 1))))
def test_invalid_buffer_dimensions_preserve_current_chart(
        qt_app: QtWidgets.QApplication, invalid: np.ndarray) -> None:
    """Reject malformed coordinates and values in each public plotting path.

    :param qt_app: Shared Qt application.
    :param invalid: Scalar or multidimensional buffer that cannot describe a curve.
    :return: None.
    """
    chart: GraphsWidget = GraphsWidget()
    coordinates: np.ndarray = np.arange(3.0)
    assert chart.set_line_series(coordinates, ['Original'], [coordinates])
    assert prepare_chart_points(coordinates, invalid) is None
    assert prepare_chart_points(invalid, coordinates) is None
    assert not chart.set_line_series(coordinates, ['Bad'], [invalid])
    assert not chart.set_line_series(invalid, ['Bad'], [coordinates])
    assert not chart.set_scatter_series(coordinates, ['Bad'], [invalid])
    assert not chart.set_scatter_series(invalid, ['Bad'], [coordinates])
    assert not chart.set_cumulative_area_series(coordinates, ['Bad'], [invalid])
    assert not chart.set_cumulative_area_series(invalid, ['Bad'], [coordinates])
    assert not chart.set_polar_series(['Bad'], [coordinates], [invalid])
    assert not chart.set_polar_series(['Bad'], [invalid], [coordinates])
    assert not chart.set_histogram(invalid, 3)
    assert not chart.replace_xy_series_data([(coordinates, invalid, None)])
    chart.add_line_series('Bad', coordinates, invalid)
    chart.add_scatter_series('Bad', coordinates, invalid)
    chart.add_horizontal_bar_series(['A', 'B', 'C'], invalid, '#008800', '#880000')
    assert chart.get_series_count() == 1
    assert chart.get_series_name(0) == 'Original'
    np.testing.assert_array_equal(chart._series[0].get_y_data(), coordinates)
    chart.dispose()
    chart.deleteLater()


def test_xy_picker_survives_parent_deletion(qt_app: QtWidgets.QApplication) -> None:
    """Return safely when a queued deletion destroys a modal picker's parent.

    :param qt_app: Shared Qt application.
    :return: None.
    """
    plot: PlotDialogue = PlotDialogue()
    plot.set_line_series(np.arange(3.0), ['A', 'B'], [np.arange(3.0), np.arange(3.0)])
    QtCore.QTimer.singleShot(0, plot, plot.deleteLater)
    plot._create_xy_plot()
    assert not shiboken6.isValid(plot)


def test_profile_input_releases_failed_plot_attempts(qt_app: QtWidgets.QApplication) -> None:
    """Release hidden partial windows after caught coordinate conversion errors.

    :param qt_app: Shared Qt application.
    :return: None.
    """
    device: Generator = Generator(name='Generator')
    dialog: ProfileInputGUI = ProfileInputGUI(None, MultiCircuit(), DeviceType.GeneratorDevice, [device], 'P')
    dialog.original_data_frame = pd.DataFrame({'P': [1.0, 2.0]}, index=['bad date', 'another bad date'])
    model: QtGui.QStandardItemModel = QtGui.QStandardItemModel(dialog)
    model.appendRow(QtGui.QStandardItem('P'))
    dialog.ui.sources_list.setModel(model)
    dialog.ui.sources_list.setCurrentIndex(model.index(0, 0))
    dialog.plot_selected()
    dialog.plot_selected()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    assert dialog._open_plot_dialogs == list()
    assert dialog.findChildren(PlotDialogue) == list()
    dialog.close()


@pytest.mark.parametrize('toolbar', (True, False))
def test_old_save_picker_cannot_clear_its_replacement(
        qt_app: QtWidgets.QApplication, toolbar: bool) -> None:
    """Retain a new picker when Qt destroys its deferred-deletion predecessor.

    :param qt_app: Shared Qt application.
    :param toolbar: Exercise the plot toolbar or chart context-menu picker.
    :return: None.
    """
    plot: PlotDialogue = PlotDialogue()
    if toolbar:
        plot.save_image()
        old: QtWidgets.QFileDialog = plot._active_save_dialog
        old.reject()
        plot.save_image()
        new: QtWidgets.QFileDialog = plot._active_save_dialog
    else:
        plot.chart._save_image_from_context_menu()
        old = plot.chart._active_save_dialog
        old.reject()
        plot.chart._save_image_from_context_menu()
        new = plot.chart._active_save_dialog
    assert new is not old
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    assert shiboken6.isValid(new)
    assert (plot._active_save_dialog if toolbar else plot.chart._active_save_dialog) is new
    new.reject()
    assert (plot._active_save_dialog if toolbar else plot.chart._active_save_dialog) is None
    plot.reject()


def test_painter_state_is_restored_when_drawing_fails(qt_app: QtWidgets.QApplication) -> None:
    """Restore the caller's transform across nested chart clipping scopes.

    :param qt_app: Shared Qt application.
    :return: None.
    """
    chart: GraphsWidget = GraphsWidget()
    chart.resize(600, 400)
    coordinates: np.ndarray = np.arange(3.0)
    assert chart.set_line_series(coordinates, ['A'], [coordinates])
    # Inject invalid internal data to exercise cleanup even if a renderer unexpectedly fails.
    chart._series[0].replace_data(coordinates, np.ones((3, 1)), QtGui.QColor('#008800'))
    image: QtGui.QImage = QtGui.QImage(600, 400, QtGui.QImage.Format.Format_ARGB32)
    painter: QtGui.QPainter = QtGui.QPainter(image)
    try:
        try:
            chart.paint_to_painter(painter)
        except TypeError as error:
            assert '0-dimensional' in str(error)
        else:
            pytest.fail('Drawing failure did not propagate')
        assert painter.isActive()
        assert painter.transform().isIdentity()
        assert not painter.hasClipping()
    finally:
        painter.end()
        chart.dispose()
        chart.deleteLater()


@pytest.mark.parametrize('suffix', ('.png', '.svg'))
def test_export_ends_painter_when_drawing_fails(
        qt_app: QtWidgets.QApplication, tmp_path: Path, suffix: str) -> None:
    """End image and SVG painters even if an unexpected drawing error propagates.

    :param qt_app: Shared Qt application.
    :param tmp_path: Isolated export folder.
    :param suffix: Export format whose paint device must be released.
    :return: None.
    """
    chart: GraphsWidget = GraphsWidget()
    chart.resize(600, 400)
    coordinates: np.ndarray = np.arange(3.0)
    assert chart.set_line_series(coordinates, ['A'], [coordinates])
    # Inject invalid internal data to exercise cleanup even if a renderer unexpectedly fails.
    chart._series[0].replace_data(coordinates, np.ones((3, 1)), QtGui.QColor('#008800'))
    try:
        save_chart_image(chart, str(tmp_path / f'failed{suffix}'))
    except TypeError as error:
        assert '0-dimensional' in str(error)
        # Inspect the failed export frame while it still retains its native paint device.
        frame: TracebackType | None = error.__traceback__
        checked_painter: bool = False
        while frame is not None:
            if frame.tb_frame.f_code.co_name == 'save_chart_image':
                painter: object = frame.tb_frame.f_locals['painter']
                assert isinstance(painter, QtGui.QPainter)
                assert not painter.isActive()
                checked_painter = True
            else:
                pass
            frame = frame.tb_next
        assert checked_painter
    else:
        pytest.fail('Drawing failure did not propagate')
    chart.dispose()
    chart.deleteLater()
