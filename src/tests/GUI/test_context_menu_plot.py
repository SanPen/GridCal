"""Check deferred plot presentation without importing simulation drivers."""

from PySide6 import QtCore, QtWidgets

from VeraGrid.Gui.PlotDialogue.plot_dialogue import PlotDialogue


def test_context_menu_plot_opens_as_owned_window(qt_app):
    owner = QtWidgets.QMainWindow()
    owner.show()
    dialog = PlotDialogue(parent=owner)
    dialog.open_from_context_menu()
    assert not dialog.isVisible()
    qt_app.processEvents()
    assert dialog.isVisible()
    assert dialog.isWindow()
    assert dialog.parentWidget() is owner
    dialog.reject()
    assert dialog.chart._disposed


def test_context_menu_plot_closed_before_delivery_stays_closed(qt_app):
    dialog = PlotDialogue()
    dialog.open_from_context_menu()
    dialog.reject()
    qt_app.processEvents()
    assert not dialog.isVisible()


def test_context_menu_plot_deleted_before_delivery(qt_app):
    dialog = PlotDialogue()
    dialog.open_from_context_menu()
    dialog.reject()
    dialog.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    qt_app.processEvents()
