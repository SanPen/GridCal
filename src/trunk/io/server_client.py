import os
import asyncio
import GridCalEngine.api as gce

# fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "IEEE39_1W.gridcal")
# fname = '/home/santi/Escritorio/Redes/Spain_France_portugal.gridcal'
fname = os.path.join('..', '..', '..', 'Grids_and_profiles', 'grids', "IEEE57.gridcal")

# read gridcal file
grid_ = gce.open_file(fname)

# define instruction for the server
instruction = gce.RemoteInstruction(operation=gce.SimulationTypes.NoSim)

# generate json to send
model_data = gce.gather_model_as_jsons_for_communication(circuit=grid_, instruction=instruction)

# get the certificate
gce.get_certificate(base_url="https://localhost:8000",
                    certificate_path=gce.get_certificate_path(),
                    pwd="")

# send json
reply_from_server = asyncio.get_event_loop().run_until_complete(
    gce.send_json_data(json_data=model_data,
                       endpoint_url="https://localhost:8000/upload",
                       certificate=gce.get_certificate_path())
    )


print(reply_from_server)
