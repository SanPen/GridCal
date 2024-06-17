"""Package applying Qt compat of PyQt6, PySide6, PyQt5 and PySide2."""
from GridCal.ThirdParty.qdarktheme.qtpy.qt_compat import QtImportError
from GridCal.ThirdParty.qdarktheme.qtpy.qt_version import __version__

try:
    from GridCal.ThirdParty.qdarktheme.qtpy import QtCore, QtGui, QtSvg, QtWidgets
except ImportError:
    from GridCal.ThirdParty.qdarktheme._util import get_logger as __get_logger

    __logger = __get_logger(__name__)
    __logger.warning("Failed to import QtCore, QtGui, QtSvg and QtWidgets.")
