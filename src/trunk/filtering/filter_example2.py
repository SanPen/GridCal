import numpy as np
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Utils.Filtering.results_table_filtering import FilterResultsTable, parse_expression


flt1 = parse_expression("idx != 4 and val != 5 or col < 3 and val >= 6")

print()