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
from GridCal.Engine.IO.file_handler import FileOpen
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.OPF.opf_driver import OptimalPowerFlowOptions
from GridCal.Engine.Simulations.OPF.opf_ts_driver import OptimalPowerFlowTimeSeries


def test_api_dcopf():
    # TODO Make this work and parameterize this test using pytest

    fname = os.path.join('..', '..', 'Grids_and_profiles', 'grids', 'Lynn 5 Bus pv.gridcal')
    print('loading...')
    grid = FileOpen(fname).open()

    opf_options = OptimalPowerFlowOptions(power_flow_options=PowerFlowOptions())

    print('Running ts...')
    opf_ts = OptimalPowerFlowTimeSeries(grid, opf_options)
    opf_ts.run()
    # opf.results


if __name__ == '__main__':
    test_api_dcopf()
