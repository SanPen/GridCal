import os
import json
import numpy as np
from typing import Dict
import GridCalEngine as gce
from GridCalEngine.Devices.Branches.overhead_line_type import kron_reduction

grid_folder = "NEV Network 1"
folder = os.path.join("networks", grid_folder)


with open(os.path.join("cables", "cableparameters.json")) as f:
    cable_json = json.load(f)

with open(os.path.join(folder, "net.json")) as f:
    net_json = json.load(f)

with open(os.path.join(folder, "imbalance.json")) as f:
    loads_json = json.load(f)

print()

grid = gce.MultiCircuit()


buses_json = net_json["network"]["bus"]
branches_json = net_json["network"]["branch"]

load_dict: Dict[str, gce.Load] = dict()
for key, val in loads_json.items():

    load = gce.Load(
        name=val.get("name", "")
    )

    load.P1, load.P2, load.P3 = np.array(val['p']) * 1e-6
    load.Q1, load.Q2, load.Q3 = np.array(val['q']) * 1e-6

    load_dict[key] = load


bus_dict: Dict[str, gce.Bus] = dict()
for key, val in buses_json.items():

    bus = gce.Bus(name=val.get("name", ""),
                  is_slack=val.get("slack", False))

    grid.add_bus(bus)
    bus_dict[key] = bus

    if val.get("load", False):
        load = load_dict.get(val.get("name"), None)
        if load is not None:
            grid.add_load(bus=bus, api_obj=load)

for key, val in branches_json.items():

    ff = val.get("nodefrom", None)
    tt = val.get("nodeto", None)

    if ff is not None or tt is not None:
        f = bus_dict.get(str(ff), None)
        t = bus_dict.get(str(tt), None)

        if f is not None or t is not None:
            line = gce.Line(
                name=f"line {f}-{t}",
                length=val.get('length', 1.0)
            )
            line.bus_from = f
            line.bus_to = t

            line.ys = gce.AdmittanceMatrix(size=3)
            line.ysh = gce.AdmittanceMatrix(size=3)

            cable_type = val.get("type", None)
            if cable_type is not None:
                cable_params = cable_json[cable_type]
                r = np.array(cable_params['real'])
                i = np.array(cable_params['image'])
                zs = r + 1j * i

                Zbase = (f.Vnom * f.Vnom) / grid.Sbase
                zs_pu = zs * line.length / Zbase

                if r.shape[0] == 4:
                    zs_red = kron_reduction(zs_pu, keep=np.array([0, 1, 2]), embed=np.array([3]))
                    line.ys.values = 1.0 / zs_red

                elif r.shape[0] == 3:
                    line.ys.values = 1.0 / zs_pu

            grid.add_line(line)


gce.save_file(grid, grid_folder + ".gridcal")
