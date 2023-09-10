# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import os

from GridCalEngine.IO.file_handler import FileOpen


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
