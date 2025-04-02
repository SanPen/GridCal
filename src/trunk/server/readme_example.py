

import os
import asyncio
import GridCalEngine as gce

# path to your file
fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "IEEE57.gridcal")

# read gridcal file
grid_ = gce.open_file(fname)

# define instruction for the server
instruction = gce.RemoteInstruction(operation=gce.SimulationTypes.NoSim)

# generate json to send
model_data = gce.gather_model_as_jsons_for_communication(circuit=grid_, instruction=instruction)

# get the sever certificate
gce.get_certificate(base_url="http://34.175.24.148:80",
                    certificate_path=gce.get_certificate_path(),
                    pwd="")

# send json

gce.send_json_data(json_data=model_data,
                   endpoint_url="http://34.175.24.148:80/upload",
                   certificate=gce.get_certificate_path())

print(reply_from_server)