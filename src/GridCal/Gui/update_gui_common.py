# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
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

"""
Script to update correctly the main GUI (.py) file from the Qt design (.ui) file
"""
import os
import sys
from subprocess import call


def correct_file_imports(filename):
    """
    Correct file with qtpy agnostic imports
    :param filename: file name
    :return: Nothing
    """
    with open(filename, 'r') as file:
        file_data = file.read()

    # Replace the target string
    file_data = file_data.replace('import icons_rc', 'from .icons_rc import *')
    file_data = file_data.replace('from .matplotlibwidget import MatplotlibWidget', 'from GridCal.Gui.Widgets.matplotlibwidget import MatplotlibWidget')
    file_data = file_data.replace('from qrangeslider3 import QRangeSlider3', 'from GridCal.Gui.Widgets.custom_qrangeslider import QRangeSlider3')
    # file_data = file_data.replace('PySide6', 'qtpy')
    # file_data = file_data.replace('PyQt5', 'qtpy')
    # file_data = file_data.replace('PyQt6', 'qtpy')

    # Write the file out again
    with open(filename, 'w') as file:
        file.write(file_data)


def convert_resource_file(source, rcc_cmd='pyside6-rcc'):

    folder = os.path.dirname(sys.executable)
    f1 = folder.split(os.sep)[-1]

    if f1 == 'bin':
        fbase = folder
    else:
        if 'script' in folder.lower():
            fbase = folder
        else:
            fbase = os.path.join(folder, 'Script')

    # get the target fil name
    target = source.replace('.qrc', '_rc.py')

    # define the possible commands
    possible_cmds = [os.path.join(fbase, rcc_cmd),
                     os.path.join(fbase, rcc_cmd + '.exe'),
                     rcc_cmd]

    for cmd in possible_cmds:

        try:
            call([sys.executable, os.path.join(fbase, cmd), source, '-o', target])
            correct_file_imports(target)
            print(rcc_cmd, ' (py) ok')
            return True
        except:
            print('Failed with', rcc_cmd)


def convert_ui_file(source, uic_cmd='pyside6-uic'):
    """
    Convert UI file to .py with qtpy agnostic imports
    :param source:
    :param uic_cmd:
    :return:
    """
    folder = os.path.dirname(sys.executable)
    f1 = folder.split(os.sep)[-1]

    if f1 == 'bin':
        fbase = folder
    else:
        if 'script' in folder.lower():
            fbase = folder
        else:
            fbase = os.path.join(folder, 'Script')

    # get the target fil name
    target = source.replace('.ui', '.py')

    # define the possible commands
    possible_cmds = [os.path.join(fbase, uic_cmd),
                     os.path.join(fbase, uic_cmd + '.exe'),
                     uic_cmd]

    for cmd in possible_cmds:

        try:
            call([sys.executable, os.path.join(fbase, cmd), source, '-o', target])
            correct_file_imports(filename=target)
            print(uic_cmd, ' (py) ok')
            return True

        except:
            pass

    print('Could not find the right command to convert', source)
    return False


