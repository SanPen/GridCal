import os
from GridCalEngine.api import *

np.set_printoptions(linewidth=10000)

fname = os.path.join('Estabanell2.gridcal')
main_circuit = FileOpen(fname).open()

