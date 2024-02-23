
import numpy as np
from GridCalEngine.Simulations.results_table import ResultsTable
from GridCalEngine.Utils.Filtering.filtering import FilterResultsTable

ncols = 10
nrows = 20

np.random.seed(0)
res = ResultsTable(data=np.random.rand(nrows, ncols) * 100.0 - 50.0,
                   columns=[f"column{i}" for i in range(ncols)],
                   index=[f"index{i}" for i in range(nrows)])

flt = FilterResultsTable(table=res)

# expr = "val > 0.5 and val < 12 and col != [column1, column2]"
# expr = "val > 48 and val > 0"
# expr = "val > 20 and val < 48 and val > 30"
# expr = "col = column1"
# expr = "col != [column1, column4]"
expr = "col notlike [n2, n6] and val > 0"

flt.parse(expression=expr)
res2 = flt.apply()

print(res2.to_df())

