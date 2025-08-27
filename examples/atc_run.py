from VeraGridEngine.IO import FileOpen
from VeraGridEngine.api import *

fname = r'C:\Users\penversa\Git\GridCal\Grids_and_profiles\grids\IEEE 118 Bus - ntc_areas.gridcal'

main_circuit = FileOpen(fname).open()

options = AvailableTransferCapacityOptions()
driver = AvailableTransferCapacityDriver(main_circuit, options)
driver.run()

print()
