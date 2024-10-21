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
import sys


def print_progress_bar(iteration: int, total: int, length=40, txt=""):
    """
    Simple text progress bar
    :param iteration: current iteration (1 based)
    :param total: total progress
    :param length: length of the bar in characters
    :param txt: text to print at the end of the progress bar
    """
    if iteration > total:
        iteration = total

    percent = (iteration / total)
    arrow = '=' * int(length * percent) + '>'
    spaces = ' ' * (length - len(arrow))
    sys.stdout.write(f'\r[{arrow}{spaces}] {percent:.1%} {txt}')
    sys.stdout.flush()
