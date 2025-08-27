from VeraGridEngine.api import *
import pandas as pd
pd.set_option('display.float_format', lambda x: '%.6f' % x)

fname = "/home/santi/Documentos/Git/Comparison/VeraGrid/src/tests/data/grids/RAW/IEEE 14 bus.raw"
grid = open_file(fname)
res = power_flow(grid)

print(res.get_bus_df())
print(res.get_branch_df())
