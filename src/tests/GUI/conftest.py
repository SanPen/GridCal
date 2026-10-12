import sys

import pytest
from PySide6 import QtCore
from PySide6 import QtWidgets


class ModalDialogAutoCloser(QtCore.QObject):
    """
    Close modal dialogs that block unattended GUI regression flows.
    """

    __slots__ = ("_app", "_protected_widget", "_timer")

    def __init__(
            self,
            app: QtWidgets.QApplication,
            protected_widget: QtWidgets.QWidget,
            parent: QtCore.QObject | None = None,
    ) -> None:
        """
        Build one modal-dialog closer.

        :param app: Shared Qt application.
        :param protected_widget: Main window that must not be closed by the helper.
        :param parent: Optional Qt owner.
        :return: None.
        """
        QtCore.QObject.__init__(self, parent)
        self._app: QtWidgets.QApplication = app
        self._protected_widget: QtWidgets.QWidget = protected_widget
        self._timer: QtCore.QTimer = QtCore.QTimer(self)
        self._timer.setInterval(25)
        self._timer.timeout.connect(self.close_modal_dialogs)

    def start(self) -> None:
        """
        Start polling for blocking dialogs.

        :return: None.
        """
        self._timer.start()

    def stop(self) -> None:
        """
        Stop polling for blocking dialogs.

        :return: None.
        """
        self._timer.stop()

    @QtCore.Slot()
    def close_modal_dialogs(self) -> None:
        """
        Close modal dialogs while preserving the main GUI.

        :return: None.
        """
        widget: QtWidgets.QWidget
        for widget in self._app.topLevelWidgets():
            self.close_widget(widget=widget)

    def close_widget(self, widget: QtWidgets.QWidget) -> None:
        """
        Close one eligible modal widget.

        :param widget: Candidate top-level widget.
        :return: None.
        """
        if widget is self._protected_widget:
            pass
        elif isinstance(widget, QtWidgets.QMessageBox):
            widget.accept()
        elif isinstance(widget, QtWidgets.QDialog):
            widget.reject()
        else:
            pass


@pytest.fixture(scope="session")
def qt_app() -> object:
    """
    Get or create the Qt application used by GUI tests.

    :return: Qt application instance.
    """
    app: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    else:
        pass

    yield app

    app.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()


@pytest.fixture(autouse=True)
def cleanup_qt_widgets(qt_app: object) -> object:
    """
    Ensure GUI tests do not leak top-level widgets or deferred deletions across test boundaries.

    :param qt_app: Shared Qt application instance.
    :return: Nothing.
    """
    app: QtWidgets.QApplication = qt_app

    yield

    app.processEvents()

    for widget in list(app.topLevelWidgets()):
        widget.close()
        widget.deleteLater()

    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
    app.processEvents()
