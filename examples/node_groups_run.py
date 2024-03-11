import os
from GridCalEngine.api import *

fname = os.path.join('..', 'Grids_and_profiles', 'grids', 'Illinois 200 Bus.gridcal')

grid = FileOpen(fname).open()

lin_drv = LinearAnalysisDriver(grid=grid)
lin_drv.run()

driver = NodeGroupsDriver(grid=grid,
                          sigmas=1e-3,
                          min_group_size=2,
                          ptdf_results=lin_drv.results)
driver.run()

print('\nGroups:')
for group in driver.groups_by_name:
    print(group)

for group in driver.groups_by_index:
    print(group)
