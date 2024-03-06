import os
from GridCalEngine.api import *

np.set_printoptions(linewidth=10000)


fname = os.path.join('Estabanell.gridcal')
main_circuit = FileOpen(fname).open()

main_circuit.investments.clear()
main_circuit.investments_groups.clear()
FileSave(main_circuit, 'Estabanell2.gridcal').save()
print()

