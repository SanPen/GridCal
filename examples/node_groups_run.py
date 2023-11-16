from GridCalEngine.api import *

fname = '/home/santi/Documentos/GitHub/GridCal/Grids_and_profiles/grids/Illinois 200 Bus.gridcal'

grid = FileOpen(fname).open()

driver = NodeGroupsDriver(grid=grid, sigmas=1e-3)
driver.run()

print('\nGroups:')
for group in driver.groups_by_name:
    print(group)

for group in driver.groups_by_index:
    print(group)
