import os
from GridCalEngine.api import *

fname = os.path.join('..', 'Grids_and_profiles', 'grids', 'IEEE 30 Bus with storage.xlsx')

circuit_ = FileOpen(fname).open()

study = ReliabilityStudy(circuit=circuit_, pf_options=PowerFlowOptions())

study.run()
