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
import os
import sys
PACKAGE_PARENT = '..'
SCRIPT_DIR = os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__))))
sys.path.append(os.path.normpath(os.path.join(SCRIPT_DIR, PACKAGE_PARENT)))

from GridCal.Gui.Main.GridCalMain import run

# TODO: Review the overall quality of the power flow (check that the results are the same as before, etc...)
# TODO: Integrate the OPF solvers (see if the PulpVar objects can operate vector-wise with numpy)
# TODO: Fix the cascading with the new module


if __name__ == "__main__":
    print("GridCal  \nCopyright (C) 2018 Santiago Peñate Vera\n" +
          "This program comes with ABSOLUTELY NO WARRANTY.\n" +
          "This is free software, and you are welcome to \n" +
          "redistribute it under certain conditions;\n" +
          "See the license file for more details.\n\n")
    run()
