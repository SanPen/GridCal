# GridCal
# Copyright (C) 2015 - 2024 Santiago Peñate Vera
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import os
import json
from typing import Dict
from hashlib import sha256
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks, Response
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse
from GridCalEngine.IO.gridcal.remote import RemoteInstruction, RemoteJob
from GridCalEngine.IO.gridcal.pack_unpack import parse_gridcal_data
from GridCalEngine.Devices.multi_circuit import MultiCircuit
from GridCalEngine.enumerations import SimulationTypes, JobStatus
from GridCalEngine.IO.gridcal.zip_interface import save_results_only
import GridCalEngine.api as gce

app = FastAPI()

# Store WebSocket connections in a set
__connections__ = set()

# GC_FOLDER = get_create_gridcal_folder()
# GC_SERVER_FILE = os.path.join(GC_FOLDER, "server_config.json")
SECRET_KEY = ""

JOBS_LIST: Dict[str, RemoteJob] = dict()


def get_fs_folder() -> str:
    """
    Get the folder where to save files
    :return:
    """
    return "."


def generate_job_file_path(job_id: str):
    """

    :param job_id:
    :return:
    """
    return os.path.join(get_fs_folder(), f"{job_id}.zip")


def verify_api_key(api_key: str = Header(None)):
    """
    Define a function to verify the API key
    :param api_key:
    """
    if api_key is None:
        raise HTTPException(status_code=401, detail="API Key is missing")

    # Hash the provided API key using the same algorithm and compare with the stored hash
    hashed_api_key = sha256(api_key.encode()).hexdigest()
    if hashed_api_key != SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")


@app.get("/")
async def read_root():
    """
    Root
    :return: string
    """
    return {"message": "GridCal server running", "status": "ok"}


@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    """

    :return:
    """
    return FileResponse(os.path.join(os.path.dirname(__file__), "data", "GridCal_icon.ico"))


async def stream_load_json(json_data):
    """

    :param json_data:
    :return:
    """

    async def generate():
        """
        generate
        """
        yield json.dumps(json_data).encode()

    return StreamingResponse(generate())


def run_job(grid: MultiCircuit, job: RemoteJob):
    """

    :param grid:
    :param job:
    :return:
    """
    if job.instruction.operation == SimulationTypes.PowerFlow_run:
        driver = gce.PowerFlowDriver(grid=grid)

    elif job.instruction.operation == SimulationTypes.PowerFlowTimeSeries_run:

        driver = gce.PowerFlowTimeSeriesDriver(grid=grid)

    elif job.instruction.operation == SimulationTypes.OPF_run:

        driver = gce.OptimalPowerFlowDriver(grid=grid)

    elif job.instruction.operation == SimulationTypes.OPFTimeSeries_run:

        driver = gce.OptimalPowerFlowTimeSeriesDriver(grid=grid)

    else:
        return None

    job.status = JobStatus.Running
    driver.run()
    save_results_only(filename_zip=generate_job_file_path(job_id=job.id_tag),
                      sessions_data=[driver])
    job.status = JobStatus.Done


async def process_json_data(json_data: Dict[str, Dict[str, Dict[str, str]]]):
    """
    Action called on the upload
    :param json_data: the grid info generated with 'gather_model_as_jsons_for_communication'
    """
    grid = parse_gridcal_data(data=json_data)
    print(f'Circuit loaded alright nbus{grid.get_bus_number()}, nbr{grid.get_branch_number()}')

    # with open("mi_red.json", "w") as f:
    #     f.write(json.dumps(json_data, indent=4))

    if 'instruction' in json_data:
        instruction = RemoteInstruction(data=json_data['instruction'])

        job = RemoteJob(grid=grid, instruction=instruction)

        # register the job
        JOBS_LIST[job.id_tag] = job

        # print("Job data\n", job.get_data())

        run_job(grid=grid, job=job)

    else:
        print('No Instruction found\n\n', json_data)


@app.post("/upload/")
async def upload_job(json_data: dict, background_tasks: BackgroundTasks):
    """

    :param json_data:
    :param background_tasks:
    :return:
    """
    background_tasks.add_task(stream_load_json, json_data)
    background_tasks.add_task(process_json_data, json_data)

    return {"message": "Job processing initiated"}


@app.get("/jobs_list")
async def jobs_list():
    """
    Root
    :return: string
    """
    return [job.get_data() for id_tag, job in JOBS_LIST.items()]


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a specific job by ID
    :param job_id: The ID of the job to delete
    :return: A message indicating the result
    """
    if job_id in JOBS_LIST:
        del JOBS_LIST[job_id]
        return {"message": f"Job {job_id} deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Job not found")


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """
    Cancel a specific job by ID
    :param job_id: The ID of the job to cancel
    :return: A message indicating the result
    """
    job = JOBS_LIST.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.cancel()
    return {"message": f"Job {job_id} canceled successfully"}


@app.get("/download_results/{job_id}")
async def download_large_file(job_id: str):
    """

    :return:
    """

    job = JOBS_LIST.get(job_id, None)

    if job is None:
        return Response(status_code=404, content="Job not found")

    if job.status != JobStatus.Done:
        return Response(status_code=405, content="Job not finished yet :/")

    # Path to your large binary file
    file_path = generate_job_file_path(job_id=job_id)

    # Check if the file exists
    if not os.path.exists(file_path):
        return Response(status_code=406, content=f"File not found {file_path}")

    # Function to stream the file
    def iterfile(chunk_size=1024 * 1024):
        """

        :param chunk_size:
        :return:
        """
        with open(file_path, "rb") as file:
            sent = 0
            while chunk := file.read(chunk_size):  # Read in chunks of 1MB
                sent += chunk_size
                job.progress = f"{sent} MB"
                yield chunk

    print("Sending", job_id)

    # Return a streaming response
    return StreamingResponse(iterfile(), media_type="application/octet-stream")


if __name__ == "__main__":
    import uvicorn

    # uvicorn.run(app, host="0.0.0.0", port=8000, ssl_keyfile="key.pem", ssl_certfile="cert.pem")
    uvicorn.run(app, host="0.0.0.0", port=8000)
