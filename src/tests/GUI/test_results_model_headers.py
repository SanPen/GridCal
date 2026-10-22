# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
import pytest
from PySide6 import QtCore, QtGui

from VeraGrid.Gui.results_model import ResultsModel
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.enumerations import DeviceType


@pytest.mark.parametrize("label", ("Investment group", 42, np.array(("Investment group",)),
                                  pd.Timestamp("2030-01-01")))
def test_results_headers_provide_text_for_qt(label: object) -> None:
    """
    Verify imported labels support Qt header measurement and text painting.

    :param label: Scalar or array-valued result column label.
    :return: None.
    """
    columns: np.ndarray = np.empty(1, dtype=object)
    columns[0] = label
    table: ResultsTable = ResultsTable(
        data=np.zeros((1, 1)), columns=columns, index=np.array(("Result",)),
        title="Imported headers", cols_device_type=DeviceType.NoDevice,
        idx_device_type=DeviceType.NoDevice,
    )
    model: ResultsModel = ResultsModel(table=table)
    text: str = model.headerData(0, QtCore.Qt.Orientation.Horizontal)

    # Exercise the same string operations used by wrapped header painting.
    assert isinstance(text, str)
    assert isinstance(text.replace("_", " "), str)
    if isinstance(label, pd.Timestamp):
        assert text == "2030/01/01  00:00:00"
    else:
        assert text == str(label)
    assert table.cols_c[0] is label

    # QFontMetrics reproduces the failing Qt overload without requiring a display.
    application: QtGui.QGuiApplication = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication(
        ["header-test", "-platform", "offscreen"]
    )
    metrics: QtGui.QFontMetrics = QtGui.QFontMetrics(application.font())
    rect: QtCore.QRect = metrics.boundingRect(
        QtCore.QRect(0, 0, 100, 5000),
        QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.TextFlag.TextWordWrap |
        QtCore.Qt.TextFlag.TextExpandTabs, text, 4,
    )
    assert rect.height() > 0
