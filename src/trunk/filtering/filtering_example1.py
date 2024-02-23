
import numpy as np
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Utils.Filtering.filtering import FilterResultsTable

ncols = 10
nrows = 20
res = ResultsTable(data=np.random.rand(nrows, ncols),
                   columns=[f"column{i}" for i in range(ncols)],
                   index=[f"index{i}" for i in range(nrows)])

flt = FilterResultsTable(table=res)

expr = "val > 0.5"

flt.parse(expression=expr)

res2 = flt.apply()

print(res2.to_df())

print()