# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import os
from VeraGridEngine.IO.file_handler import FileOpen


def test_all_grids():
    # get the directory of this file
    current_path = os.path.dirname(__file__)

    # navigate to the grids folder
    grids_path = os.path.join(current_path, 'data', 'grids')

    files = os.listdir(grids_path)
    failed = list()
    for file_name in files:

        path = os.path.join(grids_path, file_name)

        print('-' * 160)
        print('Loading', file_name, '...', end='')
        try:
            file_handler = FileOpen(path)
            circuit = file_handler.open()

            print('ok')
        except:
            print('Failed')
            failed.append(file_name)

    print('Failed:')
    for f in failed:
        print('\t', f)

    for f in failed:
        print('Attempting', f)
        path = os.path.join(grids_path, f)
        file_handler = FileOpen(path)
        circuit = file_handler.open()

    assert len(failed) == 0


def test_line_templates_finding():
    """
    Test that checks that a line assigned a line template that is not a Sequence line can open it
    :return:
    """
    # get the directory of this file
    current_path = os.path.dirname(__file__)

    # navigate to the grids folder
    fname = os.path.join(current_path, 'data', 'grids', 'test_line_templates.gridcal')

    opener = FileOpen(fname)
    grid = opener.open()

    if opener.logger.has_logs():
        opener.logger.print()

    assert not opener.logger.has_logs()


def test_issue_337():
    # get the directory of this file
    current_path = os.path.dirname(__file__)

    # navigate to the grids folder
    fname = os.path.join(current_path, 'data', 'grids', 'RAW', 'issue_337.raw')

    grid = FileOpen(fname).open()

    print()