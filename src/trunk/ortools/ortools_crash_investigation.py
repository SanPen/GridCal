import ortools.linear_solver.pywraplp as ort
from ortools.linear_solver.python import model_builder

fname = "mip__2024-10-09 19:33:10.284816.lp"
# fname = "pass_thought_file.mps"


solver = model_builder.Solver("cbc")
mdl = model_builder.Model()
if fname.endswith(".lp"):
    mdl.import_from_lp_file(fname)
elif fname.endswith(".mps"):
    mdl.import_from_mps_file(fname)
else:
    raise Exception("File type not supported")

status = solver.solve(mdl)
print(status)