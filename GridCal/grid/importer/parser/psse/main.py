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


from GridCal.grid.importer.parser.psse.parser import PSSeParser

if __name__ == '__main__':
    # fname = 'raw/ExampleGrid_PSSEver32.raw'
    fname = 'raw/ExampleGrid_PSSEver33.raw'

    parser = PSSeParser(fname)
    pass
