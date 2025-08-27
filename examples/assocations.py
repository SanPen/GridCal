import os
import VeraGridEngine.api as gce
import pandas as pd
pd.set_option('display.precision', 2)

folder = os.path.join('..', 'Grids_and_profiles', 'grids')
fname = os.path.join(folder, 'association_test.gridcal')

main_circuit = gce.open_file(fname)

print()
