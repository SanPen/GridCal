import os
import pandas as pd
import GridCalEngine as gce


folder = "/home/santi/matpower8.0b1/data"

# run this one to compile the stuff
# gce.power_flow(gce.open_file(os.path.join(folder, "/home/santi/matpower8.0b1/data/case5.m")))
res = gce.power_flow(gce.open_file(os.path.join(folder, "case16am.m")))

print(res.converged)
