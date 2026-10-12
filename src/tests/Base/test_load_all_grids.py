# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os

import pytest

from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.file_save import FileSave


@pytest.mark.parametrize(
    "file_name",
    sorted(os.listdir(os.path.join("data", "grids"))),
)
def test_all_grids(file_name: str) -> None:
    """
    Verify that one direct entry from the shared grid catalogue can be loaded.

    Parametrizing the catalogue lets pytest report progress and attribute a slow
    or failing load to its exact fixture instead of hiding every load behind one
    long-running test item.

    :param file_name: Direct file or directory entry from ``data/grids``.
    :return: None.
    """
    # Rebuild the established relative fixture path for the current catalogue entry.
    path: str = os.path.join("data", "grids", file_name)

    # Exercise the production loader directly so pytest preserves the original traceback.
    file_handler: FileOpen = FileOpen(path)
    file_handler.open()


def test_line_templates_finding(tmp_path):
    """
    Test that checks that a line assigned a line template that is not a Sequence line can open it
    :return:
    """
    # navigate to the grids folder
    fname = os.path.join('data', 'grids', 'test_line_templates.gridcal')


    opener = FileOpen(fname)
    grid = opener.open()

    # it it fails, it may be because the file structure changed and the input file needs updating
    # FileSave(grid, str(fname)).save()

    normalized_fname = tmp_path / 'test_line_templates_normalized.gridcal'
    FileSave(grid, str(normalized_fname)).save()

    reopened = FileOpen(str(normalized_fname))
    reopened.open()

    if reopened.logger.has_logs():
        reopened.logger.print()

    assert not reopened.logger.has_logs()


def test_issue_337():

    # navigate to the grids folder
    fname = os.path.join('data', 'grids', 'RAW', 'issue_337.raw')

    grid = FileOpen(fname).open()

    print()
