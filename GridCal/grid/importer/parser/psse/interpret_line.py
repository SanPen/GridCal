# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.


def interpret_line(line, splitter=','):
    """
    Split text into arguments and parse each of them to an appropriate format (int, float or string)
    Args:
        line:
        splitter:
    Returns: list of arguments
    """
    parsed = list()
    elms = line.split(splitter)

    for elm in elms:
        try:
            # try int
            el = int(elm)
        except Exception as ex1:
            try:
                # try float
                el = float(elm)
            except Exception as ex2:
                # otherwise just leave it as string
                el = elm.strip()
        parsed.append(el)
    return parsed
