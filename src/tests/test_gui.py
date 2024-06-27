import os
import sys
import pytest
from pytestqt.qtbot import QtBot
from PySide6.QtTest import QTest
from GridCal.Gui.Main.GridCalMain import MainGUI, QApplication


# @pytest.fixture
# def app(qtbot: QtBot):
#     app = QApplication.instance() if QApplication.instance() else QApplication(sys.argv)
#     main_window = MainGUI()
#     qtbot.addWidget(main_window)
#     return main_window


# def test_gui1(qtbot: QtBot, app: MainGUI):
#     """
#
#     :param qtbot:
#     :param app:
#     :return:
#     """
#     app.open_file_now(filenames=os.path.join("data", "grids", "IEEE57.gridcal"))
#     app.run_power_flow()
#
#     qtbot.waitCallback()
#     QTest.currentAppName()
