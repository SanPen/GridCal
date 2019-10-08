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
import time

from GridCal.Engine.IO.file_handler import FileOpen
from multiprocessing import Pool

from GridCal.Engine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver, \
    PowerFlowMP, SolverType, PowerFlowOptions


def simulation_constructor(args):
    """
    function to create a copy of the grid and a power flow associated

    :param args:
    :return:
    """
    # grd = grid.copy()
    # grd.name = 'grid ' + str(i)
    # grd.compile()
    # return PowerFlowDriver(grd, options)
    return PowerFlowMP(args[0], args[1])


def instance_executor(instance: PowerFlowDriver):
    """
    function to run the instance

    :param instance:
    :return:
    """
    instance.run()

    return instance.grid


def test_api_multi_core():

    batch_size = 10000

    # fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_300BUS.xls'
    # fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_118.xls'
    # fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_57BUS.xls'
    fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/IEEE_30_new.xlsx'
    # fname = 'D:\GitHub\GridCal\Grids_and_profiles\grids\IEEE_30_new.xlsx'
    # fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_14.xls'
    # fname = '/Data/Doctorado/spv_phd/GridCal_project/GridCal/IEEE_39Bus(Islands).xls'

    grid = FileOpen(fname).open()
    grid.compile()
    print('\n\n', grid.name)

    options = PowerFlowOptions(SolverType.NR, verbose=False)
    power_flow = PowerFlowDriver(grid, options)
    power_flow.run()

    # create instances of the of the power flow simulation given the grid
    print('cloning...')
    pool = Pool()
    instances = pool.map(simulation_constructor, [[grid, options]]*batch_size)
    # run asynchronous power flows on the created instances
    print('running...')
    instances = pool.map_async(instance_executor, instances)

    # monitor progress
    while True:
        if instances.ready():
            break
        remaining = instances._number_left
        progress = ((batch_size - remaining + 1) / batch_size) * 100
        print("Waiting for", remaining, "tasks to complete...", progress, '%')

        time.sleep(0.5)

    # display the collected results
    for instance in instances.get():
        print('\n\n' + instance.name)
        # print('\t|V|:', abs(instance.power_flow.results.voltage))

    # print('\t|V|:', abs(grid.power_flow.results.voltage))
    # print('\t|Sbranch|:', abs(grid.power_flow.results.Sbranch))
    # print('\t|loading|:', abs(grid.power_flow_results.loading) * 100)
    # print('\terr:', grid.power_flow_results.error)
    # print('\tConv:', grid.power_flow_results.converged)


if __name__ == '__main__':
    test_api_multi_core()
